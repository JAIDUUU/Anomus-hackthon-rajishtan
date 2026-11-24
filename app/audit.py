import json
from datetime import datetime
from fastapi import Request
from sqlalchemy.orm import Session
from app.db import AuditLog, User


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

    log_entry = AuditLog(
        user_id=usr_id,
        username=usr_name,
        role=usr_role,
        action=action,
        details=details_str,
        ip_address=ip_addr,
        timestamp=datetime.utcnow()
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
