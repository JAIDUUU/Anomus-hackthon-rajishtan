import os
import json
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, Float, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "prototype.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False)  # admin, investigating_officer, senior_officer
    full_name = Column(String(100), nullable=False)
    badge_number = Column(String(50), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Case(Base):
    __tablename__ = "cases"

    id = Column(String(50), primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    status = Column(String(30), default="ACTIVE")
    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    brief_data = Column(Text, default="{}")

    cdr_records = relationship("CDRRecord", back_populates="case", cascade="all, delete-orphan")
    ipdr_records = relationship("IPDRRecord", back_populates="case", cascade="all, delete-orphan")
    import_batches = relationship("ImportBatch", back_populates="case", cascade="all, delete-orphan")
    ai_observations = relationship("AIObservation", back_populates="case", cascade="all, delete-orphan")


class CDRRecord(Base):
    __tablename__ = "cdr_records"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(50), ForeignKey("cases.id"), index=True, nullable=False)
    a_number = Column(String(30), index=True, nullable=False)
    b_number = Column(String(30), index=True, nullable=False)
    call_type = Column(String(20), nullable=False)  # IN, OUT, SMS
    start_time = Column(String(30), index=True, nullable=False)  # ISO string YYYY-MM-DDTHH:MM:SS
    duration_sec = Column(Integer, default=0)
    imei = Column(String(30), index=True, default="")
    imsi = Column(String(30), index=True, default="")
    cell_id = Column(String(50), index=True, default="")
    source_file = Column(String(200), nullable=False)
    source_row = Column(Integer, nullable=False)
    raw_data_json = Column(Text, default="{}")

    case = relationship("Case", back_populates="cdr_records")


class IPDRRecord(Base):
    __tablename__ = "ipdr_records"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(50), ForeignKey("cases.id"), index=True, nullable=False)
    subscriber_number = Column(String(30), index=True, nullable=False)
    source_ip = Column(String(50), index=True, nullable=False)
    source_port = Column(Integer, nullable=False)
    destination_ip = Column(String(50), default="")
    destination_port = Column(Integer, default=0)
    session_start = Column(String(30), index=True, nullable=False)
    session_end = Column(String(30), nullable=False)
    bytes_transferred = Column(Integer, default=0)
    app_hint = Column(String(100), default="")
    source_file = Column(String(200), nullable=False)
    source_row = Column(Integer, nullable=False)
    raw_data_json = Column(Text, default="{}")

    case = relationship("Case", back_populates="ipdr_records")


class CellTower(Base):
    __tablename__ = "cell_towers"

    id = Column(Integer, primary_key=True, index=True)
    cell_id = Column(String(50), unique=True, index=True, nullable=False)
    lac = Column(Integer, default=0)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    area_name = Column(String(150), nullable=False)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(50), ForeignKey("cases.id"), index=True, nullable=False)
    filename = Column(String(200), nullable=False)
    file_type = Column(String(20), nullable=False)  # CDR, IPDR, TOWER
    mapping_name = Column(String(100), default="")
    total_rows = Column(Integer, default=0)
    valid_rows = Column(Integer, default=0)
    rejected_rows = Column(Integer, default=0)
    validation_summary_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="import_batches")


class AIObservation(Base):
    __tablename__ = "ai_observations"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(50), ForeignKey("cases.id"), index=True, nullable=False)
    query_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=False)
    evidence_json = Column(Text, default="[]")
    confidence_note = Column(String(255), default="")
    status = Column(String(30), default="pending_verification")  # pending_verification, verified, rejected
    verified_by = Column(String(50), default="")
    verified_at = Column(DateTime, nullable=True)
    officer_notes = Column(Text, default="")
    suggested_followups = Column(Text, default="[]")
    suggested_filters = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="ai_observations")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String(50), nullable=False)
    role = Column(String(30), default="")
    action = Column(String(50), index=True, nullable=False)  # LOGIN, UPLOAD, QUERY, AI_QUERY, EVIDENCE_VIEW, VERIFY, REPORT
    details = Column(Text, default="{}")
    ip_address = Column(String(50), default="")
    timestamp = Column(DateTime, default=datetime.utcnow)
    prev_hash = Column(String(64), default="")
    entry_hash = Column(String(64), default="")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    # Safe additive migration for existing SQLite databases missing SHA-256 hash chain columns
    with engine.begin() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(audit_logs)").fetchall()}
        if "prev_hash" not in cols:
            conn.exec_driver_sql("ALTER TABLE audit_logs ADD COLUMN prev_hash VARCHAR(64) DEFAULT ''")
        if "entry_hash" not in cols:
            conn.exec_driver_sql("ALTER TABLE audit_logs ADD COLUMN entry_hash VARCHAR(64) DEFAULT ''")
