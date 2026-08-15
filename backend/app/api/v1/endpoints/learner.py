from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.schemas.learner import (
    AnswerRequest,
    AnswerResponse,
    ConceptLearnerResponse,
    ExplanationResponse,
    SubjectLearnerResponse,
    TestStartResponse,
)
from app.services import subjects as subjects_service
from app.services import users as users_service
from app.services.concept_context import get_concept_chunks
from app.services.study import explain_concept, start_test, submit_answer
from app.ai.service import AIService

router = APIRouter(tags=["learner"])


async def _owner(claims: dict) -> str:
    auth_user_id = claims.get("sub")
    owner_id = await users_service.get_user_id_by_auth(auth_user_id) if auth_user_id else None
    if not owner_id:
        raise HTTPException(status_code=404, detail="User profile not found")
    return owner_id


async def _subject(owner_id: str, subject_id: str) -> dict:
    subject = await subjects_service.get_subject(owner_id, subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


async def _concept(subject_id: str, concept_id: str) -> dict:
    from app.services import concepts as concepts_service

    concepts = await concepts_service.list_concepts(subject_id)
    for c in concepts:
        if c["id"] == concept_id:
            return c
    raise HTTPException(status_code=404, detail="Concept not found")


async def _question_in_session(session: dict, question_id: str) -> dict:
    from app.services import questions as questions_service

    question = await questions_service.get_question(question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    if question["subjectId"] != session["subjectId"] or question["conceptId"] != session["conceptId"]:
        raise HTTPException(status_code=400, detail="Question does not belong to this session")
    return question


@router.get("/subjects/{subject_id}/learner", response_model=SubjectLearnerResponse)
async def get_subject_learner(subject_id: str, claims: dict = Depends(get_current_user)):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)

    from app.services import learner as learner_service

    model = await learner_service.get_learner_model(owner_id, subject_id)
    if model is None:
        return {"subjectId": subject_id, "overallMastery": 0.0, "conceptStates": {}, "version": 1}
    return {
        "subjectId": subject_id,
        "overallMastery": model["overallMastery"],
        "conceptStates": model["conceptStates"],
        "version": model["version"],
    }


@router.get("/subjects/{subject_id}/concepts/{concept_id}/learner", response_model=ConceptLearnerResponse)
async def get_concept_learner(subject_id: str, concept_id: str, claims: dict = Depends(get_current_user)):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)
    concept = await _concept(subject_id, concept_id)

    from app.services import learner as learner_service
    from app.services import misconceptions as misconceptions_service

    state = await learner_service.get_concept_state(owner_id, subject_id, concept_id)
    misconceptions = await misconceptions_service.list_misconceptions_for_concept(
        owner_id, subject_id, concept_id
    )
    state = {**state, "conceptId": concept_id, "conceptName": concept["name"]}
    return {
        "subjectId": subject_id,
        "conceptId": concept_id,
        "conceptName": concept["name"],
        "state": state,
        "misconceptions": misconceptions,
    }


@router.post("/subjects/{subject_id}/concepts/{concept_id}/explain", response_model=ExplanationResponse)
async def explain(subject_id: str, concept_id: str, claims: dict = Depends(get_current_user)):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)
    concept = await _concept(subject_id, concept_id)

    try:
        explanation = await explain_concept(
            owner_id, subject_id, concept, learner_id=owner_id, ai=AIService()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Explanation generation failed: {exc}") from exc

    return {
        "conceptId": concept_id,
        "conceptName": concept["name"],
        "explanation": explanation,
    }


@router.post("/subjects/{subject_id}/concepts/{concept_id}/test", response_model=TestStartResponse)
async def start_concept_test(subject_id: str, concept_id: str, claims: dict = Depends(get_current_user)):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)
    concept = await _concept(subject_id, concept_id)

    try:
        result = await start_test(
            owner_id, subject_id, concept, learner_id=owner_id, ai=AIService()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Question generation failed: {exc}") from exc

    return result


@router.post("/subjects/{subject_id}/sessions/{session_id}/answers", response_model=AnswerResponse)
async def submit_concept_answer(
    subject_id: str,
    session_id: str,
    body: AnswerRequest,
    claims: dict = Depends(get_current_user),
):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)

    from app.services import sessions as sessions_service

    session = await sessions_service.get_session(owner_id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["subjectId"] != subject_id:
        raise HTTPException(status_code=400, detail="Session does not belong to this subject")

    concept = await _concept(subject_id, session["conceptId"])
    question = await _question_in_session(session, body.questionId)

    try:
        result = await submit_answer(
            owner_id,
            subject_id,
            session,
            concept,
            question,
            learner_id=owner_id,
            response=body.response,
            reasoning=body.reasoning,
            selected_option_id=body.selectedOptionId,
            ai=AIService(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Answer evaluation failed: {exc}") from exc

    return result