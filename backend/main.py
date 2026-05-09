from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from backend.routes import auth_routes
from backend.routes import match_routes
from backend.routes import event_routes
from backend.routes import feedback_routes

from backend.models.base import Base
from backend.database import engine

# Importamos modelos para que SQLAlchemy detecte todas las tablas
from backend.models.user import User
from backend.models.match import Match
from backend.models.event import Event
from backend.models.event_participant import EventParticipant
from backend.models.feedback import Feedback
from backend.models.event_review import EventReview

from backend.schema_upgrades import run_schema_upgrades


app = FastAPI(title="MeetMate")
templates = Jinja2Templates(directory="frontend/templates")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


app.add_middleware(
    SessionMiddleware,
    secret_key="clave-super-secreta"
)


app.include_router(auth_routes.router)
app.include_router(match_routes.router)
app.include_router(event_routes.router)
app.include_router(feedback_routes.router)


Base.metadata.create_all(bind=engine)
run_schema_upgrades()


@app.get("/", response_class=HTMLResponse)
def get_index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.get("/welcome", response_class=HTMLResponse)
def get_welcome(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="welcome.html",
        context={}
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    username = request.session.get("username")

    if not username:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={}
        )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "username": username
        }
    )