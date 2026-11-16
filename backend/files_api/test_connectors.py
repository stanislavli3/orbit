import json
from pathlib import Path
from unittest.mock import patch

import pytest

from files_api.connectors import GoogleDriveConnector, index_source
from files_api.extractor import extract_metadata
from files_api.matlab import parse_m, parse_mat, write_mat_v5, MatlabParseError
from files_api.models import ConnectedSource, UploadedFile
from projects.models import Project

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


@pytest.fixture
def project(db, user):
    return Project.objects.create(name="P", owner=user)


@pytest.fixture(autouse=True)
def no_embeddings():
    with patch("files_api.embeddings.generate_embedding", return_value=[]):
        yield


# ── SCRUM-21: MATLAB parsing ──────────────────────────────────────────────


@pytest.mark.parametrize("compress", [False, True])
def test_parse_mat_variables(compress):
    data = write_mat_v5({"x": [[1.0, 2.0, 3.0]], "M": [[1, 2], [3, 4], [5, 6]]}, compress=compress)
    result = parse_mat(data)
    assert result["variables"] == [
        {"name": "x", "class": "double", "shape": [1, 3]},
        {"name": "M", "class": "double", "shape": [3, 2]},
    ]


def test_parse_sample_mat_file():
    result = parse_mat((SAMPLES / "matlab" / "simulation_results.mat").read_bytes())
    assert {v["name"] for v in result["variables"]} == {"time_s", "tip_deflection_m", "load_case"}


def test_parse_m_signatures_and_header():
    result = parse_m((SAMPLES / "matlab" / "beam_deflection.m").read_bytes())
    names = [f["name"] for f in result["functions"]]
    assert names == ["beam_deflection", "section_c"]
    main = result["functions"][0]
    assert main["inputs"] == ["load_N", "length_m", "E_Pa", "I_m4"]
    assert main["outputs"] == ["delta", "stress"]
    assert result["header_comment"].startswith("BEAM_DEFLECTION")


def test_parse_m_script():
    result = parse_m(b"% Run the sweep\nx = 1:10;\nplot(x)\n")
    assert result["kind"] == "script" and result["header_comment"] == "Run the sweep"


@pytest.mark.parametrize("payload, reason", [
    (b"short", "too small"),
    (b"not matlab".ljust(200, b" "), "Not a MAT-file"),
    (b"MATLAB 5.0".ljust(126, b" ") + b"XX", "endian"),
    (b"MATLAB 5.0".ljust(126, b" ") + b"IM" + b"\x0e\x00\x00\x00\xff\x00\x00\x00", "past end"),
    (b"MATLAB 7.3 MAT-file".ljust(126, b" ") + b"IM", "HDF5"),
])
def test_malformed_mat_fails_clearly(payload, reason):
    with pytest.raises(MatlabParseError, match=reason):
        parse_mat(payload)
    result = extract_metadata("bad.mat", payload)
    assert result["confidence"] == 0.0 and "Malformed MATLAB file" in result["error"]


def test_binary_m_file_fails_clearly():
    assert "binary" in extract_metadata("x.m", b"\x00\x01\x02")["error"]


@pytest.mark.django_db
def test_extract_task_marks_malformed_mat_failed(project, user):
    from files_api.tasks import extract_file

    f = UploadedFile.objects.create(project=project, uploaded_by=user, original_name="bad.mat",
                                    file_type="mat", s3_key="k/bad.mat", file_size=4)
    with patch("files_api.tasks.download_file_from_s3", return_value=b"junk"), \
         patch("files_api.tasks.generate_file_description") as desc:
        extract_file.run(f.id) if hasattr(extract_file, "run") else extract_file(f.id)
    f.refresh_from_db()
    assert f.status == "failed" and "Malformed MATLAB" in f.description
    desc.assert_not_called()


@pytest.mark.django_db
def test_upload_accepts_mat(auth_client, project):
    from django.core.files.uploadedfile import SimpleUploadedFile

    with patch("files_api.views.upload_file_to_s3", return_value="k/x.mat"), \
         patch("files_api.views.enqueue_bom_extraction") as bom:
        r = auth_client.post("/api/files/upload/", {
            "file": SimpleUploadedFile("x.mat", write_mat_v5({"a": [[1]]})),
            "project_id": project.id,
        })
    assert r.status_code == 201, r.content
    assert r.json()["owner"] == "test@example.com" and r.json()["source"] == "upload"
    bom.assert_not_called()


# ── SCRUM-50/54: local folder connector ───────────────────────────────────


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setenv("CONNECTOR_LOCAL_ROOTS", str(tmp_path))
    (tmp_path / "exports").mkdir()
    (tmp_path / "exports" / "bracket.step").write_bytes(
        (SAMPLES / "bracket_assembly.step").read_bytes())
    (tmp_path / "exports" / "sim.mat").write_bytes(write_mat_v5({"stress_vm": [[1, 2]]}))
    (tmp_path / "exports" / "broken.mat").write_bytes(b"garbage")
    (tmp_path / "exports" / "notes.txt").write_text("ignored")
    return tmp_path / "exports"


@pytest.mark.django_db
def test_local_folder_index_in_place(auth_client, project, folder):
    r = auth_client.post(f"/api/files/project/{project.id}/sources/",
                         {"kind": "local_folder", "config": {"path": str(folder)}}, format="json")
    assert r.status_code == 201, r.content
    sid = r.json()["id"]
    with patch("files_api.s3_service.upload_file_to_s3") as up:
        r = auth_client.post(f"/api/files/sources/{sid}/index/")
    up.assert_not_called()  # nothing copied
    assert r.status_code == 200 and r.json()["indexed"] == 2 and r.json()["failed"] == 1

    files = {f["original_name"]: f for f in auth_client.get(f"/api/files/project/{project.id}/").json()}
    assert set(files) == {"bracket.step", "sim.mat", "broken.mat"}
    sim = files["sim.mat"]
    assert sim["source"] == "local_folder" and sim["external_url"].startswith("file://")
    assert sim["external_url"].endswith("sim.mat") and sim["owner"]
    assert files["broken.mat"]["status"] == "failed"

    # Search hits parsed MATLAB variable names.
    hits = auth_client.get(f"/api/files/project/{project.id}/?q=stress_vm").json()
    assert [h["original_name"] for h in hits] == ["sim.mat"]

    # Download links back to the original location.
    dl = auth_client.get(f"/api/files/{sim['id']}/download/").json()
    assert dl["url"] == sim["external_url"]

    # Re-index after a file is removed drops it; originals are never deleted by Orbit.
    (folder / "broken.mat").unlink()
    r = auth_client.post(f"/api/files/sources/{sid}/index/")
    assert r.json()["removed"] == 1
    auth_client.delete(f"/api/files/{sim['id']}/")
    assert (folder / "sim.mat").exists()


@pytest.mark.django_db
def test_local_folder_outside_allowed_roots_rejected(auth_client, project, folder):
    r = auth_client.post(f"/api/files/project/{project.id}/sources/",
                         {"kind": "local_folder", "config": {"path": "/etc"}}, format="json")
    assert r.status_code == 400 and "allowed roots" in r.json()["error"]


@pytest.mark.django_db
def test_sources_scoped_to_owner(api_client, other_user, project, folder):
    api_client.force_authenticate(other_user)
    r = api_client.post(f"/api/files/project/{project.id}/sources/",
                        {"kind": "local_folder", "config": {"path": str(folder)}}, format="json")
    assert r.status_code == 404


# ── SCRUM-78: Google Drive connector (fully mocked) ───────────────────────


@pytest.mark.django_db
def test_drive_not_configured(auth_client, project, monkeypatch):
    monkeypatch.delenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", raising=False)
    status = auth_client.get("/api/files/connectors/").json()
    assert status["google_drive"]["configured"] is False
    assert "not configured" in status["google_drive"]["detail"]
    r = auth_client.post(f"/api/files/project/{project.id}/sources/",
                         {"kind": "google_drive", "config": {"folder_id": "abc"}}, format="json")
    assert r.status_code == 400 and "not configured" in r.json()["error"]


@pytest.mark.django_db
def test_drive_index_records_owner_and_editor(auth_client, project, monkeypatch):
    monkeypatch.setenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", json.dumps({"client_email": "orbit@sa"}))
    r = auth_client.post(f"/api/files/project/{project.id}/sources/", {
        "kind": "google_drive",
        "config": {"folder_id": "https://drive.google.com/drive/folders/FOLDER1?usp=sharing"},
    }, format="json")
    assert r.status_code == 201, r.content
    assert r.json()["config"] == {"folder_id": "FOLDER1"}
    source = ConnectedSource.objects.get(id=r.json()["id"])

    listing = {"files": [
        {"id": "f1", "name": "beam.m", "size": "120", "modifiedTime": "2026-11-01T10:00:00Z",
         "webViewLink": "https://drive.google.com/file/d/f1/view",
         "owners": [{"displayName": "Alice Eng"}],
         "lastModifyingUser": {"displayName": "Bob Sim"}},
        {"id": "f2", "name": "readme.docx", "size": "5"},
    ]}
    calls = []

    def fake_get(self, url, fields=None):
        calls.append((url, fields))
        if fields and fields.get("alt") == "media":
            return b"function y = beam(x)\n% Beam model\ny = x;\n"
        return json.dumps(listing).encode()

    with patch.object(GoogleDriveConnector, "_get", fake_get):
        summary = index_source(source)
    assert summary == {"indexed": 1, "failed": 0, "removed": 0, "total": 1}
    assert "'FOLDER1' in parents" in calls[0][1]["q"]

    f = auth_client.get(f"/api/files/project/{project.id}/?q=Bob").json()
    assert len(f) == 1
    f = f[0]
    assert f["source"] == "google_drive" and f["owner"] == "Alice Eng"
    assert f["last_editor"] == "Bob Sim" and f["external_url"].endswith("/f1/view")
    assert f["source_modified_at"].startswith("2026-11-01")


def test_drive_scope_is_readonly():
    from files_api.connectors import DRIVE_SCOPE

    assert DRIVE_SCOPE.endswith("/drive.readonly")
