from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from backend.database import SessionLocal
from backend.models.event import Event
from backend.models.event_participant import EventParticipant
from backend.models.user import User

router = APIRouter()
templates = Jinja2Templates(directory="backend/templates")


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


def build_events_context(request: Request, db: Session, user: User, message=None, error=None, editing_event_id=None):
    events = (
        db.query(Event)
        .options(
            joinedload(Event.creator),
            joinedload(Event.participants).joinedload(EventParticipant.user),
        )
        .order_by(Event.date.asc(), Event.id.desc())
        .all()
    )

    event_cards = []
    for event in events:
        participant_ids = [participant.user_id for participant in event.participants]
        participant_names = [participant.user.username for participant in event.participants if participant.user]
        event_cards.append(
            {
                "id": event.id,
                "name": event.name,
                "description": event.description,
                "date": event.date,
                "location": event.location,
                "creator_name": event.creator.username if event.creator else "Unknown user",
                "is_owner": user.id == event.created_by,
                "is_joined": user.id in participant_ids,
                "participants_count": len(participant_ids),
                "participants_names": participant_names,
            }
        )

    featured_events = event_cards[:3]
    return {
        "request": request,
        "user": user,
        "events": event_cards,
        "featured_events": featured_events,
        "message": message,
        "error": error,
        "editing_event_id": editing_event_id,
    }


@router.get("/events", response_class=HTMLResponse)
def events_page(request: Request, db: Session = Depends(get_db)):
    user = get_logged_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="events.html",
        context=build_events_context(request, db, user),
    )


@router.post("/events", response_class=HTMLResponse)
def create_event(
    request: Request,
    name: str = Form(""),
    description: str = Form(""),
    date: str = Form(""),
    location: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_logged_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=302)

    name = name.strip()
    description = description.strip()
    date = date.strip()
    location = location.strip()

    if not all([name, description, date, location]):
        return templates.TemplateResponse(
            request=request,
            name="events.html",
            context=build_events_context(
                request,
                db,
                user,
                error="All fields are required to create an event.",
            ),
        )

    event = Event(
        name=name,
        description=description,
        date=date,
        location=location,
        created_by=user.id,
    )
    db.add(event)
    db.commit()

    return templates.TemplateResponse(
        request=request,
        name="events.html",
        context=build_events_context(
            request,
            db,
            user,
            message="Event created successfully.",
        ),
    )


@router.post("/events/{event_id}/join", response_class=HTMLResponse)
def join_event(event_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_logged_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=302)

    event = db.query(Event).filter_by(id=event_id).first()
    if not event:
        return templates.TemplateResponse(
            request=request,
            name="events.html",
            context=build_events_context(request, db, user, error="Event not found."),
        )

    existing_participation = db.query(EventParticipant).filter_by(event_id=event_id, user_id=user.id).first()
    if existing_participation:
        return templates.TemplateResponse(
            request=request,
            name="events.html",
            context=build_events_context(request, db, user, message="You are already registered for this event."),
        )

    db.add(EventParticipant(event_id=event_id, user_id=user.id))
    db.commit()

    return templates.TemplateResponse(
        request=request,
        name="events.html",
        context=build_events_context(request, db, user, message="You have joined the event."),
    )


@router.post("/events/{event_id}/leave", response_class=HTMLResponse)
def leave_event(event_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_logged_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=302)

    participation = db.query(EventParticipant).filter_by(event_id=event_id, user_id=user.id).first()
    if participation:
        db.delete(participation)
        db.commit()
        message = "You have left the event."
    else:
        message = "You were not registered for this event."

    return templates.TemplateResponse(
        request=request,
        name="events.html",
        context=build_events_context(request, db, user, message=message),
    )


@router.post("/events/{event_id}/edit", response_class=HTMLResponse)
def edit_event(
    event_id: int,
    request: Request,
    name: str = Form(""),
    description: str = Form(""),
    date: str = Form(""),
    location: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_logged_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=302)

    event = db.query(Event).filter_by(id=event_id).first()
    if not event:
        return templates.TemplateResponse(
            request=request,
            name="events.html",
            context=build_events_context(request, db, user, error="Event not found."),
        )

    if event.created_by != user.id:
        return templates.TemplateResponse(
            request=request,
            name="events.html",
            context=build_events_context(request, db, user, error="Only the creator can edit this event."),
        )

    name = name.strip()
    description = description.strip()
    date = date.strip()
    location = location.strip()
    if not all([name, description, date, location]):
        return templates.TemplateResponse(
            request=request,
            name="events.html",
            context=build_events_context(
                request,
                db,
                user,
                error="All fields are required to edit an event.",
                editing_event_id=event_id,
            ),
        )

    event.name = name
    event.description = description
    event.date = date
    event.location = location
    db.commit()

    return templates.TemplateResponse(
        request=request,
        name="events.html",
        context=build_events_context(request, db, user, message="Event updated successfully."),
    )


@router.post("/events/{event_id}/delete", response_class=HTMLResponse)
def delete_event(event_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_logged_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=302)

    event = db.query(Event).filter_by(id=event_id).first()
    if not event:
        return templates.TemplateResponse(
            request=request,
            name="events.html",
            context=build_events_context(request, db, user, error="Event not found."),
        )

    if event.created_by != user.id:
        return templates.TemplateResponse(
            request=request,
            name="events.html",
            context=build_events_context(request, db, user, error="Only the creator can delete this event."),
        )

    db.delete(event)
    db.commit()

    return templates.TemplateResponse(
        request=request,
        name="events.html",
        context=build_events_context(request, db, user, message="Event deleted successfully."),
    )
