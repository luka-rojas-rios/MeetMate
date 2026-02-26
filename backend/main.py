from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
from backend.routes import auth_routes
from backend.routes import match_routes
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, Request, Form, Depends

app = FastAPI()
templates = Jinja2Templates(directory="backend/templates")

# --- Configurar CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Montar la carpeta static ---
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
app.add_middleware(SessionMiddleware, secret_key="clave-super-secreta")

# --- Incluir las rutas de autenticación ---
app.include_router(auth_routes.router)
app.include_router(match_routes.router)

# --- Servir el index.html ---
@app.get("/", response_class=HTMLResponse)
def get_index():
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    return html

# --- Servir el welcome.html ---
@app.get("/welcome", response_class=HTMLResponse)
def get_welcome():
    html = Path("frontend/welcome.html").read_text(encoding="utf-8")
    return html

@app.get("/match-profile", response_class=HTMLResponse)
async def match_profile_form(request: Request):
    # Mostrar el formulario por primera vez sin mensaje
    return templates.TemplateResponse("match_profile.html", {"request": request})

@app.post("/submit_match_profile", response_class=HTMLResponse)
async def submit_match_profile(request: Request):
    form = await request.form()
    datos = dict(form)

    # Simulación de lógica de match
    match_encontrado = None  # Aquí va tu lógica real

    if match_encontrado:
        return templates.TemplateResponse("match_success.html", {
            "request": request,
            "match": match_encontrado
        })
    else:
        return templates.TemplateResponse("match_profile.html", {
            "request": request,
            "message": "You don't have a match yet. You can try again by filling out the form."
        })