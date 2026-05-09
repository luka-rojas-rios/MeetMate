from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.event_participant import EventParticipant
from backend.models.feedback import Feedback
from backend.models.user import User

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


def get_current_user(request: Request, db: Session):
    user_id = request.session.get("user_id")

    if not user_id:
        return None

    return db.query(User).filter(User.id == user_id).first()


def normalize_rating(value, default=5):
    try:
        rating = int(value)
    except (TypeError, ValueError):
        rating = default

    if rating < 1:
        return 1

    if rating > 5:
        return 5

    return rating


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


def get_feedback_stats(db: Session):
    result = (
        db.query(
            func.avg(Feedback.university_rating).label("university_avg"),
            func.avg(Feedback.city_rating).label("city_avg"),
            func.avg(Feedback.overall_rating).label("overall_avg"),
            func.count(Feedback.id).label("total_feedback"),
        )
        .first()
    )

    return {
        "university_avg": round(float(result.university_avg), 1) if result and result.university_avg else None,
        "city_avg": round(float(result.city_avg), 1) if result and result.city_avg else None,
        "overall_avg": round(float(result.overall_avg), 1) if result and result.overall_avg else None,
        "total_feedback": result.total_feedback if result else 0,
    }


@router.get("/feedback")
def feedback_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    feedback = db.query(Feedback).filter(Feedback.user_id == user.id).first()
    has_used_app = user_has_used_app(user, db)

    return templates.TemplateResponse(
        request=request,
        name="feedback.html",
        context={
            "user": user,
            "feedback": feedback,
            "has_used_app": has_used_app,
            "can_leave_feedback": has_used_app,
            "error": None,
            "success": None,
        },
    )


@router.post("/feedback")
def save_feedback(
    request: Request,
    university_rating: int = Form(...),
    city_rating: int = Form(...),
    overall_rating: int = Form(...),
    comment: str = Form(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    has_used_app = user_has_used_app(user, db)

    if not has_used_app:
        feedback = db.query(Feedback).filter(Feedback.user_id == user.id).first()

        return templates.TemplateResponse(
            request=request,
            name="feedback.html",
            context={
                "user": user,
                "feedback": feedback,
                "has_used_app": False,
                "can_leave_feedback": False,
                "error": "You can only leave feedback after using the app: complete your profile, join an event, or create one.",
                "success": None,
            },
        )

    university_rating = normalize_rating(university_rating)
    city_rating = normalize_rating(city_rating)
    overall_rating = normalize_rating(overall_rating)

    existing_feedback = (
        db.query(Feedback)
        .filter(Feedback.user_id == user.id)
        .first()
    )

    if existing_feedback:
        existing_feedback.university_rating = university_rating
        existing_feedback.city_rating = city_rating
        existing_feedback.overall_rating = overall_rating
        existing_feedback.comment = comment
        existing_feedback.created_at = datetime.now().isoformat()
        feedback = existing_feedback
    else:
        feedback = Feedback(
            user_id=user.id,
            university_rating=university_rating,
            city_rating=city_rating,
            overall_rating=overall_rating,
            comment=comment,
            created_at=datetime.now().isoformat(),
        )
        db.add(feedback)

    db.commit()
    db.refresh(feedback)

    return templates.TemplateResponse(
        request=request,
        name="feedback.html",
        context={
            "user": user,
            "feedback": feedback,
            "has_used_app": True,
            "can_leave_feedback": True,
            "error": None,
            "success": "Thank you for sharing your experience.",
        },
    )


@router.get("/feedback/stats")
def feedback_stats(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    stats = get_feedback_stats(db)

    recent_feedback = (
        db.query(Feedback)
        .order_by(Feedback.id.desc())
        .limit(20)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="feedback_stats.html",
        context={
            "user": user,
            "stats": stats,
            "recent_feedback": recent_feedback,
        },
    )