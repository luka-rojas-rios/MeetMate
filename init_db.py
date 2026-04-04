<<<<<<< HEAD
from backend.models.base import Base
from backend.database import engine
from backend.models.user import User
from backend.models.match import Match
from backend.models.event import Event

Base.metadata.create_all(bind=engine)

print("✅ Tablas creadas correctamente")
=======
from backend.models.base import Base
from backend.database import engine
from backend.models.user import User
from backend.models.match import Match

Base.metadata.create_all(bind=engine)

print(" Tablas creadas correctamente")
>>>>>>> a395f1fb962c33a91de889788cd6c1e97766d457
