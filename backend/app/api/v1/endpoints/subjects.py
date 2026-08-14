from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.security import get_current_user
from app.core.storage import upload_bytes
from app.schemas.material import MaterialResponse
from app.schemas.subject import SubjectCreate, SubjectResponse
from app.services import materials as materials_service
from app.services import subjects as subjects_service
from app.services.ingestion import process_material
from app.services.users import get_user_id_by_auth

router = APIRouter(prefix="/subjects", tags=["subjects"])


async def _owner_id(claims: dict) -> str:
    auth_user_id = claims.get("sub")
    owner_id = await get_user_id_by_auth(auth_user_id) if auth_user_id else None
    if not owner_id:
        raise HTTPException(status_code=404, detail="User profile not found")
    return owner_id


@router.post("", response_model=SubjectResponse)
async def create_subject(body: SubjectCreate, claims: dict = Depends(get_current_user)):
    owner_id = await _owner_id(claims)
    subject = await subjects_service.create_subject(owner_id, body.name, body.description)
    if subject is None:
        raise HTTPException(status_code=503, detail="Subject store unavailable")
    return subject


@router.get("", response_model=list[SubjectResponse])
async def list_subjects(claims: dict = Depends(get_current_user)):
    owner_id = await _owner_id(claims)
    return await subjects_service.list_subjects(owner_id)


@router.get("/{subject_id}/materials", response_model=list[MaterialResponse])
async def list_materials(subject_id: str, claims: dict = Depends(get_current_user)):
    owner_id = await _owner_id(claims)
    subject = await subjects_service.get_subject(owner_id, subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    return await materials_service.list_materials(owner_id, subject_id)


@router.get("/{subject_id}/materials/{material_id}", response_model=MaterialResponse)
async def get_material(subject_id: str, material_id: str, claims: dict = Depends(get_current_user)):
    owner_id = await _owner_id(claims)
    material = await materials_service.get_material(owner_id, material_id)
    if material is None or material["subjectId"] != subject_id:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


@router.post("/{subject_id}/materials", response_model=MaterialResponse)
async def upload_material(
    subject_id: str,
    file: UploadFile = File(...),
    claims: dict = Depends(get_current_user),
):
    owner_id = await _owner_id(claims)
    subject = await subjects_service.get_subject(owner_id, subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Empty file")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="Only text-based PDF files are supported")

    filename = file.filename or "document.pdf"
    storage_ref = f"materials/{owner_id}/{subject_id}/{filename}"
    try:
        await upload_bytes("materials", storage_ref, content, content_type="application/pdf")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Upload failed: {exc}") from exc

    material = await materials_service.create_material(
        owner_id=owner_id,
        subject_id=subject_id,
        filename=filename,
        file_type="PDF",
        storage_reference=storage_ref,
        processing_status="UPLOADED",
    )
    if material is None:
        raise HTTPException(status_code=503, detail="Material store unavailable")

    try:
        return await process_material(
            owner_id=owner_id,
            subject_id=subject_id,
            material_id=material["id"],
            content=content,
        )
    except Exception as exc:  # noqa: BLE001
        failed = await materials_service.get_material(owner_id, material["id"])
        raise HTTPException(
            status_code=422,
            detail={"message": "Ingestion failed", "material": failed or material},
        ) from exc


@router.get("/{subject_id}/knowledge-graph")
async def get_knowledge_graph(subject_id: str, claims: dict = Depends(get_current_user)):
    owner_id = await _owner_id(claims)
    subject = await subjects_service.get_subject(owner_id, subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")

    from app.services import concepts as concepts_service
    from app.services import relationships as relationships_service

    concepts = await concepts_service.list_concepts(subject_id)
    relationships = await relationships_service.list_relationships(subject_id)
    return {
        "subject": subject,
        "concepts": concepts,
        "relationships": relationships,
        "status": subject["status"],
        "conceptCount": len(concepts),
    }