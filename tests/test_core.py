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


def test_read_and_ingest_excel_cdr(test_db):
    import io
    import pandas as pd
    from app.ingest import inspect_uploaded_file

    test_case = Case(id="TEST-XLSX-01", title="Excel Dynamic Test", created_by="tester")
    test_db.add(test_case)
    test_db.commit()

    df = pd.DataFrame([
        {
            "Caller_MSISDN": "+919829011122",
            "Called_MSISDN": "9829033344",
            "Call_Dir": "OUT",
            "Timestamp": "2026-11-22 14:15:00",
            "Duration_Seconds": "95",
            "Handset_IMEI": "354890123456781",
            "SIM_IMSI": "404450111122223",
            "Cell_Site_ID": "RAJ-JPR-101"
        },
        {
            "Caller_MSISDN": "09829033344",
            "Called_MSISDN": "9829011122",
            "Call_Dir": "IN",
            "Timestamp": "2026-11-22 15:00:00",
            "Duration_Seconds": "45",
            "Handset_IMEI": "355832119832043",
            "SIM_IMSI": "404450333344445",
            "Cell_Site_ID": "RAJ-JPR-102"
        }
    ])
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    xlsx_bytes = buf.getvalue()

    info = inspect_uploaded_file(xlsx_bytes, "operator_custom.xlsx")
    assert info["format"] == "EXCEL"
    assert info["suggested_type"] == "CDR"
    assert info["row_count"] == 2
    assert "Caller_MSISDN" in info["columns"]
    assert info["suggested_mapping"]["a_number"] == "Caller_MSISDN"
    assert info["suggested_mapping"]["b_number"] == "Called_MSISDN"

    summary = ingest_cdr_data(
        xlsx_bytes,
        "operator_custom.xlsx",
        "TEST-XLSX-01",
        {"name": "Dynamic Excel", "mappings": info["suggested_mapping"]},
        test_db
    )
    assert summary["valid_rows"] == 2
    assert summary["rejected_rows"] == 0
    assert summary["batch_id"] is not None


def test_inspect_ipdr_and_invalid_files():
    import io
    import pandas as pd
    from app.ingest import inspect_uploaded_file

    df_ipdr = pd.DataFrame([
        {
            "Subscriber_Mobile": "9811223344",
            "Public_NAT_IP": "103.50.10.5",
            "NAT_Port": "51234",
            "Session_Start": "2026-11-22 10:00:00",
            "App_Protocol": "WhatsApp VoIP"
        }
    ])
    buf = io.BytesIO()
    df_ipdr.to_excel(buf, index=False)
    info = inspect_uploaded_file(buf.getvalue(), "nat_logs.xlsx")
    assert info["suggested_type"] == "IPDR"
    assert info["suggested_mapping"]["source_ip"] == "Public_NAT_IP"
    assert info["suggested_mapping"]["source_port"] == "NAT_Port"

    with pytest.raises(ValueError):
        inspect_uploaded_file(b"", "empty.csv")

    with pytest.raises(ValueError):
        inspect_uploaded_file(b"not-valid-content", "bad.pdf")
