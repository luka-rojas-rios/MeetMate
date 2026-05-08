from pydantic import BaseModel


class MatchRequest(BaseModel):
    student_id: int
    buddy_id: int
    requested_by: int
    status: str = "pending"
    compatibility_score: int = 0
    match_reason: str | None = None