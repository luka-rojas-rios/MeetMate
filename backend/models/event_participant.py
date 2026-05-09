from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from backend.models.base import Base


class EventParticipant(Base):
    __tablename__ = "event_participants"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    event = relationship("Event", back_populates="participants")
    user = relationship("User", back_populates="joined_event_links")