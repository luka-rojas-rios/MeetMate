from backend.models.base import Base
from backend.database import engine

from backend.models.user import User
from backend.models.match import Match
from backend.models.event import Event
from backend.models.event_participant import EventParticipant
from backend.models.feedback import Feedback
from backend.models.event_review import EventReview

from backend.schema_upgrades import run_schema_upgrades


Base.metadata.create_all(bind=engine)
run_schema_upgrades()

print("Tablas creadas y actualizadas correctamente")