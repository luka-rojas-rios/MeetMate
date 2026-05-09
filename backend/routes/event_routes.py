from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models.event import Event
from backend.models.event_participant import EventParticipant
from backend.models.user import User

try:
    from backend.models.event_review import EventReview
except ImportError:
    EventReview = None


router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


EVENT_CATEGORIES = [
    "General",
    "Sports",
    "Culture",
    "Party",
    "Food",
    "University",
    "Trips",
    "Study",
    "Languages",
]


CATEGORY_ALIASES = {
    "General": ["General"],
    "Sports": ["Sports", "Sport", "Deporte", "Deportes"],
    "Culture": ["Culture", "Cultura"],
    "Party": ["Party", "Fiesta"],
    "Food": ["Food", "Comida"],
    "University": ["University", "Universidad"],
    "Trips": ["Trips", "Trip", "Travel", "Travels", "Viajes", "Viaje"],
    "Study": ["Study", "Studies", "Estudio", "Estudios"],
    "Languages": ["Languages", "Language", "Idiomas", "Idioma"],
}


def get_current_user(request: Request, db: Session):
    user_id = request.session.get("user_id")

    if not user_id:
        return None

    return db.query(User).filter(User.id == user_id).first()


def today_iso():
    return date.today().isoformat()


def normalize_date(value):
    if not value:
        return ""

    if isinstance(value, date):
        return value.isoformat()

    return str(value)


def normalize_category(category):
    if not category:
        return "General"

    category = str(category).strip()

    spanish_to_english = {
        "Deporte": "Sports",
        "Deportes": "Sports",
        "Cultura": "Culture",
        "Fiesta": "Party",
        "Comida": "Food",
        "Universidad": "University",
        "Viajes": "Trips",
        "Viaje": "Trips",
        "Travel": "Trips",
        "Travels": "Trips",
        "Estudio": "Study",
        "Estudios": "Study",
        "Idiomas": "Languages",
        "Idioma": "Languages",
    }

    if category in EVENT_CATEGORIES:
        return category

    return spanish_to_english.get(category, "General")


def get_category_filter_values(category):
    if not category:
        return []

    normalized_category = normalize_category(category)
    values = CATEGORY_ALIASES.get(normalized_category, [normalized_category])

    return [value.strip().lower() for value in values]


def is_event_expired(event: Event):
    return normalize_date(event.date) < today_iso()


def parse_event_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_max_participants(value):
    if value is None or value == "":
        return None

    try:
        number = int(value)
    except ValueError:
        return None

    if number <= 0:
        return None

    return number


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


def is_event_full(event: Event):
    max_participants = getattr(event, "max_participants", None)

    if not max_participants:
        return False

    return len(event.participants) >= max_participants


def user_is_participant(event: Event, user: User):
    if not user:
        return False

    return any(participant.user_id == user.id for participant in event.participants)


def user_has_reviewed_event(event: Event, user: User, db: Session):
    if not user or EventReview is None:
        return False

    return (
        db.query(EventReview)
        .filter(
            EventReview.event_id == event.id,
            EventReview.user_id == user.id,
        )
        .first()
        is not None
    )


def creator_reliability_label(average):
    if average is None:
        return "No reviews yet"

    if average >= 4.5:
        return "Very reliable"

    if average >= 3.5:
        return "Reliable"

    if average >= 2.5:
        return "Needs improvement"

    return "Low reliability"


def creator_rating_stats(db: Session, creator_id: int):
    if EventReview is None:
        return {
            "average": None,
            "count": 0,
            "label": "No reviews yet",
        }

    result = (
        db.query(
            func.avg(EventReview.creator_rating).label("average"),
            func.count(EventReview.id).label("count"),
        )
        .join(Event, EventReview.event_id == Event.id)
        .filter(
            Event.created_by == creator_id,
            EventReview.creator_rating.isnot(None),
            EventReview.user_id != creator_id,
        )
        .first()
    )

    average = result.average if result and result.average is not None else None
    count = result.count if result else 0

    return {
        "average": round(float(average), 1) if average is not None else None,
        "count": count or 0,
        "label": creator_reliability_label(average),
    }


def participant_user_list(event: Event):
    users = []

    for participant in event.participants:
        if participant.user:
            users.append(participant.user)

    return users


def event_to_view_model(event: Event, user: User, db: Session):
    participants_count = len(event.participants)
    creator_stats = creator_rating_stats(db, event.created_by)
    is_creator = user and event.created_by == user.id
    is_participant = user_is_participant(event, user)
    expired = is_event_expired(event)
    max_participants = getattr(event, "max_participants", None)
    category = getattr(event, "category", None)

    return {
        "id": event.id,
        "name": event.name,
        "description": event.description,
        "date": normalize_date(event.date),
        "location": event.location,
        "category": normalize_category(category),
        "max_participants": max_participants,
        "created_by": event.created_by,
        "creator": event.creator,
        "creator_stats": creator_stats,
        "participants": event.participants,
        "registered_users": participant_user_list(event),
        "participants_count": participants_count,
        "spots_left": (
            max_participants - participants_count
            if max_participants
            else None
        ),
        "is_expired": expired,
        "is_full": is_event_full(event),
        "is_participant": is_participant,
        "is_creator": is_creator,
        "has_reviewed": user_has_reviewed_event(event, user, db),
        "can_review": (
            expired
            and user
            and is_participant
            and not is_creator
            and EventReview is not None
        ),
    }


@router.get("/events")
def events_page(
    request: Request,
    q: str = "",
    category: str = "",
    view: str = "upcoming",
    error: str = None,
    success: str = None,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    today = today_iso()
    event_date_as_text = cast(Event.date, String)

    query = (
        db.query(Event)
        .options(
            joinedload(Event.creator),
            joinedload(Event.participants).joinedload(EventParticipant.user),
        )
    )

    if view == "history":
        query = query.filter(event_date_as_text < today)
    elif view == "mine":
        query = (
            query
            .outerjoin(EventParticipant, EventParticipant.event_id == Event.id)
            .filter(
                or_(
                    Event.created_by == user.id,
                    EventParticipant.user_id == user.id,
                )
            )
            .distinct()
        )
    else:
        query = query.filter(event_date_as_text >= today)

    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                Event.name.ilike(search),
                Event.description.ilike(search),
                Event.location.ilike(search),
            )
        )

    if category and hasattr(Event, "category"):
        valid_categories = get_category_filter_values(category)

        query = query.filter(
            func.lower(func.trim(Event.category)).in_(valid_categories)
        )

    events = query.order_by(event_date_as_text.asc()).all()
    event_cards = [event_to_view_model(event, user, db) for event in events]

    upcoming_joined_events = (
        db.query(Event)
        .join(EventParticipant, EventParticipant.event_id == Event.id)
        .filter(
            EventParticipant.user_id == user.id,
            event_date_as_text >= today,
        )
        .order_by(event_date_as_text.asc())
        .limit(3)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="events.html",
        context={
            "user": user,
            "events": event_cards,
            "categories": EVENT_CATEGORIES,
            "selected_category": normalize_category(category) if category else "",
            "selected_view": view,
            "search_query": q,
            "today": today,
            "upcoming_joined_events": upcoming_joined_events,
            "error": error,
            "success": success,
        },
    )


@router.post("/events/create")
def create_event(
    request: Request,
    name: str = Form(...),
    description: str = Form(...),
    event_date: str = Form(...),
    location: str = Form(...),
    category: str = Form("General"),
    max_participants: str = Form(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    parsed_date = parse_event_date(event_date)

    if parsed_date < date.today():
        return RedirectResponse(
            url="/events?error=You cannot create an event in the past.",
            status_code=303,
        )

    event = Event(
        name=name,
        description=description,
        date=parsed_date.isoformat(),
        location=location,
        created_by=user.id,
    )

    if hasattr(Event, "category"):
        event.category = normalize_category(category)

    if hasattr(Event, "max_participants"):
        event.max_participants = parse_max_participants(max_participants)

    db.add(event)
    db.commit()

    return RedirectResponse(
        url="/events?success=Event created successfully.",
        status_code=303,
    )


@router.post("/events/{event_id}/join")
def join_event(event_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        return RedirectResponse(url="/events?error=The event does not exist.", status_code=303)

    if is_event_expired(event):
        return RedirectResponse(
            url="/events?error=This event has already expired and you cannot join it.",
            status_code=303,
        )

    if event.created_by == user.id:
        return RedirectResponse(
            url="/events?error=You cannot join an event that you created.",
            status_code=303,
        )

    if user_is_participant(event, user):
        return RedirectResponse(
            url="/events?error=You have already joined this event.",
            status_code=303,
        )

    if is_event_full(event):
        return RedirectResponse(
            url="/events?error=This event is already full.",
            status_code=303,
        )

    participant = EventParticipant(
        event_id=event.id,
        user_id=user.id,
    )

    db.add(participant)
    db.commit()

    return RedirectResponse(
        url="/events?success=You have joined the event.",
        status_code=303,
    )


@router.post("/events/{event_id}/leave")
def leave_event(event_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        return RedirectResponse(url="/events?error=The event does not exist.", status_code=303)

    if is_event_expired(event):
        return RedirectResponse(
            url="/events?error=This event has already expired and you cannot leave it.",
            status_code=303,
        )

    participant = (
        db.query(EventParticipant)
        .filter(
            EventParticipant.event_id == event.id,
            EventParticipant.user_id == user.id,
        )
        .first()
    )

    if participant:
        db.delete(participant)
        db.commit()

    return RedirectResponse(
        url="/events?success=You have left the event.",
        status_code=303,
    )


@router.post("/events/{event_id}/delete")
def delete_event(event_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        return RedirectResponse(url="/events?error=The event does not exist.", status_code=303)

    if event.created_by != user.id:
        return RedirectResponse(
            url="/events?error=You cannot delete an event that you did not create.",
            status_code=303,
        )

    if is_event_expired(event):
        return RedirectResponse(
            url="/events?error=This event has already expired and cannot be deleted.",
            status_code=303,
        )

    db.delete(event)
    db.commit()

    return RedirectResponse(
        url="/events?success=Event deleted successfully.",
        status_code=303,
    )


@router.post("/events/{event_id}/edit")
def edit_event(
    event_id: int,
    request: Request,
    name: str = Form(...),
    description: str = Form(...),
    event_date: str = Form(...),
    location: str = Form(...),
    category: str = Form("General"),
    max_participants: str = Form(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        return RedirectResponse(url="/events?error=The event does not exist.", status_code=303)

    if event.created_by != user.id:
        return RedirectResponse(
            url="/events?error=You cannot edit an event that you did not create.",
            status_code=303,
        )

    if is_event_expired(event):
        return RedirectResponse(
            url="/events?error=This event has already expired and cannot be edited.",
            status_code=303,
        )

    parsed_date = parse_event_date(event_date)

    if parsed_date < date.today():
        return RedirectResponse(
            url="/events?error=You cannot change an event to a past date.",
            status_code=303,
        )

    parsed_max_participants = parse_max_participants(max_participants)

    if parsed_max_participants and parsed_max_participants < len(event.participants):
        return RedirectResponse(
            url="/events?error=The participant limit cannot be lower than the current number of participants.",
            status_code=303,
        )

    event.name = name
    event.description = description
    event.date = parsed_date.isoformat()
    event.location = location

    if hasattr(Event, "category"):
        event.category = normalize_category(category)

    if hasattr(Event, "max_participants"):
        event.max_participants = parsed_max_participants

    db.commit()

    return RedirectResponse(
        url="/events?success=Event updated successfully.",
        status_code=303,
    )


@router.post("/events/{event_id}/review")
def review_event(
    event_id: int,
    request: Request,
    rating: int = Form(...),
    comment: str = Form(None),
    creator_rating: int = Form(None),
    creator_comment: str = Form(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if EventReview is None:
        return RedirectResponse(
            url="/events?view=history&error=Reviews are not available.",
            status_code=303,
        )

    event = db.query(Event).filter(Event.id == event_id).first()

    if not event:
        return RedirectResponse(
            url="/events?view=history&error=The event does not exist.",
            status_code=303,
        )

    if not is_event_expired(event):
        return RedirectResponse(
            url="/events?error=You can only review events that have already passed.",
            status_code=303,
        )

    if event.created_by == user.id:
        return RedirectResponse(
            url="/events?view=history&error=You cannot review your own event or rate yourself as organizer.",
            status_code=303,
        )

    if not user_is_participant(event, user):
        return RedirectResponse(
            url="/events?view=history&error=You can only review events that you joined.",
            status_code=303,
        )

    rating = normalize_rating(rating)
    creator_rating = normalize_rating(creator_rating)

    existing_review = (
        db.query(EventReview)
        .filter(
            EventReview.event_id == event.id,
            EventReview.user_id == user.id,
        )
        .first()
    )

    if existing_review:
        existing_review.rating = rating
        existing_review.comment = comment
        existing_review.creator_rating = creator_rating
        existing_review.creator_comment = creator_comment
        existing_review.created_at = datetime.now().isoformat()
    else:
        review = EventReview(
            event_id=event.id,
            user_id=user.id,
            rating=rating,
            comment=comment,
            creator_rating=creator_rating,
            creator_comment=creator_comment,
            created_at=datetime.now().isoformat(),
        )
        db.add(review)

    db.commit()

    return RedirectResponse(
        url="/events?view=history&success=Review saved successfully.",
        status_code=303,
    )


@router.get("/event-creators/{creator_id}")
def event_creator_profile(
    creator_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    creator = db.query(User).filter(User.id == creator_id).first()

    if not creator:
        return RedirectResponse(url="/events?error=The organizer does not exist.", status_code=303)

    stats = creator_rating_stats(db, creator.id)

    creator_reviews = []

    if EventReview is not None:
        creator_reviews = (
            db.query(EventReview)
            .join(Event, EventReview.event_id == Event.id)
            .filter(
                Event.created_by == creator.id,
                EventReview.creator_rating.isnot(None),
                EventReview.user_id != creator.id,
            )
            .order_by(EventReview.id.desc())
            .limit(20)
            .all()
        )

    created_events = (
        db.query(Event)
        .filter(Event.created_by == creator.id)
        .order_by(cast(Event.date, String).desc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="event_creator_profile.html",
        context={
            "user": user,
            "creator": creator,
            "stats": stats,
            "creator_reviews": creator_reviews,
            "created_events": created_events,
        },
    )