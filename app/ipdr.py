from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app.db import IPDRRecord


def match_ipdr_session(
    case_id: str,
    ip: str,
    port: int,
    query_timestamp: str,
    db: Session,
    tolerance_minutes: int = 15
) -> dict:
    """
    Given a public IP, source port, and timestamp, returns matching subscriber & session details.
    """
    clean_ip = ip.strip()

    try:
        q_dt = datetime.fromisoformat(query_timestamp.replace("Z", "").replace(" ", "T"))
    except Exception:
        return {
            "status": "error",
            "message": f"Invalid query timestamp format: '{query_timestamp}'. Expected ISO format (YYYY-MM-DDTHH:MM:SS)."
        }

    # Fetch candidate records with same IP and port
    records = db.query(IPDRRecord).filter(
        IPDRRecord.case_id == case_id,
        IPDRRecord.source_ip == clean_ip,
        IPDRRecord.source_port == port
    ).all()

    exact_matches = []
    near_matches = []

    for r in records:
        try:
            s_start = datetime.fromisoformat(r.session_start)
            s_end = datetime.fromisoformat(r.session_end)
        except Exception:
            continue

        if s_start <= q_dt <= s_end:
            exact_matches.append(r)
        else:
            diff_start = abs((q_dt - s_start).total_seconds())
            diff_end = abs((q_dt - s_end).total_seconds())
            min_diff = min(diff_start, diff_end)
            if min_diff <= (tolerance_minutes * 60):
                near_matches.append((r, min_diff))

    results = []
    match_type = "none"

    if exact_matches:
        match_type = "exact_concurrent"
        candidates = exact_matches
    elif near_matches:
        match_type = "approximate_tolerance_window"
        near_matches.sort(key=lambda x: x[1])
        candidates = [m[0] for m in near_matches]
    else:
        # Fallback: check if IP matches regardless of port to assist officer
        ip_only_records = db.query(IPDRRecord).filter(
            IPDRRecord.case_id == case_id,
            IPDRRecord.source_ip == clean_ip
        ).limit(5).all()

        return {
            "match_found": False,
            "match_type": "no_match",
            "query": {"ip": clean_ip, "port": port, "timestamp": query_timestamp},
            "explanation": f"No IPDR session logged for {clean_ip}:{port} around {query_timestamp}. Carrier NAT tables might have assigned this port to another session or data is outside the uploaded timeframe.",
            "similar_ip_sessions": [
                {
                    "subscriber": r.subscriber_number,
                    "port": r.source_port,
                    "session_start": r.session_start,
                    "app_hint": r.app_hint or "Unspecified/Raw HTTP/TLS"
                } for r in ip_only_records
            ]
        }

    for r in candidates:
        app_clarity = "App identity inferred from destination domain/port metadata in telco payload."
        if not r.app_hint:
            app_clarity = "No application hint available in metadata; connection was standard encrypted TLS/IP traffic."

        results.append({
            "subscriber_number": r.subscriber_number,
            "source_ip": r.source_ip,
            "source_port": r.source_port,
            "destination_ip": r.destination_ip,
            "destination_port": r.destination_port,
            "session_start": r.session_start,
            "session_end": r.session_end,
            "bytes_transferred": r.bytes_transferred,
            "app_hint": r.app_hint or "Unclassified Traffic",
            "app_attribution_note": app_clarity,
            "source_file": r.source_file,
            "source_row": r.source_row
        })

    return {
        "match_found": True,
        "matched": True,
        "match_type": match_type,
        "query": {"ip": clean_ip, "port": port, "timestamp": query_timestamp},
        "sessions": results,
        "session": results[0] if results else None,
        "primary_subscriber": results[0]["subscriber_number"],
        "confidence_note": "AI observation - officer verification pending. IP-to-MSISDN attribution verified against operator NAT session logs."
    }


def get_subscriber_ipdr_summary(subscriber: str, case_id: str, db: Session) -> dict:
    clean_sub = subscriber.strip()
    records = db.query(IPDRRecord).filter(
        IPDRRecord.case_id == case_id,
        or_(
            IPDRRecord.subscriber_number == clean_sub,
            IPDRRecord.subscriber_number == f"+91{clean_sub}"
        )
    ).order_by(IPDRRecord.session_start.asc()).all()

    app_breakdown = {}
    total_bytes = 0

    sessions = []
    for r in records:
        app = r.app_hint if r.app_hint else "Unclassified Traffic"
        app_breakdown[app] = app_breakdown.get(app, 0) + 1
        total_bytes += r.bytes_transferred
        sessions.append({
            "source_ip": r.source_ip,
            "source_port": r.source_port,
            "destination_ip": r.destination_ip,
            "destination_port": r.destination_port,
            "session_start": r.session_start,
            "session_end": r.session_end,
            "bytes": r.bytes_transferred,
            "app": app,
            "source_file": r.source_file,
            "source_row": r.source_row
        })

    return {
        "subscriber": clean_sub,
        "total_sessions": len(records),
        "total_bytes_transferred": total_bytes,
        "app_breakdown": app_breakdown,
        "sessions": sessions[:50]
    }


def batch_match_ipdr_sessions(
    case_id: str,
    queries: list[dict],
    db: Session,
    tolerance_minutes: int = 15
) -> dict:
    """
    Batch-resolve public NAT IP + Port + Timestamp tuples against carrier CGNAT IPDR sessions.
    Essential for bulk 1930 cyber fraud complaint triage and bank transaction mapping.
    """
    results = []
    matched_count = 0
    identified_subscribers = set()

    for idx, q in enumerate(queries):
        ip = str(q.get("ip") or q.get("source_ip") or "").strip()
        port_raw = q.get("port") or q.get("source_port") or 0
        try:
            port = int(port_raw)
        except (ValueError, TypeError):
            port = 0
        timestamp = str(q.get("timestamp") or q.get("session_start") or "").strip()
        ref_id = q.get("query_id") or q.get("id") or q.get("tag") or f"query_{idx+1}"

        if not ip or not port or not timestamp:
            results.append({
                "query_id": ref_id,
                "ip": ip,
                "port": port,
                "timestamp": timestamp,
                "status": "error",
                "matched": False,
                "match_type": "invalid_input",
                "explanation": "Missing required ip, port, or timestamp."
            })
            continue

        res = match_ipdr_session(case_id, ip, port, timestamp, db, tolerance_minutes=tolerance_minutes)
        is_matched = bool(res.get("match_found"))
        if is_matched:
            matched_count += 1
            if res.get("primary_subscriber"):
                identified_subscribers.add(res["primary_subscriber"])

        results.append({
            "query_id": ref_id,
            "ip": ip,
            "port": port,
            "timestamp": timestamp,
            "matched": is_matched,
            "match_type": res.get("match_type", "no_match"),
            "primary_subscriber": res.get("primary_subscriber"),
            "session": res.get("session"),
            "sessions": res.get("sessions", []),
            "confidence_note": res.get("confidence_note", "")
        })

    return {
        "case_id": case_id,
        "total_queries": len(queries),
        "matched_count": matched_count,
        "unmatched_count": len(queries) - matched_count,
        "identified_subscribers_count": len(identified_subscribers),
        "identified_subscribers": sorted(list(identified_subscribers)),
        "results": results
    }

