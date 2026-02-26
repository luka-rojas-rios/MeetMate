from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Crear la base de datos SQLite
DATABASE_URL = "postgresql://postgres:monica@localhost:5432/MeetMate"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Crear las tablas en la base de datos
Base.metadata.create_all(bind=engine)
