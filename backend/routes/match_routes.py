from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_
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
    return templates.TemplateResponse(request=request, name="match_profile.html", context=context)


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


def get_profile_values(user: User):
    languages = {value for value in [user.language, user.language_2] if value}
    hobbies = {value for value in [user.hobby_1, user.hobby_2] if value}
    sports = {value for value in [user.favorite_sport_1, user.favorite_sport_2] if value}
    university = user.exchange_university or user.home_university
    return languages, hobbies, sports, university


def find_best_match(user: User, db: Session):
    if user.user_type != "exchange":
        return None, None

    user_languages, user_hobbies, user_sports, user_university = get_profile_values(user)
    if not user_languages or not user_university:
        return None, "Complete your profile to request a match."

    existing_pair_ids = set()
    for current_match in db.query(Match).filter(
        or_(Match.student_id == user.id, Match.buddy_id == user.id)
    ).all():
        existing_pair_ids.add(current_match.student_id)
        existing_pair_ids.add(current_match.buddy_id)

    candidates = db.query(User).filter(
        User.id != user.id,
        User.user_type == "local",
        or_(
            User.home_university == user_university,
            User.exchange_university == user_university,
        ),
    ).all()

    best_candidate = None
    best_score = -1

    for candidate in candidates:
        if candidate.id in existing_pair_ids:
            continue

        candidate_languages, candidate_hobbies, candidate_sports, candidate_university = get_profile_values(candidate)
        common_languages = user_languages & candidate_languages
        if not common_languages:
            continue

        score = 0
        score += 4 * len(common_languages)
        if candidate_university == user_university:
            score += 3
        score += 2 * len(user_hobbies & candidate_hobbies)
        score += 1 * len(user_sports & candidate_sports)

        if score > best_score:
            best_score = score
            best_candidate = candidate

    if not best_candidate:
        return None, "There are currently no compatible local students available."

    return best_candidate, None


def create_match_record(user: User, matched_user: User, db: Session):
    student_id = min(user.id, matched_user.id)
    buddy_id = max(user.id, matched_user.id)
    existing = db.query(Match).filter_by(student_id=student_id, buddy_id=buddy_id).first()
    if existing:
        return existing

    match = Match(
        student_id=student_id,
        buddy_id=buddy_id,
        created_at=datetime.utcnow().isoformat(),
        status="Created",
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


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
            request=request,
            name="match_profile.html",
            context={
                "request": request,
                "user": temp_user,
                "selected_country": country,
                "selected_city": city,
                "selected_university": university,
                "university_data": UNIVERSITY_DATA,
                "languages": LANGUAGES,
                "hobbies": HOBBIES,
                "sports": SPORTS,
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

    if user.user_type == "exchange":
        matched_user, error_message = find_best_match(user, db)
        if matched_user:
            create_match_record(user, matched_user, db)
            return templates.TemplateResponse(
                request=request,
                name="match_success.html",
                context={
                    "request": request,
                    "matched_user": matched_user,
                    "message": "Profile updated successfully. A compatible local student has been assigned.",
                },
            )
        return render_profile_form(
            request,
            user=user,
            message=f"Profile updated successfully. {error_message}",
        )

    return render_profile_form(
        request,
        user=user,
        message="Profile updated successfully. Your profile is now available for exchange students.",
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

    return templates.TemplateResponse(
        request=request,
        name="edit_profile.html",
        context={
            "user": user,
            "message": None
        }
    )


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

    return templates.TemplateResponse(
        request=request,
        name="edit_profile.html",
        context={
            "user": user,
            "message": "Personal profile updated successfully."
        }
    )
