from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Frontend-facing gateway for AutoTestDesign.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    from app.modules.fsm.router import router as fsm_router
    from app.modules.concept_risk.router import router as concept_risk_router
    from app.modules.coverage_strategy.router import router as coverage_strategy_router
    from app.modules.evidence_improve.router import router as evidence_improve_router
    from app.modules.intake_parse.router import router as intake_parse_router
    from app.modules.optimize_export.router import router as optimize_export_router
    from app.modules.test_design.router import router as test_design_router

    app.include_router(fsm_router)
    app.include_router(intake_parse_router)
    app.include_router(concept_risk_router)
    app.include_router(coverage_strategy_router)
    app.include_router(test_design_router)
    app.include_router(evidence_improve_router)
    app.include_router(optimize_export_router)
    return app


app = create_app()
