from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.models.base import Base


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)

    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    buddy_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    status = Column(String, default="pending", nullable=False)
    compatibility_score = Column(Integer, default=0)
    match_reason = Column(Text)

    created_at = Column(String)
    responded_at = Column(String)

    student = relationship(
        "User",
        foreign_keys=[student_id],
    )

    buddy = relationship(
        "User",
        foreign_keys=[buddy_id],
    )

    requester = relationship(
        "User",
        foreign_keys=[requested_by],
    )