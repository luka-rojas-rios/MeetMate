from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.models.base import Base


class EventReview(Base):
    __tablename__ = "event_reviews"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    rating = Column(Integer, nullable=False)
    comment = Column(Text)

    creator_rating = Column(Integer)
    creator_comment = Column(Text)

    created_at = Column(String)

    event = relationship("Event", back_populates="reviews")
    user = relationship("User", back_populates="event_reviews")