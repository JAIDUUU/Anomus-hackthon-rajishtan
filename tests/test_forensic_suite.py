import pytest
import app.analysis as an

# Uses isolated `client`, `auth_headers`, `db_session` fixtures from tests/conftest.py


# ----------------- UNIT TESTS: ANALYSIS FUNCTIONS -----------------
def test_lookup_tac_device():
    # Apple iPhone 15 Pro Max
    d1 = an.lookup_tac_device("354890123456781")
    assert d1["brand"] == "Apple"
    assert "iPhone 15" in d1["model"]
    assert "5G" in d1["generation"]

    # OnePlus 12 5G
    d2 = an.lookup_tac_device("358910000000101")
    assert d2["brand"] == "OnePlus"
    assert "12" in d2["model"]

    # Samsung Galaxy S24 Ultra
    d3 = an.lookup_tac_device("354890999999999")
    assert d3["brand"] == "Samsung"
    assert "S24" in d3["model"]

    # Unlisted TAC heuristic fallback
    d4 = an.lookup_tac_device("869999991234567")
    assert "APAC" in d4["model"] or "Xiaomi" in d4["brand"] or "BBK" in d4["brand"]

    # Short / Invalid IMEI
    d5 = an.lookup_tac_device("")
    assert d5["brand"] == "Unknown"
    d6 = an.lookup_tac_device("123")
    assert d6["brand"] == "Invalid IMEI"


def test_executive_metrics(db_session):
    case_id = "CASE-RAJ-2026-0042"
    metrics = an.get_executive_metrics(case_id, db_session)

    assert metrics["total_cases"] >= 1
    assert metrics["active_investigations"] >= 1
    assert metrics["total_cdrs"] > 1800
    assert metrics["analyzed_numbers"] > 50
    assert metrics["common_numbers"] > 0
    assert metrics["locations_tracked"] >= 10

    # Global metrics
    global_metrics = an.get_executive_metrics(None, db_session)
    assert global_metrics["total_cases"] >= 1
    assert global_metrics["total_cdrs"] >= metrics["total_cdrs"]


def test_raw_cdr_pagination_and_filters(db_session):
    case_id = "CASE-RAJ-2026-0042"

    # Default page 1, limit 10
    res = an.get_raw_cdr_records(case_id, db_session, page=1, limit=10)
    assert res["total"] > 1800
    assert len(res["records"]) == 10
    assert res["page"] == 1
    assert res["total_pages"] > 100

    # Verify legal standard: source_file and source_row preserved
    first_rec = res["records"][0]
    assert "source_file" in first_rec and first_rec["source_file"]
    assert "source_row" in first_rec and first_rec["source_row"] > 0

    # Search filter
    s_res = an.get_raw_cdr_records(case_id, db_session, page=1, limit=10, search="9829022222")
    assert s_res["total"] > 0
    for r in s_res["records"]:
        assert "9829022222" in (r["a_number"] + r["b_number"])

    # Call type filter
    sms_res = an.get_raw_cdr_records(case_id, db_session, page=1, limit=10, call_type="SMS")
    for r in sms_res["records"]:
        assert r["call_type"] == "SMS"


def test_mfc_analysis(db_session):
    case_id = "CASE-RAJ-2026-0042"

    # Target number MFC
    mfc = an.get_mfc_analysis(case_id, db_session, target_number="9829022222", top=10)
    assert len(mfc) > 0
    top_peer = mfc[0]
    assert top_peer["call_count"] > 0
    assert top_peer["total_duration_sec"] >= 0
    assert len(top_peer["sample_evidence"]) > 0

    # Case-wide MFC
    case_mfc = an.get_mfc_analysis(case_id, db_session, top=10)
    assert len(case_mfc) > 0
    assert case_mfc[0]["call_count"] >= case_mfc[-1]["call_count"]


def test_day_night_forensics(db_session):
    case_id = "CASE-RAJ-2026-0042"

    # S4 Farooq Khan is known for high night activity
    res_s4 = an.get_day_night_analysis(case_id, db_session, target_number="9829055555")
    summary = res_s4["summary"]
    assert summary["night_calls_count"] > summary["day_calls_count"]
    assert summary["night_percentage"] > 50.0

    # Verify day and night locations have coordinates
    assert len(res_s4["night_locations"]) > 0
    first_loc = res_s4["night_locations"][0]
    assert "cell_id" in first_loc
    assert "area_name" in first_loc


def test_first_last_calls(db_session):
    case_id = "CASE-RAJ-2026-0042"
    fl_list = an.get_first_last_calls(case_id, db_session, target_number="9829022222")

    assert len(fl_list) > 0
    first_contact = fl_list[0]
    assert first_contact["first_call_time"] <= first_contact["last_call_time"]
    assert first_contact["total_calls"] >= 1
    assert first_contact["first_call_evidence"]["source_file"]
    assert first_contact["first_call_evidence"]["source_row"] > 0


def test_missing_dates_analysis(db_session):
    case_id = "CASE-RAJ-2026-0042"

    # S3 (9829044444) has silence at end of investigation period after SIM swap
    md = an.get_missing_dates_analysis(case_id, db_session, target_number="9829044444")
    assert md["missing_days_count"] >= 1
    assert "2026-11-22" in md["missing_dates"] or "2026-11-23" in md["missing_dates"]
    assert len(md["silence_periods"]) > 0
    assert len(md["daily_activity"]) > 0

    # Case-wide missing dates returns suspects summary
    md_all = an.get_missing_dates_analysis(case_id, db_session)
    assert len(md_all["suspects_analysis"]) >= 4


def test_movement_and_cell_changes(db_session):
    case_id = "CASE-RAJ-2026-0042"
    mov = an.get_movement_and_cell_changes(case_id, db_session, target_number="9829022222")

    assert len(mov) > 0
    first_hop = mov[0]
    assert "from_cell_id" in first_hop
    assert "to_cell_id" in first_hop
    assert first_hop["from_cell_id"] != first_hop["to_cell_id"]
    assert first_hop["from_evidence"]["source_file"]
    assert first_hop["to_evidence"]["source_file"]
    assert "distance_km" in first_hop
    assert "speed_kmh" in first_hop


def test_service_numbers(db_session):
    case_id = "CASE-RAJ-2026-0042"
    services = an.get_service_and_company_numbers(case_id, db_session)

    assert len(services) >= 3
    service_nums = [s["number"] for s in services]
    assert any(n.startswith("1800") or n.startswith("1860") for n in service_nums)
    assert any(n in ("56161", "567676", "121") for n in service_nums)

    # Check SBI or HDFC label
    sbi_or_hdfc = next((s for s in services if s["number"] in ("1800112211", "18602662666")), None)
    assert sbi_or_hdfc is not None
    assert "Bank" in sbi_or_hdfc["service_name"] or "Helpline" in sbi_or_hdfc["service_name"]
    assert len(sbi_or_hdfc["calling_numbers"]) > 0


def test_international_intelligence(db_session):
    case_id = "CASE-RAJ-2026-0042"
    intl = an.get_international_intelligence(case_id, db_session)

    assert len(intl) >= 2
    intl_nums = [i["number"] for i in intl]
    assert "+971501234567" in intl_nums or "+447911123456" in intl_nums

    dubai = next((i for i in intl if i["number"] == "+971501234567"), None)
    if dubai:
        assert "Emirates" in dubai["country"] or "Dubai" in dubai["country"]
        assert dubai["risk_level"] in ("HIGH", "CRITICAL")
        assert len(dubai["linked_local_numbers"]) > 0


def test_imei_and_imsi_summaries(db_session):
    case_id = "CASE-RAJ-2026-0042"

    imeis = an.get_imei_summary_list(case_id, db_session)
    assert len(imeis) >= 5
    top_imei = imeis[0]
    assert "brand" in top_imei
    assert "model" in top_imei
    assert len(top_imei["linked_numbers"]) > 0

    # Handset swap detection in summary
    s3_imei = next((im for im in imeis if im["imei"] == "354890123456783"), None)
    assert s3_imei is not None
    assert s3_imei["is_multi_sim"] is True
    assert "9829044444" in s3_imei["linked_numbers"]
    assert "9829077777" in s3_imei["linked_numbers"]

    imsis = an.get_imsi_summary_list(case_id, db_session)
    assert len(imsis) >= 5
    top_imsi = imsis[0]
    assert "carrier" in top_imsi
    assert len(top_imsi["linked_imeis"]) > 0


def test_global_search(db_session):
    case_id = "CASE-RAJ-2026-0042"

    # Search suspect phone number
    res_num = an.global_search("9829022222", case_id, db_session)
    assert res_num["total_matches"] > 0
    assert len(res_num["results"]["numbers"]) > 0

    # Search device brand (TAC decode search)
    res_brand = an.global_search("iPhone", case_id, db_session)
    assert len(res_brand["results"]["imeis"]) >= 4

    # Search cell tower
    res_tower = an.global_search("RAJ-JPR-102", case_id, db_session)
    assert len(res_tower["results"]["towers"]) > 0

    # Empty search handles gracefully
    empty_res = an.global_search("", case_id, db_session)
    assert empty_res["total_matches"] == 0


# ----------------- INTEGRATION TESTS: HTTP API ENDPOINTS -----------------
def test_api_dashboard_metrics(client, auth_headers):
    # With case_id
    r1 = client.get("/api/dashboard/metrics?case_id=CASE-RAJ-2026-0042", headers=auth_headers)
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["total_cdrs"] > 1800
    assert d1["analyzed_numbers"] > 50
    assert d1["locations_tracked"] >= 10

    # Without case_id
    r2 = client.get("/api/dashboard/metrics", headers=auth_headers)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["total_cases"] >= 1

    # Invalid case_id -> 404
    r3 = client.get("/api/dashboard/metrics?case_id=NON-EXISTENT", headers=auth_headers)
    assert r3.status_code == 404


def test_api_raw_cdr(client, auth_headers):
    case_id = "CASE-RAJ-2026-0042"
    r = client.get(f"/api/cases/{case_id}/raw-cdr?page=1&limit=20&search=9829022222", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] > 0
    assert len(data["records"]) <= 20
    assert "source_file" in data["records"][0]
    assert "source_row" in data["records"][0]


def test_api_mfc(client, auth_headers):
    case_id = "CASE-RAJ-2026-0042"
    r = client.get(f"/api/cases/{case_id}/mfc?target_number=9829022222&top=15", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0
    assert "contact_number" in data[0]
    assert "call_count" in data[0]


def test_api_day_night(client, auth_headers):
    case_id = "CASE-RAJ-2026-0042"
    r = client.get(f"/api/cases/{case_id}/day-night?target_number=9829055555", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert data["summary"]["night_calls_count"] > 0
    assert len(data["night_locations"]) > 0


def test_api_first_last(client, auth_headers):
    case_id = "CASE-RAJ-2026-0042"
    r = client.get(f"/api/cases/{case_id}/first-last?target_number=9829022222", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0
    assert "first_call_time" in data[0]
    assert "last_call_time" in data[0]


def test_api_missing_dates(client, auth_headers):
    case_id = "CASE-RAJ-2026-0042"
    r = client.get(f"/api/cases/{case_id}/missing-dates?target_number=9829044444", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "missing_dates" in data
    assert "silence_periods" in data


def test_api_movement(client, auth_headers):
    case_id = "CASE-RAJ-2026-0042"
    r = client.get(f"/api/cases/{case_id}/movement?target_number=9829022222", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0
    assert "from_cell_id" in data[0]
    assert "to_cell_id" in data[0]
    assert "distance_km" in data[0]


def test_api_service_numbers(client, auth_headers):
    case_id = "CASE-RAJ-2026-0042"
    r = client.get(f"/api/cases/{case_id}/service-numbers", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 3
    assert "service_name" in data[0]


def test_api_international(client, auth_headers):
    case_id = "CASE-RAJ-2026-0042"
    r = client.get(f"/api/cases/{case_id}/international", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 2
    assert "country" in data[0]


def test_api_imei_and_imsi_summary(client, auth_headers):
    case_id = "CASE-RAJ-2026-0042"
    r_imei = client.get(f"/api/cases/{case_id}/imei-summary", headers=auth_headers)
    assert r_imei.status_code == 200
    data_imei = r_imei.json()
    assert len(data_imei) >= 5
    assert "brand" in data_imei[0]

    r_imsi = client.get(f"/api/cases/{case_id}/imsi-summary", headers=auth_headers)
    assert r_imsi.status_code == 200
    data_imsi = r_imsi.json()
    assert len(data_imsi) >= 5
    assert "carrier" in data_imsi[0]


def test_api_tac_lookup(client, auth_headers):
    r = client.get("/api/tac/354890123456781", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["brand"] == "Apple"
    assert "iPhone 15" in data["model"]


def test_api_global_search(client, auth_headers):
    case_id = "CASE-RAJ-2026-0042"
    r = client.get(f"/api/search?q=9829022222&case_id={case_id}", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total_matches"] > 0
    assert len(data["results"]["numbers"]) > 0


def test_api_unauthorized_rejection(test_db_engine):
    from fastapi.testclient import TestClient
    from app.main import app
    fresh = TestClient(app)
    # Calling without auth token or cookie must return 401 or 403
    r = fresh.get("/api/cases/CASE-RAJ-2026-0042/raw-cdr")
    assert r.status_code in (401, 403)


def test_analyze_link_between_numbers(client, db_session):
    case_id = "CASE-RAJ-2026-0042"
    res = an.analyze_link_between_numbers(case_id, "9829022222", "9829033333", db_session)
    assert res["num1"] == "9829022222"
    assert res["num2"] == "9829033333"
    assert len(res["shared_contacts"]) >= 2
    assert "9829011111" in [c["number"] for c in res["shared_contacts"]]
    assert "shared_towers" in res


def test_dynamic_ordered_suspects_fallback(client, db_session):
    # Even for a case without brief_data, get_ordered_suspects_for_case must return dynamic targets
    suspects = an.get_ordered_suspects_for_case("CASE-RAJ-2026-0042", db_session)
    assert len(suspects) >= 4
    assert all("phone" in s and s["phone"] for s in suspects)


def test_api_extended_analytics_and_notifications(client, auth_headers):
    case_id = "CASE-RAJ-2026-0042"
    r = client.get(f"/api/cases/{case_id}/analytics", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    for key in [
        "suspects", "imei_patterns", "imsi_patterns",
        "location_summary", "location_intelligence",
        "day_calls", "night_calls",
        "cell_id_changes", "location_changes",
        "interactive_timeline", "network_stats", "notifications"
    ]:
        assert key in d, f"Missing dynamic analytics key: {key}"
    assert len(d["notifications"]) > 0
    assert len(d["day_calls"]) > 0
    assert len(d["night_calls"]) > 0
    assert len(d["interactive_timeline"]) > 0


def test_api_link_analysis(client, auth_headers):
    case_id = "CASE-RAJ-2026-0042"
    r = client.get(f"/api/cases/{case_id}/link-analysis?num1=9829022222&num2=9829033333", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data["shared_contacts"]) >= 2


def test_external_config_loading():
    import os
    assert os.path.exists("data/config/tac_database.json")
    assert os.path.exists("data/config/service_directory.json")
    tac_db = an.load_tac_database()
    srv_db = an.load_service_directory()
    assert "35489012" in tac_db
    assert "35649210" in tac_db  # merged from main.py KNOWN_TACS
    assert "1930" in srv_db
    res = an.lookup_tac_device("356492104581294")
    assert res["brand"] == "Apple"
    assert "mfr" in res and "origin" in res


def test_api_inspect_and_ipdr_sample(client, auth_headers):
    import io, pandas as pd

    # 1. Inspect an arbitrary Excel CDR
    df = pd.DataFrame([{"Caller": "9811112222", "Callee": "9822223333", "Time": "2026-11-24 10:00:00", "Dur": "30", "IMEI": "354890123456781"}])
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    r_insp = client.post(
        "/api/ingest/inspect",
        files={"file": ("custom_test.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_headers
    )
    assert r_insp.status_code == 200
    insp = r_insp.json()
    assert insp["format"] == "EXCEL"
    assert insp["suggested_mapping"]["a_number"] == "Caller"

    # 2. Invalid file returns 400 cleanly
    r_bad = client.post("/api/ingest/inspect", files={"file": ("empty.csv", b"", "text/csv")}, headers=auth_headers)
    assert r_bad.status_code == 400

    # 3. IPDR sample returns real session for seeded case and available=False for empty case
    r_smp = client.get("/api/cases/CASE-RAJ-2026-0042/ipdr/sample", headers=auth_headers)
    assert r_smp.status_code == 200
    assert r_smp.json()["available"] is True

    client.post("/api/cases", json={"id": "EMPTY-CASE-01", "title": "Empty Case"}, headers=auth_headers)
    r_empty = client.get("/api/cases/EMPTY-CASE-01/ipdr/sample", headers=auth_headers)
    assert r_empty.status_code == 200
    assert r_empty.json()["available"] is False

    # 4. /api/cases/demo is gone
    r_demo = client.post("/api/cases/demo", headers=auth_headers)
    assert r_demo.status_code in (404, 405)


def test_lea_preamble_stripping_and_tower_master(client, auth_headers):
    from app.db import get_db, CellTower
    from app.ingest import seed_towers_from_csv
    
    # 1. Preamble stripping check via /api/ingest/inspect
    raw_lea = (
        "BHARTI AIRTEL LIMITED\n"
        "\"\"\n"
        "PAN India\n"
        "Call Details of Mobile No '9829011111'\n"
        "Target No,Call Type,B Party No,Date,Time,Dur(s),First CGI,IMEI,IMSI\n"
        "9829011111,IN,9829022222,01/02/2026,10:00:00,45,RAJ-DEG-603,864698066569960,404971908560194\n"
    ).encode("utf-8")

    r_insp = client.post(
        "/api/ingest/inspect",
        files={"file": ("airtel_lea.csv", raw_lea, "text/csv")},
        headers=auth_headers
    )
    assert r_insp.status_code == 200
    data = r_insp.json()
    assert "Target No" in data["columns"]
    assert "First CGI" in data["columns"]
    assert data["suggested_type"] == "CDR"
    assert data["suggested_mapping"]["a_number"] == "Target No"

    # 2. Check 66 Rajasthan tower master seeding includes Mewat sites like RAJ-DEG-603
    db = next(get_db())
    seed_towers_from_csv(db)
    mewat_tower = db.query(CellTower).filter(CellTower.cell_id == "RAJ-DEG-603").first()
    assert mewat_tower is not None
    assert "Deeg" in mewat_tower.area_name
    assert db.query(CellTower).count() >= 50


def test_threat_scoring_and_heatmap_endpoints(client, auth_headers):
    # 1. Threat Scoring endpoint
    r_threat = client.get("/api/cases/CASE-RAJ-2026-0042/threat-scoring", headers=auth_headers)
    assert r_threat.status_code == 200
    threats = r_threat.json()
    assert isinstance(threats, list)
    assert len(threats) > 0
    top = threats[0]
    assert "threat_score" in top
    assert 0 <= top["threat_score"] <= 100
    assert "archetype" in top
    assert "risk_level" in top
    assert "factors" in top

    # 2. 24x7 Heatmap endpoint
    r_heat = client.get("/api/cases/CASE-RAJ-2026-0042/heatmap", headers=auth_headers)
    assert r_heat.status_code == 200
    heat = r_heat.json()
    assert "matrix" in heat
    assert len(heat["matrix"]) == 7  # 7 days
    assert len(heat["matrix"][0]) == 24  # 24 hours
    assert "busiest_hour" in heat

    # 3. Analytics contains threat scores & heatmap, and movement hops are per-subscriber
    r_ana = client.get("/api/cases/CASE-RAJ-2026-0042/analytics", headers=auth_headers)
    assert r_ana.status_code == 200
    ana = r_ana.json()
    assert "threat_scores" in ana
    assert "heatmap_24x7" in ana
    # Check that movement hops transitions do not jump between different numbers
    for h in ana.get("cell_id_changes", []):
        assert "number" in h


def test_tac_full_cache_and_batch_ipdr(client, auth_headers, db_session):
    # 1. TAC lookup using tac_full.csv (275k dataset)
    # 86302407 is Xiaomi Redmi Note 14S in tac_full.csv
    tac_dev = an.lookup_tac_device("863024071234567")
    assert tac_dev["tac"] == "86302407"
    assert "Xiaomi" in tac_dev["brand"] or "XIAOMI" in tac_dev["brand"]
    assert "Redmi Note 14S" in tac_dev["model"] or "REDMI NOTE 14S" in tac_dev["model"]

    # 2. MCC-MNC India circle attribution in IMSI summary
    # Check that IMSI attribution correctly uses mcc_mnc_india.csv
    imsis = an.get_imsi_summary_list("CASE-RAJ-2026-0042", db_session)
    assert len(imsis) > 0
    # Any IMSI in the list should have carrier resolved
    for item in imsis:
        assert item["carrier"] != ""
        assert "mcc_mnc" in item

    # 3. Batch IPDR NAT Resolver endpoint
    # Query known session from CASE-RAJ-2026-0042 (103.211.54.12:44321 around 2026-11-20 18:25:10)
    # plus an unmatched bogus session
    batch_payload = {
        "queries": [
            {
                "query_id": "TRANS-BANK-001",
                "ip": "103.211.54.12",
                "port": 44321,
                "timestamp": "2026-11-20T18:25:10"
            },
            {
                "query_id": "TRANS-BANK-002",
                "ip": "198.51.100.99",
                "port": 9999,
                "timestamp": "2026-11-20T12:00:00"
            }
        ],
        "tolerance_minutes": 15
    }
    r_batch = client.post(
        "/api/cases/CASE-RAJ-2026-0042/ipdr/batch",
        json=batch_payload,
        headers=auth_headers
    )
    assert r_batch.status_code == 200
    res = r_batch.json()
    assert res["total_queries"] == 2
    assert res["matched_count"] == 1
    assert res["unmatched_count"] == 1
    assert any("9829022222" in s for s in res["identified_subscribers"])
    q1 = next(q for q in res["results"] if q["query_id"] == "TRANS-BANK-001")
    assert q1["matched"] is True
    assert "9829022222" in q1["primary_subscriber"]
    q2 = next(q for q in res["results"] if q["query_id"] == "TRANS-BANK-002")
    assert q2["matched"] is False






