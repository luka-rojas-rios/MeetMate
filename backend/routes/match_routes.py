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

MIN_COMPATIBILITY_SCORE = 50
MAX_SUGGESTIONS = 3
MATCH_ACTIVE_STATUSES = {"pending", "accepted"}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_logged_user(request: Request, db: Session):
    username = request.session.get("username")
    if not username:
        return None
    return db.query(User).filter_by(username=username).first()


def get_profile_values(user: User):
    languages = {value for value in [user.language, user.language_2] if value}
    hobbies = {value for value in [user.hobby_1, user.hobby_2] if value}
    sports = {value for value in [user.favorite_sport_1, user.favorite_sport_2] if value}
    university = user.exchange_university or user.home_university
    return languages, hobbies, sports, university


def is_profile_complete(user: User):
    languages, hobbies, sports, university = get_profile_values(user)
    required = [user.user_type, user.language, university]
    return all(required) and bool(hobbies) and bool(sports) and len(languages) >= 1


def get_profile_completion_bonus(user: User):
    fields = [
        user.first_name,
        user.last_name,
        user.birth_date,
        user.sex,
        user.nationality,
        user.phone,
        user.user_type,
        user.language,
        user.language_2,
        user.favorite_sport_1,
        user.favorite_sport_2,
        user.hobby_1,
        user.hobby_2,
        user.home_university or user.exchange_university,
    ]
    filled_fields = sum(1 for value in fields if value)

    if filled_fields >= 12:
        return 10
    if filled_fields >= 9:
        return 5
    return 0


def get_opposite_user_type(user_type: str):
    if user_type == "exchange":
        return "local"
    if user_type == "local":
        return "exchange"
    return None


def build_match_context(match: Match, user: User):
    other_user = match.buddy if match.student_id == user.id else match.student
    reasons = [reason for reason in (match.match_reason or "").split("|") if reason]

    return {
        "current_match": match,
        "current_match_user": other_user,
        "current_match_reasons": reasons,
        "current_match_status": match.status,
        "current_match_score": match.compatibility_score,
    }


def get_user_current_match(user: User, db: Session):
    return (
        db.query(Match)
        .filter(
            or_(Match.student_id == user.id, Match.buddy_id == user.id),
            Match.status.in_(tuple(MATCH_ACTIVE_STATUSES)),
        )
        .order_by(Match.id.desc())
        .first()
    )


def has_existing_pair(user_id: int, candidate_id: int, db: Session):
    return (
        db.query(Match)
        .filter(
            or_(
                and_(Match.student_id == user_id, Match.buddy_id == candidate_id),
                and_(Match.student_id == candidate_id, Match.buddy_id == user_id),
            )
        )
        .first()
        is not None
    )


def score_candidate(user: User, candidate: User):
    user_languages, user_hobbies, user_sports, user_university = get_profile_values(user)
    candidate_languages, candidate_hobbies, candidate_sports, candidate_university = get_profile_values(candidate)

    if not user_university or not candidate_university:
        return None

    # MISMA UNIVERSIDAD OBLIGATORIA
    if candidate_university != user_university:
        return None

    shared_languages = sorted(user_languages & candidate_languages)
    shared_hobbies = sorted(user_hobbies & candidate_hobbies)
    shared_sports = sorted(user_sports & candidate_sports)

    score = 40
    reasons = [f"Same university: {user_university} (+40)"]

    if shared_languages:
        language_points = len(shared_languages) * 20
        score += language_points
        reasons.append(f"Shared languages: {', '.join(shared_languages)} (+{language_points})")

    if shared_hobbies:
        hobby_points = len(shared_hobbies) * 10
        score += hobby_points
        reasons.append(f"Shared hobbies: {', '.join(shared_hobbies)} (+{hobby_points})")

    if shared_sports:
        sports_points = len(shared_sports) * 8
        score += sports_points
        reasons.append(f"Shared sports: {', '.join(shared_sports)} (+{sports_points})")

    completion_bonus = get_profile_completion_bonus(candidate)
    if completion_bonus:
        score += completion_bonus
        reasons.append(f"Complete profile bonus (+{completion_bonus})")

    return {
        "candidate": candidate,
        "score": score,
        "reasons": reasons,
    }


def find_best_matches(user: User, db: Session, limit: int = MAX_SUGGESTIONS):
    if user.user_type not in USER_TYPES:
        return [], "Choose whether you are a local or exchange student first."

    if not is_profile_complete(user):
        return [], "Complete your profile with university, languages, hobbies and sports before requesting a match."

    _, _, _, user_university = get_profile_values(user)
    target_user_type = get_opposite_user_type(user.user_type)

    if not target_user_type:
        return [], "Invalid student type."

    candidates = (
        db.query(User)
        .filter(
            User.id != user.id,
            User.user_type == target_user_type,
            or_(
                User.home_university == user_university,
                User.exchange_university == user_university,
            ),
        )
        .all()
    )

    ranked_candidates = []

    for candidate in candidates:
        if not is_profile_complete(candidate):
            continue

        # Evita repetir parejas antiguas
        if has_existing_pair(user.id, candidate.id, db):
            continue

        result = score_candidate(user, candidate)
        if not result:
            continue

        if result["score"] < MIN_COMPATIBILITY_SCORE:
            continue

        ranked_candidates.append(result)

    ranked_candidates.sort(key=lambda item: item["score"], reverse=True)

    if not ranked_candidates:
        return [], "We have not found a sufficiently compatible match in your university yet."

    return ranked_candidates[:limit], None


def create_match_record(user: User, candidate_result: dict, db: Session):
    matched_user = candidate_result["candidate"]

    # student_id = exchange / buddy_id = local
    if user.user_type == "exchange":
        student_id = user.id
        buddy_id = matched_user.id
    else:
        student_id = matched_user.id
        buddy_id = user.id

    existing = (
        db.query(Match)
        .filter(
            or_(
                and_(Match.student_id == student_id, Match.buddy_id == buddy_id),
                and_(Match.student_id == buddy_id, Match.buddy_id == student_id),
            )
        )
        .first()
    )
    if existing:
        return existing

    match = Match(
        student_id=student_id,
        buddy_id=buddy_id,
        requested_by=user.id,
        created_at=datetime.utcnow().isoformat(),
        status="pending",
        compatibility_score=candidate_result["score"],
        match_reason="|".join(candidate_result["reasons"]),
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def render_profile_form(request: Request, user: User | None = None, db: Session | None = None, **extra_context):
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

    if user and db:
        current_match = get_user_current_match(user, db)
        if current_match:
            context.update(build_match_context(current_match, user))

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
    user = get_logged_user(request, db)
    if not user:
        return render_profile_form(request, error="Sign in to edit your profile.")

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
        return render_profile_form(
            request,
            user=temp_user,
            db=db,
            error=validation_error,
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

    current_match = get_user_current_match(user, db)
    if current_match:
        return render_profile_form(
            request,
            user=user,
            db=db,
            message=f"Profile updated successfully. You already have a {current_match.status} match.",
        )

    ranked_candidates, error_message = find_best_matches(user, db)

    if not ranked_candidates:
        return render_profile_form(
            request,
            user=user,
            db=db,
            message=f"Profile updated successfully. {error_message}",
        )

    best_candidate = ranked_candidates[0]
    current_match = create_match_record(user, best_candidate, db)
    match_context = build_match_context(current_match, user)

    alternative_matches = []
    for candidate_result in ranked_candidates[1:]:
        alternative_matches.append(
            {
                "username": candidate_result["candidate"].username,
                "score": candidate_result["score"],
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="match_success.html",
        context={
            "request": request,
            "matched_user": match_context["current_match_user"],
            "message": "Profile updated successfully. We found a compatible student from your university.",
            "match_status": match_context["current_match_status"],
            "match_score": match_context["current_match_score"],
            "match_reasons": match_context["current_match_reasons"],
            "current_match": current_match,
            "alternative_matches": alternative_matches,
        },
    )


@router.get("/match-profile", response_class=HTMLResponse)
def match_profile(request: Request, db: Session = Depends(get_db)):
    user = get_logged_user(request, db)
    if not user:
        return render_profile_form(request, error="Sign in")

    return render_profile_form(
        request,
        user=user,
        db=db,
        message="Complete or update your profile to improve your matching results.",
    )


def get_match_for_logged_user(match_id: int, request: Request, db: Session):
    user = get_logged_user(request, db)
    if not user:
        return None, None

    match = (
        db.query(Match)
        .filter(
            Match.id == match_id,
            or_(Match.student_id == user.id, Match.buddy_id == user.id),
        )
        .first()
    )
    return user, match


@router.post("/matches/{match_id}/accept", response_class=HTMLResponse)
def accept_match(match_id: int, request: Request, db: Session = Depends(get_db)):
    user, match = get_match_for_logged_user(match_id, request, db)
    if not user or not match:
        return RedirectResponse(url="/match-profile", status_code=302)

    if match.status != "pending":
        return render_profile_form(request, user=user, db=db, message=f"This match is already {match.status}.")

    match.status = "accepted"
    match.responded_at = datetime.utcnow().isoformat()
    db.commit()
    db.refresh(match)

    match_context = build_match_context(match, user)
    return templates.TemplateResponse(
        request=request,
        name="match_success.html",
        context={
            "request": request,
            "matched_user": match_context["current_match_user"],
            "message": "You accepted the match.",
            "match_status": match_context["current_match_status"],
            "match_score": match_context["current_match_score"],
            "match_reasons": match_context["current_match_reasons"],
            "current_match": match,
            "alternative_matches": [],
        },
    )


@router.post("/matches/{match_id}/reject", response_class=HTMLResponse)
def reject_match(match_id: int, request: Request, db: Session = Depends(get_db)):
    user, match = get_match_for_logged_user(match_id, request, db)
    if not user or not match:
        return RedirectResponse(url="/match-profile", status_code=302)

    if match.status != "pending":
        return render_profile_form(request, user=user, db=db, message=f"This match is already {match.status}.")

    match.status = "rejected"
    match.responded_at = datetime.utcnow().isoformat()
    db.commit()

    ranked_candidates, error_message = find_best_matches(user, db)
    if ranked_candidates:
        new_match = create_match_record(user, ranked_candidates[0], db)
        new_match_context = build_match_context(new_match, user)

        return templates.TemplateResponse(
            request=request,
            name="match_success.html",
            context={
                "request": request,
                "matched_user": new_match_context["current_match_user"],
                "message": "Previous match rejected. We found a new compatible student.",
                "match_status": new_match_context["current_match_status"],
                "match_score": new_match_context["current_match_score"],
                "match_reasons": new_match_context["current_match_reasons"],
                "current_match": new_match,
                "alternative_matches": [],
            },
        )

    return render_profile_form(
        request,
        user=user,
        db=db,
        message=f"Match rejected. {error_message}",
    )


@router.post("/matches/{match_id}/cancel", response_class=HTMLResponse)
def cancel_match(match_id: int, request: Request, db: Session = Depends(get_db)):
    user, match = get_match_for_logged_user(match_id, request, db)
    if not user or not match:
        return RedirectResponse(url="/match-profile", status_code=302)

    if match.status != "accepted":
        return render_profile_form(request, user=user, db=db, message="Only accepted matches can be cancelled.")

    match.status = "cancelled"
    match.responded_at = datetime.utcnow().isoformat()
    db.commit()

    return render_profile_form(
        request,
        user=user,
        db=db,
        message="Match cancelled successfully.",
    )


@router.post("/matches/{match_id}/complete", response_class=HTMLResponse)
def complete_match(match_id: int, request: Request, db: Session = Depends(get_db)):
    user, match = get_match_for_logged_user(match_id, request, db)
    if not user or not match:
        return RedirectResponse(url="/match-profile", status_code=302)

    if match.status != "accepted":
        return render_profile_form(request, user=user, db=db, message="Only accepted matches can be marked as completed.")

    match.status = "completed"
    match.responded_at = datetime.utcnow().isoformat()
    db.commit()

    return render_profile_form(
        request,
        user=user,
        db=db,
        message="Match marked as completed.",
    )


@router.get("/edit-profile", response_class=HTMLResponse)
def edit_profile(request: Request, db: Session = Depends(get_db)):
    user = get_logged_user(request, db)
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
    user = get_logged_user(request, db)
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