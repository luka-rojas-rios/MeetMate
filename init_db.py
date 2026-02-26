from backend.models.base import Base
from backend.database import engine
from backend.models.user import User
from backend.models.match import Match

Base.metadata.create_all(bind=engine)

print("✅ Tablas creadas correctamente")
