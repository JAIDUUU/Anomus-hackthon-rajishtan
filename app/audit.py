import hashlib
import json
from datetime import datetime
from fastapi import Request
from sqlalchemy.orm import Session
from app.db import AuditLog, User


def compute_audit_hash(prev_hash: str, username: str, action: str, timestamp_str: str, details_str: str, ip_addr: str) -> str:
    raw = f"{prev_hash}|{username}|{action}|{timestamp_str}|{details_str}|{ip_addr}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def log_audit_event(
    db: Session,
    action: str,
    details: dict | str,
    user: User | None = None,
    username: str | None = None,
    role: str | None = None,
    request: Request | None = None
):
    ip_addr = "127.0.0.1"
    if request:
        if request.client:
            ip_addr = request.client.host
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip_addr = forwarded.split(",")[0].strip()

    usr_name = username or (user.username if user else "anonymous")
    usr_role = role or (user.role if user else "unauthenticated")
    usr_id = user.id if user else None

    details_str = json.dumps(details) if isinstance(details, dict) else str(details)
    now_ts = datetime.utcnow()
    ts_str = now_ts.isoformat()

    last_rec = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev_hash = last_rec.entry_hash if (last_rec and last_rec.entry_hash) else ("0" * 64)
    entry_hash = compute_audit_hash(prev_hash, usr_name, action, ts_str, details_str, ip_addr)

    log_entry = AuditLog(
        user_id=usr_id,
        username=usr_name,
        role=usr_role,
        action=action,
        details=details_str,
        ip_address=ip_addr,
        timestamp=now_ts,
        prev_hash=prev_hash,
        entry_hash=entry_hash
    )
    db.add(log_entry)
    try:
        db.commit()
    except Exception:
        db.rollback()


def get_audit_logs(db: Session, limit: int = 100, action: str | None = None):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()


def verify_audit_integrity(db: Session) -> dict:
    """
    Verifies the cryptographic SHA-256 hash chain of the entire Audit Log table.
    Ensures Section 65B Indian Evidence Act tamper-evident legal admissibility.
    """
    records = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    if not records:
        return {
            "is_valid": True,
            "total_records": 0,
            "verified_records": 0,
            "tampered_records": [],
            "latest_hash": "",
            "genesis_hash": "",
            "verification_status": "AUTHENTIC"
        }

    expected_prev = "0" * 64
    tampered_list = []
    has_started_chain = False

    for r in records:
        if not r.entry_hash:
            continue

        if not has_started_chain:
            expected_prev = r.prev_hash
            has_started_chain = True

        ts_str = r.timestamp.isoformat() if r.timestamp else ""
        expected_hash = compute_audit_hash(
            r.prev_hash,
            r.username,
            r.action,
            ts_str,
            r.details or "",
            r.ip_address or ""
        )

        is_tampered = False
        reasons = []

        if r.prev_hash != expected_prev:
            is_tampered = True
            reasons.append(f"Broken previous hash link: expected {expected_prev[:12]}..., got {r.prev_hash[:12]}...")

        if r.entry_hash != expected_hash:
            is_tampered = True
            reasons.append("Entry hash mismatch: payload or metadata altered since logging.")

        if is_tampered:
            tampered_list.append({
                "record_id": r.id,
                "timestamp": ts_str,
                "action": r.action,
                "username": r.username,
                "reasons": reasons
            })

        expected_prev = r.entry_hash

    is_valid = len(tampered_list) == 0
    hashed_records = [r for r in records if r.entry_hash]
    return {
        "is_valid": is_valid,
        "total_records": len(records),
        "verified_records": len(records) - len(tampered_list),
        "tampered_records": tampered_list,
        "latest_hash": hashed_records[-1].entry_hash if hashed_records else "",
        "genesis_hash": hashed_records[0].entry_hash if hashed_records else "",
        "verification_status": "AUTHENTIC" if is_valid else "INTEGRITY_BREACH_DETECTED"
    }

