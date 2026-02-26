from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from backend.models.auth import RegisterRequest, LoginRequest
import re
from backend.models.match import Match
from datetime import datetime
from backend.schemas.match import MatchRequest
from backend.models.user import User
from backend.models.match import Match
from backend.database import SessionLocal
from backend.models.user import User
from fastapi import Request

router = APIRouter()

# --- Dependencia para la base de datos ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Registro de usuario ---
@router.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    print("💡 Registro solicitado")

    # Convertir username a minúsculas
    username = request.username.lower()
    user = db.query(User).filter(User.username == username).first()
    if user:
        raise HTTPException(status_code=400, detail="Este nombre de usuario ya existe.")

    # Validación de contraseña
    password_errors = []
    if len(request.password) < 6:
        password_errors.append("At least 6 characters.")
    if not re.search(r"[A-Z]", request.password):
        password_errors.append("At least one capital letter.")
    if not re.search(r"[a-z]", request.password):
        password_errors.append("At least one lowercase letter.")
    if not re.search(r"[0-9]", request.password):
        password_errors.append("At least one number.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\\/]", request.password):
        password_errors.append("At least one special character.")

    if password_errors:
        raise HTTPException(status_code=400, detail=" ".join(password_errors))

    new_user = User(
        username=username,
        password=request.password,
        security_question=request.security_question,
        security_answer=request.security_answer
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "Successfully registered user 🎉"}

# --- Inicio de sesión ---
@router.post("/login")
def login(request: Request, credentials: LoginRequest, db: Session = Depends(get_db)):
    username = credentials.username.lower()
    user = db.query(User).filter(User.username.ilike(username)).first()
    if not user or user.password != credentials.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    request.session["username"] = user.username
    return {"message": "Successful login 🎉", "user": user.username}


# --- Obtener pregunta de recuperación ---
@router.get("/recover-password")
def recover_password(username: str = Query(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"security_question": user.security_question}

# --- Validar respuesta de recuperación ---
@router.post("/validate-answer")
def validate_answer(data: dict, db: Session = Depends(get_db)):
    username = data.get("username")
    security_answer = data.get("security_answer")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.security_answer != security_answer:
        raise HTTPException(status_code=401, detail="Wrong answer")

    return {"message": "Correct answer"}

# --- Resetear contraseña ---
@router.post("/reset-password")
def reset_password(data: dict, db: Session = Depends(get_db)):
    username = data.get("username")
    new_password = data.get("new_password")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validaciones para la nueva contraseña
    password_errors = []
    if len(new_password) < 6:
        password_errors.append(".")
    if not re.search(r"[A-Z]", new_password):
        password_errors.append("At least 6 characters.")
    if not re.search(r"[a-z]", new_password):
        password_errors.append("At least one lowercase letter.")
    if not re.search(r"[0-9]", new_password):
        password_errors.append("At least one number.")
    if not re.search(r"[\W_]", new_password):
        password_errors.append("At least one special character.")

    if password_errors:
        raise HTTPException(status_code=400, detail=" ".join(password_errors))

    # Actualizar contraseña
    user.password = new_password
    db.commit()

    return {"message": "Password updated successfully 🎉"}


@router.post("/match")
def create_match(request: MatchRequest, db: Session = Depends(get_db)):
    # Comprobar si ya existe
    existing = db.query(Match).filter_by(
        student_id=request.student_id, buddy_id=request.buddy_id
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
    return {"message": "Match created successfully."}

@router.get("/matches/{user_id}")
def get_user_matches(user_id: int, db: Session = Depends(get_db)):
    matches = db.query(Match).filter(
        (Match.student_id == user_id) | (Match.buddy_id == user_id)
    ).all()
    return matches
