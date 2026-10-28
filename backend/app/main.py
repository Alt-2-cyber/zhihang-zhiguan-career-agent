from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.router import router as agents_router
from app.ai.router import router as ai_router
from app.applications.router import router as applications_router
from app.audit.router import router as audit_router
from app.auth.router import router as auth_router
from app.chat.router import router as chat_router
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler
from app.core.scheduler import build_scheduler
from app.dashboard.router import router as dashboard_router
from app.employment.router import router as employment_router
from app.growth.router import router as growth_router
from app.intelligence.router import router as intelligence_router
from app.interventions.router import router as interventions_router
from app.interviews.router import router as interviews_router
from app.jobs.router import router as jobs_router
from app.plans.router import router as plans_router
from app.resumes.router import router as resumes_router
from app.reviews.router import router as reviews_router
from app.students.router import router as students_router
from app.workplace.router import router as workplace_router


@asynccontextmanager
async def lifespan(_application: FastAPI):
    scheduler = build_scheduler(get_settings())
    if scheduler:
        scheduler.start()
    try:
        yield
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    application.add_exception_handler(AppError, app_error_handler)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(auth_router, prefix="/api")
    application.include_router(audit_router, prefix="/api")
    application.include_router(chat_router, prefix="/api")
    application.include_router(ai_router, prefix="/api")
    application.include_router(students_router, prefix="/api")
    application.include_router(resumes_router, prefix="/api")
    application.include_router(plans_router, prefix="/api")
    application.include_router(jobs_router, prefix="/api")
    application.include_router(interviews_router, prefix="/api")
    application.include_router(applications_router, prefix="/api")
    application.include_router(agents_router, prefix="/api")
    application.include_router(reviews_router, prefix="/api")
    application.include_router(interventions_router, prefix="/api")
    application.include_router(dashboard_router, prefix="/api")
    application.include_router(growth_router, prefix="/api")
    application.include_router(workplace_router, prefix="/api")
    application.include_router(intelligence_router, prefix="/api")
    application.include_router(employment_router, prefix="/api")

    @application.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
