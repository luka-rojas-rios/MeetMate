from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates

from backend.routes import auth_routes
from backend.routes import match_routes
from backend.routes import event_routes

app = FastAPI()
templates = Jinja2Templates(directory="backend/templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
app.add_middleware(SessionMiddleware, secret_key="clave-super-secreta")

app.include_router(auth_routes.router)
app.include_router(match_routes.router)
app.include_router(event_routes.router)

from backend.models.base import Base
from backend.database import engine
from backend.models.user import User
from backend.models.match import Match
from backend.models.event import Event
from backend.models.event_participant import EventParticipant

Base.metadata.create_all(bind=engine)


@app.get("/", response_class=HTMLResponse)
def get_index():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    return html


@app.get("/welcome", response_class=HTMLResponse)
def get_welcome():
    html = Path("frontend/welcome.html").read_text(encoding="utf-8")
    return html


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    username = request.session.get("username")
    if not username:
        html = Path("frontend/index.html").read_text(encoding="utf-8")
        return HTMLResponse(content=html)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "username": username
        }
    )
