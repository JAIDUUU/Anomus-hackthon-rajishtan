import os
import re
import json
import io
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from app.db import CDRRecord, IPDRRecord, CellTower, ImportBatch

MAPPINGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "mappings")


def get_available_mappings():
    mappings = {}
    if os.path.exists(MAPPINGS_DIR):
        for f in os.listdir(MAPPINGS_DIR):
            if f.endswith(".json"):
                path = os.path.join(MAPPINGS_DIR, f)
                try:
                    with open(path, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                        key = f.replace(".json", "")
                        mappings[key] = data
                except Exception as e:
                    print(f"Error reading mapping {f}: {e}")
    return mappings


def save_mapping_config(mapping_id: str, config: dict):
    os.makedirs(MAPPINGS_DIR, exist_ok=True)
    clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "", mapping_id)
    path = os.path.join(MAPPINGS_DIR, f"{clean_id}.json")
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(config, fp, indent=2)
    return clean_id


def normalize_phone_number(raw_num: str | None) -> str:
    if not raw_num or pd.isna(raw_num):
        return ""
    s = str(raw_num).strip()
    s = re.sub(r"[^\d+]", "", s)
    if s.startswith("+91") and len(s) == 13:
        s = s[3:]
    elif s.startswith("91") and len(s) == 12:
        s = s[2:]
    elif s.startswith("0") and len(s) == 11:
        s = s[1:]
    return s


def parse_duration_to_sec(val, fmt: str = "seconds") -> int:
    if val is None or pd.isna(val):
        return 0
    s = str(val).strip()
    if not s:
        return 0
    if ":" in s:
        parts = s.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    try:
        return int(float(s))
    except Exception:
        raise ValueError(f"Invalid duration format: '{val}'")


def parse_datetime_flexible(val, custom_fmt: str | None = None) -> str:
    if val is None or pd.isna(val):
        raise ValueError("Timestamp is missing")
    s = str(val).strip()
    if not s:
        raise ValueError("Timestamp is blank")

    formats = []
    if custom_fmt:
        formats.append(custom_fmt)
    formats.extend([
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%d-%m-%Y %I:%M:%S %p",
        "%d/%m/%Y %I:%M:%S %p",
        "%Y-%m-%d %I:%M:%S %p"
    ])

    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue

    try:
        dt = pd.to_datetime(s)
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        raise ValueError(f"Unparseable date/time: '{s}'")


def read_tabular_bytes(file_bytes: bytes, filename: str) -> tuple[pd.DataFrame, str]:
    """Read CSV or Excel (.xlsx/.xls) bytes into a clean string DataFrame, auto-skipping LEA report preambles."""
    if not file_bytes:
        raise ValueError("Uploaded file is empty")

    ext = os.path.splitext(filename.lower())[1]
    if ext in (".xlsx", ".xls"):
        try:
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
            df.columns = [str(c).strip() for c in df.columns]
            return df, "EXCEL"
        except Exception as e:
            raise ValueError(f"Invalid Excel file '{filename}': {e}")
    elif ext in (".csv", ".tsv", ".txt", ""):
        try:
            # Detect separator and inspect preamble
            sample_head = file_bytes[:8192].decode("utf-8", errors="ignore")
            sep = "\t" if (ext == ".tsv" or ("\t" in sample_head and sample_head.count("\t") > sample_head.count(","))) else ","

            # Detect if preamble lines exist (e.g. Bharti Airtel / Reliance Jio LEA headers)
            lines = sample_head.splitlines()
            skip_rows = 0
            for idx, line in enumerate(lines[:25]):
                line_lower = line.lower()
                tok_hits = sum(1 for tok in (
                    "target", "calling", "called", "msisdn", "party", "time", "date",
                    "duration", "dur", "cgi", "cell", "imei", "imsi", "source", "dest",
                    "ip", "port", "session", "bytes", "subscriber"
                ) if tok in line_lower)
                # Header row candidate: contains delimiter and at least 2 telecom header tokens
                if line.count(sep) >= 2 and tok_hits >= 2:
                    skip_rows = idx
                    break

            df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, keep_default_na=False, sep=sep, skiprows=skip_rows)
            df.columns = [str(c).strip() for c in df.columns]
            return df, "CSV"
        except Exception as e:
            raise ValueError(f"Invalid CSV file '{filename}': {e}")
    else:
        raise ValueError(f"Unsupported file format '{ext}'. Upload CSV or Excel (.xlsx/.xls).")


def _match_column_synonym(columns: list[str], synonyms: list[str]) -> str:
    norm_map = {re.sub(r"[^a-z0-9]", "", c.lower()): c for c in columns}
    for syn in synonyms:
        if syn in norm_map:
            return norm_map[syn]
    for syn in synonyms:
        for norm_col, orig_col in norm_map.items():
            if syn in norm_col:
                return orig_col
    return ""


def inspect_uploaded_file(file_bytes: bytes, filename: str) -> dict:
    """Inspect headers & sample rows of any CSV/Excel upload and auto-suggest dynamic schema mapping."""
    df, fmt = read_tabular_bytes(file_bytes, filename)
    columns = list(df.columns)
    if not columns:
        raise ValueError("No column headers found in uploaded file")

    norm_joined = " ".join(re.sub(r"[^a-z0-9]", "", c.lower()) for c in columns)
    ipdr_score = sum(1 for tok in ("publicip", "sourceip", "natip", "srcip", "sourceport", "natport", "sessionstart", "bytestransferred", "translatedip", "pgw") if tok in norm_joined)
    suggested_type = "IPDR" if ipdr_score >= 2 else "CDR"

    if suggested_type == "IPDR":
        suggested_mapping = {
            "subscriber_number": _match_column_synonym(columns, ["subscribermsisdn", "subscribernumber", "msisdn", "phonenumber", "mobilenumber", "mobile", "subscriber", "contactno"]),
            "source_ip": _match_column_synonym(columns, ["translatedip", "sourceip", "publicnatip", "publicip", "srcip", "ipaddress", "ip"]),
            "source_port": _match_column_synonym(columns, ["translatedport", "sourceport", "publicnatport", "natport", "srcport", "port"]),
            "destination_ip": _match_column_synonym(columns, ["destinationip", "destip", "dstip", "targetip"]),
            "destination_port": _match_column_synonym(columns, ["destinationport", "destport", "dstport"]),
            "session_start": _match_column_synonym(columns, ["sessionstart", "sessionstarttimestamp", "starttime", "starttimestamp", "timestamp", "time1"]),
            "session_end": _match_column_synonym(columns, ["sessionend", "sessionendtimestamp", "endtime", "endtimestamp"]),
            "bytes_transferred": _match_column_synonym(columns, ["bytestransferred", "totalbytestransferred", "bytes", "volume", "datavolumedownlink"]),
            "app_hint": _match_column_synonym(columns, ["appprotocolhint", "apphint", "application", "protocol", "service", "accesspointname"]),
        }
    else:
        suggested_mapping = {
            "a_number": _match_column_synonym(columns, ["targetno", "targetnumber", "callingpartytelephonenumber", "callingparty", "callingnumber", "callermsisdn", "callernumber", "anumber", "aparty", "srcnum", "caller", "msisdn"]),
            "b_number": _match_column_synonym(columns, ["bpartyno", "bpartynumber", "calledpartytelephonenumber", "calledparty", "callednumber", "calledmsisdn", "calleenumber", "bnumber", "bparty", "dstnum", "callee", "target"]),
            "call_type": _match_column_synonym(columns, ["calltype", "calldirection", "direction", "calldir", "eventtype", "type"]),
            "start_time": _match_column_synonym(columns, ["starttime", "calldatetime", "datetime", "calltimestamp", "timestamp", "calldt", "calldate", "date"]),
            "duration_sec": _match_column_synonym(columns, ["durs", "dursec", "calldurationsec", "durationsec", "durationseconds", "callduration", "duration", "secs", "sec"]),
            "imei": _match_column_synonym(columns, ["imeinum", "imei", "handsetimei", "deviceimei", "imeinumber"]),
            "imsi": _match_column_synonym(columns, ["imsinum", "imsi", "simimsi", "imsinumber"]),
            "cell_id": _match_column_synonym(columns, ["firstcgi", "firstcellid", "towercellid", "cellid", "cellsiteid", "cgi", "towerid", "towercode", "tower"]),
        }

    preview_rows = df.head(3).to_dict(orient="records")
    return {
        "filename": filename,
        "format": fmt,
        "columns": columns,
        "row_count": len(df),
        "preview_rows": preview_rows,
        "suggested_type": suggested_type,
        "suggested_mapping": suggested_mapping,
    }


def _save_import_batch(
    db: Session, case_id: str, filename: str, file_type: str, mapping_name: str, summary: dict
) -> dict:
    batch = ImportBatch(
        case_id=case_id,
        filename=filename,
        file_type=file_type,
        mapping_name=mapping_name,
        total_rows=summary["total_rows"],
        valid_rows=summary["valid_rows"],
        rejected_rows=summary["rejected_rows"],
        validation_summary_json=json.dumps(summary)
    )
    db.add(batch)
    db.flush()
    summary["batch_id"] = batch.id
    batch.validation_summary_json = json.dumps(summary)
    db.commit()
    return summary


def ingest_cdr_data(
    file_bytes: bytes,
    filename: str,
    case_id: str,
    mapping_config: dict,
    db: Session
) -> dict:
    df, _ = read_tabular_bytes(file_bytes, filename)

    col_map = mapping_config.get("mappings", {})
    date_fmt = mapping_config.get("date_format")
    dur_fmt = mapping_config.get("duration_format", "seconds")
    call_type_map = mapping_config.get("call_type_mapping", {})

    total_rows = len(df)
    valid_records = []
    rejected_rows = []
    missing_counts = {
        "a_number": 0,
        "b_number": 0,
        "start_time": 0,
        "imei": 0,
        "imsi": 0,
        "cell_id": 0
    }
    seen_keys = set()

    for idx, row in df.iterrows():
        source_row = idx + 2  # 1-based index plus header row
        reasons = []

        raw_a = row.get(col_map.get("a_number", "Calling_Number"), "").strip()
        raw_b = row.get(col_map.get("b_number", "Called_Number"), "").strip()

        start_time_cfg = col_map.get("start_time")
        if isinstance(start_time_cfg, list) and len(start_time_cfg) == 2:
            d_val = row.get(start_time_cfg[0], "").strip()
            t_val = row.get(start_time_cfg[1], "").strip()
            raw_time = f"{d_val} {t_val}".strip() if (d_val or t_val) else ""
        else:
            raw_time = row.get(start_time_cfg or "Call_Date_Time", "").strip()
            if not raw_time:
                if "Call_Date" in row and "Call_Initiation_Time" in row:
                    raw_time = f"{row['Call_Date'].strip()} {row['Call_Initiation_Time'].strip()}".strip()
                elif "call_date" in row and "call_start_time" in row:
                    raw_time = f"{row['call_date'].strip()} {row['call_start_time'].strip()}".strip()
                elif "call_date" in row and "call_time" in row:
                    raw_time = f"{row['call_date'].strip()} {row['call_time'].strip()}".strip()

        raw_dur = row.get(col_map.get("duration_sec", "Call_Duration_Sec"), "").strip()
        raw_type = row.get(col_map.get("call_type", "Call_Direction"), "").strip()
        raw_imei = row.get(col_map.get("imei", "IMEI_Num"), "").strip()
        raw_imsi = row.get(col_map.get("imsi", "IMSI_Num"), "").strip()
        raw_cell = row.get(col_map.get("cell_id", "Tower_Cell_ID"), "").strip()

        # Check required fields
        if not raw_a:
            reasons.append("Missing source/calling number (a_number)")
            missing_counts["a_number"] += 1
        if not raw_b:
            reasons.append("Missing destination/called number (b_number)")
            missing_counts["b_number"] += 1
        if not raw_time:
            reasons.append("Missing start timestamp")
            missing_counts["start_time"] += 1
        if not raw_imei:
            reasons.append("Missing IMEI identifier")
            missing_counts["imei"] += 1
        if not raw_imsi:
            missing_counts["imsi"] += 1
        if not raw_cell:
            missing_counts["cell_id"] += 1

        norm_a = normalize_phone_number(raw_a)
        norm_b = normalize_phone_number(raw_b)
        if raw_a and not norm_a:
            reasons.append(f"Invalid calling number format: '{raw_a}'")
        if raw_b and not norm_b:
            reasons.append(f"Invalid called number format: '{raw_b}'")

        # Parse timestamp
        iso_time = ""
        if raw_time:
            try:
                iso_time = parse_datetime_flexible(raw_time, date_fmt)
            except ValueError as ve:
                reasons.append(str(ve))

        # Parse duration
        dur_sec = 0
        if raw_dur:
            try:
                dur_sec = parse_duration_to_sec(raw_dur, dur_fmt)
                if dur_sec < 0:
                    reasons.append("Duration cannot be negative")
            except ValueError as ve:
                reasons.append(str(ve))

        # Check for duplicates
        dedup_key = (norm_a, norm_b, iso_time, raw_type)
        if iso_time and dedup_key in seen_keys:
            reasons.append(f"Duplicate call record at {iso_time}")
        elif iso_time:
            seen_keys.add(dedup_key)

        # Standardize call type
        clean_call_type = call_type_map.get(raw_type, raw_type).upper()
        if not clean_call_type:
            clean_call_type = "OUT" if dur_sec > 0 else "SMS"
        elif "IN" in clean_call_type:
            clean_call_type = "IN"
        elif "SMS" in clean_call_type:
            clean_call_type = "SMS"
        else:
            clean_call_type = "OUT"

        if reasons:
            rejected_rows.append({
                "source_row": source_row,
                "reasons": reasons,
                "raw_sample": {k: str(v) for k, v in row.items()}
            })
        else:
            raw_dict = {k: str(v) for k, v in row.items()}
            rec = CDRRecord(
                case_id=case_id,
                a_number=norm_a,
                b_number=norm_b,
                call_type=clean_call_type,
                start_time=iso_time,
                duration_sec=dur_sec,
                imei=raw_imei,
                imsi=raw_imsi,
                cell_id=raw_cell,
                source_file=filename,
                source_row=source_row,
                raw_data_json=json.dumps(raw_dict)
            )
            valid_records.append(rec)

    # Auto-upsert any new CellTowers discovered from coordinates embedded in uploaded CDRs
    if valid_records:
        existing_cells = {t[0] for t in db.query(CellTower.cell_id).all()}
        new_discovered_towers = []
        for rec in valid_records:
            cid = (rec.cell_id or "").strip()
            if not cid or cid in existing_cells:
                continue
            try:
                raw_m = json.loads(rec.raw_data_json)
                lat_val = next((raw_m.get(k) for k in ("Lat", "lat", "Latitude", "latitude", "First Lat", "Cell_Lat") if raw_m.get(k)), "")
                lon_val = next((raw_m.get(k) for k in ("Lon", "lon", "Long", "Longitude", "longitude", "First Lon", "Cell_Lon") if raw_m.get(k)), "")
                area_val = next((raw_m.get(k) for k in ("Cell Address", "Area", "area_name", "Location", "Tower Address") if raw_m.get(k)), cid)
                lac_val = next((raw_m.get(k) for k in ("LAC", "lac") if raw_m.get(k)), "0")
                if lat_val and lon_val:
                    new_discovered_towers.append(CellTower(
                        cell_id=cid,
                        lac=int(float(lac_val)) if str(lac_val).replace(".", "").isdigit() else 0,
                        lat=float(lat_val),
                        lon=float(lon_val),
                        area_name=str(area_val).strip()
                    ))
                    existing_cells.add(cid)
            except Exception:
                pass
        if new_discovered_towers:
            db.bulk_save_objects(new_discovered_towers)

        db.bulk_save_objects(valid_records)

    summary = {
        "filename": filename,
        "mapping_used": mapping_config.get("name", "Custom"),
        "total_rows": total_rows,
        "valid_rows": len(valid_records),
        "rejected_rows": len(rejected_rows),
        "missing_counts": missing_counts,
        "rejected_details": rejected_rows[:20]  # first 20 for preview
    }

    return _save_import_batch(db, case_id, filename, "CDR", mapping_config.get("name", "Custom"), summary)


def ingest_ipdr_data(
    file_bytes: bytes,
    filename: str,
    case_id: str,
    mapping_config: dict,
    db: Session
) -> dict:
    df, _ = read_tabular_bytes(file_bytes, filename)

    col_map = mapping_config.get("mappings", {})
    date_fmt = mapping_config.get("date_format", "%Y-%m-%d %H:%M:%S")

    total_rows = len(df)
    valid_records = []
    rejected_rows = []
    missing_counts = {
        "subscriber_number": 0,
        "source_ip": 0,
        "source_port": 0,
        "session_start": 0
    }

    for idx, row in df.iterrows():
        source_row = idx + 2
        reasons = []

        sub_num = row.get(col_map.get("subscriber_number", "subscriber_msisdn"), "").strip() or row.get("phone_number", "").strip()
        src_ip = row.get(col_map.get("source_ip", "source_ip"), "").strip() or row.get("public_nat_ip", "").strip() or row.get("ip_address", "").strip()
        src_port_val = row.get(col_map.get("source_port", "source_port"), "").strip() or row.get("public_nat_port", "").strip()
        dst_ip = row.get(col_map.get("destination_ip", "dest_ip"), "").strip() or row.get("destination_ip", "").strip()
        dst_port_val = row.get(col_map.get("destination_port", "dest_port"), "").strip() or row.get("destination_port", "").strip()
        sess_start_val = row.get(col_map.get("session_start", "session_start"), "").strip() or row.get("session_start_timestamp", "").strip()
        sess_end_val = row.get(col_map.get("session_end", "session_end"), "").strip() or row.get("session_end_timestamp", "").strip()
        bytes_val = row.get(col_map.get("bytes_transferred", "bytes_transferred"), "").strip() or row.get("total_bytes_transferred", "0").strip()
        app_hint = row.get(col_map.get("app_hint", "app_protocol_hint"), "").strip() or "Internet Data / HTTPS"

        if not sub_num:
            reasons.append("Missing subscriber number")
            missing_counts["subscriber_number"] += 1
        if not src_ip:
            reasons.append("Missing source public IP")
            missing_counts["source_ip"] += 1
        if not sess_start_val:
            reasons.append("Missing session start time")
            missing_counts["session_start"] += 1

        norm_sub = normalize_phone_number(sub_num)
        try:
            src_port = int(src_port_val) if src_port_val else 0
        except Exception:
            src_port = 0
            if src_port_val:
                reasons.append(f"Invalid source port '{src_port_val}'")

        try:
            dst_port = int(dst_port_val) if dst_port_val else 0
        except Exception:
            dst_port = 0

        try:
            bytes_transferred = int(bytes_val) if bytes_val else 0
        except Exception:
            bytes_transferred = 0

        iso_start, iso_end = "", ""
        try:
            iso_start = parse_datetime_flexible(sess_start_val, date_fmt)
        except Exception as e:
            reasons.append(f"Session start error: {e}")

        try:
            iso_end = parse_datetime_flexible(sess_end_val, date_fmt) if sess_end_val else iso_start
        except Exception as e:
            iso_end = iso_start

        if reasons:
            rejected_rows.append({
                "source_row": source_row,
                "reasons": reasons,
                "raw_sample": {k: str(v) for k, v in row.items()}
            })
        else:
            raw_dict = {k: str(v) for k, v in row.items()}
            rec = IPDRRecord(
                case_id=case_id,
                subscriber_number=norm_sub,
                source_ip=src_ip,
                source_port=src_port,
                destination_ip=dst_ip,
                destination_port=dst_port,
                session_start=iso_start,
                session_end=iso_end,
                bytes_transferred=bytes_transferred,
                app_hint=app_hint,
                source_file=filename,
                source_row=source_row,
                raw_data_json=json.dumps(raw_dict)
            )
            valid_records.append(rec)

    if valid_records:
        db.bulk_save_objects(valid_records)

    summary = {
        "filename": filename,
        "mapping_used": mapping_config.get("name", "IPDR Mapping"),
        "total_rows": total_rows,
        "valid_rows": len(valid_records),
        "rejected_rows": len(rejected_rows),
        "missing_counts": missing_counts,
        "rejected_details": rejected_rows[:20]
    }

    return _save_import_batch(db, case_id, filename, "IPDR", mapping_config.get("name", "IPDR Mapping"), summary)


def seed_towers_from_csv(db: Session, csv_path: str | None = None):
    base_data = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    paths_to_try = []
    if csv_path:
        paths_to_try.append(csv_path)
    else:
        paths_to_try.extend([
            os.path.join(base_data, "rajasthan_cell_towers_master.csv"),
            os.path.join(base_data, "towers.csv"),
            os.path.join(base_data, "sample_police_data", "sample_cell_towers.csv"),
        ])

    existing_cell_ids = {t[0] for t in db.query(CellTower.cell_id).all()}
    new_towers = []
    for chosen_path in paths_to_try:
        if not os.path.exists(chosen_path):
            continue
        df = pd.read_csv(chosen_path)
        for _, row in df.iterrows():
            cid = str(row["cell_id"]).strip()
            if cid and cid not in existing_cell_ids:
                lac_val = 0
                if pd.notna(row.get("lac")):
                    try:
                        lac_val = int(float(str(row["lac"]).strip()))
                    except Exception:
                        lac_val = 0
                t = CellTower(
                    cell_id=cid,
                    lac=lac_val,
                    lat=float(row["lat"]),
                    lon=float(row["lon"]),
                    area_name=str(row["area_name"]).strip()
                )
                new_towers.append(t)
                existing_cell_ids.add(cid)

    if new_towers:
        db.bulk_save_objects(new_towers)
        db.commit()
