def load_all_models() -> None:
    """Import every mapped model for CLI tools that do not load API routers."""
    import app.applications.models  # noqa: F401
    import app.audit.models  # noqa: F401
    import app.auth.models  # noqa: F401
    import app.interventions.models  # noqa: F401
    import app.interviews.models  # noqa: F401
    import app.jobs.models  # noqa: F401
    import app.plans.models  # noqa: F401
    import app.resumes.models  # noqa: F401
    import app.reviews.models  # noqa: F401
    import app.risks.models  # noqa: F401
    import app.students.models  # noqa: F401
