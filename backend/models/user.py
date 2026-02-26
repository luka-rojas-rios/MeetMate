from sqlalchemy import Column, Integer, String
from backend.models.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    security_question = Column(String, nullable=False)
    security_answer = Column(String, nullable=False)

    user_type = Column(String)
    language = Column(String)
    language_2 = Column(String)
    home_university = Column(String)
    exchange_university = Column(String)
    favorite_sport_1 = Column(String)
    favorite_sport_2 = Column(String)
    hobby_1 = Column(String)
    hobby_2 = Column(String)