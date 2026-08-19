from fastapi import APIRouter, Depends, HTTPException

from app.ai.service import AIService
from app.core.security import get_current_user
from app.schemas.learner import (
    DiagnosticAnswerRequest,
    DiagnosticAnswerResponse,
    DiagnosticDecisionResponse,
    DiagnosticStartRequest,
    DiagnosticStartResponse,
    DiagnosisResponse,
    EvidenceBundleResponse,
    ProbeStartResponse,
)
from app.services import subjects as subjects_service
from app.services import users as users_service
from app.services.diagnostics import (
    analyze_session,
    evidence_bundle,
    finalize_diagnosis,
    generate_probe_for,
    start_diagnostic,
    submit_diagnostic_answer,
)

router = APIRouter(tags=["diagnostics"])


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


async def _session(owner_id: str, session_id: str, subject_id: str) -> dict:
    from app.services import sessions as sessions_service

    session = await sessions_service.get_session(owner_id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["subjectId"] != subject_id:
        raise HTTPException(status_code=400, detail="Session does not belong to this subject")
    return session


async def _question_in_session(session: dict, question_id: str) -> dict:
    from app.services import questions as questions_service

    question = await questions_service.get_question(question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    if question["subjectId"] != session["subjectId"] or question["conceptId"] != session["conceptId"]:
        raise HTTPException(status_code=400, detail="Question does not belong to this session")
    return question


@router.post("/subjects/{subject_id}/diagnostic", response_model=DiagnosticStartResponse)
async def start_diagnostic_session(
    subject_id: str,
    body: DiagnosticStartRequest = DiagnosticStartRequest(),
    claims: dict = Depends(get_current_user),
):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)

    result = await start_diagnostic(
        owner_id, subject_id, ai=AIService(), entry_concept_id=body.conceptId
    )
    if result.get("status") in ("NO_TARGET", "RESOLUTION_ERROR", "GENERATION_ERROR",
                                "VALIDATION_ERROR", "SESSION_ERROR"):
        code = 422 if result.get("status") in ("GENERATION_ERROR", "VALIDATION_ERROR") else 409
        raise HTTPException(status_code=code, detail=result)
    return result


@router.post(
    "/subjects/{subject_id}/sessions/{session_id}/diagnostic-answers",
    response_model=DiagnosticAnswerResponse,
)
async def post_diagnostic_answer(
    subject_id: str,
    session_id: str,
    body: DiagnosticAnswerRequest,
    claims: dict = Depends(get_current_user),
):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)
    session = await _session(owner_id, session_id, subject_id)
    concept = await _concept(subject_id, session["conceptId"])
    question = await _question_in_session(session, body.questionId)

    try:
        result = await submit_diagnostic_answer(
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
        raise HTTPException(status_code=502, detail=f"Diagnostic answer evaluation failed: {exc}") from exc
    return result


@router.get(
    "/subjects/{subject_id}/sessions/{session_id}/diagnostic-decision",
    response_model=DiagnosticDecisionResponse,
)
async def get_diagnostic_decision(subject_id: str, session_id: str, claims: dict = Depends(get_current_user)):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)
    session = await _session(owner_id, session_id, subject_id)

    decision = await analyze_session(owner_id, session)
    return {
        "status": decision["status"],
        "rootCause": decision.get("rootCause"),
        "confidence": decision.get("confidence"),
        "statement": decision.get("statement"),
        "evidenceSignals": decision.get("evidenceSignals", []),
        "hypotheses": decision.get("hypotheses", []),
        "needsProbe": decision["status"] == "AMBIGUOUS",
        "differentiationTarget": _target(decision),
    }


def _target(decision: dict) -> dict | None:
    from app.services.diagnostic_analysis import differentiation_target

    return differentiation_target(decision)


@router.post(
    "/subjects/{subject_id}/sessions/{session_id}/diagnostic-probe",
    response_model=ProbeStartResponse,
)
async def start_diagnostic_probe(subject_id: str, session_id: str, claims: dict = Depends(get_current_user)):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)
    session = await _session(owner_id, session_id, subject_id)
    concept = await _concept(subject_id, session["conceptId"])

    decision = await analyze_session(owner_id, session)
    if decision.get("status") != "AMBIGUOUS":
        return {"status": "NOT_AMBIGUOUS"}

    try:
        result = await generate_probe_for(
            owner_id, subject_id, session, concept, decision, ai=AIService()
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Probe generation failed: {exc}") from exc
    return {"status": "PROBE_READY", **result}


@router.post(
    "/subjects/{subject_id}/sessions/{session_id}/diagnosis",
    response_model=DiagnosisResponse,
)
async def create_final_diagnosis(subject_id: str, session_id: str, claims: dict = Depends(get_current_user)):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)
    session = await _session(owner_id, session_id, subject_id)
    concept = await _concept(subject_id, session["conceptId"])

    decision = await analyze_session(owner_id, session)
    try:
        result = await finalize_diagnosis(owner_id, subject_id, session, concept, decision)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Diagnosis finalization failed: {exc}") from exc
    return result


@router.get(
    "/subjects/{subject_id}/sessions/{session_id}/evidence-bundle",
    response_model=EvidenceBundleResponse,
)
async def get_evidence_bundle(subject_id: str, session_id: str, claims: dict = Depends(get_current_user)):
    owner_id = await _owner(claims)
    await _subject(owner_id, subject_id)
    result = await evidence_bundle(owner_id, subject_id, session_id)
    if result["status"] == "NOT_FOUND":
        raise HTTPException(status_code=404, detail="Session not found")
    return result