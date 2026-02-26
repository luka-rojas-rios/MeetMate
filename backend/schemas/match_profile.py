from pydantic import BaseModel

class MatchProfileRequest(BaseModel):
    user_type: str
    language: str
    home_university: str
    exchange_university: str
    favorite_sport_1: str
    favorite_sport_2: str
    hobby_1: str
    hobby_2: str
