from pydantic import BaseModel, Field

class RegisterRequest(BaseModel):
    username: str = Field(..., example="usuario123")
    password: str = Field(..., example="Contraseña123!")
    security_question: str = Field(..., example="¿En qué ciudad naciste?")
    security_answer: str = Field(..., example="Madrid")

class LoginRequest(BaseModel):
    username: str
    password: str

class MatchRequest(BaseModel):
    student_id: int
    buddy_id: int
