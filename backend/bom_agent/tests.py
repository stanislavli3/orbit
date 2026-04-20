import io
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient

from bom_agent.excel_export import render_bom_workbook, upload_bom_workbook
from bom_agent.models import BomLineItem, BomResearchRun, SupplierQuote
from bom_agent.research_pipeline import run_bom_research
from projects.models import Project


class BomWorkbookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="bom-user",
            email="bom@example.com",
            password="x",
        )
        self.project = Project.objects.create(name="Orbital Valve", owner=self.user)
        self.run = BomResearchRun.objects.create(
            project=self.project,
            created_by=self.user,
            status="researching",
            inputs_json={
                "production_volume": "50–100 units",
                "timeline": "8 weeks",
                "budget": "$125.50",
                "exchange_rates": "1.12",
                "shipping_assumptions": "1.18",
                "compliance": ["RoHS", "REACH"],
            },
            completed_at=timezone.now(),
        )
        self.item = BomLineItem.objects.create(
            run=self.run,
            part_name="Valve Body",
            part_number="VB-001",
            material_spec="6061-T6 Aluminum",
            quantity=12,
            status="sourced",
        )
        self.run.research_log = [
            {
                "ts": "10:00:00",
                "type": "search",
                "message": "Search query: valve body machining supplier",
                "item_id": self.item.id,
                "part_name": self.item.part_name,
                "query": "valve body machining supplier",
            }
        ]
        self.run.results_json = {
            f"item_{self.item.id}": {
                "material": "6061-T6 Aluminum",
                "risk_flags": ["single-source", "geographic-concentration"],
                "risk_summary": "Only one AVL supplier was found in the required region.",
                "summary": "Preferred supplier is Apex Machining based on cost and lead time.",
            }
        }
        self.run.save(update_fields=["research_log", "results_json"])

        SupplierQuote.objects.create(
            line_item=self.item,
            supplier_name="Apex Machining",
            unit_price="8.50",
            moq=10,
            lead_time_days=21,
            tooling_cost="250.00",
            landed_cost_usd="9.10",
            source_url="https://example.com/apex",
            notes="AVL supplier [Country: USA]",
            is_avl=True,
        )
        SupplierQuote.objects.create(
            line_item=self.item,
            supplier_name="Global Fabrication",
            unit_price="9.40",
            moq=25,
            lead_time_days=35,
            tooling_cost="180.00",
            landed_cost_usd="10.00",
            source_url="https://example.com/global",
            notes="Secondary quote [Country: China]",
            is_avl=False,
        )

    def test_render_bom_workbook_has_required_sheets_formulas_and_formatting(self):
        workbook_bytes = render_bom_workbook(self.run)
        workbook = load_workbook(io.BytesIO(workbook_bytes), data_only=False)
        try:
            self.assertEqual(
                workbook.sheetnames,
                [
                    "BOM Summary",
                    "Supplier Comparison",
                    "Assumptions & Inputs",
                    "Research Log",
                    "Risk Matrix",
                ],
            )

            summary = workbook["BOM Summary"]
            self.assertEqual(summary["G2"].value, "=E2*F2")
            self.assertEqual(summary["G3"].value, "=SUM(G2:G2)")
            self.assertEqual(summary.freeze_panes, "A2")

            comparison = workbook["Supplier Comparison"]
            self.assertEqual(len(comparison.conditional_formatting), 2)
            self.assertEqual(comparison.freeze_panes, "A2")

            inputs = workbook["Assumptions & Inputs"]
            self.assertEqual(inputs["C8"].font.color.rgb, "FF0000FF")
            self.assertTrue(inputs["D12"].value.startswith("="))
            self.assertEqual(inputs["D12"].font.color.rgb, "FF000000")

            research = workbook["Research Log"]
            self.assertEqual(research["E4"].value, "https://example.com/apex")

            risk = workbook["Risk Matrix"]
            self.assertEqual(risk["C2"].value, "Flagged")
        finally:
            workbook.close()

    def test_upload_bom_workbook_uses_expected_s3_key(self):
        expected_key = (
            f"bom-reports/{self.run.project_id}/run-{self.run.id}/"
            f"bom-research-run-{self.run.id}.xlsx"
        )
        with patch("bom_agent.excel_export.upload_bytes_to_s3") as upload_mock:
            key = upload_bom_workbook(self.run)

        self.assertEqual(key, expected_key)
        upload_mock.assert_called_once()
        self.assertEqual(
            upload_mock.call_args.kwargs["content_type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


class BomRunExcelViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="view-user",
            email="view@example.com",
            password="x",
        )
        self.project = Project.objects.create(name="Excel Project", owner=self.user)
        self.run = BomResearchRun.objects.create(
            project=self.project,
            created_by=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_bom_run_excel_view_returns_404_without_excel(self):
        response = self.client.get(f"/api/bom/runs/{self.run.id}/excel/")
        self.assertEqual(response.status_code, 404)

    def test_bom_run_excel_view_returns_presigned_url(self):
        self.run.excel_s3_key = "bom-reports/1/run-1/report.xlsx"
        self.run.save(update_fields=["excel_s3_key"])

        with patch(
            "files_api.s3_service.generate_presigned_url",
            return_value="https://example.com/download.xlsx?sig=1",
        ) as presign_mock, patch(
            "files_api.s3_service.get_s3_object_metadata",
            return_value={
                "size": 4096,
                "last_modified": timezone.now(),
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            },
        ) as metadata_mock:
            response = self.client.get(f"/api/bom/runs/{self.run.id}/excel/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["url"], "https://example.com/download.xlsx?sig=1")
        self.assertEqual(payload["file_size"], 4096)
        self.assertEqual(payload["filename"], "report.xlsx")
        self.assertIsNotNone(payload["generated_at"])
        presign_mock.assert_called_once_with(
            "bom-reports/1/run-1/report.xlsx",
            expires=3600,
        )
        metadata_mock.assert_called_once_with("bom-reports/1/run-1/report.xlsx")


class BomRunListViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="history-user",
            email="history@example.com",
            password="x",
        )
        self.other_user = User.objects.create_user(
            username="history-other",
            email="history-other@example.com",
            password="x",
        )
        self.project = Project.objects.create(name="History Project", owner=self.user)
        self.other_project = Project.objects.create(name="Other Project", owner=self.other_user)
        self.run_one = BomResearchRun.objects.create(
            project=self.project,
            created_by=self.user,
            status="completed",
            completed_at=timezone.now(),
        )
        BomLineItem.objects.create(run=self.run_one, part_name="Bracket", quantity=4, status="sourced")
        self.run_two = BomResearchRun.objects.create(
            project=self.project,
            created_by=self.user,
            status="researching",
        )
        BomLineItem.objects.create(run=self.run_two, part_name="Valve", quantity=2, status="researching")
        other_run = BomResearchRun.objects.create(
            project=self.other_project,
            created_by=self.other_user,
            status="completed",
        )
        BomLineItem.objects.create(run=other_run, part_name="Hidden", quantity=1, status="sourced")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_bom_run_list_filters_by_project_and_user(self):
        response = self.client.get(f"/api/bom/runs/?project_id={self.project.id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]["id"], self.run_two.id)
        self.assertEqual(payload[1]["id"], self.run_one.id)
        self.assertEqual(len(payload[0]["line_items"]), 1)


class BomResearchPipelineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pipeline-user",
            email="pipeline@example.com",
            password="x",
        )
        self.project = Project.objects.create(name="Pipeline Project", owner=self.user)

    def test_run_bom_research_generates_excel_key(self):
        run = BomResearchRun.objects.create(
            project=self.project,
            created_by=self.user,
            status="gathering_inputs",
            inputs_json={"production_volume": "1–10 units"},
            completed_at=timezone.now() - timedelta(hours=1),
        )
        item = BomLineItem.objects.create(
            run=run,
            part_name="Bracket",
            quantity=4,
            status="pending",
        )

        def stub_research_item(*args, **kwargs):
            BomLineItem.objects.filter(pk=item.pk).update(status="sourced")

        expected_key = (
            f"bom-reports/{self.project.id}/run-{run.id}/"
            f"bom-research-run-{run.id}.xlsx"
        )
        with patch("assistant.rag.find_library_docs", return_value=[]), patch(
            "bom_agent.research_pipeline._research_item", side_effect=stub_research_item
        ), patch(
            "bom_agent.excel_export.upload_bom_workbook",
            return_value=expected_key,
        ) as upload_mock:
            run_bom_research(run.id)

        run.refresh_from_db()
        self.assertEqual(run.status, "completed")
        self.assertEqual(run.excel_s3_key, expected_key)
        self.assertIsNotNone(run.completed_at)
        upload_mock.assert_called_once()
