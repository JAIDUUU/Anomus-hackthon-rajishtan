import os
import json
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Query, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from pydantic import BaseModel

from app.db import (
    get_db, init_db, Case, CDRRecord, IPDRRecord, CellTower,
    ImportBatch, AIObservation, AuditLog, User
)
from app.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_role, seed_default_users
)
from app.audit import log_audit_event, get_audit_logs
from app.ingest import (
    get_available_mappings, save_mapping_config,
    ingest_cdr_data, ingest_ipdr_data, seed_towers_from_csv,
    inspect_uploaded_file
)
from app.analysis import (
    analyze_communication_patterns, find_common_numbers,
    get_location_timeline, detect_meetings, detect_imei_sim_changes,
    get_network_graph_data, get_suspect_numbers_for_case,
    get_ordered_suspects_for_case, analyze_link_between_numbers,
    lookup_tac_device, get_executive_metrics, get_raw_cdr_records,
    get_mfc_analysis, get_day_night_analysis, get_first_last_calls,
    get_missing_dates_analysis, get_movement_and_cell_changes,
    get_service_and_company_numbers, get_international_intelligence,
    get_imei_summary_list, get_imsi_summary_list, global_search
)
from app.ipdr import match_ipdr_session, get_subscriber_ipdr_summary
from app.assistant import run_ai_assistant
from app.reports import generate_pdf_report, generate_excel_report

app = FastAPI(
    title="Rajasthan Police CDR/IPDR Analysis Tool & AI Assistant",
    description="PS03 Prototype for Rajasthan Police Hackathon 2026",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


@app.on_event("startup")
def on_startup():
    init_db()
    db = next(get_db())
    try:
        seed_default_users(db)
        seed_towers_from_csv(db)
    finally:
        db.close()


# Pydantic schemas
class LoginRequest(BaseModel):
    username: str
    password: str


class CreateCaseRequest(BaseModel):
    id: str
    title: str
    description: str = ""


class AIQueryRequest(BaseModel):
    query: str


class ObservationVerifyRequest(BaseModel):
    action: str  # "verify" or "reject"
    notes: str = ""


# ----------------- AUTH ROUTES -----------------
@app.post("/api/auth/login")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        log_audit_event(
            db, action="LOGIN_FAILED",
            details={"attempted_username": req.username},
            request=request
        )
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"sub": user.username, "role": user.role})
    log_audit_event(
        db, action="LOGIN_SUCCESS",
        details={"username": user.username, "role": user.role},
        user=user, request=request
    )

    response = Response(
        content=json.dumps({
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "full_name": user.full_name,
                "badge_number": user.badge_number
            }
        }),
        media_type="application/json"
    )
    # Also set cookie for seamless browser interactions
    response.set_cookie(key="access_token", value=token, httponly=False, samesite="lax")
    return response


@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "full_name": current_user.full_name,
        "badge_number": current_user.badge_number
    }


# ----------------- CASE MANAGEMENT -----------------
@app.get("/api/cases")
def list_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    cases = db.query(Case).order_by(Case.created_at.desc()).all()
    results = []
    for c in cases:
        results.append({
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "status": c.status,
            "created_by": c.created_by,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "cdr_count": db.query(CDRRecord).filter(CDRRecord.case_id == c.id).count(),
            "ipdr_count": db.query(IPDRRecord).filter(IPDRRecord.case_id == c.id).count()
        })
    return results


@app.post("/api/cases")
def create_case(
    req: CreateCaseRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    existing = db.query(Case).filter(Case.id == req.id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Case with ID '{req.id}' already exists")

    new_case = Case(
        id=req.id,
        title=req.title,
        description=req.description,
        created_by=current_user.username
    )
    db.add(new_case)
    db.commit()

    log_audit_event(
        db, action="CREATE_CASE",
        details={"case_id": req.id, "title": req.title},
        user=current_user, request=request
    )
    return {"message": "Case created successfully", "case_id": req.id}


@app.get("/api/cases/{case_id}")
def get_case_details(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Case not found")

    brief = json.loads(c.brief_data) if c.brief_data else {}
    cdr_count = db.query(CDRRecord).filter(CDRRecord.case_id == case_id).count()
    ipdr_count = db.query(IPDRRecord).filter(IPDRRecord.case_id == case_id).count()
    batch_count = db.query(ImportBatch).filter(ImportBatch.case_id == case_id).count()

    return {
        "id": c.id,
        "title": c.title,
        "description": c.description,
        "status": c.status,
        "created_by": c.created_by,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "brief_data": brief,
        "stats": {
            "cdr_count": cdr_count,
            "ipdr_count": ipdr_count,
            "batch_count": batch_count
        }
    }


# ----------------- 1-CLICK DEMO CASE LOADER -----------------
@app.post("/api/cases/demo")
def load_demo_case(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    """
    1-Click loader that initializes the demo case:
    1. Creates case CASE-RAJ-2026-0042
    2. Loads synthetic towers
    3. Ingests cdr_operator_A.csv, cdr_operator_B.csv, ipdr_operator_A.csv
    4. Seeds initial AI observations
    """
    case_id = "CASE-RAJ-2026-0042"

    # Seed towers first
    seed_towers_from_csv(db)

    # Read case brief
    brief_path = os.path.join(DATA_DIR, "case_brief.json")
    brief_data = "{}"
    if os.path.exists(brief_path):
        with open(brief_path, "r", encoding="utf-8") as f:
            brief_data = f.read()

    existing_case = db.query(Case).filter(Case.id == case_id).first()
    if not existing_case:
        demo_case = Case(
            id=case_id,
            title="Operation Maru-Drishti (Cyber Syndicate Analysis)",
            description="Synthetic investigation involving 4 syndicate operatives (S1-S4), a central Kingpin, shared contacts, SIM swaps, and meeting rendezvous in Jaipur.",
            created_by=current_user.username,
            brief_data=brief_data
        )
        db.add(demo_case)
        db.commit()
    else:
        existing_case.brief_data = brief_data
        db.commit()

    mappings = get_available_mappings()
    results = {}

    # Ingest CDR A
    cdr_a_path = os.path.join(DATA_DIR, "cdr_operator_A.csv")
    if os.path.exists(cdr_a_path):
        # Check if already imported
        already = db.query(ImportBatch).filter(
            ImportBatch.case_id == case_id,
            ImportBatch.filename == "cdr_operator_A.csv"
        ).first()
        if not already:
            with open(cdr_a_path, "rb") as f:
                res_a = ingest_cdr_data(
                    f.read(), "cdr_operator_A.csv", case_id,
                    mappings.get("operator_a", {}), db
                )
                results["operator_a"] = res_a

    # Ingest CDR B
    cdr_b_path = os.path.join(DATA_DIR, "cdr_operator_B.csv")
    if os.path.exists(cdr_b_path):
        already = db.query(ImportBatch).filter(
            ImportBatch.case_id == case_id,
            ImportBatch.filename == "cdr_operator_B.csv"
        ).first()
        if not already:
            with open(cdr_b_path, "rb") as f:
                res_b = ingest_cdr_data(
                    f.read(), "cdr_operator_B.csv", case_id,
                    mappings.get("operator_b", {}), db
                )
                results["operator_b"] = res_b

    # Ingest IPDR A
    ipdr_path = os.path.join(DATA_DIR, "ipdr_operator_A.csv")
    if os.path.exists(ipdr_path):
        already = db.query(ImportBatch).filter(
            ImportBatch.case_id == case_id,
            ImportBatch.filename == "ipdr_operator_A.csv"
        ).first()
        if not already:
            with open(ipdr_path, "rb") as f:
                res_ipdr = ingest_ipdr_data(
                    f.read(), "ipdr_operator_A.csv", case_id,
                    mappings.get("ipdr_operator_a", {}), db
                )
                results["ipdr"] = res_ipdr

    log_audit_event(
        db, action="LOAD_DEMO_CASE",
        details={"case_id": case_id, "ingested": list(results.keys())},
        user=current_user, request=request
    )

    return {
        "status": "success",
        "case_id": case_id,
        "message": "Demo case loaded successfully with synthetic CDR and IPDR data.",
        "results": results
    }


# ----------------- FEATURE 1: DATA INGESTION -----------------
@app.get("/api/mappings")
def list_mappings():
    return get_available_mappings()


@app.post("/api/mappings")
def save_mapping(
    mapping_id: str = Form(...),
    config_json: str = Form(...),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    try:
        config = json.loads(config_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    saved_id = save_mapping_config(mapping_id, config)
    return {"status": "saved", "mapping_id": saved_id}


@app.post("/api/ingest/inspect")
async def inspect_file_headers(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    content = await file.read()
    try:
        return inspect_uploaded_file(content, file.filename or "upload.csv")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.post("/api/cases/{case_id}/upload")
async def upload_case_file(
    case_id: str,
    request: Request,
    file: UploadFile = File(...),
    file_type: str = Form("CDR"),  # CDR or IPDR
    mapping_name: str = Form("auto"),  # mapping key from data/mappings or 'auto'
    custom_mapping_json: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer"))
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    content = await file.read()
    mappings = get_available_mappings()

    if custom_mapping_json:
        try:
            parsed = json.loads(custom_mapping_json)
            chosen_mapping = parsed if "mappings" in parsed else {"name": "Custom Dynamic Mapping", "mappings": parsed}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid custom mapping JSON: {e}")
    elif mapping_name and mapping_name in mappings:
        chosen_mapping = mappings[mapping_name]
    else:
        # Dynamic auto-inspection when no preset mapping is matched
        try:
            inspected = inspect_uploaded_file(content, file.filename or "upload.csv")
            chosen_mapping = {"name": "Auto-Detected Dynamic", "mappings": inspected["suggested_mapping"]}
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))

    try:
        if file_type.upper() == "IPDR":
            summary = ingest_ipdr_data(content, file.filename or "upload.csv", case_id, chosen_mapping, db)
        else:
            summary = ingest_cdr_data(content, file.filename or "upload.csv", case_id, chosen_mapping, db)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    log_audit_event(
        db, action="UPLOAD",
        details={
            "case_id": case_id,
            "filename": file.filename,
            "file_type": file_type,
            "valid_rows": summary["valid_rows"],
            "rejected_rows": summary["rejected_rows"]
        },
        user=current_user, request=request
    )

    return summary


@app.get("/api/cases/{case_id}/batches")
def get_case_batches(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    batches = db.query(ImportBatch).filter(ImportBatch.case_id == case_id).order_by(ImportBatch.created_at.desc()).all()
    results = []
    for b in batches:
        summary = json.loads(b.validation_summary_json) if b.validation_summary_json else {}
        results.append({
            "id": b.id,
            "filename": b.filename,
            "file_type": b.file_type,
            "mapping_name": b.mapping_name,
            "total_rows": b.total_rows,
            "valid_rows": b.valid_rows,
            "rejected_rows": b.rejected_rows,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "summary": summary
        })
    return results


# ----------------- FEATURE 2: COMMUNICATION PATTERNS -----------------
@app.get("/api/cases/{case_id}/patterns")
def get_patterns(
    case_id: str,
    number: str = Query(..., description="Phone number to analyze"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer"))
):
    clean_num = number.strip().replace("+91", "").lstrip("0")
    res = analyze_communication_patterns(clean_num, case_id, db)
    log_audit_event(
        db, action="QUERY",
        details={"type": "patterns", "number": clean_num, "case_id": case_id},
        user=current_user, request=request
    )
    return res


# ----------------- FEATURE 3: CROSS-SUSPECT CORRELATION -----------------
@app.get("/api/cases/{case_id}/common")
def get_common(
    case_id: str,
    numbers: str = Query(..., description="Comma-separated phone numbers"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer"))
):
    num_list = [n.strip().replace("+91", "").lstrip("0") for n in numbers.split(",") if n.strip()]
    res = find_common_numbers(num_list, case_id, db)
    log_audit_event(
        db, action="QUERY",
        details={"type": "common_numbers", "numbers": num_list, "case_id": case_id},
        user=current_user, request=request
    )
    return res


# ----------------- FEATURE 4: LOCATION & DEVICE -----------------
@app.get("/api/cases/{case_id}/towers/timeline")
def get_tower_timeline(
    case_id: str,
    number: str = Query(..., description="Phone number to trace"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer"))
):
    clean_num = number.strip().replace("+91", "").lstrip("0")
    res = get_location_timeline(clean_num, case_id, db)
    log_audit_event(
        db, action="QUERY",
        details={"type": "location_timeline", "number": clean_num, "case_id": case_id},
        user=current_user, request=request
    )
    return res


@app.get("/api/cases/{case_id}/meetings")
def get_meetings(
    case_id: str,
    num1: str = Query(...),
    num2: str = Query(...),
    window: int = Query(30, description="Time window in minutes"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer"))
):
    c_n1 = num1.strip().replace("+91", "").lstrip("0")
    c_n2 = num2.strip().replace("+91", "").lstrip("0")
    res = detect_meetings(c_n1, c_n2, case_id, db, window)
    log_audit_event(
        db, action="QUERY",
        details={"type": "meeting_detection", "num1": c_n1, "num2": c_n2, "window": window},
        user=current_user, request=request
    )
    return {"num1": c_n1, "num2": c_n2, "window_minutes": window, "meetings": res}


@app.get("/api/cases/{case_id}/device-changes")
def get_device_changes(
    case_id: str,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer"))
):
    res = detect_imei_sim_changes(case_id, db)
    log_audit_event(
        db, action="QUERY",
        details={"type": "device_changes", "case_id": case_id},
        user=current_user, request=request
    )
    return res


# ----------------- FEATURE 5: IPDR ANALYSIS -----------------
@app.get("/api/cases/{case_id}/ipdr/match")
def match_ipdr(
    case_id: str,
    ip: str = Query(...),
    port: int = Query(...),
    timestamp: str = Query(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer"))
):
    res = match_ipdr_session(case_id, ip, port, timestamp, db)
    log_audit_event(
        db, action="QUERY",
        details={"type": "ipdr_match", "ip": ip, "port": port, "timestamp": timestamp},
        user=current_user, request=request
    )
    return res


@app.get("/api/cases/{case_id}/ipdr/subscriber")
def get_subscriber_ipdr(
    case_id: str,
    subscriber: str = Query(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer"))
):
    res = get_subscriber_ipdr_summary(subscriber, case_id, db)
    log_audit_event(
        db, action="QUERY",
        details={"type": "ipdr_subscriber", "subscriber": subscriber},
        user=current_user, request=request
    )
    return res


@app.get("/api/cases/{case_id}/ipdr/sample")
def get_ipdr_sample(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    """Return one actual uploaded IPDR session from DB for quick testing (zero hardcoding)."""
    rec = db.query(IPDRRecord).filter(IPDRRecord.case_id == case_id).order_by(IPDRRecord.id.asc()).first()
    if not rec:
        return {"available": False}
    return {
        "available": True,
        "source_ip": rec.source_ip,
        "source_port": rec.source_port,
        "timestamp": rec.session_start.replace("T", " "),
        "subscriber": rec.subscriber_number
    }


# ----------------- FEATURE 6: NETWORK GRAPH -----------------
@app.get("/api/cases/{case_id}/network")
def get_network(
    case_id: str,
    min_calls: int = Query(1),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer"))
):
    res = get_network_graph_data(case_id, db, min_calls)
    log_audit_event(
        db, action="QUERY",
        details={"type": "network_graph", "min_calls": min_calls, "case_id": case_id},
        user=current_user, request=request
    )
    return res


# ----------------- FEATURE 7: AI ASSISTANT & OBSERVATIONS -----------------
@app.post("/api/cases/{case_id}/assistant")
def ask_assistant(
    case_id: str,
    req: AIQueryRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer"))
):
    res = run_ai_assistant(req.query, case_id, current_user.role, db)
    log_audit_event(
        db, action="AI_QUERY",
        details={"query": req.query, "observation_id": res["observation_id"]},
        user=current_user, request=request
    )
    return res


@app.get("/api/cases/{case_id}/observations")
def list_observations(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    observations = db.query(AIObservation).filter(AIObservation.case_id == case_id).order_by(AIObservation.created_at.desc()).all()
    results = []
    for o in observations:
        results.append({
            "id": o.id,
            "query": o.query_text,
            "answer": o.answer_text,
            "evidence": json.loads(o.evidence_json) if o.evidence_json else [],
            "confidence_note": o.confidence_note,
            "status": o.status,
            "verified_by": o.verified_by,
            "verified_at": o.verified_at.isoformat() if o.verified_at else None,
            "officer_notes": o.officer_notes,
            "suggested_followups": json.loads(o.suggested_followups) if o.suggested_followups else [],
            "suggested_filters": json.loads(o.suggested_filters) if o.suggested_filters else {},
            "created_at": o.created_at.isoformat() if o.created_at else None
        })
    return results


@app.post("/api/cases/{case_id}/observations/{obs_id}/verify")
def verify_observation(
    case_id: str,
    obs_id: int,
    req: ObservationVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("senior_officer"))  # Only senior officer can verify!
):
    obs = db.query(AIObservation).filter(
        AIObservation.id == obs_id,
        AIObservation.case_id == case_id
    ).first()
    if not obs:
        raise HTTPException(status_code=404, detail="AI observation not found")

    new_status = "verified" if req.action.lower() == "verify" else "rejected"
    obs.status = new_status
    obs.verified_by = f"{current_user.full_name} ({current_user.badge_number})"
    obs.verified_at = datetime.utcnow()
    obs.officer_notes = req.notes
    db.commit()

    log_audit_event(
        db, action="VERIFY_OBSERVATION",
        details={"obs_id": obs_id, "status": new_status, "notes": req.notes},
        user=current_user, request=request
    )
    return {
        "status": "success",
        "observation_id": obs.id,
        "new_status": new_status,
        "verified_by": obs.verified_by
    }


# ----------------- EVIDENCE RECORD MODAL -----------------
@app.get("/api/cases/{case_id}/record/{record_type}/{source_row}")
def get_evidence_record(
    case_id: str,
    record_type: str,
    source_row: int,
    source_file: str = Query(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer"))
):
    """
    Opens exact raw record and fields for evidence trail.
    """
    if record_type.upper() == "IPDR":
        rec = db.query(IPDRRecord).filter(
            IPDRRecord.case_id == case_id,
            IPDRRecord.source_row == source_row,
            IPDRRecord.source_file == source_file
        ).first()
    else:
        rec = db.query(CDRRecord).filter(
            CDRRecord.case_id == case_id,
            CDRRecord.source_row == source_row,
            CDRRecord.source_file == source_file
        ).first()

    if not rec:
        raise HTTPException(status_code=404, detail="Evidence source record not found")

    raw_data = json.loads(rec.raw_data_json) if rec.raw_data_json else {}

    log_audit_event(
        db, action="EVIDENCE_VIEW",
        details={"record_type": record_type, "source_file": source_file, "source_row": source_row},
        user=current_user, request=request
    )

    return {
        "source_file": rec.source_file,
        "source_row": rec.source_row,
        "record_id": rec.id,
        "raw_payload": raw_data
    }


# ----------------- FEATURE 8: REPORTS -----------------
@app.get("/api/cases/{case_id}/report")
def download_report(
    case_id: str,
    format: str = Query("pdf", pattern="^(pdf|xlsx)$"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer"))
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    log_audit_event(
        db, action="REPORT_DOWNLOAD",
        details={"case_id": case_id, "format": format},
        user=current_user, request=request
    )

    filename_prefix = f"Report_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if format == "pdf":
        buf = generate_pdf_report(case_id, db)
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename_prefix}.pdf"}
        )
    else:
        buf = generate_excel_report(case_id, db)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename_prefix}.xlsx"}
        )


# ----------------- TAC LOOKUP -----------------
@app.get("/api/tac/{imei}")
def get_tac_info(
    imei: str,
    request: Request = None,
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    return lookup_tac_device(imei)


# ----------------- EXECUTIVE DASHBOARD METRICS -----------------
@app.get("/api/dashboard/metrics")
def get_dashboard_metrics(
    case_id: str | None = Query(None, description="Optional Case ID to filter metrics"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    if case_id:
        c = db.query(Case).filter(Case.id == case_id).first()
        if not c:
            raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    res = get_executive_metrics(case_id, db)
    log_audit_event(
        db, action="QUERY",
        details={"type": "dashboard_metrics", "case_id": case_id},
        user=current_user, request=request
    )
    return res


# ----------------- RAW CDR PAGINATED QUERY -----------------
@app.get("/api/cases/{case_id}/raw-cdr")
def get_raw_cdr(
    case_id: str,
    search: str = Query("", description="Search term for phone, imei, imsi, tower"),
    call_type: str = Query("", description="Filter call type: IN, OUT, SMS"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=500, description="Records per page"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    res = get_raw_cdr_records(case_id, db, page=page, limit=limit, search=search, call_type=call_type)
    log_audit_event(
        db, action="QUERY",
        details={"type": "raw_cdr", "case_id": case_id, "page": page, "limit": limit, "search": search, "call_type": call_type},
        user=current_user, request=request
    )
    return res


# ----------------- MOST FREQUENT CONTACTS (MFC) -----------------
@app.get("/api/cases/{case_id}/mfc")
def get_mfc(
    case_id: str,
    target_number: str | None = Query(None, description="Optional target phone number to analyze"),
    top: int = Query(25, ge=1, le=200, description="Number of top contacts to return"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    res = get_mfc_analysis(case_id, db, target_number=target_number, top=top)
    log_audit_event(
        db, action="QUERY",
        details={"type": "mfc", "case_id": case_id, "target_number": target_number, "top": top},
        user=current_user, request=request
    )
    return res


# ----------------- DAY VS NIGHT FORENSICS -----------------
@app.get("/api/cases/{case_id}/day-night")
def get_day_night(
    case_id: str,
    target_number: str | None = Query(None, description="Optional target phone number"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    res = get_day_night_analysis(case_id, db, target_number=target_number)
    log_audit_event(
        db, action="QUERY",
        details={"type": "day_night", "case_id": case_id, "target_number": target_number},
        user=current_user, request=request
    )
    return res


# ----------------- FIRST / LAST CALL PER CONTACT -----------------
@app.get("/api/cases/{case_id}/first-last")
def get_first_last(
    case_id: str,
    target_number: str | None = Query(None, description="Optional target phone number"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    res = get_first_last_calls(case_id, db, target_number=target_number)
    log_audit_event(
        db, action="QUERY",
        details={"type": "first_last", "case_id": case_id, "target_number": target_number},
        user=current_user, request=request
    )
    return res


# ----------------- MISSING DATES / SILENCE ANALYSIS -----------------
@app.get("/api/cases/{case_id}/missing-dates")
def get_missing_dates(
    case_id: str,
    target_number: str | None = Query(None, description="Optional target phone number"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    res = get_missing_dates_analysis(case_id, db, target_number=target_number)
    log_audit_event(
        db, action="QUERY",
        details={"type": "missing_dates", "case_id": case_id, "target_number": target_number},
        user=current_user, request=request
    )
    return res


# ----------------- MOVEMENT AND CELL CHANGES -----------------
@app.get("/api/cases/{case_id}/movement")
def get_movement(
    case_id: str,
    target_number: str | None = Query(None, description="Optional target phone number"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    res = get_movement_and_cell_changes(case_id, db, target_number=target_number)
    log_audit_event(
        db, action="QUERY",
        details={"type": "movement", "case_id": case_id, "target_number": target_number},
        user=current_user, request=request
    )
    return res


# ----------------- SERVICE AND COMPANY NUMBERS -----------------
@app.get("/api/cases/{case_id}/service-numbers")
def get_service_numbers_endpoint(
    case_id: str,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    res = get_service_and_company_numbers(case_id, db)
    log_audit_event(
        db, action="QUERY",
        details={"type": "service_numbers", "case_id": case_id},
        user=current_user, request=request
    )
    return res


# ----------------- INTERNATIONAL INTELLIGENCE -----------------
@app.get("/api/cases/{case_id}/international")
def get_international_endpoint(
    case_id: str,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    res = get_international_intelligence(case_id, db)
    log_audit_event(
        db, action="QUERY",
        details={"type": "international", "case_id": case_id},
        user=current_user, request=request
    )
    return res


# ----------------- IMEI SUMMARY -----------------
@app.get("/api/cases/{case_id}/imei-summary")
def get_imei_summary_endpoint(
    case_id: str,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    res = get_imei_summary_list(case_id, db)
    log_audit_event(
        db, action="QUERY",
        details={"type": "imei_summary", "case_id": case_id},
        user=current_user, request=request
    )
    return res


# ----------------- IMSI SUMMARY -----------------
@app.get("/api/cases/{case_id}/imsi-summary")
def get_imsi_summary_endpoint(
    case_id: str,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    res = get_imsi_summary_list(case_id, db)
    log_audit_event(
        db, action="QUERY",
        details={"type": "imsi_summary", "case_id": case_id},
        user=current_user, request=request
    )
    return res


# ----------------- GLOBAL SEARCH -----------------
@app.get("/api/search")
def get_global_search(
    q: str = Query(..., min_length=1, description="Search term for number, IMEI, IMSI, tower, case"),
    case_id: str | None = Query(None, description="Optional Case ID to limit scope"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    res = global_search(q, case_id, db)
    log_audit_event(
        db, action="QUERY",
        details={"type": "global_search", "query": q, "case_id": case_id},
        user=current_user, request=request
    )
    return res


# ----------------- FORENSIC ANALYTICS AGGREGATION -----------------
@app.get("/api/cases/{case_id}/link-analysis")
def get_link_analysis_endpoint(
    case_id: str,
    num1: str = Query(...),
    num2: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    return analyze_link_between_numbers(case_id, num1.strip(), num2.strip(), db)


@app.get("/api/cases/{case_id}/analytics")
def get_case_analytics(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    records = db.query(CDRRecord).filter(CDRRecord.case_id == case_id).order_by(CDRRecord.start_time.asc()).all()
    ipdr_records = db.query(IPDRRecord).filter(IPDRRecord.case_id == case_id).order_by(IPDRRecord.session_start.asc()).all()
    towers = {t.cell_id: t for t in db.query(CellTower).all()}
    suspects_list = get_ordered_suspects_for_case(case_id, db)

    if not records:
        return {
            "suspects": suspects_list,
            "mfc": [], "first_last": [], "day_night": {"day_calls": 0, "night_calls": 0, "day_pct": 0, "night_pct": 0, "night_numbers": []},
            "day_locations": [], "night_locations": [], "missing_dates": [], "movement": [],
            "service_numbers": [], "international_numbers": [], "imei_summary": [], "imsi_summary": [],
            "imei_patterns": [], "imsi_patterns": [], "location_summary": [], "location_intelligence": {},
            "day_calls": [], "night_calls": [], "cell_id_changes": [], "location_changes": [],
            "interactive_timeline": [], "network_stats": {"top_hubs": [], "top_pairs": []},
            "notifications": [], "ownership": suspects_list
        }

    contact_stats = defaultdict(lambda: {
        "calls": 0, "duration": 0, "in": 0, "out": 0, "sms": 0,
        "first_call": None, "last_call": None, "night_calls": 0, "imeis": set(), "imsis": set(), "towers": set()
    })
    tower_day = defaultdict(int)
    tower_night = defaultdict(int)
    tower_meta = defaultdict(lambda: {"hits": 0, "numbers": set(), "first_seen": None, "last_seen": None})
    imei_stats = defaultdict(lambda: {"calls": 0, "numbers": set(), "imsis": set(), "first_seen": None, "last_seen": None})
    imsi_stats = defaultdict(lambda: {"calls": 0, "numbers": set(), "imeis": set(), "first_seen": None, "last_seen": None})
    pair_stats = defaultdict(lambda: {"calls": 0, "duration": 0})
    
    day_calls_count = 0
    night_calls_count = 0
    day_calls_list = []
    night_calls_list = []
    all_dates = set()
    movement_hops = []
    cell_id_changes = []
    location_changes = []
    last_tower = None
    last_area = None
    last_time = None
    timeline_events = []

    for r in records:
        a, b = r.a_number, r.b_number
        st = r.start_time
        dur = r.duration_sec or 0
        call_type = r.call_type
        imei = r.imei
        imsi = r.imsi
        cell = r.cell_id
        t_obj = towers.get(cell)
        area_name = t_obj.area_name if t_obj else (f"Cell {cell}" if cell else "Unknown")

        # date extraction
        try:
            dt = datetime.fromisoformat(st)
            all_dates.add(dt.strftime("%Y-%m-%d"))
            hour = dt.hour
        except Exception:
            dt = None
            hour = 12

        if a and b and a != b:
            pk = tuple(sorted([a, b]))
            pair_stats[pk]["calls"] += 1
            pair_stats[pk]["duration"] += dur

        if cell:
            tm = tower_meta[cell]
            tm["hits"] += 1
            if a:
                tm["numbers"].add(a)
            if not tm["first_seen"] or st < tm["first_seen"]:
                tm["first_seen"] = st
            if not tm["last_seen"] or st > tm["last_seen"]:
                tm["last_seen"] = st

        call_row = {
            "timestamp": st,
            "a_number": a,
            "b_number": b,
            "call_type": call_type,
            "duration_sec": dur,
            "cell_id": cell or "-",
            "area_name": area_name,
            "source_file": r.source_file,
            "source_row": r.source_row
        }

        is_night = (hour >= 22 or hour < 6)
        if is_night:
            night_calls_count += 1
            if len(night_calls_list) < 100:
                night_calls_list.append(call_row)
            if cell:
                tower_night[cell] += 1
        else:
            day_calls_count += 1
            if len(day_calls_list) < 100:
                day_calls_list.append(call_row)
            if cell:
                tower_day[cell] += 1

        if len(timeline_events) < 80:
            timeline_events.append({
                "timestamp": st,
                "event_type": f"CDR_{call_type}",
                "entity": a,
                "target": b,
                "location": area_name,
                "details": f"{call_type} {dur}s via {cell or '-'}",
                "evidence": f"{r.source_file}:Row {r.source_row}"
            })

        # Track contact stats
        for num, is_a in [(a, True), (b, False)]:
            s = contact_stats[num]
            s["calls"] += 1
            s["duration"] += dur
            if call_type == "SMS":
                s["sms"] += 1
            elif (is_a and call_type == "OUT") or (not is_a and call_type == "IN"):
                s["out"] += 1
            else:
                s["in"] += 1

            if not s["first_call"] or st < s["first_call"]:
                s["first_call"] = st
            if not s["last_call"] or st > s["last_call"]:
                s["last_call"] = st
            if is_night:
                s["night_calls"] += 1
            if imei:
                s["imeis"].add(imei)
            if imsi:
                s["imsis"].add(imsi)
            if cell:
                s["towers"].add(cell)

        # Track IMEI stats
        if imei:
            ims = imei_stats[imei]
            ims["calls"] += 1
            ims["numbers"].add(a)
            if imsi:
                ims["imsis"].add(imsi)
            if not ims["first_seen"] or st < ims["first_seen"]:
                ims["first_seen"] = st
            if not ims["last_seen"] or st > ims["last_seen"]:
                ims["last_seen"] = st

        # Track IMSI stats
        if imsi:
            iss = imsi_stats[imsi]
            iss["calls"] += 1
            iss["numbers"].add(a)
            if imei:
                iss["imeis"].add(imei)
            if not iss["first_seen"] or st < iss["first_seen"]:
                iss["first_seen"] = st
            if not iss["last_seen"] or st > iss["last_seen"]:
                iss["last_seen"] = st

        # Tower movement hop & Cell ID / Location changes
        if cell and cell != last_tower:
            delta_sec = 0
            if dt and last_time:
                delta_sec = int((dt - last_time).total_seconds())
            t_obj = towers.get(cell)
            hop = {
                "seq": len(movement_hops) + 1,
                "timestamp": st,
                "from_cell": last_tower or "-",
                "cell_id": cell,
                "from_area": last_area or "-",
                "area_name": area_name,
                "lat": t_obj.lat if t_obj else None,
                "lon": t_obj.lon if t_obj else None,
                "number": a,
                "time_delta_sec": delta_sec
            }
            movement_hops.append(hop)
            if last_tower and len(cell_id_changes) < 100:
                cell_id_changes.append(hop)
            if last_area and area_name != last_area and len(location_changes) < 100:
                location_changes.append(hop)
            last_tower = cell
            last_area = area_name
            last_time = dt

    total_all_calls = len(records)
    # 1. MFC
    mfc_list = []
    for num, s in sorted(contact_stats.items(), key=lambda x: x[1]["calls"], reverse=True)[:30]:
        pct = round((s["calls"] / max(1, total_all_calls)) * 100, 1)
        mfc_list.append({
            "number": num,
            "calls": s["calls"],
            "duration": s["duration"],
            "in_count": s["in"],
            "out_count": s["out"],
            "sms_count": s["sms"],
            "first_call": s["first_call"],
            "last_call": s["last_call"],
            "percentage": pct
        })

    # 2. First / Last Call table
    first_last_list = []
    for num, s in sorted(contact_stats.items(), key=lambda x: x[1]["calls"], reverse=True)[:40]:
        span_days = 0
        if s["first_call"] and s["last_call"]:
            try:
                d1 = datetime.fromisoformat(s["first_call"])
                d2 = datetime.fromisoformat(s["last_call"])
                span_days = max(1, (d2 - d1).days + 1)
            except Exception:
                span_days = 1
        first_last_list.append({
            "number": num,
            "first_call": s["first_call"],
            "last_call": s["last_call"],
            "total_calls": s["calls"],
            "days_span": span_days,
            "avg_duration": round(s["duration"] / max(1, s["calls"]), 1)
        })

    # 3. Day / Night breakdown
    day_pct = round((day_calls_count / max(1, total_all_calls)) * 100, 1)
    night_pct = round((night_calls_count / max(1, total_all_calls)) * 100, 1)
    night_numbers = [
        {"number": num, "night_calls": s["night_calls"], "total_calls": s["calls"], "night_ratio": round((s["night_calls"] / s["calls"]) * 100, 1)}
        for num, s in contact_stats.items() if s["night_calls"] > 0
    ]
    night_numbers.sort(key=lambda x: x["night_calls"], reverse=True)

    # 4. Day & Night Locations
    day_locs = [
        {"cell_id": cid, "area_name": towers[cid].area_name if cid in towers else cid, "visits": cnt, "lat": towers[cid].lat if cid in towers else None, "lon": towers[cid].lon if cid in towers else None}
        for cid, cnt in sorted(tower_day.items(), key=lambda x: x[1], reverse=True)
    ]
    night_locs = [
        {"cell_id": cid, "area_name": towers[cid].area_name if cid in towers else cid, "visits": cnt, "lat": towers[cid].lat if cid in towers else None, "lon": towers[cid].lon if cid in towers else None}
        for cid, cnt in sorted(tower_night.items(), key=lambda x: x[1], reverse=True)
    ]

    # 5. Missing dates (Silence Gaps)
    missing_dates = []
    if all_dates:
        sorted_dates = sorted(all_dates)
        try:
            start_d = datetime.strptime(sorted_dates[0], "%Y-%m-%d")
            end_d = datetime.strptime(sorted_dates[-1], "%Y-%m-%d")
            curr = start_d
            while curr <= end_d:
                ds = curr.strftime("%Y-%m-%d")
                if ds not in all_dates:
                    missing_dates.append({
                        "date": ds,
                        "day_name": curr.strftime("%A"),
                        "status": "SILENCE_GAP",
                        "description": "Zero call transactions recorded"
                    })
                curr += timedelta(days=1)
        except Exception:
            pass

    # 6. Service & Company Numbers (1800, 1860, shortcodes < 6 digits, bank lines)
    service_numbers = []
    international_numbers = []
    for num, s in contact_stats.items():
        clean = num.strip().replace("+", "")
        if clean.startswith("1800") or clean.startswith("1860") or len(clean) <= 6:
            label = "Toll Free Service" if clean.startswith(("1800", "1860")) else "Shortcode / Bank OTP Line"
            service_numbers.append({
                "number": num,
                "label": label,
                "calls": s["calls"],
                "first_seen": s["first_call"],
                "last_seen": s["last_call"]
            })
        elif num.startswith("+") and not num.startswith("+91"):
            international_numbers.append({
                "number": num,
                "country_code": num[:3],
                "calls": s["calls"],
                "first_seen": s["first_call"],
                "last_seen": s["last_call"]
            })

    # 7. IMEI Summary with TAC
    imei_summary = []
    for im, st in imei_stats.items():
        tac_data = lookup_tac_device(im)
        imei_summary.append({
            "imei": im,
            "brand": tac_data["brand"],
            "model": tac_data["model"],
            "generation": tac_data["generation"],
            "calls": st["calls"],
            "associated_numbers": list(st["numbers"]),
            "associated_imsis": list(st["imsis"]),
            "first_seen": st["first_seen"],
            "last_seen": st["last_seen"]
        })
    imei_summary.sort(key=lambda x: x["calls"], reverse=True)

    # 8. IMSI Summary
    imsi_summary = []
    for im, st in imsi_stats.items():
        imsi_summary.append({
            "imsi": im,
            "calls": st["calls"],
            "associated_numbers": list(st["numbers"]),
            "associated_imeis": list(st["imeis"]),
            "first_seen": st["first_seen"],
            "last_seen": st["last_seen"]
        })
    imsi_summary.sort(key=lambda x: x["calls"], reverse=True)

    # 9. IMEI & IMSI Patterns (Multi-SIM / Multi-IMEI Anomaly & Usage Patterns)
    imei_patterns = [
        {
            "imei": item["imei"],
            "device": f"{item['brand']} {item['model']}",
            "distinct_sims": len(item["associated_numbers"]),
            "distinct_imsis": len(item["associated_imsis"]),
            "calls": item["calls"],
            "pattern_flag": "MULTI_SIM_SWAP" if len(item["associated_numbers"]) > 1 else "SINGLE_SIM_BINDING",
            "numbers": item["associated_numbers"],
            "span": f"{item['first_seen']} -> {item['last_seen']}"
        }
        for item in imei_summary
    ]
    imsi_patterns = [
        {
            "imsi": item["imsi"],
            "distinct_imeis": len(item["associated_imeis"]),
            "distinct_numbers": len(item["associated_numbers"]),
            "calls": item["calls"],
            "pattern_flag": "MULTI_HANDSET_HOP" if len(item["associated_imeis"]) > 1 else "CONSISTENT_DEVICE",
            "imeis": item["associated_imeis"],
            "span": f"{item['first_seen']} -> {item['last_seen']}"
        }
        for item in imsi_summary
    ]

    # 10. Location Summary & Location Intelligence
    total_hits = sum(tm["hits"] for tm in tower_meta.values())
    location_summary = []
    for cid, tm in sorted(tower_meta.items(), key=lambda x: x[1]["hits"], reverse=True):
        t_obj = towers.get(cid)
        location_summary.append({
            "cell_id": cid,
            "area_name": t_obj.area_name if t_obj else f"Cell {cid}",
            "hits": tm["hits"],
            "unique_numbers": len(tm["numbers"]),
            "pct": round((tm["hits"] / max(1, total_hits)) * 100, 1),
            "first_seen": tm["first_seen"],
            "last_seen": tm["last_seen"],
            "lat": t_obj.lat if t_obj else None,
            "lon": t_obj.lon if t_obj else None
        })

    location_intelligence = {
        "total_unique_towers": len(tower_meta),
        "primary_day_tower": day_locs[0] if day_locs else None,
        "primary_night_tower": night_locs[0] if night_locs else None,
        "most_visited_tower": location_summary[0] if location_summary else None,
        "total_tower_hops": len(cell_id_changes),
        "total_area_transitions": len(location_changes)
    }

    # 11. Interactive Timeline (CDR + IPDR combined chronologically)
    for ipr in ipdr_records[:30]:
        timeline_events.append({
            "timestamp": ipr.session_start,
            "event_type": "IPDR_SESSION",
            "entity": ipr.subscriber_number,
            "target": f"{ipr.source_ip}:{ipr.source_port}",
            "location": ipr.app_hint or "CGNAT Session",
            "details": f"App: {ipr.app_hint or 'Data'} ({ipr.bytes_transferred} B)",
            "evidence": f"{ipr.source_file}:Row {ipr.source_row}"
        })
    timeline_events.sort(key=lambda x: x["timestamp"], reverse=True)

    # 12. Network Analysis Stats
    top_hubs = [
        {"number": num, "calls": s["calls"], "unique_towers": len(s["towers"]), "duration": s["duration"], "in_out": f"{s['in']}/{s['out']}"}
        for num, s in sorted(contact_stats.items(), key=lambda x: x[1]["calls"], reverse=True)[:15]
    ]
    top_pairs = [
        {"source": p[0], "target": p[1], "calls": st["calls"], "duration": st["duration"]}
        for p, st in sorted(pair_stats.items(), key=lambda x: x[1]["calls"], reverse=True)[:20]
    ]

    # 13. Dynamic Notifications derived from actual forensic findings
    notifications = []
    dev_changes = detect_imei_sim_changes(case_id, db)
    for sw in dev_changes.get("multi_number_imeis", [])[:3]:
        notifications.append({
            "severity": "critical",
            "title": "SIM Swap Detected",
            "message": f"IMEI {sw['imei']} swapped across {sw['distinct_numbers_count']} numbers: {', '.join(sw['numbers'])}.",
            "meta": "Multi-SIM Hardware Alert"
        })
    if len(suspects_list) >= 2:
        n1, n2 = suspects_list[0].get("phone"), suspects_list[1].get("phone")
        if n1 and n2:
            meets = detect_meetings(n1, n2, case_id, db, time_window_minutes=30)
            for m in meets[:2]:
                diff_mins = round(m["time_diff_sec"] / 60, 1)
                notifications.append({
                    "severity": "warning",
                    "title": "Physical Co-Location Alert",
                    "message": f"{n1} and {n2} co-located at {m['area_name']} ({m['cell_id']}) within {diff_mins} mins.",
                    "meta": m["event_target_1"]["timestamp"]
                })
    latest_batch = db.query(ImportBatch).filter(ImportBatch.case_id == case_id).order_by(ImportBatch.created_at.desc()).first()
    if latest_batch:
        notifications.append({
            "severity": "info",
            "title": "Data Ingestion Active",
            "message": f"{latest_batch.filename} ({latest_batch.file_type}): {latest_batch.valid_rows} valid rows indexed ({latest_batch.rejected_rows} rejected).",
            "meta": latest_batch.mapping_name or "Normalized"
        })

    return {
        "suspects": suspects_list,
        "mfc": mfc_list,
        "first_last": first_last_list,
        "day_night": {
            "day_calls": day_calls_count,
            "night_calls": night_calls_count,
            "day_pct": day_pct,
            "night_pct": night_pct,
            "night_numbers": night_numbers[:20]
        },
        "day_calls": day_calls_list,
        "night_calls": night_calls_list,
        "day_locations": day_locs[:15],
        "night_locations": night_locs[:15],
        "location_summary": location_summary[:25],
        "location_intelligence": location_intelligence,
        "missing_dates": missing_dates,
        "movement": movement_hops[:40],
        "cell_id_changes": cell_id_changes,
        "location_changes": location_changes,
        "interactive_timeline": timeline_events[:80],
        "network_stats": {"top_hubs": top_hubs, "top_pairs": top_pairs},
        "service_numbers": service_numbers,
        "international_numbers": international_numbers,
        "imei_summary": imei_summary,
        "imsi_summary": imsi_summary,
        "imei_patterns": imei_patterns,
        "imsi_patterns": imsi_patterns,
        "notifications": notifications,
        "ownership": suspects_list
    }


# ----------------- GLOBAL SEARCH ACROSS ALL DATA -----------------
@app.get("/api/cases/{case_id}/search")
def search_case_data(
    case_id: str,
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("investigating_officer", "senior_officer", "admin"))
):
    query = f"%{q.strip()}%"
    cdrs = db.query(CDRRecord).filter(
        CDRRecord.case_id == case_id,
        or_(
            CDRRecord.a_number.like(query),
            CDRRecord.b_number.like(query),
            CDRRecord.imei.like(query),
            CDRRecord.imsi.like(query),
            CDRRecord.cell_id.like(query)
        )
    ).limit(20).all()

    ipdrs = db.query(IPDRRecord).filter(
        IPDRRecord.case_id == case_id,
        or_(
            IPDRRecord.subscriber_number.like(query),
            IPDRRecord.source_ip.like(query),
            IPDRRecord.destination_ip.like(query),
            IPDRRecord.app_hint.like(query)
        )
    ).limit(20).all()

    towers = db.query(CellTower).filter(
        or_(
            CellTower.cell_id.like(query),
            CellTower.area_name.like(query)
        )
    ).limit(10).all()

    return {
        "query": q,
        "cdr_count": len(cdrs),
        "ipdr_count": len(ipdrs),
        "tower_count": len(towers),
        "cdrs": [{
            "id": r.id,
            "a_number": r.a_number,
            "b_number": r.b_number,
            "call_type": r.call_type,
            "start_time": r.start_time,
            "duration_sec": r.duration_sec,
            "imei": r.imei,
            "imsi": r.imsi,
            "cell_id": r.cell_id,
            "source_file": r.source_file,
            "source_row": r.source_row
        } for r in cdrs],
        "ipdrs": [{
            "id": r.id,
            "subscriber_number": r.subscriber_number,
            "source_ip": r.source_ip,
            "source_port": r.source_port,
            "session_start": r.session_start,
            "app_hint": r.app_hint,
            "source_file": r.source_file,
            "source_row": r.source_row
        } for r in ipdrs],
        "towers": [{
            "cell_id": t.cell_id,
            "area_name": t.area_name,
            "lat": t.lat,
            "lon": t.lon
        } for t in towers]
    }


# ----------------- FEATURE 9: AUDIT LOGS -----------------
@app.get("/api/audit")
def view_audit_logs(
    limit: int = Query(100),
    action: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "senior_officer"))  # Only admin & senior officer
):
    logs = get_audit_logs(db, limit, action)
    results = []
    for l in logs:
        results.append({
            "id": l.id,
            "username": l.username,
            "role": l.role,
            "action": l.action,
            "details": json.loads(l.details) if l.details else {},
            "ip_address": l.ip_address,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None
        })
    return results


@app.get("/favicon.ico")
def serve_favicon():
    return Response(status_code=204)


# ----------------- STATIC UI MOUNT -----------------
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

