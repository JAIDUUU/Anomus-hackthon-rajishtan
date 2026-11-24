def test_full_demo(client):
    login_res = client.post("/api/auth/login", json={
        "username": "io_sharma",
        "password": "IO@RajPolice2026"
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    headers_io = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    sp_res = client.post("/api/auth/login", json={
        "username": "sp_verma",
        "password": "SP@RajPolice2026"
    })
    assert sp_res.status_code == 200
    headers_sp = {"Authorization": f"Bearer {sp_res.json()['access_token']}"}

    # Verify /api/cases/demo endpoint is removed
    demo_removed = client.post("/api/cases/demo", headers=headers_io)
    assert demo_removed.status_code in (404, 405)

    case_id = "CASE-RAJ-2026-0042"
    case_info = client.get(f"/api/cases/{case_id}", headers=headers_io).json()
    assert case_info["stats"]["cdr_count"] > 1800
    assert case_info["stats"]["ipdr_count"] > 250

    pat_res = client.get(f"/api/cases/{case_id}/patterns?number=9829022222", headers=headers_io).json()
    assert pat_res["total_calls"] > 0

    comm_res = client.get(f"/api/cases/{case_id}/common?numbers=9829022222,9829033333", headers=headers_io).json()
    common_nums = [c["common_number"] for c in comm_res["common_contacts"]]
    assert "9414088888" in common_nums
    assert "9414099999" in common_nums
    assert "9829011111" in common_nums

    meet_res = client.get(f"/api/cases/{case_id}/meetings?num1=9829022222&num2=9829033333&window=30", headers=headers_io).json()
    meetings = meet_res["meetings"]
    assert len(meetings) > 0
    assert any(m["cell_id"] == "RAJ-JPR-102" for m in meetings)

    dev_res = client.get(f"/api/cases/{case_id}/device-changes", headers=headers_io).json()
    s3_swap = next((s for s in dev_res["multi_number_imeis"] if s["imei"] == "354890123456783"), None)
    assert s3_swap is not None
    assert "9829044444" in s3_swap["numbers"]
    assert "9829077777" in s3_swap["numbers"]

    ipdr_res = client.get(f"/api/cases/{case_id}/ipdr/match?ip=103.211.54.12&port=44321&timestamp=2026-11-20+18:25:10", headers=headers_io).json()
    assert ipdr_res["match_found"] is True
    assert "9829022222" in ipdr_res["primary_subscriber"]

    ai_q1 = client.post(f"/api/cases/{case_id}/assistant", headers=headers_io, json={
        "query": "Who are the top frequent contacts of S1 9829022222?"
    }).json()
    assert ai_q1["status"] == "pending_verification"
    assert len(ai_q1["evidence"]) > 0

    ai_q2 = client.post(f"/api/cases/{case_id}/assistant", headers=headers_io, json={
        "query": "S3 9829044444 ne kab sim badla ya device change kiya?"
    }).json()
    assert "SIM Swap Detected" in ai_q2["answer"]

    ai_q3 = client.post(f"/api/cases/{case_id}/assistant", headers=headers_io, json={
        "query": "Call me kya baat hui aur recording sunao"
    }).json()
    assert "Information Not Available in Uploaded Data" in ai_q3["answer"]

    obs_id = ai_q1["observation_id"]
    verify_res = client.post(f"/api/cases/{case_id}/observations/{obs_id}/verify", headers=headers_sp, json={
        "action": "verify",
        "notes": "Verified against operator raw logs under Section 65B."
    })
    assert verify_res.status_code == 200

    io_verify_attempt = client.post(f"/api/cases/{case_id}/observations/{obs_id}/verify", headers=headers_io, json={
        "action": "verify"
    })
    assert io_verify_attempt.status_code == 403

    pdf_res = client.get(f"/api/cases/{case_id}/report?format=pdf", headers=headers_io)
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"

    xlsx_res = client.get(f"/api/cases/{case_id}/report?format=xlsx", headers=headers_io)
    assert xlsx_res.status_code == 200

    audit_res = client.get("/api/audit", headers=headers_sp).json()
    actions = [a["action"] for a in audit_res]
    assert "LOGIN_SUCCESS" in actions
    assert "AI_QUERY" in actions
    assert "VERIFY_OBSERVATION" in actions
    assert "REPORT_DOWNLOAD" in actions
