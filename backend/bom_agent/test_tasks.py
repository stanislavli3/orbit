"""Story 2 — durable task queue: enqueueing, resumability, and restart recovery."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from bom_agent.models import (
    BomLineItem,
    BomResearchRun,
    LibraryDocument,
    LibraryEmbedding,
    SupplierQuote,
)
from bom_agent.research_pipeline import run_bom_research
from bom_agent.tasks import (
    enqueue_bom_research,
    ingest_library_document,
    recover_orphaned_jobs,
    research_bom_run,
)
from bom_agent.team_requests import maybe_resume_research
from core.jobs import MAX_RETRIES
from core.models import JobFailure
from projects.models import Project


def _quote(item, supplier="Acme"):
    return SupplierQuote.objects.create(
        line_item=item, supplier_name=supplier, unit_price=1, moq=1, lead_time_days=1
    )


class BomTaskTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="queue-user", password="x")
        self.project = Project.objects.create(name="Queue Project", owner=self.user)
        self.run = BomResearchRun.objects.create(
            project=self.project, created_by=self.user, status="researching"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)


class EnqueueTests(BomTaskTestCase):
    def test_inputs_submit_enqueues_research_after_commit(self):
        self.run.status = "gathering_inputs"
        self.run.save()

        with patch("bom_agent.tasks.research_bom_run.delay") as delay, \
                self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                f"/api/bom/runs/{self.run.id}/inputs/", {"answers": {}}, format="json"
            )
            delay.assert_not_called()  # not before commit

        self.assertEqual(response.status_code, 200)
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, "researching")
        delay.assert_called_once_with(self.run.id, self.run.job_token)

    def test_team_reply_resume_marks_researching_and_enqueues(self):
        self.run.status = "awaiting_team_input"
        self.run.save()

        with patch("bom_agent.tasks.research_bom_run.delay") as delay, \
                self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(maybe_resume_research(self.run))

        self.run.refresh_from_db()
        self.assertEqual(self.run.status, "researching")
        delay.assert_called_once_with(self.run.id, self.run.job_token)

    def test_each_enqueue_issues_a_new_token(self):
        with patch("bom_agent.tasks.research_bom_run.delay"), \
                self.captureOnCommitCallbacks(execute=True):
            enqueue_bom_research(self.run)
            first = self.run.job_token
            enqueue_bom_research(self.run)
        self.assertNotEqual(first, self.run.job_token)


class ResearchTaskGuardTests(BomTaskTestCase):
    @patch("bom_agent.research_pipeline.run_bom_research")
    def test_stale_token_is_a_no_op(self, pipeline):
        BomResearchRun.objects.filter(pk=self.run.pk).update(job_token="new")
        research_bom_run(self.run.id, "old")
        pipeline.assert_not_called()

    @patch("bom_agent.research_pipeline.run_bom_research")
    def test_late_redelivery_of_finished_run_is_a_no_op(self, pipeline):
        BomResearchRun.objects.filter(pk=self.run.pk).update(job_token="t", status="completed")
        research_bom_run(self.run.id, "t")
        pipeline.assert_not_called()

    @patch("bom_agent.research_pipeline.run_bom_research")
    def test_current_token_runs_pipeline(self, pipeline):
        BomResearchRun.objects.filter(pk=self.run.pk).update(job_token="t")
        research_bom_run(self.run.id, "t")
        pipeline.assert_called_once_with(self.run.id, job_token="t")


@patch("bom_agent.excel_export.upload_bom_workbook", return_value="")
@patch("assistant.rag.find_library_docs", return_value=[])
class ResumeTests(BomTaskTestCase):
    def test_resume_skips_sourced_items_and_clears_partial_quotes(self, *_):
        done = BomLineItem.objects.create(run=self.run, part_name="Done", status="sourced")
        _quote(done)
        interrupted = BomLineItem.objects.create(run=self.run, part_name="Half", status="researching")
        _quote(interrupted, "Partial Co")

        researched = []

        def fake_research(item, run, *args):
            researched.append(item.pk)
            _quote(item, "Fresh Co")
            BomLineItem.objects.filter(pk=item.pk).update(status="sourced")

        with patch("bom_agent.research_pipeline._research_item", side_effect=fake_research):
            run_bom_research(self.run.id)

        self.assertEqual(researched, [interrupted.pk])
        self.assertEqual(done.quotes.count(), 1)
        self.assertEqual(
            list(interrupted.quotes.values_list("supplier_name", flat=True)), ["Fresh Co"]
        )
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, "completed")

    def test_superseded_job_stops_before_next_item(self, *_):
        BomResearchRun.objects.filter(pk=self.run.pk).update(job_token="old")
        BomLineItem.objects.create(run=self.run, part_name="A", status="pending")
        BomLineItem.objects.create(run=self.run, part_name="B", status="pending")

        calls = []

        def fake_research(item, run, *args):
            calls.append(item.pk)
            # A worker restart re-queued this run while we were mid-item.
            BomResearchRun.objects.filter(pk=run.pk).update(job_token="new")

        with patch("bom_agent.research_pipeline._research_item", side_effect=fake_research):
            run_bom_research(self.run.id, job_token="old")

        self.assertEqual(len(calls), 1)
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, "researching")  # left for the newer job


class RecoveryTests(BomTaskTestCase):
    def test_recovery_requeues_in_flight_runs_and_ingests_only(self):
        finished = BomResearchRun.objects.create(
            project=self.project, created_by=self.user, status="completed"
        )
        waiting = BomResearchRun.objects.create(
            project=self.project, created_by=self.user, status="awaiting_team_input"
        )
        docs = {
            s: LibraryDocument.objects.create(
                workspace_owner=self.user, original_name=f"{s}.csv", s3_key=f"lib/{s}",
                file_size=1, file_type="csv", ingest_status=s,
            )
            for s in ("pending", "processing", "ready", "failed")
        }

        with patch("bom_agent.tasks.research_bom_run.delay") as research, \
                patch("bom_agent.tasks.ingest_library_document.delay") as ingest, \
                self.captureOnCommitCallbacks(execute=True):
            recover_orphaned_jobs()

        self.run.refresh_from_db()
        research.assert_called_once_with(self.run.id, self.run.job_token)
        self.assertEqual(
            sorted(c.args[0] for c in ingest.call_args_list),
            sorted([docs["pending"].pk, docs["processing"].pk]),
        )
        self.assertEqual(self.run.research_log[-1]["type"], "warn")
        for untouched in (finished, waiting):
            untouched.refresh_from_db()
            self.assertEqual(untouched.job_token, "")


class LibraryIngestTests(BomTaskTestCase):
    def setUp(self):
        super().setUp()
        self.doc = LibraryDocument.objects.create(
            workspace_owner=self.user, original_name="avl.csv", s3_key="lib/avl.csv",
            file_size=10, file_type="csv",
        )

    def test_success_marks_ready_and_stores_embedding(self):
        def fake_download(bucket, key, buf):
            buf.write(b"Supplier,Region\nAcme,US\n")

        with patch("bom_agent.tasks.get_s3_client") as s3, \
                patch("bom_agent.tasks.generate_embedding", return_value=[0.1, 0.2]):
            s3.return_value.download_fileobj.side_effect = fake_download
            ingest_library_document(self.doc.pk)

        self.doc.refresh_from_db()
        self.assertEqual(self.doc.ingest_status, "ready")
        self.assertIn("Acme", self.doc.extracted_text)
        self.assertTrue(LibraryEmbedding.objects.filter(document=self.doc).exists())

    def test_failure_is_visible(self):
        with patch("bom_agent.tasks.get_s3_client", side_effect=RuntimeError("s3 down")):
            with self.assertRaises(RuntimeError):
                ingest_library_document(self.doc.pk)

        self.doc.refresh_from_db()
        self.assertEqual(self.doc.ingest_status, "failed")

    def test_doc_deleted_while_queued_is_a_no_op(self):
        doc_id = self.doc.pk
        self.doc.delete()
        ingest_library_document(doc_id)  # must not raise


class FailureHandlingTests(BomTaskTestCase):
    """Story 4 — failed jobs are recorded, bounded, and leave their row `failed`."""

    def test_library_ingest_failure_is_recorded(self):
        doc = LibraryDocument.objects.create(
            workspace_owner=self.user, original_name="avl.csv", s3_key="lib/avl.csv",
            file_size=10, file_type="csv",
        )
        with patch("bom_agent.tasks.get_s3_client", side_effect=RuntimeError("s3 down")):
            result = ingest_library_document.apply(args=[doc.pk])

        self.assertTrue(result.failed())
        doc.refresh_from_db()
        self.assertEqual(doc.ingest_status, "failed")
        failure = JobFailure.objects.get()
        self.assertEqual((failure.job_type, failure.target_id), ("library_ingest", str(doc.pk)))

    def test_transient_pipeline_error_retries_then_fails_the_run(self):
        BomResearchRun.objects.filter(pk=self.run.pk).update(job_token="t")

        with patch(
            "bom_agent.research_pipeline.run_bom_research", side_effect=ConnectionError("net")
        ) as pipeline:
            result = research_bom_run.apply(args=[self.run.id, "t"])

        self.assertTrue(result.failed())
        self.assertEqual(pipeline.call_count, MAX_RETRIES + 1)
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, "failed")
        self.assertEqual(self.run.research_log[-1]["type"], "error")
        self.assertEqual(JobFailure.objects.get().job_type, "bom_research")

    def test_permanent_pipeline_error_fails_the_run_once_and_is_recorded(self):
        with patch("assistant.rag.find_library_docs", side_effect=ValueError("bad library")):
            run_bom_research(self.run.id)

        self.run.refresh_from_db()
        self.assertEqual(self.run.status, "failed")
        failure = JobFailure.objects.get()
        self.assertEqual(failure.job_type, "bom_research")
        self.assertEqual(failure.error_class, "ValueError")

    def test_transient_pipeline_error_is_left_for_the_task_to_retry(self):
        with patch("assistant.rag.find_library_docs", side_effect=ConnectionError("net")):
            with self.assertRaises(ConnectionError):
                run_bom_research(self.run.id)

        self.run.refresh_from_db()
        self.assertEqual(self.run.status, "researching")  # not failed yet
        self.assertFalse(JobFailure.objects.exists())


class CorruptDocumentTests(BomTaskTestCase):
    """Story 4 — a corrupt library document fails the job loudly; it never looks `ready`."""

    def _ingest(self, file_type, content):
        doc = LibraryDocument.objects.create(
            workspace_owner=self.user, original_name=f"doc.{file_type}",
            s3_key=f"lib/doc.{file_type}", file_size=len(content), file_type=file_type,
        )

        def fake_download(bucket, key, buf):
            buf.write(content)

        with patch("bom_agent.tasks.get_s3_client") as s3, \
                patch("bom_agent.tasks.generate_embedding", return_value=[0.1]), \
                patch("core.jobs.send_alert") as alert, \
                self.captureOnCommitCallbacks(execute=True):
            s3.return_value.download_fileobj.side_effect = fake_download
            result = ingest_library_document.apply(args=[doc.pk])
        doc.refresh_from_db()
        return doc, result, alert

    def test_corrupt_pdf_is_dead_lettered_and_alerted(self):
        doc, result, alert = self._ingest("pdf", b"%PDF-1.4 not really a pdf \x00\x01")

        self.assertTrue(result.failed())
        self.assertEqual(doc.ingest_status, "failed")
        failure = JobFailure.objects.get()
        self.assertEqual((failure.job_type, failure.target_id), ("library_ingest", str(doc.pk)))
        alert.assert_called_once()

    def test_corrupt_xlsx_is_dead_lettered_and_alerted(self):
        doc, result, alert = self._ingest("xlsx", b"PK this is not a workbook")

        self.assertTrue(result.failed())
        self.assertEqual(doc.ingest_status, "failed")
        self.assertEqual(JobFailure.objects.get().job_type, "library_ingest")
        alert.assert_called_once()

    def test_image_only_pdf_still_ingests(self):
        # Valid PDF with no text layer (e.g. a scan): not an error, falls back
        # to name+type for the embedding.
        import io

        import pypdf

        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=72, height=72)
        buf = io.BytesIO()
        writer.write(buf)

        doc, result, alert = self._ingest("pdf", buf.getvalue())

        self.assertFalse(result.failed())
        self.assertEqual(doc.ingest_status, "ready")
        self.assertEqual(doc.extracted_text, "")
        self.assertTrue(LibraryEmbedding.objects.filter(document=doc).exists())
        self.assertFalse(JobFailure.objects.exists())
        alert.assert_not_called()
