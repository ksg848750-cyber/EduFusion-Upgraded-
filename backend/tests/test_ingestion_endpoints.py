from datetime import datetime, timezone

from app.api.v1.endpoints import subjects as subjects_module

OWNER_ID = "11111111-2222-3333-4444-555555555555"
PDF_BYTES = b"%PDF-1.4 fake test fixture"


def _subject(**o):
    base = {
        "id": "aaaa-0001",
        "ownerId": OWNER_ID,
        "name": "CA",
        "description": "",
        "status": "ACTIVE",
        "conceptCount": 0,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    base.update(o)
    return base


def _material(**o):
    base = {
        "id": "bbbb-0001",
        "subjectId": "aaaa-0001",
        "ownerId": OWNER_ID,
        "filename": "notes.pdf",
        "fileType": "PDF",
        "storageReference": "materials/owner/subj/notes.pdf",
        "processingStatus": "COMPLETED",
        "pageCount": 3,
        "processingError": None,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    base.update(o)
    return base


def _patch_owner(monkeypatch, owner_id=OWNER_ID):
    async def fake(auth_user_id):
        return owner_id

    monkeypatch.setattr(subjects_module, "get_user_id_by_auth", fake)


def test_upload_rejects_non_pdf(client, monkeypatch):
    _patch_owner(monkeypatch)

    async def fake_get_subject(owner_id, subject_id):
        return _subject(id=subject_id)

    monkeypatch.setattr(subjects_module.subjects_service, "get_subject", fake_get_subject)
    resp = client.post(
        "/api/v1/subjects/aaaa-0001/materials",
        files={"file": ("notes.txt", b"not a pdf", "text/plain")},
    )
    assert resp.status_code == 422


def test_upload_rejects_empty_file(client, monkeypatch):
    _patch_owner(monkeypatch)

    async def fake_get_subject(owner_id, subject_id):
        return _subject(id=subject_id)

    monkeypatch.setattr(subjects_module.subjects_service, "get_subject", fake_get_subject)
    resp = client.post(
        "/api/v1/subjects/aaaa-0001/materials",
        files={"file": ("notes.pdf", b"", "application/pdf")},
    )
    assert resp.status_code == 422


def test_upload_success_runs_pipeline(client, monkeypatch):
    _patch_owner(monkeypatch)

    async def fake_get_subject(owner_id, subject_id):
        return _subject(id=subject_id)

    async def fake_upload_bytes(bucket, path, content, content_type="application/pdf"):
        assert bucket == "materials"
        assert content == PDF_BYTES
        return path

    async def fake_create_material(owner_id, subject_id, filename, file_type, storage_reference, processing_status="UPLOADED"):
        return _material(
            subjectId=subject_id,
            filename=filename,
            storageReference=storage_reference,
            processingStatus=processing_status,
        )

    async def fake_process(owner_id, subject_id, material_id, content, ai=None):
        assert content == PDF_BYTES
        return _material(processingStatus="COMPLETED")

    monkeypatch.setattr(subjects_module.subjects_service, "get_subject", fake_get_subject)
    monkeypatch.setattr(subjects_module, "upload_bytes", fake_upload_bytes)
    monkeypatch.setattr(subjects_module.materials_service, "create_material", fake_create_material)
    monkeypatch.setattr(subjects_module, "process_material", fake_process)

    resp = client.post(
        "/api/v1/subjects/aaaa-0001/materials",
        files={"file": ("notes.pdf", PDF_BYTES, "application/pdf")},
    )
    assert resp.status_code == 200
    assert resp.json()["processingStatus"] == "COMPLETED"


def test_upload_marks_failed_and_returns_422(client, monkeypatch):
    _patch_owner(monkeypatch)

    async def fake_get_subject(owner_id, subject_id):
        return _subject(id=subject_id)

    async def fake_create_material(**kwargs):
        return _material(processingStatus="UPLOADED")

    async def fake_process(owner_id, subject_id, material_id, content, ai=None):
        raise ValueError("boom")

    failed = {
        **_material(processingStatus="FAILED", processingError="boom"),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }

    async def fake_get_material(owner_id, material_id):
        return failed

    monkeypatch.setattr(subjects_module.subjects_service, "get_subject", fake_get_subject)
    monkeypatch.setattr(subjects_module, "upload_bytes", lambda *a, **k: _async_return("ref"))
    monkeypatch.setattr(subjects_module.materials_service, "create_material", fake_create_material)
    monkeypatch.setattr(subjects_module, "process_material", fake_process)
    monkeypatch.setattr(subjects_module.materials_service, "get_material", fake_get_material)

    resp = client.post(
        "/api/v1/subjects/aaaa-0001/materials",
        files={"file": ("notes.pdf", PDF_BYTES, "application/pdf")},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["material"]["processingStatus"] == "FAILED"


async def _async_return(v):
    return v


def test_knowledge_graph_requires_subject_owner(client, monkeypatch):
    _patch_owner(monkeypatch)

    async def fake_get_subject(owner_id, subject_id):
        return None

    monkeypatch.setattr(subjects_module.subjects_service, "get_subject", fake_get_subject)
    resp = client.get("/api/v1/subjects/aaaa-0001/knowledge-graph")
    assert resp.status_code == 404


def test_knowledge_graph_returns_nodes_and_edges(client, monkeypatch):
    _patch_owner(monkeypatch)

    async def fake_get_subject(owner_id, subject_id):
        return _subject(id=subject_id, conceptCount=2)

    async def fake_list_concepts(subject_id):
        return [
            {"id": "c1", "name": "Pipeline", "canonicalName": "pipeline", "description": ""},
            {"id": "c2", "name": "Hazard", "canonicalName": "hazard", "description": ""},
        ]

    async def fake_list_relationships(subject_id):
        return [{"id": "r1", "fromName": "pipeline", "toName": "hazard", "relationshipType": "RELATED_TO"}]

    monkeypatch.setattr(subjects_module.subjects_service, "get_subject", fake_get_subject)
    import app.services.concepts as concepts_service
    import app.services.relationships as relationships_service

    monkeypatch.setattr(concepts_service, "list_concepts", fake_list_concepts)
    monkeypatch.setattr(relationships_service, "list_relationships", fake_list_relationships)

    resp = client.get("/api/v1/subjects/aaaa-0001/knowledge-graph")
    assert resp.status_code == 200
    body = resp.json()
    assert body["conceptCount"] == 2
    assert len(body["concepts"]) == 2
    assert body["relationships"][0]["relationshipType"] == "RELATED_TO"