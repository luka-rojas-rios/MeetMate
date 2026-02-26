from fastapi import APIRouter, HTTPException, Depends, Form, Request
from sqlalchemy.orm import Session
from datetime import datetime
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from backend.database import SessionLocal
from backend.schemas.match import MatchRequest
from backend.models.match import Match
from backend.models.user import User
from sqlalchemy import or_

router = APIRouter()
templates = Jinja2Templates(directory="backend/templates")

# --- Conexión a la base de datos ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Crear un match ---
@router.post("/match")
def create_match(request: MatchRequest, db: Session = Depends(get_db)):
    existing = db.query(Match).filter_by(
        student_id=request.student_id,
        buddy_id=request.buddy_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="There is already a match between these users.")

    match = Match(
        student_id=request.student_id,
        buddy_id=request.buddy_id,
        created_at=datetime.utcnow().isoformat()
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return {"message": "Match created successfully."}

# --- Obtener matches de un usuario ---
@router.get("/matches/{user_id}")
def get_user_matches(user_id: int, db: Session = Depends(get_db)):
    matches = db.query(Match).filter(
        (Match.student_id == user_id) | (Match.buddy_id == user_id)
    ).all()
    return matches

# --- Formulario de perfil para hacer match ---
@router.post("/submit_match_profile", response_class=HTMLResponse)
def submit_match_profile(
    request: Request,
    user_type: str = Form(...),
    language: str = Form(...),
    language2: str = Form(None),
    home_university: str = Form(...),
    exchange_university: str = Form(...),
    favorite_sport_1: str = Form(None),
    favorite_sport_2: str = Form(None),
    hobby_1: str = Form(None),
    hobby_2: str = Form(None),
    db: Session = Depends(get_db)
):
    username = request.session.get("username")
    if not username:
        return templates.TemplateResponse("match_profile.html", {"request": request, "error": "Inicia sesión"})

    user = db.query(User).filter_by(username=username).first()
    if not user:
        return templates.TemplateResponse("match_profile.html", {"request": request, "error": "User not found"})

    # Guardar datos del perfil
    user.user_type = user_type
    user.language = language
    user.language_2 = language2
    user.home_university = home_university
    user.exchange_university = exchange_university
    user.favorite_sport_1 = favorite_sport_1
    user.favorite_sport_2 = favorite_sport_2
    user.hobby_1 = hobby_1
    user.hobby_2 = hobby_2
    db.commit()

    # Buscar match
    opposite_type = "exchange" if user_type == "local" else "local"
    university = exchange_university if user_type == "exchange" else home_university

    possible_matches = db.query(User).filter(
        User.user_type == opposite_type,
        or_(
            User.language == language,
            User.language == language2,
            User.language_2 == language,
            User.language_2 == language2
        ),
        (User.exchange_university == university) | (User.home_university == university)
    ).all()

    for match_candidate in possible_matches:
        already_exists = db.query(Match).filter_by(
            student_id=min(user.id, match_candidate.id),
            buddy_id=max(user.id, match_candidate.id)
        ).first()

        if not already_exists:
            match = Match(
                student_id=min(user.id, match_candidate.id),
                buddy_id=max(user.id, match_candidate.id),
                created_at=datetime.utcnow().isoformat()
            )
            db.add(match)
            db.commit()
            db.refresh(match)

            # ✅ Guardar en sesión el ID del match y el dueño
            request.session["match_id"] = match.id
            request.session["match_owner"] = user.id

            return templates.TemplateResponse("match_success.html", {
                "request": request,
                "matched_user": match_candidate
            })

    # ✅ Guardar en sesión que no hubo match
    request.session["match_id"] = None
    request.session["match_owner"] = user.id

    return templates.TemplateResponse("match_profile.html", {
        "request": request,
        "message": "Profile saved, but no compatible match found yet."
    })

# --- Página de perfil de match ---
@router.get("/match-profile", response_class=HTMLResponse)
def match_profile(request: Request, db: Session = Depends(get_db)):
    username = request.session.get("username")
    if not username:
        return templates.TemplateResponse("match_profile.html", {"request": request, "error": "Sign in"})

    user = db.query(User).filter_by(username=username).first()
    if not user:
        return templates.TemplateResponse("match_profile.html", {"request": request, "error": "User not found"})

    # Buscar si este usuario tiene algún match guardado en la base de datos
    match = db.query(Match).filter(
        (Match.student_id == user.id) | (Match.buddy_id == user.id)
    ).order_by(Match.created_at.desc()).first()

    if match:
        buddy_id = match.buddy_id if match.buddy_id != user.id else match.student_id
        matched_user = db.query(User).filter_by(id=buddy_id).first()
        return templates.TemplateResponse("match_success.html", {
            "request": request,
            "matched_user": matched_user
        })

    return templates.TemplateResponse("match_profile.html", {
        "request": request,
        "message": "You don't have a match yet. You can try again by filling out the form."
    })
