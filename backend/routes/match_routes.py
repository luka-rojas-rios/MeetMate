from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.match import Match
from backend.models.user import User
from backend.profile_options import (
    HOBBIES,
    LANGUAGES,
    SPORTS,
    UNIVERSITY_DATA,
    USER_TYPES,
    find_university_location,
)
from backend.schemas.match import MatchRequest

router = APIRouter()
templates = Jinja2Templates(directory="backend/templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def render_profile_form(request: Request, user: User | None = None, **extra_context):
    selected_university = None
    country = None
    city = None
    if user:
        selected_university = user.exchange_university or user.home_university
        country, city = find_university_location(selected_university)

    context = {
        "request": request,
        "user": user,
        "selected_country": country,
        "selected_city": city,
        "selected_university": selected_university,
        "university_data": UNIVERSITY_DATA,
        "languages": LANGUAGES,
        "hobbies": HOBBIES,
        "sports": SPORTS,
        **extra_context,
    }
    return templates.TemplateResponse("match_profile.html", context)


def validate_profile_data(
    user_type: str,
    language: str,
    language2: str | None,
    country: str,
    city: str,
    selected_university: str,
    favorite_sport_1: str | None,
    favorite_sport_2: str | None,
    hobby_1: str | None,
    hobby_2: str | None,
):
    if user_type not in USER_TYPES:
        return "Invalid student type."

    if language not in LANGUAGES:
        return "Language 1 is invalid."

    if language2 and language2 not in LANGUAGES:
        return "Language 2 is invalid."

    if language2 and language2 == language:
        return "Please choose two different languages or leave Language 2 empty."

    if hobby_1 and hobby_1 not in HOBBIES:
        return "Hobby 1 is invalid."

    if hobby_2 and hobby_2 not in HOBBIES:
        return "Hobby 2 is invalid."

    if hobby_1 and hobby_2 and hobby_1 == hobby_2:
        return "Please choose two different hobbies or leave Hobby 2 empty."

    if favorite_sport_1 and favorite_sport_1 not in SPORTS:
        return "First favorite sport is invalid."

    if favorite_sport_2 and favorite_sport_2 not in SPORTS:
        return "Second favorite sport is invalid."

    if favorite_sport_1 and favorite_sport_2 and favorite_sport_1 == favorite_sport_2:
        return "Please choose two different sports or leave the second one empty."

    if country not in UNIVERSITY_DATA:
        return "Selected country is invalid."

    if city not in UNIVERSITY_DATA[country]:
        return "Selected city is invalid."

    if selected_university not in UNIVERSITY_DATA[country][city]:
        return "Selected university is invalid."

    return None


@router.post("/match")
def create_match(request: MatchRequest, db: Session = Depends(get_db)):
    existing = db.query(Match).filter_by(
        student_id=request.student_id,
        buddy_id=request.buddy_id,
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="There is already a match between these users.")

    match = Match(
        student_id=request.student_id,
        buddy_id=request.buddy_id,
        created_at=datetime.utcnow().isoformat(),
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return {"message": "Match created successfully."}


@router.get("/matches/{user_id}")
def get_user_matches(user_id: int, db: Session = Depends(get_db)):
    matches = db.query(Match).filter(
        (Match.student_id == user_id) | (Match.buddy_id == user_id)
    ).all()
    return matches


@router.post("/submit_match_profile", response_class=HTMLResponse)
def submit_match_profile(
    request: Request,
    user_type: str = Form(...),
    language: str = Form(...),
    language2: str = Form(""),
    country: str = Form(...),
    city: str = Form(...),
    university: str = Form(...),
    favorite_sport_1: str = Form(""),
    favorite_sport_2: str = Form(""),
    hobby_1: str = Form(""),
    hobby_2: str = Form(""),
    db: Session = Depends(get_db),
):
    username = request.session.get("username")
    if not username:
        return render_profile_form(request, error="Sign in to edit your profile.")

    user = db.query(User).filter_by(username=username).first()
    if not user:
        return render_profile_form(request, error="User not found.")

    validation_error = validate_profile_data(
        user_type=user_type,
        language=language,
        language2=language2,
        country=country,
        city=city,
        selected_university=university,
        favorite_sport_1=favorite_sport_1,
        favorite_sport_2=favorite_sport_2,
        hobby_1=hobby_1,
        hobby_2=hobby_2,
    )
    if validation_error:
        temp_user = User(
            username=user.username,
            user_type=user_type,
            language=language,
            language_2=language2,
            home_university=university if user_type == "local" else "",
            exchange_university=university if user_type == "exchange" else "",
            favorite_sport_1=favorite_sport_1,
            favorite_sport_2=favorite_sport_2,
            hobby_1=hobby_1,
            hobby_2=hobby_2,
        )
        return templates.TemplateResponse(
            "match_profile.html",
            {
                "request": request,
                "user": temp_user,
                "selected_country": country,
                "selected_city": city,
                "selected_university": university,
                "error": validation_error,
            },
        )

    user.user_type = user_type
    user.language = language
    user.language_2 = language2 or None
    user.home_university = university if user_type == "local" else None
    user.exchange_university = university if user_type == "exchange" else None
    user.favorite_sport_1 = favorite_sport_1 or None
    user.favorite_sport_2 = favorite_sport_2 or None
    user.hobby_1 = hobby_1 or None
    user.hobby_2 = hobby_2 or None
    db.commit()
    db.refresh(user)

    opposite_type = "exchange" if user_type == "local" else "local"
    university_to_match = user.exchange_university if user_type == "exchange" else user.home_university

    possible_matches = db.query(User).filter(
        User.id != user.id,
        User.user_type == opposite_type,
        or_(
            User.language == language,
            User.language == language2,
            User.language_2 == language,
            User.language_2 == language2,
        ),
        or_(
            User.exchange_university == university_to_match,
            User.home_university == university_to_match,
        ),
    ).all()

    for match_candidate in possible_matches:
        already_exists = db.query(Match).filter_by(
            student_id=min(user.id, match_candidate.id),
            buddy_id=max(user.id, match_candidate.id),
        ).first()

        if not already_exists:
            match = Match(
                student_id=min(user.id, match_candidate.id),
                buddy_id=max(user.id, match_candidate.id),
                created_at=datetime.utcnow().isoformat(),
            )
            db.add(match)
            db.commit()
            db.refresh(match)

            request.session["match_id"] = match.id
            request.session["match_owner"] = user.id

            return templates.TemplateResponse(
                "match_success.html",
                {
                    "request": request,
                    "matched_user": match_candidate,
                    "message": "Profile updated successfully. Your new data was also used for matching.",
                },
            )

    request.session["match_id"] = None
    request.session["match_owner"] = user.id

    return render_profile_form(
        request,
        user=user,
        message="Profile updated successfully. Your latest information will be used for future matching.",
    )

@router.get("/match-profile", response_class=HTMLResponse)
def match_profile(request: Request, db: Session = Depends(get_db)):
    username = request.session.get("username")
    if not username:
        return render_profile_form(request, error="Sign in")

    user = db.query(User).filter_by(username=username).first()
    if not user:
        return render_profile_form(request, error="User not found")

    return render_profile_form(
        request,
        user=user,
        message="Complete or update your profile to improve your matching results.",
    )

@router.get("/edit-profile", response_class=HTMLResponse)
def edit_profile(request: Request, db: Session = Depends(get_db)):
    username = request.session.get("username")
    if not username:
        return RedirectResponse(url="/", status_code=302)

    user = db.query(User).filter_by(username=username).first()
    if not user:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("edit_profile.html", {
        "request": request,
        "user": user,
        "message": None
    })

@router.post("/edit-profile", response_class=HTMLResponse)
def save_profile(
    request: Request,
    first_name: str = Form(""),
    last_name: str = Form(""),
    birth_date: str = Form(""),
    sex: str = Form(""),
    nationality: str = Form(""),
    phone: str = Form(""),
    db: Session = Depends(get_db)
):
    username = request.session.get("username")
    if not username:
        return RedirectResponse(url="/", status_code=302)

    user = db.query(User).filter_by(username=username).first()
    if not user:
        return RedirectResponse(url="/", status_code=302)

    user.first_name = first_name
    user.last_name = last_name
    user.birth_date = birth_date if birth_date else None
    user.sex = sex
    user.nationality = nationality
    user.phone = phone

    db.commit()
    db.refresh(user)

    return templates.TemplateResponse("edit_profile.html", {
        "request": request,
        "user": user,
        "message": "Personal profile updated successfully."
    })