from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.feedback import Feedback

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


@router.get("/feedback")
def feedback_page(request: Request, db: Session = Depends(get_db)):
    success = request.query_params.get("success")
    error = request.query_params.get("error")

    return templates.TemplateResponse(
        "feedback.html",
        {
            "request": request,
            "success": success,
            "error": error,
        },
    )


@router.post("/feedback")
def submit_feedback(
    request: Request,
    university_rating: int = Form(...),
    city_rating: int = Form(...),
    overall_rating: int = Form(...),
    comment: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        # Si ya usas sesión en login, cambia esto para coger el usuario real.
        user_id = request.session.get("user_id")

        if not user_id:
            return RedirectResponse(url="/feedback?error=You must be logged in", status_code=303)

        if not (1 <= university_rating <= 5 and 1 <= city_rating <= 5 and 1 <= overall_rating <= 5):
            return RedirectResponse(url="/feedback?error=Ratings must be between 1 and 5", status_code=303)

        new_feedback = Feedback(
            user_id=user_id,
            university_rating=university_rating,
            city_rating=city_rating,
            overall_rating=overall_rating,
            comment=comment.strip() if comment else None,
        )

        db.add(new_feedback)
        db.commit()

        return RedirectResponse(url="/feedback?success=Feedback submitted successfully", status_code=303)

    except Exception:
        return RedirectResponse(url="/feedback?error=Could not save feedback", status_code=303)