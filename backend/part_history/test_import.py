"""SCRUM-58 — import historical part costs from a spreadsheet."""

import io

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from part_history.importer import ImportFileError, import_costs
from part_history.models import HistoricalCost, ImportBatch, Part

GOOD_CSV = b"""P/N,Description,Matl,Unit Cost,MY,Program
ORB-1042,"Bracket, Mounting",6061-T6,$4.10,MY22,Atlas
ORB-0770,Spacer,6061-T6,"1,050.00",'21,
"""

BAD_CSV = b"""Part No,Cost,Model Year,Program
ORB-1,4.10,2022,Atlas
,3.00,2022,Atlas
ORB-2,abc,2022,Atlas
ORB-3,-1,2022,Atlas
ORB-4,2.00,,
ORB-5,2.00,next year,Atlas
ORB-1,4.10,2022,Atlas
"""


def test_csv_import_with_column_aliases(user):
    report = import_costs(user, GOOD_CSV, "costs.csv")

    assert (report["imported_rows"], report["rejected"]) == (2, [])
    bracket = HistoricalCost.objects.get(part__part_number="ORB-1042")
    assert (str(bracket.unit_cost), bracket.model_year, bracket.program) == ("4.1000", 2022, "Atlas")
    assert bracket.source == "costs.csv row 2"
    assert bracket.part.material == "6061-T6"
    spacer = HistoricalCost.objects.get(part__part_number="ORB-0770")
    assert (str(spacer.unit_cost), spacer.model_year) == ("1050.0000", 2021)


def test_rejected_rows_are_reported_with_reasons(user):
    report = import_costs(user, BAD_CSV, "bad.csv")

    assert report["imported_rows"] == 1
    assert {r["row"]: r["errors"] for r in report["rejected"]} == {
        3: ["Missing part number"],
        4: ["Cost 'abc' is not a number"],
        5: ["Cost must be greater than 0"],
        6: ["Needs a model year or a program"],
        7: ["Model year 'next year' not understood"],
        8: ["Duplicate of row 2"],
    }
    batch = ImportBatch.objects.get()
    assert (batch.imported_rows, batch.rejected_rows, len(batch.rejected_json)) == (1, 6, 6)


def test_dry_run_saves_nothing(user):
    report = import_costs(user, BAD_CSV, "bad.csv", dry_run=True)
    assert (report["valid_rows"], report["imported_rows"], len(report["rejected"])) == (1, 0, 6)
    assert not HistoricalCost.objects.exists() and not ImportBatch.objects.exists()


def test_xlsx_import_with_header_below_a_title_row(user):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Cost history export"])
    ws.append(["Part Number", "Description", "Unit Price", "Model Year"])
    ws.append(["ORB-2002", "Shaft", 12.2, 2023])
    buf = io.BytesIO()
    wb.save(buf)

    report = import_costs(user, buf.getvalue(), "export.xlsx")
    assert report["imported_rows"] == 1
    cost = HistoricalCost.objects.get()
    assert (str(cost.unit_cost), cost.model_year, cost.source) == ("12.2000", 2023, "export.xlsx row 3")


@pytest.mark.parametrize("data, name, message", [
    (b"a,b\n1,2\n", "x.csv", "header row"),
    (b"Part Number,Cost\nA,1\n", "x.csv", "Model Year"),
    (b"whatever", "x.pdf", ".csv or .xlsx"),
])
def test_unusable_files_are_refused(user, data, name, message):
    with pytest.raises(ImportFileError, match=message):
        import_costs(user, data, name)


def test_existing_part_is_matched_case_insensitively_and_not_overwritten(user):
    Part.objects.create(workspace_owner=user, part_number="orb-1042", description="Keep me")
    import_costs(user, GOOD_CSV, "costs.csv")
    part = Part.objects.get(part_number__iexact="ORB-1042")
    assert (part.description, part.material, part.costs.count()) == ("Keep me", "6061-T6", 1)


def test_deleting_a_batch_undoes_its_import(user):
    import_costs(user, GOOD_CSV, "costs.csv")
    ImportBatch.objects.get().delete()
    assert not HistoricalCost.objects.exists()


def test_seed_command_is_labelled_and_repeatable(user):
    call_command("seed_part_history", user.username)
    call_command("seed_part_history", user.email)

    assert ImportBatch.objects.count() == 1  # the second run replaced the first
    costs = HistoricalCost.objects.all()
    assert costs.count() == 12
    assert all(c.is_sample and c.program.startswith("SAMPLE") for c in costs)


# ── API ──────────────────────────────────────────────────────────────────────

def test_import_api(auth_client):
    upload = SimpleUploadedFile("bad.csv", BAD_CSV, content_type="text/csv")
    response = auth_client.post("/api/parts/imports/", {"file": upload}, format="multipart")
    assert response.status_code == 201
    assert (response.json()["imported_rows"], len(response.json()["rejected"])) == (1, 6)

    [batch] = auth_client.get("/api/parts/imports/").json()
    assert batch["rejected_rows"] == 6


def test_import_api_dry_run(auth_client):
    upload = SimpleUploadedFile("bad.csv", BAD_CSV, content_type="text/csv")
    response = auth_client.post("/api/parts/imports/", {"file": upload, "dry_run": "true"}, format="multipart")
    assert response.status_code == 200
    assert response.json()["dry_run"] is True
    assert not HistoricalCost.objects.exists()


def test_import_api_explains_a_bad_file(auth_client):
    upload = SimpleUploadedFile("x.pdf", b"x")
    response = auth_client.post("/api/parts/imports/", {"file": upload}, format="multipart")
    assert response.status_code == 400
    assert ".csv or .xlsx" in response.json()["detail"]
