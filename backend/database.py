from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.base import Base


DATABASE_URL = "postgresql://postgres.xgonjhokozuravsayldx:Proyectos2*@aws-1-eu-west-1.pooler.supabase.com:5432/postgres"


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()