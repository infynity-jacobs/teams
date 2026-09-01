import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models import User, RoleEnum
from app.utils.security import hash_password

from app.routers import auth, users, teams, leads, import_xlsx, reports, audit
from app.routers import settings as settings_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("leadcrm")

app = FastAPI(title=settings.APP_NAME)

origins = ["*"] if settings.CORS_ORIGINS == "*" else [o.strip() for o in settings.CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(teams.router)
app.include_router(leads.router)
app.include_router(import_xlsx.router)
app.include_router(reports.router)
app.include_router(audit.router)
app.include_router(settings_router.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            admin = User(
                username=settings.BOOTSTRAP_ADMIN_USERNAME,
                email=settings.BOOTSTRAP_ADMIN_EMAIL,
                full_name="System Administrator",
                role=RoleEnum.super_admin,
                hashed_password=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
            )
            db.add(admin)
            db.commit()
            logger.warning(
                "Bootstrapped initial Super Admin user '%s'. "
                "Log in and change the password immediately.",
                settings.BOOTSTRAP_ADMIN_USERNAME,
            )
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}


# Serve the frontend (built as static files) if present, so the whole app
# can be run as a single service. In production you may instead serve the
# frontend directory directly via Nginx (see deploy/nginx_leadcrm.conf).
FRONTEND_DIR = os.getenv("FRONTEND_DIR", "/app/frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
