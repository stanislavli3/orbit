"""Story 4 — email send and reply polling aren't queued jobs, but their failures are recorded."""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from bom_agent.models import BomLineItem, BomResearchRun, TeamContact, TeamRequest
from core.models import JobFailure
from projects.models import Project


class EmailFailureRecordingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="email-user", password="x")
        project = Project.objects.create(name="Mail Project", owner=self.user)
        self.run = BomResearchRun.objects.create(
            project=project, created_by=self.user, status="awaiting_team_input"
        )
        item = BomLineItem.objects.create(run=self.run, part_name="Plate", status="needs_input")
        contact = TeamContact.objects.create(
            workspace_owner=self.user, added_by=self.user, full_name="Mina",
            email="mina@example.com", role="Engineer", department="Eng",
            expertise_tags=["materials"], preferred_channel="email",
        )
        self.request_obj = TeamRequest.objects.create(
            run=self.run, contact=contact, line_item=item,
            recipient_email=contact.email, recipient_name=contact.full_name,
            question="Which material?", question_key=f"material_file_{item.id}",
            channel="email", email_subject="Material", email_body="Please confirm.",
            status="approved",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_send_failure_is_recorded(self):
        with patch(
            "bom_agent.bom_views.send_team_request_via_gmail",
            side_effect=RuntimeError("Gmail API error (429): rate limited"),
        ):
            response = self.client.post(
                f"/api/bom/runs/{self.run.id}/emails/{self.request_obj.id}/send/"
            )

        self.assertEqual(response.status_code, 502)
        failure = JobFailure.objects.get()
        self.assertEqual((failure.job_type, failure.target_id), ("email_send", str(self.request_obj.id)))
        self.assertIn("429", failure.error_message)

    def test_unapproved_send_is_a_user_error_not_a_failure(self):
        TeamRequest.objects.filter(pk=self.request_obj.pk).update(status="draft")
        response = self.client.post(
            f"/api/bom/runs/{self.run.id}/emails/{self.request_obj.id}/send/"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(JobFailure.objects.exists())

    def test_send_all_records_each_failed_send(self):
        with patch(
            "bom_agent.bom_views.send_team_request_via_gmail",
            side_effect=RuntimeError("Gmail down"),
        ):
            response = self.client.post(f"/api/bom/runs/{self.run.id}/emails/send-all/")

        self.assertEqual(response.json()["error_count"], 1)
        self.assertEqual(JobFailure.objects.get().job_type, "email_send")

    def test_poll_endpoint_failure_is_recorded_and_still_surfaces(self):
        with patch(
            "bom_agent.bom_views.poll_run_replies", side_effect=RuntimeError("token revoked")
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(f"/api/bom/runs/{self.run.id}/emails/poll/")

        failure = JobFailure.objects.get()
        self.assertEqual((failure.job_type, failure.target_id), ("email_poll", str(self.run.id)))

    def test_poll_command_records_a_failing_run_and_keeps_polling_the_rest(self):
        project = self.run.project
        healthy = BomResearchRun.objects.create(project=project, created_by=self.user)

        def poll(run):
            if run.pk == self.run.pk:
                raise RuntimeError("token revoked")
            return []

        out, err = StringIO(), StringIO()
        with patch("bom_agent.management.commands.poll_bom_email_replies.poll_run_replies",
                   side_effect=poll) as polled:
            call_command("poll_bom_email_replies", stdout=out, stderr=err)

        self.assertEqual(polled.call_count, 2)  # the healthy run was still polled
        self.assertEqual(JobFailure.objects.get().target_id, str(self.run.id))
        self.assertIn("poll failed", err.getvalue())
        self.assertIsNotNone(healthy.pk)
