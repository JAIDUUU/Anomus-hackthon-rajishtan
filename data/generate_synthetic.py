#!/usr/bin/env python3
"""
Synthetic Data Generator for Rajasthan Police Cyber Hackathon 2026 (PS03)
Produces authentic Indian DoT / Telecom Service Provider (TSP) format datasets:
1. towers.csv (Real Rajasthan cell towers)
2. case_brief.json (4 suspects, kingpin, meeting, SIM swap, night activity)
3. cdr_operator_A.csv (22-column DoT Standard LEA format, +91, separate date/time, sec duration)
4. cdr_operator_B.csv (22-column MSC Core Switch format, no +91, mm:ss duration)
5. ipdr_operator_A.csv (22-column Carrier NAT IPDR log format, CGNAT RFC 6598)
"""

import os
import json
import random
from datetime import datetime, timedelta

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

random.seed(42)

TOWERS = [
    # Jaipur
    {"cell_id": "RAJ-JPR-101", "lac": 4011, "lat": 26.9124, "lon": 75.7873, "area_name": "Jaipur - Sindhi Camp"},
    {"cell_id": "RAJ-JPR-102", "lac": 4011, "lat": 26.9174, "lon": 75.8056, "area_name": "Jaipur - MI Road"},
    {"cell_id": "RAJ-JPR-103", "lac": 4012, "lat": 26.8532, "lon": 75.8052, "area_name": "Jaipur - Malviya Nagar"},
    {"cell_id": "RAJ-JPR-104", "lac": 4012, "lat": 26.9030, "lon": 75.7420, "area_name": "Jaipur - Vaishali Nagar"},
    {"cell_id": "RAJ-JPR-105", "lac": 4013, "lat": 26.8550, "lon": 75.7600, "area_name": "Jaipur - Mansarovar"},
    # Jodhpur
    {"cell_id": "RAJ-JDH-201", "lac": 4021, "lat": 26.2970, "lon": 73.0185, "area_name": "Jodhpur - Clock Tower"},
    {"cell_id": "RAJ-JDH-202", "lac": 4021, "lat": 26.2750, "lon": 73.0120, "area_name": "Jodhpur - Sardarpura"},
    {"cell_id": "RAJ-JDH-203", "lac": 4022, "lat": 26.2610, "lon": 73.0420, "area_name": "Jodhpur - Ratanada"},
    # Udaipur
    {"cell_id": "RAJ-UDP-301", "lac": 4031, "lat": 24.5925, "lon": 73.6740, "area_name": "Udaipur - Fatehsagar"},
    {"cell_id": "RAJ-UDP-302", "lac": 4031, "lat": 24.5760, "lon": 73.6830, "area_name": "Udaipur - City Palace"},
    {"cell_id": "RAJ-UDP-303", "lac": 4032, "lat": 24.5710, "lon": 73.7150, "area_name": "Udaipur - Hiran Magri"},
    # Kota
    {"cell_id": "RAJ-KTA-401", "lac": 4041, "lat": 25.1630, "lon": 75.8450, "area_name": "Kota - Aerodrome Circle"},
    {"cell_id": "RAJ-KTA-402", "lac": 4041, "lat": 25.1380, "lon": 75.8360, "area_name": "Kota - Vigyan Nagar"},
    # Ajmer
    {"cell_id": "RAJ-AJM-501", "lac": 4051, "lat": 26.4560, "lon": 74.6290, "area_name": "Ajmer - Dargah Bazar"},
    {"cell_id": "RAJ-AJM-502", "lac": 4051, "lat": 26.4710, "lon": 74.6420, "area_name": "Ajmer - Civil Lines"},
]

SUSPECTS = {
    "S1": {"number": "9829022222", "imei": "354890123456781", "imsi": "404450123456781", "name": "Vikram Singh (Suspect 1)"},
    "S2": {"number": "9829033333", "imei": "354890123456782", "imsi": "404450123456782", "name": "Rajesh Meena (Suspect 2)"},
    "S3_OLD": {"number": "9829044444", "imei": "354890123456783", "imsi": "404450123456783", "name": "Amit Rathore (Suspect 3 - Old SIM)"},
    "S3_NEW": {"number": "9829077777", "imei": "354890123456783", "imsi": "404450999999999", "name": "Amit Rathore (Suspect 3 - Swapped SIM)"},
    "S4": {"number": "9829055555", "imei": "354890123456784", "imsi": "404450123456784", "name": "Farooq Khan (Suspect 4 - Night Activity)"},
    "KINGPIN": {"number": "9829011111", "imei": "354890999999999", "imsi": "404450888888888", "name": "Mastermind KP"},
    "COMMON_1": {"number": "9414088888", "name": "Shared Courier Contact 1"},
    "COMMON_2": {"number": "9414099999", "name": "Shared Hawala Contact 2"},
}

SERVICE_NUMBERS = [
    {"number": "1800112211", "label": "SBI Toll-Free Helpline", "type": "Toll-Free"},
    {"number": "18602662666", "label": "HDFC PhoneBanking Gateway", "type": "Toll-Free"},
    {"number": "56161", "label": "Bank OTP Alert Gateway", "type": "Shortcode"},
    {"number": "567676", "label": "Transaction Verification Shortcode", "type": "Shortcode"},
    {"number": "121", "label": "Carrier Customer Service", "type": "Shortcode"}
]

INTERNATIONAL_NUMBERS = [
    {"number": "+971501234567", "country": "United Arab Emirates (Dubai)", "code": "+971"},
    {"number": "+447911123456", "country": "United Kingdom (London)", "code": "+44"},
    {"number": "+14155552671", "country": "United States (San Francisco)", "code": "+1"}
]

BACKGROUND_NUMBERS = [f"94140{i:05d}" for i in range(1000, 1080)]
BACKGROUND_IMEIS = [f"3589100000{i:05d}" for i in range(100, 150)]
BACKGROUND_IMSIS = [f"4044510000{i:05d}" for i in range(100, 150)]

START_DATE = datetime(2026, 11, 15, 0, 0, 0)
END_DATE = datetime(2026, 11, 23, 23, 59, 59)


def generate_towers_csv():
    path = os.path.join(DATA_DIR, "towers.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("cell_id,lac,lat,lon,area_name\n")
        for t in TOWERS:
            f.write(f"{t['cell_id']},{t['lac']},{t['lat']},{t['lon']},{t['area_name']}\n")
    print(f"Generated {path}")


def generate_case_brief():
    brief = {
        "case_id": "CASE-RAJ-2026-0042",
        "title": "Operation Maru-Drishti (Cyber Fraud & Syndicate Analysis)",
        "jurisdiction": "Rajasthan State Cyber Crime Police Station, Jaipur",
        "investigation_period": "2026-11-15 to 2026-11-23",
        "suspects": [
            {"id": "S1", "phone": "9829022222", "name": "Vikram Singh", "role": "Syndicate Field Operative", "imei": "354890123456781"},
            {"id": "S2", "phone": "9829033333", "name": "Rajesh Meena", "role": "Logistics Coordinator", "imei": "354890123456782"},
            {"id": "S3", "phone": "9829044444", "new_phone": "9829077777", "name": "Amit Rathore", "role": "Tech Operator (SIM Swapper)", "imei": "354890123456783"},
            {"id": "S4", "phone": "9829055555", "name": "Farooq Khan", "role": "Night Operations Handler", "imei": "354890123456784"},
            {"id": "KP", "phone": "9829011111", "name": "Mastermind KP", "role": "Central Controller"}
        ],
        "key_ground_truths": {
            "kingpin_link": "9829011111 (Kingpin) has direct communication with all 4 suspects (S1, S2, S3, S4).",
            "common_contacts": "S1 (9829022222) and S2 (9829033333) both communicate with common numbers 9414088888 and 9414099999.",
            "sim_swap_imei_reuse": "Suspect S3 used IMEI 354890123456783 with 9829044444 until 2026-11-19, then switched to 9829077777 on same handset.",
            "night_activity": "Suspect S4 (9829055555) has concentrated communication between 22:00 and 05:00 hours.",
            "physical_meeting": {
                "tower": "RAJ-JPR-102 (Jaipur - MI Road)",
                "date": "2026-11-20",
                "time_window": "18:15:00 to 18:45:00",
                "participants": ["9829022222 (S1)", "9829033333 (S2)"]
            },
            "ipdr_ground_truth": "Subscriber 9829022222 (S1) generated session on 2026-11-20 18:25:10 from IP 103.211.54.12:44321 to Telegram server."
        }
    }
    path = os.path.join(DATA_DIR, "case_brief.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(brief, f, indent=2)
    print(f"Generated {path}")


def random_timestamp(start_dt, end_dt, force_hour_range=None):
    delta = end_dt - start_dt
    sec = random.randint(0, int(delta.total_seconds()))
    dt = start_dt + timedelta(seconds=sec)
    if force_hour_range:
        h_start, h_end = force_hour_range
        if h_start > h_end:
            hour = random.choice(list(range(h_start, 24)) + list(range(0, h_end)))
        else:
            hour = random.randint(h_start, h_end)
        dt = dt.replace(hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59))
    return dt


def generate_cdr_operator_a():
    path = os.path.join(DATA_DIR, "cdr_operator_A.csv")
    records = []

    def make_dot_row(a_num, b_num, c_type, dt, dur, imei, imsi, cell_id):
        tower_meta = next((t for t in TOWERS if t["cell_id"] == cell_id), TOWERS[0])
        return {
            "Target_A_Party_Number": a_num,
            "Call_Type": c_type,
            "Type_of_Connection": "Prepaid" if random.random() > 0.3 else "Postpaid",
            "B_Party_Number": b_num,
            "LRN_Called_Party": "40445",
            "Translation_LRN": "Rajasthan Telecom LSA",
            "Call_Date": dt.strftime("%d-%m-%Y"),
            "Call_Initiation_Time": dt.strftime("%H:%M:%S"),
            "Call_Duration_Sec": str(dur),
            "First_BTS_Location": tower_meta["area_name"],
            "First_Cell_Global_ID": cell_id,
            "Last_BTS_Location": tower_meta["area_name"],
            "Last_Cell_Global_ID": cell_id,
            "IMEI": imei,
            "IMSI": imsi,
            "Service_Type": "VoLTE" if dur > 0 else "SMS",
            "Roaming_Status": "HOME",
            "Circle_LSA": "Rajasthan (RJ)",
            "Call_Forwarding_Number": "",
            "Call_Release_Cause": "Normal Call Clearing (16)",
            "Switch_MSC_ID": "MSC_JPR_01_NOK",
            "Operator_Name": "Bharti Airtel Rajasthan",
            "_dt": dt
        }

    # 1. Kingpin calls to S1 and S2
    for s_info in [SUSPECTS["S1"], SUSPECTS["S2"]]:
        for _ in range(35):
            dt = random_timestamp(START_DATE, END_DATE)
            c_type = random.choice(["INCOMING", "OUTGOING", "SMS_OUT"])
            dur = 0 if "SMS" in c_type else random.randint(20, 480)
            t_cell = random.choice(TOWERS[:5])["cell_id"]
            if c_type == "OUTGOING":
                a, b = f"+91{s_info['number']}", f"+91{SUSPECTS['KINGPIN']['number']}"
            else:
                a, b = f"+91{SUSPECTS['KINGPIN']['number']}", f"+91{s_info['number']}"
            records.append(make_dot_row(a, b, c_type, dt, dur, s_info["imei"], s_info["imsi"], t_cell))

    # 2. S1 and S2 calls to Common Numbers
    for s_info in [SUSPECTS["S1"], SUSPECTS["S2"]]:
        for common_key in ["COMMON_1", "COMMON_2"]:
            for _ in range(18):
                dt = random_timestamp(START_DATE, END_DATE)
                c_type = random.choice(["OUTGOING", "INCOMING"])
                dur = random.randint(30, 240)
                t_cell = random.choice(TOWERS[:5])["cell_id"]
                if c_type == "OUTGOING":
                    a, b = f"+91{s_info['number']}", f"+91{SUSPECTS[common_key]['number']}"
                else:
                    a, b = f"+91{SUSPECTS[common_key]['number']}", f"+91{s_info['number']}"
                records.append(make_dot_row(a, b, c_type, dt, dur, s_info["imei"], s_info["imsi"], t_cell))

    # 3. Meeting at RAJ-JPR-102 (Jaipur - MI Road) on 2026-11-20
    meeting_times_s1 = [
        datetime(2026, 11, 20, 18, 16, 20),
        datetime(2026, 11, 20, 18, 22, 10),
        datetime(2026, 11, 20, 18, 38, 45)
    ]
    for dt in meeting_times_s1:
        records.append(make_dot_row(
            f"+91{SUSPECTS['S1']['number']}", f"+91{random.choice(BACKGROUND_NUMBERS)}",
            "OUTGOING", dt, 64, SUSPECTS["S1"]["imei"], SUSPECTS["S1"]["imsi"], "RAJ-JPR-102"
        ))

    # 4. Service / Bank numbers calls from S1 and S2
    for s_info in [SUSPECTS["S1"], SUSPECTS["S2"]]:
        for srv in SERVICE_NUMBERS[:3]:
            dt = random_timestamp(START_DATE, END_DATE)
            records.append(make_dot_row(
                f"+91{s_info['number']}", srv["number"], "OUTGOING", dt,
                random.randint(45, 180), s_info["imei"], s_info["imsi"], "RAJ-JPR-101"
            ))

    # 5. International calls (S1 calling Dubai & London)
    for intl in INTERNATIONAL_NUMBERS[:2]:
        dt = random_timestamp(START_DATE, END_DATE)
        records.append(make_dot_row(
            f"+91{SUSPECTS['S1']['number']}", intl["number"], "OUTGOING", dt,
            random.randint(120, 360), SUSPECTS["S1"]["imei"], SUSPECTS["S1"]["imsi"], "RAJ-JPR-102"
        ))

    # 6. Background normal chatter
    for _ in range(920):
        dt = random_timestamp(START_DATE, END_DATE)
        c_type = random.choice(["INCOMING", "OUTGOING", "SMS_IN", "SMS_OUT"])
        dur = 0 if "SMS" in c_type else random.randint(10, 600)
        t_cell = random.choice(TOWERS)["cell_id"]

        if random.random() < 0.25:
            s_info = random.choice([SUSPECTS["S1"], SUSPECTS["S2"]])
            other = random.choice(BACKGROUND_NUMBERS)
            if c_type in ["OUTGOING", "SMS_OUT"]:
                a, b = f"+91{s_info['number']}", f"+91{other}"
            else:
                a, b = f"+91{other}", f"+91{s_info['number']}"
            imei, imsi = s_info["imei"], s_info["imsi"]
        else:
            bg_a = random.choice(BACKGROUND_NUMBERS[:30])
            bg_b = random.choice(BACKGROUND_NUMBERS[30:])
            a, b = f"+91{bg_a}", f"+91{bg_b}"
            imei = random.choice(BACKGROUND_IMEIS)
            imsi = random.choice(BACKGROUND_IMSIS)

        records.append(make_dot_row(a, b, c_type, dt, dur, imei, imsi, t_cell))

    records.sort(key=lambda x: x["_dt"])

    # Broken test rows
    broken_imei = make_dot_row(f"+91{SUSPECTS['S1']['number']}", "+919414012345", "OUTGOING", datetime(2026, 11, 16, 11, 20, 0), 45, "", "404450123456781", "RAJ-JPR-101")
    records.insert(10, broken_imei)

    broken_time = make_dot_row(f"+91{SUSPECTS['S2']['number']}", "+919414012346", "INCOMING", datetime(2026, 11, 16, 12, 0, 0), 60, "354890123456782", "404450123456782", "RAJ-JPR-102")
    broken_time["Call_Date"] = "31-02-2026"
    broken_time["Call_Initiation_Time"] = "25:99:99"
    records.insert(25, broken_time)

    dup_row = dict(records[50])
    records.insert(51, dup_row)

    headers = [
        "Target_A_Party_Number", "Call_Type", "Type_of_Connection", "B_Party_Number",
        "LRN_Called_Party", "Translation_LRN", "Call_Date", "Call_Initiation_Time",
        "Call_Duration_Sec", "First_BTS_Location", "First_Cell_Global_ID",
        "Last_BTS_Location", "Last_Cell_Global_ID", "IMEI", "IMSI",
        "Service_Type", "Roaming_Status", "Circle_LSA", "Call_Forwarding_Number",
        "Call_Release_Cause", "Switch_MSC_ID", "Operator_Name"
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write(",".join(headers) + "\n")
        for r in records:
            row_vals = [str(r.get(h, "")) for h in headers]
            f.write(",".join(row_vals) + "\n")

    print(f"Generated {path} with {len(records)} rows ({len(headers)} columns)")


def generate_cdr_operator_b():
    path = os.path.join(DATA_DIR, "cdr_operator_B.csv")
    records = []

    def make_switch_row(seq, a, b, direction, dt, dur_sec, imei, imsi, cell_id):
        tower_meta = next((t for t in TOWERS if t["cell_id"] == cell_id), TOWERS[5])
        dur_str = f"{dur_sec // 60:02d}:{dur_sec % 60:02d}"
        return {
            "record_seq_no": f"SEQ_202611_{seq:06d}",
            "source_msisdn": a,
            "destination_msisdn": b,
            "call_direction": direction,
            "service_plan": "PREPAID_UNLIM",
            "call_date": dt.strftime("%d/%m/%Y"),
            "call_start_time": dt.strftime("%H:%M:%S"),
            "call_duration_mmss": dur_str,
            "call_duration_sec": str(dur_sec),
            "device_imei": imei,
            "sim_imsi": imsi,
            "first_cell_id": cell_id,
            "first_cell_name": tower_meta["area_name"],
            "last_cell_id": cell_id,
            "service_type": "VOICE_HD" if dur_sec > 0 else "SMS",
            "roam_circle": "RJ",
            "msc_id": "JIO_RJ_MSC_04",
            "route_in": "TRUNK_IN_401",
            "route_out": "TRUNK_OUT_402",
            "release_cause": "NORMAL_CLEAR",
            "bearer_capability": "TELEPHONY_SPEECH",
            "telco_operator": "Reliance Jio Infocomm RJ",
            "_dt": dt
        }

    seq_counter = 1

    # 1. Kingpin calls to S3 and S4
    for s_info in [SUSPECTS["S3_OLD"], SUSPECTS["S4"]]:
        for _ in range(30):
            dt = random_timestamp(START_DATE, datetime(2026, 11, 18, 23, 59, 59) if s_info == SUSPECTS["S3_OLD"] else END_DATE)
            c_type = random.choice(["CALL_IN", "CALL_OUT", "SMS_OUT"])
            dur = 0 if "SMS" in c_type else random.randint(25, 450)
            t_cell = random.choice(TOWERS[5:10])["cell_id"]
            if c_type == "CALL_OUT":
                a, b = s_info['number'], SUSPECTS['KINGPIN']['number']
            else:
                a, b = SUSPECTS['KINGPIN']['number'], s_info['number']
            records.append(make_switch_row(seq_counter, a, b, c_type, dt, dur, s_info["imei"], s_info["imsi"], t_cell))
            seq_counter += 1

    # 2. S3 SIM SWAP with DELIBERATE SILENCE ON 2026-11-19 (Missing Dates Analysis)
    # No calls on 19th November for S3! Handset active again on 20th November with new number
    for _ in range(35):
        dt = random_timestamp(datetime(2026, 11, 20, 0, 0, 0), END_DATE)
        c_type = random.choice(["CALL_IN", "CALL_OUT", "SMS_OUT"])
        dur = 0 if "SMS" in c_type else random.randint(30, 300)
        t_cell = random.choice(TOWERS[2:6])["cell_id"]
        other = random.choice(BACKGROUND_NUMBERS[:15])
        if c_type == "CALL_OUT":
            a, b = SUSPECTS["S3_NEW"]["number"], other
        else:
            a, b = other, SUSPECTS["S3_NEW"]["number"]
        records.append(make_switch_row(seq_counter, a, b, c_type, dt, dur, SUSPECTS["S3_NEW"]["imei"], SUSPECTS["S3_NEW"]["imsi"], t_cell))
        seq_counter += 1

    # 3. S4 Heavy Night-Time Calls (22:00 - 05:00)
    for _ in range(55):
        dt = random_timestamp(START_DATE, END_DATE, force_hour_range=(22, 5))
        c_type = random.choice(["CALL_IN", "CALL_OUT"])
        dur = random.randint(60, 600)
        t_cell = random.choice(TOWERS[10:])["cell_id"]
        other = random.choice(BACKGROUND_NUMBERS[40:55])
        if c_type == "CALL_OUT":
            a, b = SUSPECTS["S4"]["number"], other
        else:
            a, b = other, SUSPECTS["S4"]["number"]
        records.append(make_switch_row(seq_counter, a, b, c_type, dt, dur, SUSPECTS["S4"]["imei"], SUSPECTS["S4"]["imsi"], t_cell))
        seq_counter += 1

    # 4. Meeting record for S2 at RAJ-JPR-102 (Jaipur - MI Road) at 18:25 on 2026-11-20
    meeting_times_s2 = [
        datetime(2026, 11, 20, 18, 18, 30),
        datetime(2026, 11, 20, 18, 25, 40),
        datetime(2026, 11, 20, 18, 42, 10)
    ]
    for dt in meeting_times_s2:
        records.append(make_switch_row(seq_counter, SUSPECTS["S2"]["number"], random.choice(BACKGROUND_NUMBERS), "CALL_OUT", dt, 105, SUSPECTS["S2"]["imei"], SUSPECTS["S2"]["imsi"], "RAJ-JPR-102"))
        seq_counter += 1

    # 5. Service & Bank numbers in Operator B
    for srv in SERVICE_NUMBERS[2:]:
        dt = random_timestamp(START_DATE, END_DATE)
        records.append(make_switch_row(seq_counter, SUSPECTS["S3_OLD"]["number"], srv["number"], "CALL_OUT", dt, 50, SUSPECTS["S3_OLD"]["imei"], SUSPECTS["S3_OLD"]["imsi"], "RAJ-JDH-202"))
        seq_counter += 1

    # 6. Background records
    for _ in range(730):
        dt = random_timestamp(START_DATE, END_DATE)
        c_type = random.choice(["CALL_IN", "CALL_OUT", "SMS_OUT"])
        dur = 0 if "SMS" in c_type else random.randint(15, 400)
        t_cell = random.choice(TOWERS)["cell_id"]
        bg_a = random.choice(BACKGROUND_NUMBERS[:40])
        bg_b = random.choice(BACKGROUND_NUMBERS[40:])
        records.append(make_switch_row(seq_counter, bg_a, bg_b, c_type, dt, dur, random.choice(BACKGROUND_IMEIS), random.choice(BACKGROUND_IMSIS), t_cell))
        seq_counter += 1

    records.sort(key=lambda x: x["_dt"])

    # Broken rows
    broken_dest = make_switch_row(9991, SUSPECTS["S3_OLD"]["number"], "", "CALL_OUT", datetime(2026, 11, 17, 14, 10, 0), 80, "354890123456783", "404450123456783", "RAJ-JDH-201")
    records.insert(12, broken_dest)

    broken_date = make_switch_row(9992, "9414011223", "9414011224", "CALL_IN", datetime(2026, 11, 17, 15, 0, 0), 45, "358910000000101", "404451000000101", "RAJ-UDP-301")
    broken_date["call_date"] = "99/99/2026"
    records.insert(30, broken_date)

    broken_dur = make_switch_row(9993, "9414011225", "9414011226", "CALL_OUT", datetime(2026, 11, 18, 16, 30, 0), 0, "358910000000102", "404451000000102", "RAJ-KTA-401")
    broken_dur["call_duration_mmss"] = "INVALID_FORMAT"
    records.insert(45, broken_dur)

    headers = [
        "record_seq_no", "source_msisdn", "destination_msisdn", "call_direction",
        "service_plan", "call_date", "call_start_time", "call_duration_mmss",
        "call_duration_sec", "device_imei", "sim_imsi", "first_cell_id",
        "first_cell_name", "last_cell_id", "service_type", "roam_circle",
        "msc_id", "route_in", "route_out", "release_cause", "bearer_capability",
        "telco_operator"
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write(",".join(headers) + "\n")
        for r in records:
            row_vals = [str(r.get(h, "")) for h in headers]
            f.write(",".join(row_vals) + "\n")

    print(f"Generated {path} with {len(records)} rows ({len(headers)} columns)")


def generate_ipdr_operator_a():
    path = os.path.join(DATA_DIR, "ipdr_operator_A.csv")
    records = []

    apps = [
        {"app": "Telegram (Encrypted VoIP)", "port": 443, "dest": "149.154.167.50"},
        {"app": "WhatsApp Messenger", "port": 443, "dest": "157.240.23.60"},
        {"app": "Signal Private Messenger", "port": 443, "dest": "179.60.192.36"},
        {"app": "Banking / UPI Gateway", "port": 8443, "dest": "104.18.22.45"},
        {"app": "VoIP / Encrypted Trunk", "port": 5060, "dest": "185.190.140.12"},
        {"app": "HTTPS Web Surfing", "port": 443, "dest": "142.250.193.206"},
        {"app": "Tor Entry Node (Anonymized Routing)", "port": 9001, "dest": "185.220.101.5"}
    ]

    def make_ipdr_row(sub, pub_ip, pub_port, dst_ip, dst_port, dt_start, dur, bytes_tot, app_hint):
        dt_end = dt_start + timedelta(seconds=dur)
        uplink = int(bytes_tot * 0.35)
        downlink = bytes_tot - uplink
        priv_ip = f"100.64.{random.randint(10, 200)}.{random.randint(2, 254)}"
        priv_port = random.randint(1024, 65535)
        clean_num = sub.replace("+91", "")
        return {
            "subscriber_msisdn": sub,
            "user_account_id": f"RJ_NAT_ACC_{clean_num}",
            "private_source_ip": priv_ip,
            "private_source_port": str(priv_port),
            "public_nat_ip": pub_ip,
            "public_nat_port": str(pub_port),
            "destination_ip": dst_ip,
            "destination_port": str(dst_port),
            "session_start_timestamp": dt_start.strftime("%Y-%m-%d %H:%M:%S"),
            "session_end_timestamp": dt_end.strftime("%Y-%m-%d %H:%M:%S"),
            "session_duration_sec": str(dur),
            "bytes_uplink": str(uplink),
            "bytes_downlink": str(downlink),
            "total_bytes_transferred": str(bytes_tot),
            "packets_sent": str(uplink // 700 + 10),
            "packets_received": str(downlink // 1200 + 15),
            "protocol_type": "TCP/TLS",
            "cell_tower_site": "RAJ-JPR-102",
            "apn_name": "airtelgprs.com",
            "app_protocol_hint": app_hint,
            "isp_operator": "Airtel Broadband & 5G RJ",
            "telecom_circle": "Rajasthan LSA"
        }

    # 1. S1 (9829022222) using IP 103.211.54.12:44321 on 2026-11-20 18:25:10
    meeting_ipdr = make_ipdr_row(
        "+919829022222", "103.211.54.12", 44321, "149.154.167.50", 443,
        datetime(2026, 11, 20, 18, 25, 10), 390, 2458900, "Telegram (Encrypted VoIP)"
    )
    records.append(meeting_ipdr)

    # 2. Suspect S3 Tor Gateway session
    s3_ipdr = make_ipdr_row(
        "+919829044444", "103.211.54.88", 51234, "185.220.101.5", 9001,
        datetime(2026, 11, 18, 23, 14, 0), 7560, 8945000, "Tor Entry Node (Anonymized Routing)"
    )
    records.append(s3_ipdr)

    # 3. 310 realistic IPDR sessions
    all_subscribers = [
        SUSPECTS["S1"]["number"], SUSPECTS["S2"]["number"],
        SUSPECTS["S3_OLD"]["number"], SUSPECTS["S3_NEW"]["number"],
        SUSPECTS["S4"]["number"], SUSPECTS["KINGPIN"]["number"]
    ] + BACKGROUND_NUMBERS[:25]

    for _ in range(310):
        sub = random.choice(all_subscribers)
        app_obj = random.choice(apps)
        dt_start = random_timestamp(START_DATE, END_DATE)
        dur = random.randint(30, 3600)
        src_port = random.randint(1024, 65535)
        nat_oct = random.choice([54, 55, 68, 72])
        last_oct = random.randint(2, 250)
        src_ip = f"103.211.{nat_oct}.{last_oct}"
        bytes_tx = random.randint(15000, 15000000)
        formatted_sub = f"+91{sub}" if random.random() > 0.5 else sub

        records.append(make_ipdr_row(
            formatted_sub, src_ip, src_port, app_obj["dest"], app_obj["port"],
            dt_start, dur, bytes_tx, app_obj["app"]
        ))

    headers = [
        "subscriber_msisdn", "user_account_id", "private_source_ip", "private_source_port",
        "public_nat_ip", "public_nat_port", "destination_ip", "destination_port",
        "session_start_timestamp", "session_end_timestamp", "session_duration_sec",
        "bytes_uplink", "bytes_downlink", "total_bytes_transferred", "packets_sent",
        "packets_received", "protocol_type", "cell_tower_site", "apn_name",
        "app_protocol_hint", "isp_operator", "telecom_circle"
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write(",".join(headers) + "\n")
        for r in records:
            row_vals = [str(r.get(h, "")) for h in headers]
            f.write(",".join(row_vals) + "\n")

    print(f"Generated {path} with {len(records)} rows ({len(headers)} columns)")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    generate_towers_csv()
    generate_case_brief()
    generate_cdr_operator_a()
    generate_cdr_operator_b()
    generate_ipdr_operator_a()
    print("Synthetic realistic telecom datasets generated successfully.")


if __name__ == "__main__":
    main()
