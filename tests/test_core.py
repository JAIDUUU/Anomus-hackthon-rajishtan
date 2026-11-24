import pytest
import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, Case, CDRRecord, IPDRRecord
from app.ingest import normalize_phone_number, parse_duration_to_sec, ingest_cdr_data
from app.analysis import find_common_numbers, detect_imei_sim_changes
from app.assistant import run_ai_assistant


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    yield db
    db.close()


def test_phone_and_duration_normalization():
    # Test phone normalization
    assert normalize_phone_number("+919829022222") == "9829022222"
    assert normalize_phone_number("09829022222") == "9829022222"
    assert normalize_phone_number("919829022222") == "9829022222"
    assert normalize_phone_number("9829022222") == "9829022222"

    # Test duration normalization
    assert parse_duration_to_sec("120", "seconds") == 120
    assert parse_duration_to_sec("02:05", "mm:ss") == 125
    assert parse_duration_to_sec("01:10:05", "mm:ss") == 4205


def test_ingest_cdr_normalization_and_validation(test_db):
    test_case = Case(id="TEST-CASE-01", title="Test Case", created_by="tester")
    test_db.add(test_case)
    test_db.commit()

    mapping_config = {
        "name": "Test Mapping",
        "mappings": {
            "a_number": "Calling_Number",
            "b_number": "Called_Number",
            "call_type": "Call_Direction",
            "start_time": "Call_Date_Time",
            "duration_sec": "Call_Duration_Sec",
            "imei": "IMEI_Num",
            "imsi": "IMSI_Num",
            "cell_id": "Tower_Cell_ID"
        },
        "date_format": "%Y-%m-%d %H:%M:%S",
        "duration_format": "seconds"
    }

    # CSV with 1 valid row, 1 missing IMEI, 1 bad timestamp, 1 duplicate
    csv_content = (
        "Calling_Number,Called_Number,Call_Direction,Call_Date_Time,Call_Duration_Sec,IMEI_Num,IMSI_Num,Tower_Cell_ID\n"
        "+919829022222,+919414088888,OUTGOING,2026-11-20 10:00:00,120,354890123456781,404450123456781,RAJ-JPR-101\n"
        "+919829022222,+919414088888,OUTGOING,2026-11-20 10:00:00,120,354890123456781,404450123456781,RAJ-JPR-101\n"  # Duplicate
        "+919829022222,+919414088888,OUTGOING,2026-11-20 11:00:00,60,,404450123456781,RAJ-JPR-101\n"  # Missing IMEI
        "+919829022222,+919414088888,OUTGOING,2026-13-45 99:99:99,60,354890123456781,404450123456781,RAJ-JPR-101\n"  # Bad timestamp
    ).encode("utf-8")

    summary = ingest_cdr_data(csv_content, "test.csv", "TEST-CASE-01", mapping_config, test_db)

    assert summary["total_rows"] == 4
    assert summary["valid_rows"] == 1
    assert summary["rejected_rows"] == 3
    assert summary["missing_counts"]["imei"] == 1


def test_common_numbers_detection(test_db):
    test_case = Case(id="TEST-CASE-02", title="Common Numbers Test", created_by="tester")
    test_db.add(test_case)

    # S1 calls Common 9414088888
    test_db.add(CDRRecord(
        case_id="TEST-CASE-02", a_number="9829022222", b_number="9414088888",
        call_type="OUT", start_time="2026-11-20T10:00:00", duration_sec=60,
        source_file="test.csv", source_row=2
    ))
    # S2 calls Common 9414088888
    test_db.add(CDRRecord(
        case_id="TEST-CASE-02", a_number="9829033333", b_number="9414088888",
        call_type="OUT", start_time="2026-11-20T11:00:00", duration_sec=80,
        source_file="test.csv", source_row=3
    ))
    test_db.commit()

    res = find_common_numbers(["9829022222", "9829033333"], "TEST-CASE-02", test_db)
    assert res["common_contacts_count"] == 1
    assert res["common_contacts"][0]["common_number"] == "9414088888"


def test_imei_sim_change_detection(test_db):
    test_case = Case(id="TEST-CASE-03", title="IMEI Change Test", created_by="tester")
    test_db.add(test_case)

    # Same IMEI used by 9829044444 and later by 9829077777
    test_db.add(CDRRecord(
        case_id="TEST-CASE-03", a_number="9829044444", b_number="9414011111",
        call_type="OUT", start_time="2026-11-18T10:00:00", duration_sec=40,
        imei="354890123456783", imsi="404450123456783", source_file="test.csv", source_row=2
    ))
    test_db.add(CDRRecord(
        case_id="TEST-CASE-03", a_number="9829077777", b_number="9414022222",
        call_type="OUT", start_time="2026-11-20T14:00:00", duration_sec=90,
        imei="354890123456783", imsi="404450999999999", source_file="test.csv", source_row=3
    ))
    test_db.commit()

    changes = detect_imei_sim_changes("TEST-CASE-03", test_db)
    assert len(changes["multi_number_imeis"]) == 1
    assert changes["multi_number_imeis"][0]["imei"] == "354890123456783"
    assert "9829044444" in changes["multi_number_imeis"][0]["numbers"]
    assert "9829077777" in changes["multi_number_imeis"][0]["numbers"]


def test_guardrail_unsupported_data(test_db):
    test_case = Case(id="TEST-CASE-04", title="Guardrail Test", created_by="tester")
    test_db.add(test_case)
    test_db.commit()

    # Query asking for call recording/audio content
    query = "Call me kya baat hui aur recording sunao suspect Vikram ki"
    res = run_ai_assistant(query, "TEST-CASE-04", "investigating_officer", test_db)

    # Must trigger guardrail explaining CDR has metadata only
    assert "Information Not Available in Uploaded Data" in res["answer"]
    assert "CDR and IPDR data strictly contain communication metadata" in res["answer"]
    assert res["status"] == "pending_verification"
