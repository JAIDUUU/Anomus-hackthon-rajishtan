import json
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.db as db_mod
from app.auth import seed_default_users
from app.ingest import seed_towers_from_csv
from app.main import app


@pytest.fixture(scope="session")
def test_db_engine(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("isolated_db") / "test_suite.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    db_mod.Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[db_mod.get_db] = override_get_db

    # Seed users & towers on isolated DB
    s = TestingSessionLocal()
    try:
        seed_default_users(s)
        seed_towers_from_csv(s)
    finally:
        s.close()

    yield engine, TestingSessionLocal
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def client(test_db_engine):
    _, TestingSessionLocal = test_db_engine
    c = TestClient(app)

    # Authenticate IO Sharma and upload test case via real API endpoints (not /api/cases/demo)
    login_res = c.post("/api/auth/login", json={"username": "io_sharma", "password": "IO@RajPolice2026"})
    assert login_res.status_code == 200
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    brief_path = os.path.join(data_dir, "case_brief.json")
    brief_data = "{}"
    if os.path.exists(brief_path):
        with open(brief_path, "r", encoding="utf-8") as f:
            brief_data = f.read()

    # Create isolated test case
    c.post("/api/cases", json={
        "id": "CASE-RAJ-2026-0042",
        "title": "Operation Maru-Drishti (Test Fixture)",
        "description": "Isolated test fixture ingested via real multi-format upload API."
    }, headers=headers)

    s = TestingSessionLocal()
    try:
        case_obj = s.query(db_mod.Case).filter(db_mod.Case.id == "CASE-RAJ-2026-0042").first()
        if case_obj:
            case_obj.brief_data = brief_data
            s.commit()
    finally:
        s.close()

    for fname, ftype, map_name in [
        ("cdr_operator_A.csv", "CDR", "operator_a"),
        ("cdr_operator_B.csv", "CDR", "operator_b"),
        ("ipdr_operator_A.csv", "IPDR", "ipdr_operator_a"),
    ]:
        fpath = os.path.join(data_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "rb") as fp:
                r = c.post(
                    "/api/cases/CASE-RAJ-2026-0042/upload",
                    data={"file_type": ftype, "mapping_name": map_name},
                    files={"file": (fname, fp.read(), "text/csv")},
                    headers=headers
                )
                assert r.status_code == 200, f"Test upload failed for {fname}: {r.text}"

    return c


@pytest.fixture
def db_session(test_db_engine):
    _, TestingSessionLocal = test_db_engine
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def auth_headers(client):
    res = client.post("/api/auth/login", json={
        "username": "io_sharma",
        "password": "IO@RajPolice2026"
    })
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}
