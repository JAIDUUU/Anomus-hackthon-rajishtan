import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_full_demo():
    print("\n--- 1. Testing Login ---")
    login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "io_sharma",
        "password": "IO@RajPolice2026"
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token_io = login_res.json()["access_token"]
    headers_io = {"Authorization": f"Bearer {token_io}"}
    print("✓ IO Ajay Sharma logged in successfully.")

    # Senior officer login
    sp_res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "sp_verma",
        "password": "SP@RajPolice2026"
    })
    assert sp_res.status_code == 200
    token_sp = sp_res.json()["access_token"]
    headers_sp = {"Authorization": f"Bearer {token_sp}"}
    print("✓ SP Sangeeta Verma logged in successfully.")

    print("\n--- 2. Testing 1-Click Demo Loader ---")
    demo_res = requests.post(f"{BASE_URL}/api/cases/demo", headers=headers_io)
    assert demo_res.status_code == 200, f"Demo load failed: {demo_res.text}"
    case_id = demo_res.json()["case_id"]
    print(f"✓ Case '{case_id}' loaded with synthetic data.")

    # Check case stats
    case_info = requests.get(f"{BASE_URL}/api/cases/{case_id}", headers=headers_io).json()
    cdr_count = case_info["stats"]["cdr_count"]
    ipdr_count = case_info["stats"]["ipdr_count"]
    print(f"✓ Total Ingested CDR: {cdr_count}, IPDR: {ipdr_count}")
    assert cdr_count > 1800, f"Expected ~2000 CDR rows, got {cdr_count}"
    assert ipdr_count > 250, f"Expected ~300 IPDR rows, got {ipdr_count}"

    print("\n--- 3. Testing Communication Patterns for S1 (9829022222) ---")
    pat_res = requests.get(f"{BASE_URL}/api/cases/{case_id}/patterns?number=9829022222", headers=headers_io).json()
    print(f"✓ S1 Total Calls: {pat_res['total_calls']}, In/Out Ratio: {pat_res['in_out_ratio']}")
    assert pat_res["total_calls"] > 0
    top_contact_numbers = [c["number"] for c in pat_res["top_contacts"]]
    print(f"✓ Top Contacts for S1: {top_contact_numbers[:3]}")

    print("\n--- 4. Testing Cross-Suspect Common Numbers (S1 & S2) ---")
    comm_res = requests.get(f"{BASE_URL}/api/cases/{case_id}/common?numbers=9829022222,9829033333", headers=headers_io).json()
    common_nums = [c["common_number"] for c in comm_res["common_contacts"]]
    print(f"✓ Common Contacts between S1 & S2: {common_nums}")
    assert "9414088888" in common_nums, "Expected shared contact 9414088888"
    assert "9414099999" in common_nums, "Expected shared contact 9414099999"
    # Kingpin should also be common
    assert "9829011111" in common_nums, "Expected kingpin 9829011111 in common"

    print("\n--- 5. Testing Physical Meeting Detection ---")
    meet_res = requests.get(f"{BASE_URL}/api/cases/{case_id}/meetings?num1=9829022222&num2=9829033333&window=30", headers=headers_io).json()
    meetings = meet_res["meetings"]
    print(f"✓ Detected {len(meetings)} physical meeting(s) between S1 & S2.")
    assert len(meetings) > 0, "Expected physical meeting at cell tower RAJ-JPR-102"
    first_meeting = meetings[0]
    print(f"  - Cell: {first_meeting['cell_id']}, Area: {first_meeting['area_name']}, Time delta: {first_meeting['time_diff_sec']}s")
    assert any(m["cell_id"] == "RAJ-JPR-102" for m in meetings), "Expected meeting at RAJ-JPR-102"
    mi_meeting = next(m for m in meetings if m["cell_id"] == "RAJ-JPR-102")
    print(f"  - Target rendezvous at {mi_meeting['area_name']} ({mi_meeting['cell_id']}) with delta {mi_meeting['time_diff_sec']}s")

    print("\n--- 6. Testing IMEI / SIM Swap Anomaly Detection ---")
    dev_res = requests.get(f"{BASE_URL}/api/cases/{case_id}/device-changes", headers=headers_io).json()
    swaps = dev_res["multi_number_imeis"]
    print(f"✓ Detected {len(swaps)} IMEI(s) associated with multiple SIM numbers.")
    s3_swap = next((s for s in swaps if s["imei"] == "354890123456783"), None)
    assert s3_swap is not None, "Expected S3 IMEI 354890123456783 to show SIM swap"
    print(f"  - S3 IMEI {s3_swap['imei']} numbers: {s3_swap['numbers']}")
    assert "9829044444" in s3_swap["numbers"]
    assert "9829077777" in s3_swap["numbers"]

    print("\n--- 7. Testing IPDR Session Match ---")
    ipdr_res = requests.get(f"{BASE_URL}/api/cases/{case_id}/ipdr/match?ip=103.211.54.12&port=44321&timestamp=2026-11-20+18:25:10", headers=headers_io).json()
    assert ipdr_res["match_found"] is True
    print(f"✓ Matched subscriber: {ipdr_res['primary_subscriber']}, App: {ipdr_res['sessions'][0]['app_hint']}")
    assert "9829022222" in ipdr_res["primary_subscriber"]
    assert "Telegram" in ipdr_res["sessions"][0]["app_hint"]

    print("\n--- 8. Testing AI Assistant Chat ---")
    # Query 1: Frequent contacts
    ai_q1 = requests.post(f"{BASE_URL}/api/cases/{case_id}/assistant", headers=headers_io, json={
        "query": "Who are the top frequent contacts of S1 9829022222?"
    }).json()
    print(f"✓ AI Q1 Answer:\n{ai_q1['answer'][:150]}...")
    assert ai_q1["status"] == "pending_verification"
    assert len(ai_q1["evidence"]) > 0

    # Query 2: Hindi query for SIM swap
    ai_q2 = requests.post(f"{BASE_URL}/api/cases/{case_id}/assistant", headers=headers_io, json={
        "query": "S3 9829044444 ne kab sim badla ya device change kiya?"
    }).json()
    print(f"✓ AI Q2 (Hindi) Answer:\n{ai_q2['answer'][:150]}...")
    assert "SIM Swap Detected" in ai_q2["answer"]

    # Query 3: Guardrail test
    ai_q3 = requests.post(f"{BASE_URL}/api/cases/{case_id}/assistant", headers=headers_io, json={
        "query": "Call me kya baat hui aur recording sunao"
    }).json()
    print(f"✓ AI Q3 (Guardrail) Answer:\n{ai_q3['answer'][:150]}...")
    assert "Information Not Available in Uploaded Data" in ai_q3["answer"]

    print("\n--- 9. Testing Senior Officer Observation Verification ---")
    obs_id = ai_q1["observation_id"]
    verify_res = requests.post(f"{BASE_URL}/api/cases/{case_id}/observations/{obs_id}/verify", headers=headers_sp, json={
        "action": "verify",
        "notes": "Verified against operator raw logs under Section 65B."
    })
    assert verify_res.status_code == 200
    print(f"✓ Observation #{obs_id} verified by {verify_res.json()['verified_by']}.")

    # Verify that IO cannot verify observation (403 Forbidden)
    io_verify_attempt = requests.post(f"{BASE_URL}/api/cases/{case_id}/observations/{obs_id}/verify", headers=headers_io, json={
        "action": "verify"
    })
    assert io_verify_attempt.status_code == 403
    print("✓ IO cannot verify observation (correctly restricted with 403 Forbidden).")

    print("\n--- 10. Testing Reports Generation (PDF & XLSX) ---")
    pdf_res = requests.get(f"{BASE_URL}/api/cases/{case_id}/report?format=pdf", headers=headers_io)
    assert pdf_res.status_code == 200
    assert len(pdf_res.content) > 1000
    assert pdf_res.headers["content-type"] == "application/pdf"
    print(f"✓ PDF report generated successfully ({len(pdf_res.content)} bytes).")

    xlsx_res = requests.get(f"{BASE_URL}/api/cases/{case_id}/report?format=xlsx", headers=headers_io)
    assert xlsx_res.status_code == 200
    assert len(xlsx_res.content) > 1000
    print(f"✓ Excel report generated successfully ({len(xlsx_res.content)} bytes).")

    print("\n--- 11. Testing Audit Log ---")
    audit_res = requests.get(f"{BASE_URL}/api/audit", headers=headers_sp).json()
    assert len(audit_res) > 5
    actions = [a["action"] for a in audit_res]
    print(f"✓ Audit logs recorded: {set(actions)}")
    assert "LOGIN_SUCCESS" in actions
    assert "AI_QUERY" in actions
    assert "VERIFY_OBSERVATION" in actions
    assert "REPORT_DOWNLOAD" in actions

    print("\n==============================================")
    print("✅ ALL DEMO FLOW SCENARIOS PASSED WITH 100% SUCCESS!")
    print("==============================================")

if __name__ == "__main__":
    test_full_demo()
