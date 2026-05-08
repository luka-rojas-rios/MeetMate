import os
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.event_participant import EventParticipant
from backend.models.feedback import Feedback
from backend.models.user import User


router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")

UPLOAD_DIR = Path("frontend/static/uploads/profile_photos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def validate_password(password: str):
    errors = []

    if len(password) < 8:
        errors.append("at least 8 characters")

    if not re.search(r"[A-Z]", password):
        errors.append("one uppercase letter")

    if not re.search(r"[a-z]", password):
        errors.append("one lowercase letter")

    if not re.search(r"[0-9]", password):
        errors.append("one number")

    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("one special character")

    if errors:
        return "The password must contain " + ", ".join(errors) + "."

    return None


def get_current_user(request: Request, db: Session):
    user_id = request.session.get("user_id")

    if not user_id:
        return None

    return db.query(User).filter(User.id == user_id).first()


def save_profile_photo(file: UploadFile | None):
    if not file or not file.filename:
        return None

    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    extension = os.path.splitext(file.filename)[1].lower()

    if extension not in allowed_extensions:
        return None

    safe_filename = f"profile_{os.urandom(8).hex()}{extension}"
    file_path = UPLOAD_DIR / safe_filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return f"uploads/profile_photos/{safe_filename}"


def user_has_used_app(user: User, db: Session):
    if not user:
        return False

    has_profile = bool(
        user.first_name
        or user.last_name
        or user.profile_photo
        or user.biography
        or user.user_type
        or user.language
        or user.home_university
        or user.exchange_university
    )

    has_joined_event = (
        db.query(EventParticipant)
        .filter(EventParticipant.user_id == user.id)
        .first()
        is not None
    )

    has_created_event = bool(user.created_events)

    return has_profile or has_joined_event or has_created_event


def user_feedback_status(user: User, db: Session):
    if not user:
        return {
            "can_leave_feedback": False,
            "has_feedback": False,
            "has_used_app": False,
        }

    feedback = db.query(Feedback).filter(Feedback.user_id == user.id).first()
    has_used_app = user_has_used_app(user, db)

    return {
        "can_leave_feedback": has_used_app,
        "has_feedback": feedback is not None,
        "has_used_app": has_used_app,
    }


@router.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "user": user,
        },
    )


@router.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "error": None,
        },
    )


@router.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    security_question: str = Form(...),
    security_answer: str = Form(...),
    db: Session = Depends(get_db),
):
    username = username.strip().lower()

    password_error = validate_password(password)

    if password_error:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "error": password_error,
            },
        )

    existing_user = db.query(User).filter(User.username == username).first()

    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "error": "That username already exists.",
            },
        )

    new_user = User(
        username=username,
        password=password,
        security_question=security_question,
        security_answer=security_answer,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    request.session["user_id"] = new_user.id
    request.session["username"] = new_user.username

    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": None,
        },
    )


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    username = username.strip().lower()

    user = (
        db.query(User)
        .filter(User.username == username, User.password == password)
        .first()
    )

    if not user:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Incorrect username or password.",
            },
        )

    request.session["user_id"] = user.id
    request.session["username"] = user.username

    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@router.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    feedback_status = user_feedback_status(user, db)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": user,
            "username": user.username,
            "feedback_status": feedback_status,
        },
    )


@router.get("/edit-profile")
def edit_profile_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="edit_profile.html",
        context={
            "user": user,
            "error": None,
            "success": None,
        },
    )


@router.post("/edit-profile")
def edit_profile(
    request: Request,
    first_name: str = Form(None),
    last_name: str = Form(None),
    birth_date: str = Form(None),
    sex: str = Form(None),
    nationality: str = Form(None),
    phone: str = Form(None),
    biography: str = Form(None),
    profile_photo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    uploaded_photo = save_profile_photo(profile_photo)

    user.first_name = first_name
    user.last_name = last_name
    user.birth_date = birth_date
    user.sex = sex
    user.nationality = nationality
    user.phone = phone
    user.biography = biography

    if uploaded_photo:
        user.profile_photo = uploaded_photo

    db.commit()
    db.refresh(user)

    return templates.TemplateResponse(
        request=request,
        name="edit_profile.html",
        context={
            "user": user,
            "error": None,
            "success": "Profile updated successfully.",
        },
    )


@router.get("/forgot-password")
def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="forgot_password.html",
        context={
            "error": None,
            "question": None,
            "username": None,
        },
    )


@router.post("/forgot-password")
def forgot_password(
    request: Request,
    username: str = Form(...),
    db: Session = Depends(get_db),
):
    username = username.strip().lower()
    user = db.query(User).filter(User.username == username).first()

    if not user:
        return templates.TemplateResponse(
            request=request,
            name="forgot_password.html",
            context={
                "error": "There is no user with that username.",
                "question": None,
                "username": None,
            },
        )

    return templates.TemplateResponse(
        request=request,
        name="forgot_password.html",
        context={
            "error": None,
            "question": user.security_question,
            "username": user.username,
        },
    )


@router.post("/reset-password")
def reset_password(
    request: Request,
    username: str = Form(...),
    security_answer: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    username = username.strip().lower()
    user = db.query(User).filter(User.username == username).first()

    if not user:
        return templates.TemplateResponse(
            request=request,
            name="forgot_password.html",
            context={
                "error": "There is no user with that username.",
                "question": None,
                "username": username,
            },
        )

    if user.security_answer.lower().strip() != security_answer.lower().strip():
        return templates.TemplateResponse(
            request=request,
            name="forgot_password.html",
            context={
                "error": "The security answer is incorrect.",
                "question": user.security_question,
                "username": username,
            },
        )

    password_error = validate_password(new_password)

    if password_error:
        return templates.TemplateResponse(
            request=request,
            name="forgot_password.html",
            context={
                "error": password_error,
                "question": user.security_question,
                "username": username,
            },
        )

    user.password = new_password
    db.commit()

    return RedirectResponse(url="/login", status_code=303)