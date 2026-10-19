"""KYC and Interview Integrity Service API.

Thin application factory routing to domain routers:
- Core: health, readyz, tenants, keys
- KYC: verifications, flow, webhooks, review
- Interview: interviews, clips, summary, tokens
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.config import get_settings
from app.auth import router as auth_router
from app.core.router import router as core_router
from app.kyc.router import router as kyc_router
from app.interview.router import router as interview_router
from app.readiness import check_system_readiness


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    s = get_settings()
    if s.seed_demo:
        db.seed_demo_tenants()

    # Fail fast if critical components unavailable under strict production mode
    if s.strict_mode and not s.dev_mode:
        all_ready, models = check_system_readiness()
        if not all_ready or (s.enable_interview and models.get("Detectif.ai (Voice AI)", {}).get("status") != "configured"):
            failed = [f"{k}: {v.get('error', 'not ready')}" for k, v in models.items() if v.get("status") not in ("ready", "configured", "uncalibrated")]
            if s.enable_interview and not s.detectif_api_key:
                failed.append("Detectif.ai: DETECTIF_API_KEY is missing")
            raise RuntimeError(f"Startup aborted under KYC_STRICT=1: {'; '.join(failed)}")

    # Process any pending KYC pipeline jobs from previous runs
    if s.enable_kyc:
        from app import pipeline
        pending = db.get_pending_pipeline_jobs()
        for job in pending:
            try:
                pipeline.process(job["vid"], job_id=job["id"])
            except Exception:
                pass
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="KYC Verification Service", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if s.dev_mode else s.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # 1. Always mount Core and Auth routers
    app.include_router(core_router)
    app.include_router(auth_router)

    # 2. Conditionally mount KYC product router
    if s.enable_kyc:
        app.include_router(kyc_router)

    # 3. Conditionally mount Interview product router
    if s.enable_interview:
        app.include_router(interview_router)

    @app.get("/", include_in_schema=False)
    def index():
        if s.enable_kyc:
            return RedirectResponse("/dashboard")
        return RedirectResponse("/readyz")

    return app


app = create_app()
