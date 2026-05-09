from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.models.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    security_question = Column(String, nullable=False)
    security_answer = Column(String, nullable=False)

    # Personal profile
    first_name = Column(String)
    last_name = Column(String)
    birth_date = Column(String)
    sex = Column(String)
    nationality = Column(String)
    phone = Column(String)
    profile_photo = Column(String)
    biography = Column(Text)

    # Match profile
    user_type = Column(String)
    language = Column(String)
    language_2 = Column(String)
    home_university = Column(String)
    exchange_university = Column(String)
    favorite_sport_1 = Column(String)
    favorite_sport_2 = Column(String)
    hobby_1 = Column(String)
    hobby_2 = Column(String)

    created_events = relationship(
        "Event",
        back_populates="creator"
    )

    joined_event_links = relationship(
        "EventParticipant",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    feedbacks = relationship(
        "Feedback",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    event_reviews = relationship(
        "EventReview",
        back_populates="user",
        cascade="all, delete-orphan"
    )