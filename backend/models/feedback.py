from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from backend.models.base import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    university_rating = Column(Integer, nullable=False)
    city_rating = Column(Integer, nullable=False)

    
    overall_rating = Column(Integer, nullable=False)

    comment = Column(String, nullable=True)
    created_at = Column(String, nullable=True)

    user = relationship(
        "User",
        back_populates="feedbacks"
    )