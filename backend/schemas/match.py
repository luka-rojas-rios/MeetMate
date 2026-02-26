from pydantic import BaseModel

class MatchRequest(BaseModel):
    student_id: int
    buddy_id: int
