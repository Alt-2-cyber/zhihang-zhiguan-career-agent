from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.applications.router import router as applications_router
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler
from app.dashboard.router import router as dashboard_router
from app.jobs.router import router as jobs_router
from app.interviews.router import router as interviews_router
from app.interventions.router import router as interventions_router
from app.plans.router import router as plans_router
from app.resumes.router import router as resumes_router
from app.reviews.router import router as reviews_router
from app.students.router import router as students_router


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name)
    application.add_exception_handler(AppError, app_error_handler)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(auth_router, prefix="/api")
    application.include_router(students_router, prefix="/api")
    application.include_router(resumes_router, prefix="/api")
    application.include_router(plans_router, prefix="/api")
    application.include_router(jobs_router, prefix="/api")
    application.include_router(interviews_router, prefix="/api")
    application.include_router(applications_router, prefix="/api")
    application.include_router(reviews_router, prefix="/api")
    application.include_router(interventions_router, prefix="/api")
    application.include_router(dashboard_router, prefix="/api")

    @application.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
