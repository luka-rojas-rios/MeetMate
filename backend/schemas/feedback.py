from pydantic import BaseModel, Field
from typing import Optional



class FeedbackCreate(BaseModel):
    university_rating: int = Field(..., ge=1, le=5)
    city_rating: int = Field(..., ge=1, le=5)
    overall_rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None