from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from backend.models.base import Base

class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    buddy_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="Pending")
    created_at = Column(String)

    student = relationship("User", foreign_keys=[student_id])
    buddy = relationship("User", foreign_keys=[buddy_id])
