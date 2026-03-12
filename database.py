from pathlib import Path

from sqlalchemy import Column, Date, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "assignment_2"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = (DB_DIR / "assignment2.db").resolve()
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ParticipantRecord(Base):
    __tablename__ = "participant_records"

    id = Column(Integer, primary_key=True, index=True)
    participant_name = Column(String, nullable=False)
    company = Column(String, nullable=False)
    department = Column(String, nullable=False)
    type_of_training = Column(String, nullable=False)
    training_date = Column(Date, nullable=False)
