from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.schemas.learner import (
    ClarifyRequest,
    ClarifyResponse,
    LessonContentResponse,
    LessonDetailResponse,
    LessonGenerateRequest,
    TeachingDecisionRequest,
    TeachingDecisionResponse,
)
from app.services import subjects as subjects_service
from app.services import users as users_service
from app.services.teaching import (
    clarify_doubt,
    compute_teaching_decision,
    generate_lesson_content,
    get_lesson,
)

router = APIRouter(tags=["teaching"])


async def _owner(claims: dict) -> str:
    auth_user_id = claims.get("sub")
    owner_id = await users_service.get_user_id_by_auth(auth_user_id) if auth_user_id else None
    if not owner_id:
        raise HTTPException(status_code=404, detail="User profile not found")
    return owner_id


async def _subject(owner_id: str, subject_id: str) -> None:
    subject = await subjects_service.get_subject(owner_id, subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")


@router.post(
    "/subjects/{subject_id}/teaching-decision",
    response_model=TeachingDecisionResponse,
)
async def post_teaching_decision(
    subject_id: str,
    body: TeachingDecisionRequest,
    claims: dict = Depends(get_current_user),
):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)

    result = await compute_teaching_decision(
        owner_id, subject_id, body.sessionId, interest_context=body.interestContext
    )
    if result.get("status") in ("SESSION_NOT_FOUND", "NO_DIAGNOSIS"):
        raise HTTPException(status_code=404, detail=result)
    if result.get("status") == "LESSON_ERROR":
        raise HTTPException(status_code=502, detail=result)
    return result


@router.post(
    "/subjects/{subject_id}/lessons/{lesson_id}/generate",
    response_model=LessonContentResponse,
)
async def post_lesson_generate(
    subject_id: str,
    lesson_id: str,
    body: LessonGenerateRequest,
    claims: dict = Depends(get_current_user),
):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)

    try:
        result = await generate_lesson_content(
            owner_id, subject_id, lesson_id, interest_context=body.interestContext
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Lesson generation failed: {exc}") from exc

    if result.get("status") in ("LESSON_NOT_FOUND", "CONCEPT_NOT_FOUND"):
        raise HTTPException(status_code=404, detail=result)
    if result.get("status") in ("LESSON_ERROR", "LESSON_COMPLETED"):
        raise HTTPException(status_code=409, detail=result)
    return result


@router.get(
    "/subjects/{subject_id}/lessons/{lesson_id}",
    response_model=LessonDetailResponse,
)
async def get_lesson_detail(
    subject_id: str,
    lesson_id: str,
    claims: dict = Depends(get_current_user),
):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)
    lesson = await get_lesson(owner_id, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return {"status": "OK", "lesson": lesson}


@router.post(
    "/subjects/{subject_id}/lessons/{lesson_id}/clarify",
    response_model=ClarifyResponse,
)
async def post_lesson_clarify(
    subject_id: str,
    lesson_id: str,
    body: ClarifyRequest,
    claims: dict = Depends(get_current_user),
):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)

    try:
        result = await clarify_doubt(owner_id, subject_id, lesson_id, body.question)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Clarification failed: {exc}") from exc

    if result.get("status") in ("LESSON_NOT_FOUND", "CONCEPT_NOT_FOUND"):
        raise HTTPException(status_code=404, detail=result)
    return result