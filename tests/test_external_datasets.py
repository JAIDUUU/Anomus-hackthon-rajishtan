import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, Case
from app.ingest import ingest_cdr_data, ingest_ipdr_data
from app.analysis import (
    analyze_communication_patterns,
    get_mfc_analysis,
    get_day_night_analysis,
    lookup_tac_device,
    get_executive_metrics
)
from app.ipdr import match_ipdr_session


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_ingest_sandhan_case_0001(test_db):
    """Test ingestion of external Sandhan hackathon case 0001 CDR and IPDR."""
    case = Case(
        id="CASE-EXT-0001",
        title="Operation Sandhan Test 1",
        description="External test dataset from open police benchmark",
        created_by="io_sharma",
        brief_data=json.dumps({"suspects": [{"phone": "9812345601"}, {"phone": "9811100011"}]})
    )
    test_db.add(case)
    test_db.commit()

    with open("data/mappings/sandhan_operator.json") as f:
        cdr_map = json.load(f)

    with open("data/external_samples/case-2026-0001/cdr.csv", "rb") as f:
        cdr_bytes = f.read()

    res = ingest_cdr_data(
        file_bytes=cdr_bytes,
        filename="cdr.csv",
        case_id="CASE-EXT-0001",
        mapping_config=cdr_map,
        db=test_db
    )
    assert res["valid_rows"] > 0
    assert res["total_rows"] > 0

    # Ingest IPDR
    with open("data/mappings/sandhan_ipdr.json") as f:
        ipdr_map = json.load(f)

    with open("data/external_samples/case-2026-0001/ipdr.csv", "rb") as f:
        ipdr_bytes = f.read()

    ipdr_res = ingest_ipdr_data(
        file_bytes=ipdr_bytes,
        filename="ipdr.csv",
        case_id="CASE-EXT-0001",
        mapping_config=ipdr_map,
        db=test_db
    )
    assert ipdr_res["valid_rows"] > 0

    # Test analysis on external data
    patterns = analyze_communication_patterns("9812345601", "CASE-EXT-0001", test_db)
    assert patterns["total_calls"] > 0
    assert len(patterns["top_contacts"]) > 0

    mfc = get_mfc_analysis("CASE-EXT-0001", test_db, target_number="9812345601")
    assert len(mfc) > 0

    # Test IPDR matching
    match = match_ipdr_session(
        case_id="CASE-EXT-0001",
        ip="103.21.244.10",
        port=0,
        query_timestamp="2026-01-04 10:30:00",
        db=test_db
    )
    assert match["matched"] is True
    assert match["primary_subscriber"] == "9812345601"


def test_ingest_vega_forensic_cdr(test_db):
    """Test ingestion of external Vega-4n6 cyber forensic CDR (3,600+ rows)."""
    case = Case(
        id="CASE-EXT-VEGA",
        title="Vega 4n6 External Forensic Benchmark",
        description="Vega open forensic CDR dataset",
        created_by="io_sharma",
        brief_data=json.dumps({"suspects": [{"phone": "923310000000"}]})
    )
    test_db.add(case)
    test_db.commit()

    with open("data/mappings/vega_operator.json") as f:
        vega_map = json.load(f)

    with open("data/external_samples/vega_4n6_cdr.csv", "rb") as f:
        cdr_bytes = f.read()

    res = ingest_cdr_data(
        file_bytes=cdr_bytes,
        filename="vega_4n6_cdr.csv",
        case_id="CASE-EXT-VEGA",
        mapping_config=vega_map,
        db=test_db
    )
    assert res["valid_rows"] > 2500

    # Verify Day/Night analytics on Vega dataset
    dn = get_day_night_analysis("CASE-EXT-VEGA", test_db)
    assert dn["summary"]["total_calls"] > 2500
    assert "day_calls_count" in dn["summary"]
    assert "night_calls_count" in dn["summary"]

    # Verify TAC device lookup on sample IMEI
    tac_info = lookup_tac_device("355553000000000")
    assert "brand" in tac_info
    assert "model" in tac_info

    # Verify Executive Metrics calculation
    metrics = get_executive_metrics("CASE-EXT-VEGA", test_db)
    assert metrics["total_cdrs"] > 2500
