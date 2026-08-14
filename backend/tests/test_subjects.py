from datetime import datetime, timezone

from app.api.v1.endpoints import subjects as subjects_module

OWNER_ID = "11111111-2222-3333-4444-555555555555"


def _subject(**overrides):
    base = {
        "id": "aaaa-0001",
        "ownerId": OWNER_ID,
        "name": "Computer Architecture",
        "description": "",
        "status": "ACTIVE",
        "conceptCount": 0,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return base


def _material(**overrides):
    base = {
        "id": "bbbb-0001",
        "subjectId": "aaaa-0001",
        "ownerId": OWNER_ID,
        "filename": "notes.pdf",
        "fileType": "PDF",
        "storageReference": "materials/user/notes.pdf",
        "processingStatus": "UPLOADED",
        "pageCount": None,
        "processingError": None,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return base


def _patch_owner(monkeypatch, owner_id=OWNER_ID):
    async def fake(auth_user_id):
        return owner_id

    monkeypatch.setattr(subjects_module, "get_user_id_by_auth", fake)


def test_subjects_requires_auth(raw_client):
    assert raw_client.get("/api/v1/subjects").status_code == 401


def test_create_subject(client, monkeypatch):
    async def fake_create(owner_id, name, description):
        return _subject(name=name, description=description)

    _patch_owner(monkeypatch)
    monkeypatch.setattr(subjects_module.subjects_service, "create_subject", fake_create)
    resp = client.post("/api/v1/subjects", json={"name": "Computer Architecture"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Computer Architecture"
    assert body["ownerId"] == OWNER_ID


def test_create_subject_validation(client, monkeypatch):
    _patch_owner(monkeypatch)
    resp = client.post("/api/v1/subjects", json={"name": ""})
    assert resp.status_code == 422


def test_list_subjects(client, monkeypatch):
    async def fake_list(owner_id):
        return [_subject(name="One"), _subject(name="Two")]

    _patch_owner(monkeypatch)
    monkeypatch.setattr(subjects_module.subjects_service, "list_subjects", fake_list)
    resp = client.get("/api/v1/subjects")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_materials_scoped_to_owner(client, monkeypatch):
    async def fake_get_subject(owner_id, subject_id):
        return _subject(id=subject_id)

    async def fake_list(owner_id, subject_id):
        return [_material(subjectId=subject_id)]

    _patch_owner(monkeypatch)
    monkeypatch.setattr(subjects_module.subjects_service, "get_subject", fake_get_subject)
    monkeypatch.setattr(subjects_module.materials_service, "list_materials", fake_list)
    resp = client.get("/api/v1/subjects/aaaa-0001/materials")
    assert resp.status_code == 200
    assert resp.json()[0]["subjectId"] == "aaaa-0001"


def test_list_materials_404_when_subject_not_owned(client, monkeypatch):
    # Simulates cross-user access: get_subject (owner-scoped) returns None.
    async def fake_get_subject(owner_id, subject_id):
        return None

    _patch_owner(monkeypatch)
    monkeypatch.setattr(subjects_module.subjects_service, "get_subject", fake_get_subject)
    resp = client.get("/api/v1/subjects/aaaa-0001/materials")
    assert resp.status_code == 404


def test_get_material_404_when_not_owned(client, monkeypatch):
    async def fake_get_material(owner_id, material_id):
        return None

    _patch_owner(monkeypatch)
    monkeypatch.setattr(subjects_module.materials_service, "get_material", fake_get_material)
    resp = client.get("/api/v1/subjects/aaaa-0001/materials/bbbb-0001")
    assert resp.status_code == 404
