from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.match import Match
from backend.models.user import User

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


SPANISH_REASON_TRANSLATIONS = {
    "Tenéis perfiles complementarios.": "You have complementary profiles.",
    "Compartís idioma o idiomas.": "You share one or more languages.",
    "Tu universidad de origen coincide con su universidad actual.": "Your home university matches their current university.",
    "Tu universidad actual coincide con su universidad de origen.": "Your current university matches their home university.",
    "Compartís algún deporte favorito.": "You share at least one favorite sport.",
    "Tenéis hobbies en común.": "You have hobbies in common.",
    "Ambos tenéis el perfil de matching completo.": "Both users have completed their matching profile.",
}


def get_current_user(request: Request, db: Session):
    user_id = request.session.get("user_id")

    if not user_id:
        return None

    return db.query(User).filter(User.id == user_id).first()


def clean(value):
    if not value:
        return ""

    return str(value).strip().lower()


def translate_match_reason_text(reason_text):
    if not reason_text:
        return reason_text

    translated_text = reason_text

    for spanish_text, english_text in SPANISH_REASON_TRANSLATIONS.items():
        translated_text = translated_text.replace(spanish_text, english_text)

    return translated_text


def prepare_match_for_display(match: Match):
    if match and match.match_reason:
        match.match_reason = translate_match_reason_text(match.match_reason)

    return match


def get_selected_language(language_value: str | None, other_language_value: str | None):
    if language_value == "Other":
        return other_language_value.strip() if other_language_value else "Other"

    return language_value


def has_match_profile(user: User):
    return bool(
        user
        and clean(user.user_type)
        and clean(user.language)
        and clean(user.home_university)
        and clean(user.exchange_university)
    )


def users_are_in_same_destination_university(user_a: User, user_b: User):
    return bool(
        user_a
        and user_b
        and clean(user_a.exchange_university)
        and clean(user_b.exchange_university)
        and clean(user_a.exchange_university) == clean(user_b.exchange_university)
    )


def get_other_user(match: Match, current_user: User):
    if match.student_id == current_user.id:
        return match.buddy

    return match.student


def get_existing_match_between_users(db: Session, user_a_id: int, user_b_id: int):
    return (
        db.query(Match)
        .filter(
            or_(
                and_(
                    Match.student_id == user_a_id,
                    Match.buddy_id == user_b_id,
                ),
                and_(
                    Match.student_id == user_b_id,
                    Match.buddy_id == user_a_id,
                ),
            )
        )
        .first()
    )


def get_accepted_matches_for_user(db: Session, user_id: int):
    return (
        db.query(Match)
        .filter(
            Match.status == "accepted",
            or_(
                Match.student_id == user_id,
                Match.buddy_id == user_id,
            ),
        )
        .order_by(Match.id.asc())
        .all()
    )


def get_accepted_match_for_user(db: Session, user_id: int, exclude_match_id: int | None = None):
    query = (
        db.query(Match)
        .filter(
            Match.status == "accepted",
            or_(
                Match.student_id == user_id,
                Match.buddy_id == user_id,
            ),
        )
    )

    if exclude_match_id:
        query = query.filter(Match.id != exclude_match_id)

    return query.order_by(Match.id.asc()).first()


def enforce_match_rules_for_user(db: Session, user: User):
    if not user:
        return None

    accepted_matches = get_accepted_matches_for_user(db, user.id)
    valid_matches = []
    changed = False
    now = datetime.now().isoformat()

    for match in accepted_matches:
        other_user = get_other_user(match, user)

        if not other_user:
            match.status = "rejected"
            match.responded_at = now
            changed = True
            continue

        if not users_are_in_same_destination_university(user, other_user):
            match.status = "rejected"
            match.responded_at = now
            changed = True
            continue

        valid_matches.append(match)

    if len(valid_matches) > 1:
        match_to_keep = valid_matches[0]

        for match in valid_matches[1:]:
            match.status = "rejected"
            match.responded_at = now
            changed = True

        if changed:
            db.commit()
            db.refresh(match_to_keep)

        return match_to_keep

    if changed:
        db.commit()

    if valid_matches:
        return valid_matches[0]

    return None


def calculate_match_score(current_user: User, candidate: User):
    score = 0
    reasons = []

    if users_are_in_same_destination_university(current_user, candidate):
        score += 4
        reasons.append("You are currently at the same destination university.")

    if clean(current_user.user_type) and clean(candidate.user_type):
        if clean(current_user.user_type) != clean(candidate.user_type):
            score += 3
            reasons.append("You have complementary profiles.")

    current_languages = {
        clean(current_user.language),
        clean(current_user.language_2),
    }

    candidate_languages = {
        clean(candidate.language),
        clean(candidate.language_2),
    }

    current_languages.discard("")
    candidate_languages.discard("")

    if current_languages.intersection(candidate_languages):
        score += 3
        reasons.append("You share one or more languages.")

    if clean(current_user.home_university) and clean(candidate.exchange_university):
        if clean(current_user.home_university) == clean(candidate.exchange_university):
            score += 2
            reasons.append("Your home university matches their current university.")

    if clean(current_user.exchange_university) and clean(candidate.home_university):
        if clean(current_user.exchange_university) == clean(candidate.home_university):
            score += 2
            reasons.append("Your current university matches their home university.")

    current_sports = {
        clean(current_user.favorite_sport_1),
        clean(current_user.favorite_sport_2),
    }

    candidate_sports = {
        clean(candidate.favorite_sport_1),
        clean(candidate.favorite_sport_2),
    }

    current_sports.discard("")
    candidate_sports.discard("")

    if current_sports.intersection(candidate_sports):
        score += 1
        reasons.append("You share at least one favorite sport.")

    current_hobbies = {
        clean(current_user.hobby_1),
        clean(current_user.hobby_2),
    }

    candidate_hobbies = {
        clean(candidate.hobby_1),
        clean(candidate.hobby_2),
    }

    current_hobbies.discard("")
    candidate_hobbies.discard("")

    if current_hobbies.intersection(candidate_hobbies):
        score += 1
        reasons.append("You have hobbies in common.")

    if score == 0:
        score = 1
        reasons.append("Both users have completed their matching profile.")

    return score, reasons


def create_pending_match(db: Session, current_user: User, candidate: User, score: int, reasons: list[str]):
    if not users_are_in_same_destination_university(current_user, candidate):
        return None

    if get_accepted_match_for_user(db, current_user.id):
        return None

    if get_accepted_match_for_user(db, candidate.id):
        return None

    existing_match = get_existing_match_between_users(db, current_user.id, candidate.id)

    if existing_match:
        return prepare_match_for_display(existing_match)

    reason_text = "\n".join(reasons)

    new_match = Match(
        student_id=current_user.id,
        buddy_id=candidate.id,
        requested_by=current_user.id,
        status="pending",
        compatibility_score=score,
        match_reason=reason_text,
        created_at=datetime.now().isoformat(),
        responded_at=None,
    )

    db.add(new_match)
    db.commit()
    db.refresh(new_match)

    return new_match


def reject_other_pending_matches_after_accept(db: Session, accepted_match: Match):
    now = datetime.now().isoformat()
    involved_user_ids = [
        accepted_match.student_id,
        accepted_match.buddy_id,
    ]

    other_pending_matches = (
        db.query(Match)
        .filter(
            Match.id != accepted_match.id,
            Match.status == "pending",
            or_(
                Match.student_id.in_(involved_user_ids),
                Match.buddy_id.in_(involved_user_ids),
            ),
        )
        .all()
    )

    for item in other_pending_matches:
        item.status = "rejected"
        item.responded_at = now

    db.commit()


def get_best_candidate(db: Session, current_user: User):
    candidates = db.query(User).filter(User.id != current_user.id).all()

    best_candidate = None
    best_score = -1
    best_reasons = []

    for candidate in candidates:
        if not has_match_profile(candidate):
            continue

        if not users_are_in_same_destination_university(current_user, candidate):
            continue

        if get_accepted_match_for_user(db, candidate.id):
            continue

        existing_match = get_existing_match_between_users(db, current_user.id, candidate.id)

        if existing_match:
            continue

        score, reasons = calculate_match_score(current_user, candidate)

        if score > best_score:
            best_candidate = candidate
            best_score = score
            best_reasons = reasons

    return best_candidate, best_score, best_reasons


@router.get("/match-profile")
def match_profile_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="match_profile.html",
        context={
            "user": user,
            "error": None,
            "success": None,
        },
    )


@router.post("/match-profile")
def save_match_profile(
    request: Request,
    user_type: str = Form(...),
    language: str = Form(...),
    language_other: str = Form(None),
    language_2: str = Form(None),
    language_2_other: str = Form(None),
    home_university: str = Form(...),
    exchange_university: str = Form(...),
    favorite_sport_1: str = Form(None),
    favorite_sport_2: str = Form(None),
    hobby_1: str = Form(None),
    hobby_2: str = Form(None),
    action: str = Form("save"),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    selected_language = get_selected_language(language, language_other)
    selected_language_2 = get_selected_language(language_2, language_2_other)

    user.user_type = user_type
    user.language = selected_language
    user.language_2 = selected_language_2
    user.home_university = home_university
    user.exchange_university = exchange_university
    user.favorite_sport_1 = favorite_sport_1
    user.favorite_sport_2 = favorite_sport_2
    user.hobby_1 = hobby_1
    user.hobby_2 = hobby_2

    db.commit()
    db.refresh(user)

    if action == "find_match":
        return RedirectResponse(url="/find-match", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="match_profile.html",
        context={
            "user": user,
            "error": None,
            "success": "Matching profile saved successfully.",
        },
    )


@router.get("/find-match")
def find_match(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    accepted_match = enforce_match_rules_for_user(db, user)

    if accepted_match:
        accepted_user = get_other_user(accepted_match, user)

        return templates.TemplateResponse(
            request=request,
            name="match_success.html",
            context={
                "user": user,
                "match_request": prepare_match_for_display(accepted_match),
                "match_user": accepted_user,
                "status_title": "You already have an accepted match",
                "status_message": "Only one accepted match is allowed. Once you have an accepted match, you cannot search for another one.",
                "reasons": [],
                "needs_profile": False,
            },
        )

    if not has_match_profile(user):
        return templates.TemplateResponse(
            request=request,
            name="match_success.html",
            context={
                "user": user,
                "match_request": None,
                "match_user": None,
                "status_title": "Incomplete matching profile",
                "status_message": "Before searching for a match, you need to complete and save your matching profile.",
                "reasons": [],
                "needs_profile": True,
            },
        )

    candidate, score, reasons = get_best_candidate(db, user)

    if not candidate:
        return templates.TemplateResponse(
            request=request,
            name="match_success.html",
            context={
                "user": user,
                "match_request": None,
                "match_user": None,
                "status_title": "No new matches available",
                "status_message": "No available users from your destination university were found. They may already be matched, or there may already be a previous request.",
                "reasons": [],
                "needs_profile": False,
            },
        )

    match_request = create_pending_match(
        db=db,
        current_user=user,
        candidate=candidate,
        score=score,
        reasons=reasons,
    )

    if not match_request:
        return templates.TemplateResponse(
            request=request,
            name="match_success.html",
            context={
                "user": user,
                "match_request": None,
                "match_user": None,
                "status_title": "No new matches available",
                "status_message": "No available users from your destination university were found.",
                "reasons": [],
                "needs_profile": False,
            },
        )

    return templates.TemplateResponse(
        request=request,
        name="match_success.html",
        context={
            "user": user,
            "match_request": prepare_match_for_display(match_request),
            "match_user": candidate,
            "status_title": "Match request sent",
            "status_message": "Your request will remain pending until the other person accepts or rejects it.",
            "reasons": reasons,
            "needs_profile": False,
        },
    )


@router.get("/my-matches")
def my_matches(
    request: Request,
    error: str = None,
    success: str = None,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    enforce_match_rules_for_user(db, user)

    matches = (
        db.query(Match)
        .filter(
            or_(
                Match.student_id == user.id,
                Match.buddy_id == user.id,
            )
        )
        .order_by(Match.id.desc())
        .all()
    )

    pending_received = []
    pending_sent = []
    accepted_matches = []
    rejected_matches = []

    for match in matches:
        prepare_match_for_display(match)
        other_user = get_other_user(match, user)

        if not other_user:
            continue

        item = {
            "match": match,
            "other_user": other_user,
        }

        if match.status == "pending" and match.requested_by != user.id:
            pending_received.append(item)
        elif match.status == "pending" and match.requested_by == user.id:
            pending_sent.append(item)
        elif match.status == "accepted":
            accepted_matches.append(item)
        elif match.status == "rejected":
            rejected_matches.append(item)

    return templates.TemplateResponse(
        request=request,
        name="my_matches.html",
        context={
            "user": user,
            "pending_received": pending_received,
            "pending_sent": pending_sent,
            "accepted_matches": accepted_matches,
            "rejected_matches": rejected_matches,
            "error": error,
            "success": success,
        },
    )


@router.post("/matches/{match_id}/accept")
def accept_match(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    enforce_match_rules_for_user(db, user)

    match = (
        db.query(Match)
        .filter(
            Match.id == match_id,
            or_(
                Match.student_id == user.id,
                Match.buddy_id == user.id,
            ),
        )
        .first()
    )

    if not match:
        return RedirectResponse(url="/my-matches?error=The request does not exist.", status_code=303)

    if match.status != "pending":
        return RedirectResponse(url="/my-matches?error=This request is no longer pending.", status_code=303)

    if match.requested_by == user.id:
        return RedirectResponse(url="/my-matches?error=You cannot accept a request that you sent.", status_code=303)

    other_user = get_other_user(match, user)

    if not other_user:
        return RedirectResponse(url="/my-matches?error=The other user does not exist.", status_code=303)

    enforce_match_rules_for_user(db, other_user)

    if not users_are_in_same_destination_university(user, other_user):
        return RedirectResponse(
            url="/my-matches?error=You can only accept matches with users from your destination university.",
            status_code=303,
        )

    if get_accepted_match_for_user(db, user.id, exclude_match_id=match.id):
        return RedirectResponse(
            url="/my-matches?error=You already have an accepted match. You cannot accept another one.",
            status_code=303,
        )

    if get_accepted_match_for_user(db, other_user.id, exclude_match_id=match.id):
        return RedirectResponse(
            url="/my-matches?error=The other person already has an accepted match.",
            status_code=303,
        )

    match.status = "accepted"
    match.responded_at = datetime.now().isoformat()

    db.commit()
    db.refresh(match)

    reject_other_pending_matches_after_accept(db, match)

    return RedirectResponse(url="/my-matches?success=Match accepted successfully.", status_code=303)


@router.post("/matches/{match_id}/reject")
def reject_match(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    match = (
        db.query(Match)
        .filter(
            Match.id == match_id,
            or_(
                Match.student_id == user.id,
                Match.buddy_id == user.id,
            ),
        )
        .first()
    )

    if not match:
        return RedirectResponse(url="/my-matches?error=The request does not exist.", status_code=303)

    if match.requested_by == user.id:
        return RedirectResponse(url="/my-matches?error=You cannot reject a request that you sent.", status_code=303)

    match.status = "rejected"
    match.responded_at = datetime.now().isoformat()

    db.commit()

    return RedirectResponse(url="/my-matches?success=Request rejected.", status_code=303)


@router.get("/matches/{match_id}")
def matched_profile(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    enforce_match_rules_for_user(db, user)

    match = (
        db.query(Match)
        .filter(
            Match.id == match_id,
            or_(
                Match.student_id == user.id,
                Match.buddy_id == user.id,
            ),
        )
        .first()
    )

    if not match:
        return RedirectResponse(url="/my-matches", status_code=303)

    matched_user = get_other_user(match, user)

    if not matched_user:
        return RedirectResponse(url="/my-matches", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="matched_profile.html",
        context={
            "user": user,
            "matched_user": matched_user,
            "match": prepare_match_for_display(match),
        },
    )