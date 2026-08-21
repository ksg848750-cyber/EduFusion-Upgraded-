"""M7 Reassessment API — closes the adaptive loop.

POST /subjects/{id}/lessons/{lesson_id}/reassess   → generate reassessment question
POST /subjects/{id}/reassessments/{id}/answer      → submit answer + get outcome
GET  /subjects/{id}/lessons/{lesson_id}/reassessment → get current reassessment
"""

from fastapi import APIRouter, Depends, HTTPException

from app.ai.service import AIService
from app.core.security import get_current_user
from app.schemas.learner import (
    ReassessmentAnswerRequest,
    ReassessmentAnswerResponse,
    ReassessmentRequest,
    ReassessmentResponse,
)
from app.services import concepts as concepts_service
from app.services import subjects as subjects_service
from app.services import users as users_service
from app.services import answers as answers_service
from app.services.concept_context import get_concept_chunks
from app.services.reassessments import (
    create_reassessment,
    get_reassessment_by_lesson,
    submit_reassessment_answer,
)
from app.services.teaching import get_lesson

router = APIRouter(tags=["reassessment"])


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
    "/subjects/{subject_id}/lessons/{lesson_id}/reassess",
    response_model=ReassessmentResponse,
)
async def post_reassess(
    subject_id: str,
    lesson_id: str,
    body: ReassessmentRequest = ReassessmentRequest(),
    claims: dict = Depends(get_current_user),
):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)

    # Load the lesson
    lesson = await get_lesson(owner_id, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    if lesson["subjectId"] != subject_id:
        raise HTTPException(status_code=400, detail="Lesson does not belong to this subject")

    # Check if reassessment already exists
    existing = await get_reassessment_by_lesson(lesson_id, owner_id)
    if existing and existing["status"] != "PENDING":
        raise HTTPException(status_code=409, detail="Reassessment already completed")

    # Load concept
    concept = None
    for c in await concepts_service.list_concepts(subject_id):
        if c["id"] == lesson["conceptId"]:
            concept = c
            break
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    # Get existing questions to avoid duplication
    from app.core.database import connection as db_conn
    existing_questions = []
    async with db_conn() as conn:
        if conn:
            rows = await conn.execute(
                """
                SELECT question_type, question_text, options, correct_option_id
                FROM public.questions
                WHERE subject_id = %s AND concept_id = %s
                ORDER BY created_at DESC LIMIT 10
                """,
                (subject_id, lesson["conceptId"]),
            )
            for r in await rows.fetchall():
                existing_questions.append({
                    "questionType": r[0],
                    "questionText": r[1],
                    "options": r[2] or [],
                    "correctOptionId": r[3] or "",
                })

    # Get chunks for grounding
    chunks = await get_concept_chunks(owner_id, subject_id, concept)

    # Generate reassessment question
    ai = AIService()
    try:
        generated = await ai.generate_reassessment(
            concept=concept,
            root_cause=lesson["rootCause"],
            teaching_strategy=lesson["teachingStrategy"],
            existing_questions=existing_questions,
            chunks=chunks,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Reassessment generation failed: {exc}") from exc

    # Persist the reassessment
    question_data = {
        "questionType": generated.questionType,
        "questionText": generated.questionText,
        "expectedAnswer": generated.expectedAnswer,
        "expectedReasoning": generated.expectedReasoning,
        "options": [{"id": o.id, "text": o.text} for o in generated.options],
        "correctOptionId": generated.correctOptionId,
    }
    reassessment = await create_reassessment(
        owner_id, subject_id, lesson_id, question_data,
    )
    if reassessment is None:
        raise HTTPException(status_code=500, detail="Failed to persist reassessment")

    return ReassessmentResponse(
        status="OK",
        reassessmentId=reassessment["id"],
        lessonId=lesson_id,
        conceptId=lesson["conceptId"],
        questionType=generated.questionType,
        questionText=generated.questionText,
        options=[{"id": o.id, "text": o.text} for o in generated.options],
        attempt=reassessment["attempt"],
    )


@router.post(
    "/subjects/{subject_id}/reassessments/{reassessment_id}/answer",
    response_model=ReassessmentAnswerResponse,
)
async def post_reassessment_answer(
    subject_id: str,
    reassessment_id: str,
    body: ReassessmentAnswerRequest,
    claims: dict = Depends(get_current_user),
):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)

    from app.services.reassessments import get_reassessment
    reassessment = await get_reassessment(reassessment_id, owner_id)
    if reassessment is None:
        raise HTTPException(status_code=404, detail="Reassessment not found")
    if reassessment["subjectId"] != subject_id:
        raise HTTPException(status_code=400, detail="Reassessment does not belong to this subject")
    if reassessment["status"] != "PENDING":
        raise HTTPException(status_code=409, detail="Reassessment already answered")

    # Deterministic correctness check for MCQ
    correctness = False
    reasoning_quality = "PARTIAL"
    if reassessment["questionType"] == "MCQ" and body.selectedOptionId:
        correctness = body.selectedOptionId == reassessment["correctOptionId"]
    elif body.response:
        # For short answer: deterministic check against expected answer
        expected = (reassessment.get("expectedAnswer") or "").lower().strip()
        response = body.response.lower().strip()
        correctness = expected in response or response in expected
        if not correctness and len(response) > 20:
            # Let the LLM evaluate for longer responses
            from app.ai.service import AIService
            ai = AIService()
            concept = None
            for c in await concepts_service.list_concepts(subject_id):
                if c["id"] == reassessment["conceptId"]:
                    concept = c
                    break
            if concept:
                try:
                    from app.services.concept_context import get_concept_chunks
                    chunks = await get_concept_chunks(owner_id, subject_id, concept)
                    eval_result = await ai.evaluate_answer(
                        concept=concept,
                        question={
                            "questionText": reassessment["questionText"],
                            "questionType": reassessment["questionType"],
                            "expectedAnswer": reassessment["expectedAnswer"],
                            "expectedReasoning": reassessment["expectedReasoning"],
                        },
                        chunks=chunks,
                        student_response=body.response,
                        student_reasoning=body.reasoning,
                    )
                    correctness = eval_result.correct
                    reasoning_quality = eval_result.reasoningQuality
                except Exception:
                    pass

    # If MCQ and no selectedOptionId, try matching response text
    if reassessment["questionType"] == "MCQ" and not body.selectedOptionId and body.response:
        for opt in reassessment.get("options", []):
            if opt.get("id") == body.response or opt.get("text", "").lower().strip() == body.response.lower().strip():
                body.selectedOptionId = opt["id"]
                correctness = opt["id"] == reassessment["correctOptionId"]
                break

    # Determine reasoning quality
    if correctness and not body.reasoning:
        reasoning_quality = "SOLID"
    elif body.reasoning and len(body.reasoning) > 50:
        reasoning_quality = "SOLID"
    elif body.reasoning:
        reasoning_quality = "PARTIAL"
    else:
        reasoning_quality = "POOR"

    result = await submit_reassessment_answer(
        owner_id=owner_id,
        reassessment_id=reassessment_id,
        response=body.response,
        reasoning=body.reasoning,
        correctness=correctness,
        reasoning_quality=reasoning_quality,
    )
    if result is None:
        raise HTTPException(status_code=500, detail="Failed to submit reassessment answer")

    return ReassessmentAnswerResponse(
        status="OK",
        reassessmentId=result["id"],
        outcome=result["status"],
        correctness=result["correctness"],
        mastery=result["mastery"],
        conceptStatus=result["conceptStatus"],
        attempt=result["attempt"],
    )


@router.get(
    "/subjects/{subject_id}/lessons/{lesson_id}/reassessment",
    response_model=ReassessmentResponse,
)
async def get_lesson_reassessment(
    subject_id: str,
    lesson_id: str,
    claims: dict = Depends(get_current_user),
):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)

    reassessment = await get_reassessment_by_lesson(lesson_id, owner_id)
    if reassessment is None:
        raise HTTPException(status_code=404, detail="No reassessment found for this lesson")

    return ReassessmentResponse(
        status="OK",
        reassessmentId=reassessment["id"],
        lessonId=lesson_id,
        conceptId=reassessment["conceptId"],
        questionType=reassessment["questionType"],
        questionText=reassessment["questionText"],
        options=reassessment.get("options", []),
        attempt=reassessment["attempt"],
    )
