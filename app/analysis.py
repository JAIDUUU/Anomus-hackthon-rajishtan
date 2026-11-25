import json
import math
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, asc, func
from app.db import CDRRecord, IPDRRecord, CellTower, Case

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "config")


def _load_json_config(filename: str) -> dict:
    """Load external JSON lookup config dynamically from data/config/."""
    path = os.path.join(CONFIG_DIR, filename)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_tac_database() -> dict:
    return _load_json_config("tac_database.json")


def load_service_directory() -> dict:
    return _load_json_config("service_directory.json")

INTERNATIONAL_PREFIXES = {
    "+971": ("United Arab Emirates (Dubai)", "HIGH"),
    "+44": ("United Kingdom (London)", "MEDIUM"),
    "+1": ("United States / Canada", "MEDIUM"),
    "+92": ("Pakistan", "CRITICAL"),
    "+880": ("Bangladesh", "HIGH"),
    "+977": ("Nepal", "MEDIUM"),
    "+86": ("China", "HIGH"),
    "+855": ("Cambodia", "HIGH"),
    "+95": ("Myanmar", "HIGH"),
    "+60": ("Malaysia", "MEDIUM"),
    "+65": ("Singapore", "LOW"),
    "+66": ("Thailand", "MEDIUM"),
    "+966": ("Saudi Arabia", "MEDIUM"),
    "+968": ("Oman", "MEDIUM"),
    "+974": ("Qatar", "MEDIUM"),
    "+965": ("Kuwait", "MEDIUM"),
    "+49": ("Germany", "LOW"),
    "+33": ("France", "LOW"),
    "+7": ("Russia / Kazakhstan", "HIGH"),
    "+61": ("Australia", "LOW"),
    "+380": ("Ukraine", "MEDIUM"),
    "+90": ("Turkey", "MEDIUM"),
    "+234": ("Nigeria", "HIGH"),
    "+254": ("Kenya", "MEDIUM"),
    "+62": ("Indonesia", "MEDIUM"),
    "+63": ("Philippines", "MEDIUM"),
    "+94": ("Sri Lanka", "MEDIUM")
}


def haversine_km(lat1: float | None, lon1: float | None, lat2: float | None, lon2: float | None) -> float | None:
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None
    try:
        r = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(r * c, 2)
    except Exception:
        return None


def is_service_number(number: str | None) -> tuple[bool, str, str]:
    if not number:
        return (False, "", "")
    s = str(number).strip()
    srv_dir = load_service_directory()
    if s in srv_dir:
        return (True, srv_dir[s]["service_name"], srv_dir[s]["category"])
    if s.startswith("1800"):
        return (True, "Toll-Free 1800 Customer Helpline", "Toll-Free Helpline")
    if s.startswith("1860"):
        return (True, "Shared Cost 1860 Helpline", "Toll-Free Helpline")
    if s.startswith("1900"):
        return (True, "Premium Rate 1900 Service", "Special Service")
    if len(s) <= 6 and s.isdigit():
        return (True, f"Telecom Shortcode {s}", "Telecom Shortcode")
    return (False, "", "")


def is_international_number(number: str | None) -> tuple[bool, str, str, str]:
    if not number:
        return (False, "", "", "")
    s = str(number).strip()
    if s.startswith("1800") or s.startswith("1860") or s.startswith("1900") or (len(s) <= 6 and s.isdigit()):
        return (False, "", "", "")
    if s.startswith("+"):
        if s.startswith("+91"):
            return (False, "", "", "")
        for prefix, (country, risk) in sorted(INTERNATIONAL_PREFIXES.items(), key=lambda x: len(x[0]), reverse=True):
            if s.startswith(prefix):
                return (True, country, prefix, risk)
        return (True, "International Destination", s[:4], "MEDIUM")
    if s.startswith("00"):
        if s.startswith("0091"):
            return (False, "", "", "")
        cand = "+" + s[2:]
        for prefix, (country, risk) in sorted(INTERNATIONAL_PREFIXES.items(), key=lambda x: len(x[0]), reverse=True):
            if cand.startswith(prefix):
                return (True, country, prefix, risk)
        return (True, "International Destination", cand[:4], "MEDIUM")
    return (False, "", "", "")


# ----------------- TAC LOOKUP -----------------
def lookup_tac_device(imei: str) -> dict:
    """
    Decodes an 8-digit TAC into brand, model, generation, and device details.
    """
    if not imei:
        return {
            "imei": "",
            "tac": "",
            "brand": "Unknown",
            "model": "Unknown Device",
            "marketing_name": "Unknown Device",
            "generation": "Unknown",
            "device_type": "Unknown",
            "manufacturer": "Unknown",
            "luhn_valid": False,
            "valid_length": False
        }
    digits = re.sub(r"\D", "", str(imei).strip())
    if len(digits) < 8:
        return {
            "imei": imei,
            "tac": digits,
            "brand": "Invalid IMEI",
            "model": f"Short IMEI ({imei})",
            "marketing_name": f"Invalid IMEI ({imei})",
            "generation": "Unknown",
            "device_type": "Unknown",
            "manufacturer": "Unknown",
            "luhn_valid": False,
            "valid_length": False
        }

    tac = digits[:8]
    valid_luhn = False
    if len(digits) >= 14:
        d_list = [int(c) for c in digits[:15]]
        if len(d_list) == 15:
            checksum = 0
            for i in range(14):
                d = d_list[i]
                if i % 2 == 1:
                    d *= 2
                    if d > 9:
                        d = (d // 10) + (d % 10)
                checksum += d
            check_digit = (10 - (checksum % 10)) % 10
            valid_luhn = (check_digit == d_list[14])
        else:
            valid_luhn = True

    origin_map = {
        "Apple": "United States (Designed in California)",
        "Samsung": "South Korea (Suwon)",
        "OnePlus": "China (Shenzhen)",
        "Xiaomi": "China (Beijing)",
        "Poco": "China (Beijing)",
        "Vivo": "China (Dongguan)",
        "iQOO": "China (Dongguan)",
        "Oppo": "China (Dongguan)",
        "Realme": "China (Shenzhen)",
        "Google": "United States (Mountain View, CA)",
    }

    tac_db = load_tac_database()
    if tac in tac_db:
        data = tac_db[tac]
        b = data["brand"]
        origin = data.get("origin") or origin_map.get(b, "Global / GSMA Member State")
        return {
            "imei": imei,
            "tac": tac,
            "brand": b,
            "model": data["model"],
            "marketing_name": f"{b} {data['model']}",
            "generation": data["generation"],
            "device_type": data.get("device_type", "Smartphone"),
            "manufacturer": data["manufacturer"],
            "mfr": data["manufacturer"],
            "origin": origin,
            "luhn_valid": valid_luhn,
            "valid_length": len(digits) in (14, 15, 16)
        }

    # Heuristic resolution for unlisted TAC based on GSMA block prefixes
    if tac.startswith("35"):
        brand = "Android (Qualcomm/MediaTek)"
        model = f"Global Smartphone (TAC {tac})"
        gen = "4G LTE / 5G"
        dev_type = "Smartphone"
        mfr = "GSMA Standard Allocation"
        origin = "Global / East Asia"
    elif tac.startswith("86"):
        brand = "Xiaomi / BBK Group (Vivo/Oppo)"
        model = f"APAC Smartphone (TAC {tac})"
        gen = "4G LTE / 5G"
        dev_type = "Smartphone"
        mfr = "China MIIT / GSMA"
        origin = "China (APAC)"
    elif tac.startswith("01"):
        brand = "Apple / North America"
        model = f"Cellular Handset (TAC {tac})"
        gen = "4G LTE / 5G"
        dev_type = "Smartphone"
        mfr = "PTCRB / GSMA"
        origin = "United States"
    elif tac.startswith("99"):
        brand = "Multi-Mode CDMA/LTE"
        model = f"Terminal (TAC {tac})"
        gen = "4G LTE"
        dev_type = "Smartphone"
        mfr = "TIA / GSMA"
        origin = "Global Multi-Band"
    else:
        brand = "Generic Cellular Device"
        model = f"Handset (TAC {tac})"
        gen = "GSM / VoLTE"
        dev_type = "Mobile Terminal"
        mfr = "GSMA Standard Allocation"
        origin = "International"

    return {
        "imei": imei,
        "tac": tac,
        "brand": brand,
        "model": model,
        "marketing_name": f"{brand} {model}",
        "generation": gen,
        "device_type": dev_type,
        "manufacturer": mfr,
        "mfr": mfr,
        "origin": origin,
        "luhn_valid": valid_luhn,
        "valid_length": len(digits) in (14, 15, 16)
    }


# ----------------- EXECUTIVE METRICS -----------------
def get_executive_metrics(case_id: str | None, db: Session) -> dict:
    """
    Computes dynamic executive metrics from SQLite via SQLAlchemy and pandas:
    - total_cases, pending_cases, completed_cases, active_investigations
    - total_cdrs, analyzed_numbers, common_numbers, locations_tracked, total_ipdrs
    """
    total_cases = db.query(Case).count()
    completed_cases = db.query(Case).filter(Case.status == "COMPLETED").count()
    active_cases = db.query(Case).filter(Case.status == "ACTIVE").count()
    pending_cases = db.query(Case).filter(Case.status != "COMPLETED").count()

    cdr_q = db.query(CDRRecord)
    ipdr_q = db.query(IPDRRecord)
    if case_id:
        cdr_q = cdr_q.filter(CDRRecord.case_id == case_id)
        ipdr_q = ipdr_q.filter(IPDRRecord.case_id == case_id)

    total_cdrs = cdr_q.count()
    total_ipdrs = ipdr_q.count()

    # Unique numbers analyzed across a_number and b_number
    all_cdr_recs = cdr_q.with_entities(CDRRecord.a_number, CDRRecord.b_number).all()
    nums = set()
    for a, b in all_cdr_recs:
        if a:
            nums.add(a)
        if b:
            nums.add(b)
    analyzed_numbers = len(nums)

    # Locations tracked (distinct non-empty cell_id)
    cell_recs = cdr_q.with_entities(CDRRecord.cell_id).distinct().all()
    locations_tracked = len([c[0] for c in cell_recs if c[0]])

    # Common numbers calculation
    if case_id:
        suspects = list(get_suspect_numbers_for_case(case_id, db))
        if len(suspects) >= 2:
            comm = find_common_numbers(suspects, case_id, db)
            common_numbers = comm.get("common_contacts_count", 0)
        else:
            caller_map = defaultdict(set)
            for a, b in all_cdr_recs:
                if a and b:
                    caller_map[b].add(a)
            common_numbers = sum(1 for peers in caller_map.values() if len(peers) >= 2)
    else:
        caller_map = defaultdict(set)
        for a, b in all_cdr_recs:
            if a and b:
                caller_map[b].add(a)
        common_numbers = sum(1 for peers in caller_map.values() if len(peers) >= 2)

    return {
        "total_cases": total_cases,
        "pending_cases": pending_cases,
        "completed_cases": completed_cases,
        "active_investigations": active_cases,
        "total_cdrs": total_cdrs,
        "total_uploaded_cdrs": total_cdrs,
        "total_ipdrs": total_ipdrs,
        "analyzed_numbers": analyzed_numbers,
        "common_numbers": common_numbers,
        "locations_tracked": locations_tracked
    }


# ----------------- RAW CDR RECORDS (PAGINATED) -----------------
def get_raw_cdr_records(case_id: str, db: Session, page: int = 1, limit: int = 50, search: str = "", call_type: str = "") -> dict:
    """
    Paginated raw records with full pagination metadata and source preservation.
    """
    page = max(1, page)
    limit = max(1, min(limit, 500))

    q = db.query(CDRRecord).filter(CDRRecord.case_id == case_id)

    if search:
        s = f"%{search.strip()}%"
        q = q.filter(
            or_(
                CDRRecord.a_number.like(s),
                CDRRecord.b_number.like(s),
                CDRRecord.imei.like(s),
                CDRRecord.imsi.like(s),
                CDRRecord.cell_id.like(s)
            )
        )

    if call_type:
        clean_ct = call_type.strip().upper()
        if "IN" in clean_ct:
            clean_ct = "IN"
        elif "SMS" in clean_ct:
            clean_ct = "SMS"
        elif "OUT" in clean_ct:
            clean_ct = "OUT"
        q = q.filter(CDRRecord.call_type == clean_ct)

    total_records = q.count()
    total_pages = (total_records + limit - 1) // limit if total_records > 0 else 1
    offset = (page - 1) * limit

    records = q.order_by(CDRRecord.start_time.asc()).offset(offset).limit(limit).all()
    towers = {t.cell_id: t.area_name for t in db.query(CellTower).all()}

    results = []
    for r in records:
        results.append({
            "id": r.id,
            "case_id": r.case_id,
            "a_number": r.a_number,
            "b_number": r.b_number,
            "call_type": r.call_type,
            "start_time": r.start_time,
            "duration_sec": r.duration_sec,
            "imei": r.imei,
            "imsi": r.imsi,
            "cell_id": r.cell_id,
            "area_name": towers.get(r.cell_id, "Unknown Area"),
            "location_name": towers.get(r.cell_id, "Unknown Area"),
            "source_file": r.source_file,
            "source_row": r.source_row
        })

    return {
        "records": results,
        "total": total_records,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


# ----------------- MOST FREQUENT CONTACTS (MFC) -----------------
def get_mfc_analysis(case_id: str, db: Session, target_number: str | None = None, top: int = 25) -> list[dict]:
    """
    Top contacts sorted dynamically by call frequency and total duration.
    """
    top = max(1, min(top, 200))
    q = db.query(CDRRecord).filter(CDRRecord.case_id == case_id)

    clean_num = None
    if target_number:
        clean_num = target_number.strip().replace("+91", "").lstrip("0")
        q = q.filter(or_(CDRRecord.a_number == clean_num, CDRRecord.b_number == clean_num))

    records = q.order_by(CDRRecord.start_time.asc()).all()
    towers = {t.cell_id: t.area_name for t in db.query(CellTower).all()}

    contact_stats = defaultdict(lambda: {
        "call_count": 0,
        "total_duration_sec": 0,
        "incoming_count": 0,
        "outgoing_count": 0,
        "sms_count": 0,
        "first_call": None,
        "last_call": None,
        "dates_active": set(),
        "sample_evidence": []
    })

    for r in records:
        dur = r.duration_sec or 0
        if clean_num:
            peer = r.b_number if r.a_number == clean_num else r.a_number
            is_calling = (r.a_number == clean_num)
        else:
            peer = r.b_number if r.b_number else r.a_number
            is_calling = True

        st = contact_stats[peer]
        st["call_count"] += 1
        st["total_duration_sec"] += dur
        if r.call_type == "SMS":
            st["sms_count"] += 1
        elif (is_calling and r.call_type == "OUT") or (not is_calling and r.call_type == "IN"):
            st["outgoing_count"] += 1
        else:
            st["incoming_count"] += 1

        if not st["first_call"] or r.start_time < st["first_call"]:
            st["first_call"] = r.start_time
        if not st["last_call"] or r.start_time > st["last_call"]:
            st["last_call"] = r.start_time

        st["dates_active"].add(r.start_time[:10])

        if len(st["sample_evidence"]) < 3:
            st["sample_evidence"].append({
                "source_file": r.source_file,
                "source_row": r.source_row,
                "timestamp": r.start_time,
                "a_number": r.a_number,
                "b_number": r.b_number,
                "call_type": r.call_type,
                "duration_sec": r.duration_sec,
                "cell_id": r.cell_id,
                "location_name": towers.get(r.cell_id, "Unknown Area")
            })

    results = []
    for peer, st in contact_stats.items():
        results.append({
            "contact_number": peer,
            "call_count": st["call_count"],
            "total_duration_sec": st["total_duration_sec"],
            "incoming_count": st["incoming_count"],
            "outgoing_count": st["outgoing_count"],
            "sms_count": st["sms_count"],
            "days_active": len(st["dates_active"]),
            "first_call": st["first_call"],
            "last_call": st["last_call"],
            "sample_evidence": st["sample_evidence"]
        })

    results.sort(key=lambda x: (x["call_count"], x["total_duration_sec"]), reverse=True)
    return results[:top]


# ----------------- DAY VS NIGHT FORENSICS -----------------
def get_day_night_analysis(case_id: str, db: Session, target_number: str | None = None) -> dict:
    """
    Day (06:00-22:00) vs Night (22:00-06:00) calls and cell tower locations.
    """
    q = db.query(CDRRecord).filter(CDRRecord.case_id == case_id)
    clean_num = None
    if target_number:
        clean_num = target_number.strip().replace("+91", "").lstrip("0")
        q = q.filter(or_(CDRRecord.a_number == clean_num, CDRRecord.b_number == clean_num))

    records = q.order_by(CDRRecord.start_time.asc()).all()
    towers = {t.cell_id: t for t in db.query(CellTower).all()}

    day_calls = []
    night_calls = []
    day_tower_counts = defaultdict(int)
    night_tower_counts = defaultdict(int)
    day_duration = 0
    night_duration = 0

    for r in records:
        dur = r.duration_sec or 0
        hour = 12
        try:
            hour = datetime.fromisoformat(r.start_time).hour
        except Exception:
            pass

        t_meta = towers.get(r.cell_id)
        ev = {
            "source_file": r.source_file,
            "source_row": r.source_row,
            "timestamp": r.start_time,
            "a_number": r.a_number,
            "b_number": r.b_number,
            "call_type": r.call_type,
            "duration_sec": r.duration_sec,
            "cell_id": r.cell_id,
            "area_name": t_meta.area_name if t_meta else "Unknown Area",
            "lat": t_meta.lat if t_meta else None,
            "lon": t_meta.lon if t_meta else None
        }

        # Day: 06:00 <= hour < 22:00; Night: hour >= 22 or hour < 06
        if 6 <= hour < 22:
            day_calls.append(ev)
            day_duration += dur
            if r.cell_id:
                day_tower_counts[r.cell_id] += 1
        else:
            night_calls.append(ev)
            night_duration += dur
            if r.cell_id:
                night_tower_counts[r.cell_id] += 1

    total = len(records)
    day_locations = []
    for cid, cnt in sorted(day_tower_counts.items(), key=lambda x: x[1], reverse=True):
        t_meta = towers.get(cid)
        day_locations.append({
            "cell_id": cid,
            "count": cnt,
            "area_name": t_meta.area_name if t_meta else "Unknown Tower",
            "lat": t_meta.lat if t_meta else None,
            "lon": t_meta.lon if t_meta else None
        })

    night_locations = []
    for cid, cnt in sorted(night_tower_counts.items(), key=lambda x: x[1], reverse=True):
        t_meta = towers.get(cid)
        night_locations.append({
            "cell_id": cid,
            "count": cnt,
            "area_name": t_meta.area_name if t_meta else "Unknown Tower",
            "lat": t_meta.lat if t_meta else None,
            "lon": t_meta.lon if t_meta else None
        })

    return {
        "target_number": clean_num,
        "summary": {
            "total_calls": total,
            "day_calls_count": len(day_calls),
            "night_calls_count": len(night_calls),
            "day_percentage": round((len(day_calls) / max(total, 1)) * 100, 2),
            "night_percentage": round((len(night_calls) / max(total, 1)) * 100, 2),
            "day_duration_sec": day_duration,
            "night_duration_sec": night_duration
        },
        "day_calls": day_calls[:100],
        "night_calls": night_calls[:100],
        "day_locations": day_locations,
        "night_locations": night_locations
    }


# ----------------- FIRST / LAST CALL ANALYSIS -----------------
def get_first_last_calls(case_id: str, db: Session, target_number: str | None = None) -> list[dict]:
    """
    Per contact: first call timestamp/cell, last call timestamp/cell, total calls, duration, days active.
    """
    q = db.query(CDRRecord).filter(CDRRecord.case_id == case_id)
    clean_num = None
    if target_number:
        clean_num = target_number.strip().replace("+91", "").lstrip("0")
        q = q.filter(or_(CDRRecord.a_number == clean_num, CDRRecord.b_number == clean_num))

    records = q.order_by(CDRRecord.start_time.asc()).all()
    towers = {t.cell_id: t.area_name for t in db.query(CellTower).all()}

    stats = defaultdict(lambda: {
        "first_rec": None,
        "last_rec": None,
        "total_calls": 0,
        "total_duration_sec": 0,
        "dates": set()
    })

    for r in records:
        if clean_num:
            peer = r.b_number if r.a_number == clean_num else r.a_number
        else:
            peer = r.b_number if r.b_number else r.a_number

        s = stats[peer]
        s["total_calls"] += 1
        s["total_duration_sec"] += (r.duration_sec or 0)
        s["dates"].add(r.start_time[:10])

        if not s["first_rec"] or r.start_time < s["first_rec"].start_time:
            s["first_rec"] = r
        if not s["last_rec"] or r.start_time > s["last_rec"].start_time:
            s["last_rec"] = r

    results = []
    for peer, s in stats.items():
        f = s["first_rec"]
        l = s["last_rec"]
        results.append({
            "contact_number": peer,
            "total_calls": s["total_calls"],
            "total_duration_sec": s["total_duration_sec"],
            "days_active": len(s["dates"]),
            "first_call_time": f.start_time,
            "first_call_cell": f.cell_id,
            "first_call_area": towers.get(f.cell_id, "Unknown Area"),
            "first_call_type": f.call_type,
            "first_call_evidence": {
                "source_file": f.source_file,
                "source_row": f.source_row,
                "timestamp": f.start_time,
                "cell_id": f.cell_id
            },
            "last_call_time": l.start_time,
            "last_call_cell": l.cell_id,
            "last_call_area": towers.get(l.cell_id, "Unknown Area"),
            "last_call_type": l.call_type,
            "last_call_evidence": {
                "source_file": l.source_file,
                "source_row": l.source_row,
                "timestamp": l.start_time,
                "cell_id": l.cell_id
            }
        })

    results.sort(key=lambda x: x["last_call_time"], reverse=True)
    return results


# ----------------- MISSING DATES / SILENCE ANALYSIS -----------------
def get_missing_dates_analysis(case_id: str, db: Session, target_number: str | None = None) -> dict:
    """
    Identifies calendar dates with 0 activity (silence periods/phone turned off)
    between suspect start and end dates or entire case investigation timeframe.
    """
    all_case_records = db.query(CDRRecord).filter(CDRRecord.case_id == case_id).all()
    if not all_case_records:
        return {
            "target_number": target_number,
            "investigation_start_date": None,
            "investigation_end_date": None,
            "total_days": 0,
            "active_days_count": 0,
            "missing_days_count": 0,
            "missing_dates": [],
            "silence_periods": [],
            "daily_activity": [],
            "suspects_analysis": []
        }

    case_dates = sorted(set(r.start_time[:10] for r in all_case_records if r.start_time))
    case_start = min(case_dates)
    case_end = max(case_dates)

    def analyze_number_dates(num: str):
        recs = [r for r in all_case_records if r.a_number == num or r.b_number == num]
        if not recs:
            return {
                "number": num,
                "first_activity": None,
                "last_activity": None,
                "missing_dates": [],
                "silence_periods": [],
                "daily_counts": []
            }

        dates_with_calls = defaultdict(int)
        for r in recs:
            dates_with_calls[r.start_time[:10]] += 1

        active_dates = sorted(dates_with_calls.keys())
        first_act = active_dates[0]
        last_act = active_dates[-1]

        cur = datetime.fromisoformat(case_start).date()
        end_d = datetime.fromisoformat(case_end).date()

        missing = []
        daily = []
        while cur <= end_d:
            d_str = cur.isoformat()
            cnt = dates_with_calls.get(d_str, 0)
            daily.append({"date": d_str, "calls": cnt})
            if cnt == 0:
                missing.append(d_str)
            cur += timedelta(days=1)

        silence_periods = []
        if missing:
            cur_p_start = missing[0]
            cur_p_end = missing[0]
            cur_p_days = 1

            for i in range(1, len(missing)):
                d_prev = datetime.fromisoformat(missing[i-1]).date()
                d_curr = datetime.fromisoformat(missing[i]).date()
                if (d_curr - d_prev).days == 1:
                    cur_p_end = missing[i]
                    cur_p_days += 1
                else:
                    silence_periods.append({
                        "start_date": cur_p_start,
                        "end_date": cur_p_end,
                        "gap_days": cur_p_days,
                        "description": f"Silence period of {cur_p_days} day(s) with 0 activity"
                    })
                    cur_p_start = missing[i]
                    cur_p_end = missing[i]
                    cur_p_days = 1

            silence_periods.append({
                "start_date": cur_p_start,
                "end_date": cur_p_end,
                "gap_days": cur_p_days,
                "description": f"Silence period of {cur_p_days} day(s) with 0 activity"
            })

        return {
            "number": num,
            "first_activity": first_act,
            "last_activity": last_act,
            "active_days_count": len(active_dates),
            "missing_days_count": len(missing),
            "missing_dates": missing,
            "silence_periods": silence_periods,
            "daily_counts": daily
        }

    if target_number:
        clean_num = target_number.strip().replace("+91", "").lstrip("0")
        target_res = analyze_number_dates(clean_num)
        return {
            "target_number": clean_num,
            "investigation_start_date": case_start,
            "investigation_end_date": case_end,
            "total_days": len(target_res["daily_counts"]),
            "active_days_count": target_res["active_days_count"],
            "missing_days_count": target_res["missing_days_count"],
            "missing_dates": target_res["missing_dates"],
            "silence_periods": target_res["silence_periods"],
            "daily_activity": target_res["daily_counts"],
            "suspects_analysis": []
        }
    else:
        suspects = list(get_suspect_numbers_for_case(case_id, db))
        suspect_analyses = [analyze_number_dates(s) for s in suspects]

        case_date_counts = defaultdict(int)
        for r in all_case_records:
            case_date_counts[r.start_time[:10]] += 1

        cur = datetime.fromisoformat(case_start).date()
        end_d = datetime.fromisoformat(case_end).date()
        case_missing = []
        case_daily = []
        while cur <= end_d:
            d_str = cur.isoformat()
            cnt = case_date_counts.get(d_str, 0)
            case_daily.append({"date": d_str, "calls": cnt})
            if cnt == 0:
                case_missing.append(d_str)
            cur += timedelta(days=1)

        return {
            "target_number": None,
            "investigation_start_date": case_start,
            "investigation_end_date": case_end,
            "total_days": len(case_daily),
            "active_days_count": len(case_dates),
            "missing_days_count": len(case_missing),
            "missing_dates": case_missing,
            "silence_periods": [],
            "daily_activity": case_daily,
            "suspects_analysis": suspect_analyses
        }


# ----------------- MOVEMENT AND CELL CHANGES -----------------
def get_movement_and_cell_changes(case_id: str, db: Session, target_number: str | None = None) -> list[dict]:
    """
    Chronological cell transitions with time intervals, distance (haversine) and speed calculation.
    """
    q = db.query(CDRRecord).filter(
        CDRRecord.case_id == case_id,
        CDRRecord.cell_id != ""
    )
    clean_num = None
    if target_number:
        clean_num = target_number.strip().replace("+91", "").lstrip("0")
        q = q.filter(or_(CDRRecord.a_number == clean_num, CDRRecord.b_number == clean_num))

    records = q.order_by(CDRRecord.start_time.asc()).all()
    towers = {t.cell_id: t for t in db.query(CellTower).all()}

    # Group records by subscriber to ensure transitions belong to the same entity
    recs_by_num = defaultdict(list)
    for r in records:
        key = clean_num if clean_num else r.a_number
        recs_by_num[key].append(r)

    transitions = []

    for num, num_recs in recs_by_num.items():
        seq = 1
        for i in range(1, len(num_recs)):
            prev_r = num_recs[i - 1]
            curr_r = num_recs[i]

            if prev_r.cell_id != curr_r.cell_id:
                t1 = towers.get(prev_r.cell_id)
                t2 = towers.get(curr_r.cell_id)

                dist_km = haversine_km(
                    t1.lat if t1 else None,
                    t1.lon if t1 else None,
                    t2.lat if t2 else None,
                    t2.lon if t2 else None
                )

                time_diff = 0
                try:
                    dt1 = datetime.fromisoformat(prev_r.start_time)
                    dt2 = datetime.fromisoformat(curr_r.start_time)
                    time_diff = max(0, int((dt2 - dt1).total_seconds()))
                except Exception:
                    pass

                speed_kmh = 0.0
                if dist_km and time_diff > 0:
                    speed_kmh = round(dist_km / (time_diff / 3600), 2)

                is_suspicious = speed_kmh > 150.0  # Impossible terrestrial speed indicating SIM hop/cloning

                hrs = int(time_diff // 3600)
                mins = int((time_diff % 3600) // 60)
                secs = int(time_diff % 60)
                diff_fmt = f"{hrs}h {mins}m" if hrs > 0 else f"{mins}m {secs}s"

                transitions.append({
                    "subscriber_number": num,
                    "transition_seq": seq,
                    "from_cell_id": prev_r.cell_id,
                    "from_area": t1.area_name if t1 else "Unknown Area",
                    "from_lat": t1.lat if t1 else None,
                    "from_lon": t1.lon if t1 else None,
                    "to_cell_id": curr_r.cell_id,
                    "to_area": t2.area_name if t2 else "Unknown Area",
                    "to_lat": t2.lat if t2 else None,
                    "to_lon": t2.lon if t2 else None,
                    "start_time": prev_r.start_time,
                    "end_time": curr_r.start_time,
                    "time_diff_sec": time_diff,
                    "time_diff_formatted": diff_fmt,
                    "distance_km": dist_km,
                    "speed_kmh": speed_kmh,
                    "is_suspicious_speed": is_suspicious,
                    "from_evidence": {
                        "source_file": prev_r.source_file,
                        "source_row": prev_r.source_row,
                        "timestamp": prev_r.start_time,
                        "cell_id": prev_r.cell_id,
                        "call_type": prev_r.call_type
                    },
                    "to_evidence": {
                        "source_file": curr_r.source_file,
                        "source_row": curr_r.source_row,
                        "timestamp": curr_r.start_time,
                        "cell_id": curr_r.cell_id,
                        "call_type": curr_r.call_type
                    }
                })
                seq += 1

    transitions.sort(key=lambda x: x["end_time"], reverse=True)
    return transitions


# ----------------- SERVICE AND COMPANY NUMBERS -----------------
def get_service_and_company_numbers(case_id: str, db: Session) -> list[dict]:
    """
    Identifies 1800, 1860, shortcodes, banks, OTP gateways with call counts and suspect linkages.
    """
    records = db.query(CDRRecord).filter(CDRRecord.case_id == case_id).all()
    towers = {t.cell_id: t.area_name for t in db.query(CellTower).all()}

    service_map = defaultdict(lambda: {
        "service_name": "",
        "category": "",
        "call_count": 0,
        "total_duration_sec": 0,
        "first_contact": None,
        "last_contact": None,
        "calling_numbers": set(),
        "evidence": []
    })

    for r in records:
        for num in [r.b_number, r.a_number]:
            if not num:
                continue
            is_srv, srv_name, cat = is_service_number(num)
            if is_srv:
                st = service_map[num]
                st["service_name"] = srv_name
                st["category"] = cat
                st["call_count"] += 1
                st["total_duration_sec"] += (r.duration_sec or 0)
                other = r.a_number if num == r.b_number else r.b_number
                if other:
                    st["calling_numbers"].add(other)

                if not st["first_contact"] or r.start_time < st["first_contact"]:
                    st["first_contact"] = r.start_time
                if not st["last_contact"] or r.start_time > st["last_contact"]:
                    st["last_contact"] = r.start_time

                if len(st["evidence"]) < 5:
                    st["evidence"].append({
                        "source_file": r.source_file,
                        "source_row": r.source_row,
                        "timestamp": r.start_time,
                        "a_number": r.a_number,
                        "b_number": r.b_number,
                        "call_type": r.call_type,
                        "duration_sec": r.duration_sec,
                        "cell_id": r.cell_id,
                        "location_name": towers.get(r.cell_id, "Unknown Area")
                    })

    results = []
    for num, st in service_map.items():
        results.append({
            "number": num,
            "service_name": st["service_name"],
            "category": st["category"],
            "call_count": st["call_count"],
            "total_duration_sec": st["total_duration_sec"],
            "first_contact": st["first_contact"],
            "last_contact": st["last_contact"],
            "calling_numbers": sorted(list(st["calling_numbers"])),
            "evidence": st["evidence"]
        })

    results.sort(key=lambda x: x["call_count"], reverse=True)
    return results


# ----------------- INTERNATIONAL INTELLIGENCE -----------------
def get_international_intelligence(case_id: str, db: Session) -> list[dict]:
    """
    Identifies communications with non-Indian international dialing codes (+971, +1, +44, etc.).
    """
    records = db.query(CDRRecord).filter(CDRRecord.case_id == case_id).all()
    towers = {t.cell_id: t.area_name for t in db.query(CellTower).all()}

    intl_map = defaultdict(lambda: {
        "country": "",
        "country_code": "",
        "risk_level": "MEDIUM",
        "call_count": 0,
        "total_duration_sec": 0,
        "first_seen": None,
        "last_seen": None,
        "linked_local_numbers": set(),
        "call_types": set(),
        "evidence": []
    })

    for r in records:
        for num in [r.b_number, r.a_number]:
            if not num:
                continue
            is_intl, country, code, risk = is_international_number(num)
            if is_intl:
                st = intl_map[num]
                st["country"] = country
                st["country_code"] = code
                st["risk_level"] = risk
                st["call_count"] += 1
                st["total_duration_sec"] += (r.duration_sec or 0)
                st["call_types"].add(r.call_type)

                local = r.a_number if num == r.b_number else r.b_number
                if local:
                    st["linked_local_numbers"].add(local)

                if not st["first_seen"] or r.start_time < st["first_seen"]:
                    st["first_seen"] = r.start_time
                if not st["last_seen"] or r.start_time > st["last_seen"]:
                    st["last_seen"] = r.start_time

                if len(st["evidence"]) < 5:
                    st["evidence"].append({
                        "source_file": r.source_file,
                        "source_row": r.source_row,
                        "timestamp": r.start_time,
                        "a_number": r.a_number,
                        "b_number": r.b_number,
                        "call_type": r.call_type,
                        "duration_sec": r.duration_sec,
                        "cell_id": r.cell_id,
                        "location_name": towers.get(r.cell_id, "Unknown Area")
                    })

    results = []
    for num, st in intl_map.items():
        results.append({
            "number": num,
            "country": st["country"],
            "country_code": st["country_code"],
            "risk_level": st["risk_level"],
            "call_count": st["call_count"],
            "total_duration_sec": st["total_duration_sec"],
            "first_seen": st["first_seen"],
            "last_seen": st["last_seen"],
            "linked_local_numbers": sorted(list(st["linked_local_numbers"])),
            "call_types": sorted(list(st["call_types"])),
            "evidence": st["evidence"]
        })

    results.sort(key=lambda x: x["call_count"], reverse=True)
    return results


# ----------------- IMEI SUMMARY LIST -----------------
def get_imei_summary_list(case_id: str, db: Session) -> list[dict]:
    """
    Grouped by IMEI: TAC device model, linked IMSIs, linked numbers, call count, first/last seen.
    """
    records = db.query(CDRRecord).filter(
        CDRRecord.case_id == case_id,
        CDRRecord.imei != ""
    ).all()
    towers = {t.cell_id: t.area_name for t in db.query(CellTower).all()}

    imei_map = defaultdict(lambda: {
        "call_count": 0,
        "total_duration_sec": 0,
        "linked_imsis": set(),
        "linked_numbers": set(),
        "towers_used": set(),
        "first_seen": None,
        "last_seen": None,
        "sample_evidence": []
    })

    for r in records:
        st = imei_map[r.imei]
        st["call_count"] += 1
        st["total_duration_sec"] += (r.duration_sec or 0)
        if r.imsi:
            st["linked_imsis"].add(r.imsi)
        if r.a_number:
            st["linked_numbers"].add(r.a_number)
        if r.cell_id:
            st["towers_used"].add(r.cell_id)

        if not st["first_seen"] or r.start_time < st["first_seen"]:
            st["first_seen"] = r.start_time
        if not st["last_seen"] or r.start_time > st["last_seen"]:
            st["last_seen"] = r.start_time

        if len(st["sample_evidence"]) < 3:
            st["sample_evidence"].append({
                "source_file": r.source_file,
                "source_row": r.source_row,
                "timestamp": r.start_time,
                "a_number": r.a_number,
                "b_number": r.b_number,
                "call_type": r.call_type,
                "duration_sec": r.duration_sec,
                "cell_id": r.cell_id,
                "location_name": towers.get(r.cell_id, "Unknown Area")
            })

    results = []
    for imei, st in imei_map.items():
        device = lookup_tac_device(imei)
        results.append({
            "imei": imei,
            "tac": imei[:8] if len(imei) >= 8 else "",
            "device_info": device,
            "brand": device["brand"],
            "model": device["model"],
            "generation": device["generation"],
            "call_count": st["call_count"],
            "total_duration_sec": st["total_duration_sec"],
            "linked_imsis": sorted(list(st["linked_imsis"])),
            "linked_numbers": sorted(list(st["linked_numbers"])),
            "is_multi_sim": (len(st["linked_numbers"]) > 1 or len(st["linked_imsis"]) > 1),
            "unique_towers_count": len(st["towers_used"]),
            "first_seen": st["first_seen"],
            "last_seen": st["last_seen"],
            "sample_evidence": st["sample_evidence"]
        })

    results.sort(key=lambda x: x["call_count"], reverse=True)
    return results


# ----------------- IMSI SUMMARY LIST -----------------
def get_imsi_summary_list(case_id: str, db: Session) -> list[dict]:
    """
    Grouped by IMSI: carrier info, linked IMEIs, linked numbers, call count, first/last seen.
    """
    records = db.query(CDRRecord).filter(
        CDRRecord.case_id == case_id,
        CDRRecord.imsi != ""
    ).all()
    towers = {t.cell_id: t.area_name for t in db.query(CellTower).all()}

    imsi_map = defaultdict(lambda: {
        "call_count": 0,
        "total_duration_sec": 0,
        "linked_imeis": set(),
        "linked_numbers": set(),
        "towers_used": set(),
        "first_seen": None,
        "last_seen": None,
        "sample_evidence": []
    })

    for r in records:
        st = imsi_map[r.imsi]
        st["call_count"] += 1
        st["total_duration_sec"] += (r.duration_sec or 0)
        if r.imei:
            st["linked_imeis"].add(r.imei)
        if r.a_number:
            st["linked_numbers"].add(r.a_number)
        if r.cell_id:
            st["towers_used"].add(r.cell_id)

        if not st["first_seen"] or r.start_time < st["first_seen"]:
            st["first_seen"] = r.start_time
        if not st["last_seen"] or r.start_time > st["last_seen"]:
            st["last_seen"] = r.start_time

        if len(st["sample_evidence"]) < 3:
            st["sample_evidence"].append({
                "source_file": r.source_file,
                "source_row": r.source_row,
                "timestamp": r.start_time,
                "a_number": r.a_number,
                "b_number": r.b_number,
                "call_type": r.call_type,
                "duration_sec": r.duration_sec,
                "cell_id": r.cell_id,
                "location_name": towers.get(r.cell_id, "Unknown Area")
            })

    results = []
    for imsi, st in imsi_map.items():
        carrier = "Indian Telecom Carrier"
        if imsi.startswith("40445"):
            carrier = "Bharti Airtel (Rajasthan)"
        elif imsi.startswith("40585"):
            carrier = "Reliance Jio (Rajasthan)"
        elif imsi.startswith("40420"):
            carrier = "Vodafone Idea (Vi)"
        elif imsi.startswith("40400"):
            carrier = "BSNL Rajasthan"

        linked_devices = [lookup_tac_device(im) for im in sorted(list(st["linked_imeis"]))]

        results.append({
            "imsi": imsi,
            "carrier": carrier,
            "mcc_mnc": f"{imsi[:3]}-{imsi[3:5]}" if len(imsi) >= 5 else "",
            "call_count": st["call_count"],
            "total_duration_sec": st["total_duration_sec"],
            "linked_imeis": sorted(list(st["linked_imeis"])),
            "linked_devices": linked_devices,
            "linked_numbers": sorted(list(st["linked_numbers"])),
            "is_multi_handset": len(st["linked_imeis"]) > 1,
            "unique_towers_count": len(st["towers_used"]),
            "first_seen": st["first_seen"],
            "last_seen": st["last_seen"],
            "sample_evidence": st["sample_evidence"]
        })

    results.sort(key=lambda x: x["call_count"], reverse=True)
    return results


# ----------------- GLOBAL SEARCH -----------------
def global_search(query: str, case_id: str | None, db: Session) -> dict:
    """
    Multi-field global search across cases, numbers, IMEIs, IMSIs, Cell IDs, IPDR IPs.
    """
    q_str = str(query).strip() if query else ""
    if not q_str:
        return {
            "query": "",
            "case_id": case_id,
            "total_matches": 0,
            "results": {
                "cases": [],
                "numbers": [],
                "imeis": [],
                "imsis": [],
                "towers": [],
                "ipdr": []
            }
        }

    s_pattern = f"%{q_str}%"

    # 1. Search Cases
    cases_q = db.query(Case).filter(
        or_(
            Case.id.ilike(s_pattern),
            Case.title.ilike(s_pattern),
            Case.description.ilike(s_pattern)
        )
    )
    if case_id:
        cases_q = cases_q.filter(Case.id == case_id)
    matched_cases = [
        {"id": c.id, "title": c.title, "status": c.status, "created_at": c.created_at.isoformat() if c.created_at else None}
        for c in cases_q.limit(20).all()
    ]

    # 2. Search CDR Records
    cdr_base = db.query(CDRRecord)
    if case_id:
        cdr_base = cdr_base.filter(CDRRecord.case_id == case_id)

    num_cdrs = cdr_base.filter(
        or_(CDRRecord.a_number.like(s_pattern), CDRRecord.b_number.like(s_pattern))
    ).limit(60).all()

    number_map = defaultdict(lambda: {"count": 0, "first_seen": None, "last_seen": None, "samples": []})
    for r in num_cdrs:
        for n in [r.a_number, r.b_number]:
            if q_str in n:
                st = number_map[n]
                st["count"] += 1
                if not st["first_seen"] or r.start_time < st["first_seen"]:
                    st["first_seen"] = r.start_time
                if not st["last_seen"] or r.start_time > st["last_seen"]:
                    st["last_seen"] = r.start_time
                if len(st["samples"]) < 2:
                    st["samples"].append({
                        "source_file": r.source_file,
                        "source_row": r.source_row,
                        "timestamp": r.start_time,
                        "call_type": r.call_type
                    })

    matched_numbers = [
        {
            "number": n,
            "call_count": st["count"],
            "first_seen": st["first_seen"],
            "last_seen": st["last_seen"],
            "evidence": st["samples"]
        }
        for n, st in number_map.items()
    ]

    # IMEIs: search by IMEI digits OR brand / model name
    all_imei_recs = cdr_base.filter(CDRRecord.imei != "").all()
    matching_imeis_set = set()
    for r in all_imei_recs:
        if q_str in r.imei:
            matching_imeis_set.add(r.imei)
        else:
            dev = lookup_tac_device(r.imei)
            if q_str.lower() in dev["brand"].lower() or q_str.lower() in dev["model"].lower():
                matching_imeis_set.add(r.imei)

    imei_map = defaultdict(lambda: {"count": 0, "first_seen": None, "last_seen": None, "numbers": set(), "samples": []})
    for r in all_imei_recs:
        if r.imei in matching_imeis_set:
            st = imei_map[r.imei]
            st["count"] += 1
            st["numbers"].add(r.a_number)
            if not st["first_seen"] or r.start_time < st["first_seen"]:
                st["first_seen"] = r.start_time
            if not st["last_seen"] or r.start_time > st["last_seen"]:
                st["last_seen"] = r.start_time
            if len(st["samples"]) < 2:
                st["samples"].append({"source_file": r.source_file, "source_row": r.source_row, "timestamp": r.start_time})

    matched_imeis = [
        {
            "imei": im,
            "device": lookup_tac_device(im),
            "call_count": st["count"],
            "linked_numbers": list(st["numbers"]),
            "first_seen": st["first_seen"],
            "last_seen": st["last_seen"],
            "evidence": st["samples"]
        }
        for im, st in imei_map.items()
    ]

    # IMSIs
    imsi_cdrs = cdr_base.filter(CDRRecord.imsi.like(s_pattern)).limit(50).all()
    imsi_map = defaultdict(lambda: {"count": 0, "first_seen": None, "last_seen": None, "numbers": set(), "samples": []})
    for r in imsi_cdrs:
        st = imsi_map[r.imsi]
        st["count"] += 1
        st["numbers"].add(r.a_number)
        if not st["first_seen"] or r.start_time < st["first_seen"]:
            st["first_seen"] = r.start_time
        if not st["last_seen"] or r.start_time > st["last_seen"]:
            st["last_seen"] = r.start_time
        if len(st["samples"]) < 2:
            st["samples"].append({"source_file": r.source_file, "source_row": r.source_row, "timestamp": r.start_time})

    matched_imsis = [
        {
            "imsi": ims,
            "call_count": st["count"],
            "linked_numbers": list(st["numbers"]),
            "first_seen": st["first_seen"],
            "last_seen": st["last_seen"],
            "evidence": st["samples"]
        }
        for ims, st in imsi_map.items()
    ]

    # Cell Towers
    towers_q = db.query(CellTower).filter(
        or_(
            CellTower.cell_id.ilike(s_pattern),
            CellTower.area_name.ilike(s_pattern)
        )
    ).limit(20).all()
    matched_towers = [
        {
            "cell_id": t.cell_id,
            "area_name": t.area_name,
            "lat": t.lat,
            "lon": t.lon,
            "lac": t.lac
        }
        for t in towers_q
    ]

    # IPDR Records
    ipdr_q = db.query(IPDRRecord)
    if case_id:
        ipdr_q = ipdr_q.filter(IPDRRecord.case_id == case_id)
    ipdr_matched = ipdr_q.filter(
        or_(
            IPDRRecord.subscriber_number.like(s_pattern),
            IPDRRecord.source_ip.like(s_pattern),
            IPDRRecord.destination_ip.like(s_pattern),
            IPDRRecord.app_hint.ilike(s_pattern)
        )
    ).limit(30).all()

    matched_ipdr = [
        {
            "id": ip.id,
            "subscriber_number": ip.subscriber_number,
            "source_ip": ip.source_ip,
            "source_port": ip.source_port,
            "destination_ip": ip.destination_ip,
            "destination_port": ip.destination_port,
            "session_start": ip.session_start,
            "session_end": ip.session_end,
            "app_hint": ip.app_hint,
            "bytes_transferred": ip.bytes_transferred,
            "source_file": ip.source_file,
            "source_row": ip.source_row
        }
        for ip in ipdr_matched
    ]

    total_matches = (
        len(matched_cases) +
        len(matched_numbers) +
        len(matched_imeis) +
        len(matched_imsis) +
        len(matched_towers) +
        len(matched_ipdr)
    )

    return {
        "query": q_str,
        "case_id": case_id,
        "total_matches": total_matches,
        "results": {
            "cases": matched_cases,
            "numbers": matched_numbers,
            "imeis": matched_imeis,
            "imsis": matched_imsis,
            "towers": matched_towers,
            "ipdr": matched_ipdr
        }
    }


# ----------------- ORIGINAL CORE FORENSIC MODULES -----------------
def get_ordered_suspects_for_case(case_id: str, db: Session) -> list[dict]:
    """Return suspects from case brief, or dynamically derive top active targets from CDRs."""
    c = db.query(Case).filter(Case.id == case_id).first()
    if c and c.brief_data:
        try:
            data = json.loads(c.brief_data)
            suspects = data.get("suspects", [])
            if suspects:
                return suspects
        except Exception:
            pass

    # Dynamic derivation from CDR records when case brief has no predefined suspects
    rows = db.query(CDRRecord).filter(CDRRecord.case_id == case_id).all()
    if not rows:
        return []

    counts = defaultdict(lambda: {"calls": 0, "imeis": set(), "imsis": set()})
    for r in rows:
        if r.a_number:
            counts[r.a_number]["calls"] += 1
            if r.imei:
                counts[r.a_number]["imeis"].add(r.imei)
            if r.imsi:
                counts[r.a_number]["imsis"].add(r.imsi)

    top_nums = sorted(counts.items(), key=lambda x: x[1]["calls"], reverse=True)[:6]
    derived = []
    for idx, (phone, info) in enumerate(top_nums, start=1):
        imei = sorted(info["imeis"])[0] if info["imeis"] else ""
        tac = lookup_tac_device(imei) if imei else {}
        handset = f"{tac.get('brand', 'Unknown')} {tac.get('model', 'Terminal')}".strip() if tac else "Smartphone"
        derived.append({
            "id": f"T{idx}",
            "name": f"Target {idx}",
            "phone": phone,
            "role": "Primary Active Subscriber" if idx <= 2 else "Active Contact",
            "imei": imei,
            "handset": handset,
            "notes": f"Dynamically profiled from {info['calls']} CDR transactions."
        })
    return derived


def get_suspect_numbers_for_case(case_id: str, db: Session) -> set[str]:
    suspects = get_ordered_suspects_for_case(case_id, db)
    nums = set()
    for s in suspects:
        if s.get("phone"):
            nums.add(s["phone"])
        if s.get("new_phone"):
            nums.add(s["new_phone"])
    return nums


def analyze_communication_patterns(number: str, case_id: str, db: Session) -> dict:
    """
    Analyzes all communications for a given phone number.
    Returns:
    - total_calls, total_duration, in_count, out_count, sms_count, in_out_ratio
    - first_comm, last_comm
    - top_contacts (with call count and duration)
    - night_activity (22:00 to 05:00)
    - unusual_contacts (called only once, or only at night)
    """
    records = db.query(CDRRecord).filter(
        CDRRecord.case_id == case_id,
        or_(CDRRecord.a_number == number, CDRRecord.b_number == number)
    ).order_by(CDRRecord.start_time.asc()).all()

    if not records:
        return {
            "target_number": number,
            "total_calls": 0,
            "total_duration_sec": 0,
            "incoming_calls": 0,
            "outgoing_calls": 0,
            "sms_count": 0,
            "in_out_ratio": 0.0,
            "first_communication": None,
            "last_communication": None,
            "top_contacts": [],
            "night_activity": {"count": 0, "percentage": 0.0, "records": []},
            "unusual_contacts": []
        }

    total_calls = len(records)
    total_duration = 0
    in_count = 0
    out_count = 0
    sms_count = 0

    contact_stats = defaultdict(lambda: {
        "call_count": 0,
        "total_duration": 0,
        "first_seen": None,
        "last_seen": None,
        "night_calls": 0,
        "sample_evidence": []
    })

    night_records = []
    first_comm = records[0].start_time
    last_comm = records[-1].start_time

    for r in records:
        dur = r.duration_sec or 0
        total_duration += dur
        is_calling = (r.a_number == number)
        peer = r.b_number if is_calling else r.a_number

        if r.call_type == "SMS":
            sms_count += 1
        elif (is_calling and r.call_type == "OUT") or (not is_calling and r.call_type == "IN"):
            out_count += 1
        else:
            in_count += 1

        dt_hour = 12
        try:
            dt_hour = datetime.fromisoformat(r.start_time).hour
        except Exception:
            pass

        is_night = (dt_hour >= 22 or dt_hour < 5)

        stats = contact_stats[peer]
        stats["call_count"] += 1
        stats["total_duration"] += dur
        if not stats["first_seen"] or r.start_time < stats["first_seen"]:
            stats["first_seen"] = r.start_time
        if not stats["last_seen"] or r.start_time > stats["last_seen"]:
            stats["last_seen"] = r.start_time

        evidence_item = {
            "source_file": r.source_file,
            "source_row": r.source_row,
            "timestamp": r.start_time,
            "a_number": r.a_number,
            "b_number": r.b_number,
            "call_type": r.call_type,
            "duration_sec": r.duration_sec,
            "cell_id": r.cell_id
        }

        if len(stats["sample_evidence"]) < 5:
            stats["sample_evidence"].append(evidence_item)

        if is_night:
            stats["night_calls"] += 1
            night_records.append(evidence_item)

    in_out_ratio = round(in_count / max(out_count, 1), 2)
    night_pct = round((len(night_records) / max(total_calls, 1)) * 100, 2)

    top_contacts = []
    for peer, s in sorted(contact_stats.items(), key=lambda x: x[1]["call_count"], reverse=True)[:15]:
        top_contacts.append({
            "number": peer,
            "call_count": s["call_count"],
            "total_duration_sec": s["total_duration"],
            "first_seen": s["first_seen"],
            "last_seen": s["last_seen"],
            "sample_evidence": s["sample_evidence"]
        })

    unusual_contacts = []
    for peer, s in contact_stats.items():
        reasons = []
        if s["call_count"] == 1:
            reasons.append("Single one-off communication")
        if s["night_calls"] > 0 and s["night_calls"] == s["call_count"]:
            reasons.append(f"Exclusively night-time ({s['night_calls']} night calls)")
        if reasons:
            unusual_contacts.append({
                "number": peer,
                "call_count": s["call_count"],
                "total_duration_sec": s["total_duration"],
                "reasons": reasons,
                "sample_evidence": s["sample_evidence"]
            })
    unusual_contacts.sort(key=lambda x: x["call_count"])

    return {
        "target_number": number,
        "total_calls": total_calls,
        "total_duration_sec": total_duration,
        "incoming_calls": in_count,
        "outgoing_calls": out_count,
        "sms_count": sms_count,
        "in_out_ratio": in_out_ratio,
        "first_communication": first_comm,
        "last_communication": last_comm,
        "top_contacts": top_contacts,
        "night_activity": {
            "count": len(night_records),
            "percentage": night_pct,
            "records": night_records[:20]
        },
        "unusual_contacts": unusual_contacts[:20]
    }


def find_common_numbers(numbers: list[str], case_id: str, db: Session) -> dict:
    """
    Finds numbers contacted by 2 or more of the specified phone numbers.
    """
    if len(numbers) < 2:
        return {"numbers": numbers, "common_contacts": [], "mutual_calls": []}

    contacts_per_target = {}
    evidence_map = defaultdict(lambda: defaultdict(list))

    for num in numbers:
        records = db.query(CDRRecord).filter(
            CDRRecord.case_id == case_id,
            or_(CDRRecord.a_number == num, CDRRecord.b_number == num)
        ).all()

        peers = set()
        for r in records:
            peer = r.b_number if r.a_number == num else r.a_number
            peers.add(peer)
            if len(evidence_map[num][peer]) < 3:
                evidence_map[num][peer].append({
                    "source_file": r.source_file,
                    "source_row": r.source_row,
                    "timestamp": r.start_time,
                    "a_number": r.a_number,
                    "b_number": r.b_number,
                    "duration_sec": r.duration_sec
                })
        contacts_per_target[num] = peers

    all_peers = set.union(*contacts_per_target.values()) if contacts_per_target else set()
    common = []
    for peer in all_peers:
        connected_to = [num for num in numbers if peer in contacts_per_target[num]]
        if len(connected_to) >= 2:
            ev_list = []
            for num in connected_to:
                ev_list.extend(evidence_map[num][peer])
            common.append({
                "common_number": peer,
                "connected_to_targets": connected_to,
                "target_count": len(connected_to),
                "evidence": ev_list
            })

    common.sort(key=lambda x: x["target_count"], reverse=True)

    mutual = []
    for i in range(len(numbers)):
        for j in range(i + 1, len(numbers)):
            n1, n2 = numbers[i], numbers[j]
            direct_recs = db.query(CDRRecord).filter(
                CDRRecord.case_id == case_id,
                or_(
                    and_(CDRRecord.a_number == n1, CDRRecord.b_number == n2),
                    and_(CDRRecord.a_number == n2, CDRRecord.b_number == n1)
                )
            ).order_by(CDRRecord.start_time.asc()).all()

            if direct_recs:
                mutual.append({
                    "party_a": n1,
                    "party_b": n2,
                    "call_count": len(direct_recs),
                    "evidence": [{
                        "source_file": r.source_file,
                        "source_row": r.source_row,
                        "timestamp": r.start_time,
                        "a_number": r.a_number,
                        "b_number": r.b_number,
                        "duration_sec": r.duration_sec
                    } for r in direct_recs[:10]]
                })

    return {
        "targets": numbers,
        "common_contacts_count": len(common),
        "common_contacts": common,
        "direct_mutual_links": mutual
    }


def get_location_timeline(number: str, case_id: str, db: Session) -> dict:
    """
    Returns the tower timeline and movement path for a phone number.
    """
    records = db.query(CDRRecord).filter(
        CDRRecord.case_id == case_id,
        or_(CDRRecord.a_number == number, CDRRecord.b_number == number),
        CDRRecord.cell_id != ""
    ).order_by(CDRRecord.start_time.asc()).all()

    towers = {t.cell_id: t for t in db.query(CellTower).all()}

    timeline = []
    tower_frequencies = defaultdict(int)

    for idx, r in enumerate(records):
        t_meta = towers.get(r.cell_id)
        tower_frequencies[r.cell_id] += 1
        item = {
            "seq": idx + 1,
            "timestamp": r.start_time,
            "cell_id": r.cell_id,
            "area_name": t_meta.area_name if t_meta else "Unknown Tower",
            "lat": t_meta.lat if t_meta else None,
            "lon": t_meta.lon if t_meta else None,
            "call_type": r.call_type,
            "duration_sec": r.duration_sec,
            "peer": r.b_number if r.a_number == number else r.a_number,
            "source_file": r.source_file,
            "source_row": r.source_row
        }
        timeline.append(item)

    repeated_towers = [
        {"cell_id": cid, "count": cnt, "area_name": towers[cid].area_name if cid in towers else "Unknown"}
        for cid, cnt in sorted(tower_frequencies.items(), key=lambda x: x[1], reverse=True)
        if cnt > 1
    ]

    return {
        "number": number,
        "total_tower_events": len(timeline),
        "timeline": timeline,
        "repeated_towers": repeated_towers
    }


def detect_meetings(
    number1: str,
    number2: str,
    case_id: str,
    db: Session,
    time_window_minutes: int = 30
) -> list[dict]:
    """
    Detects instances where two numbers connected to the same cell tower within a given time window.
    """
    towers = {t.cell_id: t for t in db.query(CellTower).all()}

    recs1 = db.query(CDRRecord).filter(
        CDRRecord.case_id == case_id,
        or_(CDRRecord.a_number == number1, CDRRecord.b_number == number1),
        CDRRecord.cell_id != ""
    ).order_by(CDRRecord.start_time.asc()).all()

    recs2 = db.query(CDRRecord).filter(
        CDRRecord.case_id == case_id,
        or_(CDRRecord.a_number == number2, CDRRecord.b_number == number2),
        CDRRecord.cell_id != ""
    ).order_by(CDRRecord.start_time.asc()).all()

    meetings = []
    seen_pairs = set()

    for r1 in recs1:
        try:
            dt1 = datetime.fromisoformat(r1.start_time)
        except Exception:
            continue

        for r2 in recs2:
            if r1.cell_id != r2.cell_id:
                continue
            try:
                dt2 = datetime.fromisoformat(r2.start_time)
            except Exception:
                continue

            diff = abs((dt1 - dt2).total_seconds())
            if diff <= (time_window_minutes * 60):
                pair_key = (min(r1.id, r2.id), max(r1.id, r2.id))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                t_meta = towers.get(r1.cell_id)
                meetings.append({
                    "cell_id": r1.cell_id,
                    "area_name": t_meta.area_name if t_meta else "Unknown Area",
                    "lat": t_meta.lat if t_meta else None,
                    "lon": t_meta.lon if t_meta else None,
                    "time_diff_sec": int(diff),
                    "event_target_1": {
                        "number": number1,
                        "timestamp": r1.start_time,
                        "source_file": r1.source_file,
                        "source_row": r1.source_row,
                        "call_type": r1.call_type
                    },
                    "event_target_2": {
                        "number": number2,
                        "timestamp": r2.start_time,
                        "source_file": r2.source_file,
                        "source_row": r2.source_row,
                        "call_type": r2.call_type
                    }
                })

    return meetings


def detect_imei_sim_changes(case_id: str, db: Session) -> dict:
    """
    Detects:
    1. Same IMEI with multiple IMSIs or multiple numbers (SIM swaps / handset sharing).
    2. Same phone number used with multiple IMEIs (Handset hopping).
    """
    records = db.query(CDRRecord).filter(
        CDRRecord.case_id == case_id,
        CDRRecord.imei != ""
    ).order_by(CDRRecord.start_time.asc()).all()

    imei_to_numbers = defaultdict(lambda: defaultdict(list))
    imei_to_imsis = defaultdict(lambda: defaultdict(list))
    number_to_imeis = defaultdict(lambda: defaultdict(list))

    for r in records:
        imei = r.imei
        imsi = r.imsi
        num = r.a_number

        ev = {
            "source_file": r.source_file,
            "source_row": r.source_row,
            "timestamp": r.start_time,
            "a_number": r.a_number,
            "b_number": r.b_number,
            "imei": imei,
            "imsi": imsi,
            "cell_id": r.cell_id
        }

        imei_to_numbers[imei][num].append(ev)
        if imsi:
            imei_to_imsis[imei][imsi].append(ev)
        number_to_imeis[num][imei].append(ev)

    multi_number_imeis = []
    for imei, nums in imei_to_numbers.items():
        if len(nums) > 1:
            history = []
            for n, ev_list in nums.items():
                first_seen = min(e["timestamp"] for e in ev_list)
                last_seen = max(e["timestamp"] for e in ev_list)
                history.append({
                    "number": n,
                    "count": len(ev_list),
                    "first_seen": first_seen,
                    "last_seen": last_seen,
                    "sample_evidence": ev_list[:2]
                })
            multi_number_imeis.append({
                "imei": imei,
                "distinct_numbers_count": len(nums),
                "numbers": list(nums.keys()),
                "history": history
            })

    multi_imsi_imeis = []
    for imei, imsis in imei_to_imsis.items():
        if len(imsis) > 1:
            history = []
            for ims, ev_list in imsis.items():
                first_seen = min(e["timestamp"] for e in ev_list)
                last_seen = max(e["timestamp"] for e in ev_list)
                history.append({
                    "imsi": ims,
                    "count": len(ev_list),
                    "first_seen": first_seen,
                    "last_seen": last_seen,
                    "sample_evidence": ev_list[:2]
                })
            multi_imsi_imeis.append({
                "imei": imei,
                "distinct_imsis_count": len(imsis),
                "imsis": list(imsis.keys()),
                "history": history
            })

    multi_imei_numbers = []
    for num, imeis in number_to_imeis.items():
        if len(imeis) > 1:
            history = []
            for im, ev_list in imeis.items():
                first_seen = min(e["timestamp"] for e in ev_list)
                last_seen = max(e["timestamp"] for e in ev_list)
                history.append({
                    "imei": im,
                    "count": len(ev_list),
                    "first_seen": first_seen,
                    "last_seen": last_seen,
                    "sample_evidence": ev_list[:2]
                })
            multi_imei_numbers.append({
                "number": num,
                "distinct_imeis_count": len(imeis),
                "imeis": list(imeis.keys()),
                "history": history
            })

    return {
        "multi_number_imeis": multi_number_imeis,
        "multi_imsi_imeis": multi_imsi_imeis,
        "multi_imei_numbers": multi_imei_numbers
    }


def get_network_graph_data(case_id: str, db: Session, min_calls: int = 1) -> dict:
    """
    Builds node and edge structure formatted for Cytoscape.js.
    """
    records = db.query(CDRRecord).filter(CDRRecord.case_id == case_id).all()
    suspect_set = get_suspect_numbers_for_case(case_id, db)

    edges_map = defaultdict(lambda: {"count": 0, "duration": 0, "evidence": []})
    node_degree = defaultdict(int)

    for r in records:
        a, b = r.a_number, r.b_number
        if not a or not b or a == b:
            continue
        edge_pair = tuple(sorted([a, b]))
        edges_map[edge_pair]["count"] += 1
        edges_map[edge_pair]["duration"] += r.duration_sec
        node_degree[a] += 1
        node_degree[b] += 1
        if len(edges_map[edge_pair]["evidence"]) < 3:
            edges_map[edge_pair]["evidence"].append({
                "source_file": r.source_file,
                "source_row": r.source_row,
                "timestamp": r.start_time,
                "a": a,
                "b": b,
                "duration": r.duration_sec
            })

    nodes = []
    edges = []
    included_nodes = set()

    for (n1, n2), stats in edges_map.items():
        if stats["count"] < min_calls:
            continue
        included_nodes.add(n1)
        included_nodes.add(n2)
        edges.append({
            "data": {
                "id": f"e_{n1}_{n2}",
                "source": n1,
                "target": n2,
                "call_count": stats["count"],
                "total_duration": stats["duration"],
                "evidence": stats["evidence"]
            }
        })

    for n in included_nodes:
        is_suspect = n in suspect_set
        nodes.append({
            "data": {
                "id": n,
                "label": n,
                "degree": node_degree[n],
                "is_suspect": is_suspect
            }
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges)
        }
    }


def analyze_link_between_numbers(case_id: str, num1: str, num2: str, db: Session) -> dict:
    """
    Deep link analysis between two numbers: direct calls, shared bridge contacts,
    shared cell towers, and shared IMEIs.
    """
    records = db.query(CDRRecord).filter(CDRRecord.case_id == case_id).all()
    towers = {t.cell_id: t.area_name for t in db.query(CellTower).all()}

    direct_calls = []
    contacts_1 = defaultdict(int)
    contacts_2 = defaultdict(int)
    towers_1 = set()
    towers_2 = set()
    imeis_1 = set()
    imeis_2 = set()

    for r in records:
        a, b = r.a_number, r.b_number
        if (a == num1 and b == num2) or (a == num2 and b == num1):
            direct_calls.append({
                "timestamp": r.start_time,
                "caller": a,
                "receiver": b,
                "call_type": r.call_type,
                "duration_sec": r.duration_sec,
                "cell_id": r.cell_id,
                "source_file": r.source_file,
                "source_row": r.source_row
            })
        if a == num1 or b == num1:
            other = b if a == num1 else a
            if other and other != num1 and other != num2:
                contacts_1[other] += 1
            if r.cell_id and a == num1:
                towers_1.add(r.cell_id)
            if r.imei and a == num1:
                imeis_1.add(r.imei)
        if a == num2 or b == num2:
            other = b if a == num2 else a
            if other and other != num1 and other != num2:
                contacts_2[other] += 1
            if r.cell_id and a == num2:
                towers_2.add(r.cell_id)
            if r.imei and a == num2:
                imeis_2.add(r.imei)

    shared_contacts = []
    for num in set(contacts_1.keys()) & set(contacts_2.keys()):
        shared_contacts.append({
            "number": num,
            "calls_with_num1": contacts_1[num],
            "calls_with_num2": contacts_2[num],
            "total_bridge_calls": contacts_1[num] + contacts_2[num]
        })
    shared_contacts.sort(key=lambda x: x["total_bridge_calls"], reverse=True)

    shared_towers = [
        {"cell_id": cid, "area_name": towers.get(cid, cid)}
        for cid in sorted(towers_1 & towers_2)
    ]
    shared_imeis = sorted(imeis_1 & imeis_2)

    return {
        "num1": num1,
        "num2": num2,
        "direct_calls_count": len(direct_calls),
        "direct_calls": direct_calls[:30],
        "shared_contacts": shared_contacts,
        "shared_towers": shared_towers,
        "shared_imeis": shared_imeis,
        "link_strength": "DIRECT" if direct_calls else ("BRIDGE_CONNECTED" if shared_contacts else "NONE")
    }


# ----------------- THREAT RISK SCORING & 24x7 TEMPORAL HEATMAP -----------------
def calculate_suspect_threat_scores(case_id: str, db: Session) -> list[dict]:
    """
    Computes an objective, multi-factor Threat Risk Score (0-100) and Archetype Classifier
    for all suspects in the active case:
    - Nocturnal Call Ratio (>25% night activity -> up to 25 pts)
    - SIM Swapping & Device Hopping (multi-SIM IMEI or multi-IMEI number -> up to 30 pts)
    - Impossible/High-Speed Travel (>150 km/h -> up to 20 pts)
    - International / High-Risk Contacts (+15 pts)
    - Cross-Suspect Common Syndicate Bridges (+10 pts)
    """
    suspects = get_ordered_suspects_for_case(case_id, db)
    if not suspects:
        return []

    imei_sim_data = detect_imei_sim_changes(case_id, db)
    swapped_imei_map = {item["imei"]: item for item in imei_sim_data.get("multi_number_imeis", [])}
    swapped_num_map = {item["number"]: item for item in imei_sim_data.get("multi_imei_numbers", [])}

    suspect_phones = [s["phone"] for s in suspects if s.get("phone")]
    common_data = find_common_numbers(suspect_phones, case_id, db) if len(suspect_phones) >= 2 else {"common_contacts": []}
    shared_bridge_numbers = {c["common_number"] for c in common_data.get("common_contacts", [])}

    scored_suspects = []

    for s in suspects:
        phone = s.get("phone", "")
        new_phone = s.get("new_phone", "")
        phones_to_check = [p for p in (phone, new_phone) if p]

        records = db.query(CDRRecord).filter(
            CDRRecord.case_id == case_id,
            or_(CDRRecord.a_number.in_(phones_to_check), CDRRecord.b_number.in_(phones_to_check))
        ).all()

        total_calls = len(records)
        night_calls = 0
        intl_calls = 0
        peers = set()
        imeis_used = set()

        for r in records:
            if r.imei:
                imeis_used.add(r.imei)
            hour = 12
            try:
                hour = datetime.fromisoformat(r.start_time).hour
            except Exception:
                pass
            if hour >= 22 or hour < 6:
                night_calls += 1

            peer = r.b_number if r.a_number in phones_to_check else r.a_number
            if peer:
                peers.add(peer)
                is_intl, _, _, risk = is_international_number(peer)
                if is_intl:
                    intl_calls += 1

        night_pct = round((night_calls / max(1, total_calls)) * 100, 1)

        transitions = get_movement_and_cell_changes(case_id, db, target_number=phone)
        impossible_hops = [t for t in transitions if t.get("is_suspicious_speed")]

        score = 10
        factors = []

        if night_pct >= 40:
            score += 25
            factors.append(f"Excessive nocturnal communications ({night_pct}% night calls)")
        elif night_pct >= 25:
            score += 15
            factors.append(f"Elevated nocturnal activity ({night_pct}% night calls)")

        has_sim_swap = False
        for im in imeis_used:
            if im in swapped_imei_map:
                has_sim_swap = True
                factors.append(f"Hardware IMEI {im} rotated across {swapped_imei_map[im]['distinct_numbers_count']} SIMs")
                break
        for ph in phones_to_check:
            if ph in swapped_num_map:
                has_sim_swap = True
                factors.append(f"Phone {ph} hopped across {swapped_num_map[ph]['distinct_imeis_count']} handsets")
                break
        if has_sim_swap:
            score += 30

        if impossible_hops:
            score += 20
            max_spd = max(h["speed_kmh"] for h in impossible_hops)
            factors.append(f"Impossible terrestrial velocity detected ({max_spd} km/h) - cloned SIM indicator")

        if intl_calls > 0:
            score += 15
            factors.append(f"Direct foreign international communications ({intl_calls} calls)")

        linked_bridges = peers & shared_bridge_numbers
        if len(linked_bridges) >= 2:
            score += 10
            factors.append(f"Directly connects to {len(linked_bridges)} shared syndicate courier nodes")

        final_score = max(5, min(100, score))

        if final_score >= 70:
            risk_level = "CRITICAL"
        elif final_score >= 45:
            risk_level = "HIGH"
        elif final_score >= 25:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        if "Kingpin" in s.get("name", "") or "Kingpin" in s.get("role", "") or (len(linked_bridges) >= 2 and total_calls >= 25):
            archetype = "Kingpin / Syndicate Head"
        elif night_pct >= 40:
            archetype = "Night Phisher / Bulk Scammer"
        elif has_sim_swap:
            archetype = "Burner SIM / Hardware Rotator"
        elif "Mule" in s.get("name", "") or "Mule" in s.get("role", ""):
            archetype = "Mule Cashout Operative"
        elif impossible_hops:
            archetype = "Cloned SIM / Dual Roamer"
        else:
            archetype = "Active Syndicate Operative"

        if not factors:
            factors.append("Standard telecommunications transaction baseline.")

        scored_suspects.append({
            "id": s.get("id", f"T{len(scored_suspects)+1}"),
            "name": s.get("name", f"Target {phone}"),
            "phone": phone,
            "new_phone": new_phone,
            "role": s.get("role", "Target"),
            "handset": s.get("handset", "Smartphone"),
            "imei": s.get("imei", ""),
            "threat_score": final_score,
            "risk_level": risk_level,
            "archetype": archetype,
            "total_calls": total_calls,
            "night_percentage": night_pct,
            "factors": factors,
            "notes": s.get("notes", "")
        })

    scored_suspects.sort(key=lambda x: x["threat_score"], reverse=True)
    return scored_suspects


def get_temporal_heatmap_24x7(case_id: str, db: Session, target_number: str | None = None) -> dict:
    """
    Builds a 7-day (Monday to Sunday) x 24-hour (0 to 23) activity matrix
    of call frequency.
    """
    q = db.query(CDRRecord).filter(CDRRecord.case_id == case_id)
    if target_number:
        clean_num = target_number.strip().replace("+91", "").lstrip("0")
        q = q.filter(or_(CDRRecord.a_number == clean_num, CDRRecord.b_number == clean_num))

    records = q.all()
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    hours = list(range(24))

    matrix = [[0 for _ in range(24)] for _ in range(7)]
    hour_totals = defaultdict(int)
    day_totals = defaultdict(int)
    max_val = 0

    for r in records:
        if not r.start_time:
            continue
        try:
            dt = datetime.fromisoformat(r.start_time)
            day_idx = dt.weekday()
            h = dt.hour
            matrix[day_idx][h] += 1
            hour_totals[h] += 1
            day_totals[day_idx] += 1
            if matrix[day_idx][h] > max_val:
                max_val = matrix[day_idx][h]
        except Exception:
            continue

    busiest_hour = max(hour_totals.items(), key=lambda x: x[1])[0] if hour_totals else 12
    busiest_day_idx = max(day_totals.items(), key=lambda x: x[1])[0] if day_totals else 0
    busiest_day = days[busiest_day_idx]

    return {
        "case_id": case_id,
        "target_number": target_number,
        "days": days,
        "hours": hours,
        "matrix": matrix,
        "max_count": max_val,
        "total_events": len(records),
        "busiest_hour": busiest_hour,
        "busiest_day": busiest_day
    }

