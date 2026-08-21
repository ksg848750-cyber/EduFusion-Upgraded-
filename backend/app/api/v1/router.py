from fastapi import APIRouter

from app.api.v1.endpoints import auth, diagnostics, health, learner, reassessments, subjects, teaching

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(subjects.router)
api_router.include_router(learner.router)
api_router.include_router(diagnostics.router)
api_router.include_router(teaching.router)
api_router.include_router(reassessments.router)
