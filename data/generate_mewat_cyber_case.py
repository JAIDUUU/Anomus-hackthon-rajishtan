#!/usr/bin/env python3
"""
Mewat-Bharatpur Cybercrime Syndicate Dataset Generator
Tailored specifically for Rajasthan Police Hackathon 2026 (PS03)

Models realistic cyber fraud operations:
- Bharatpur / Deeg / Kaman (Mewat cyber crime hotbelt)
- Jaipur Sindhi Camp & Malviya Nagar (Hawala & Mule ATM cashouts)
- Cross-operator CDRs (Airtel + Jio + Vi)
- CGNAT IPDR logs with WhatsApp STUN (3478), Bank OTP Gateways, and Telegram ports
"""

import os
import json
import random
from datetime import datetime, timedelta

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
CASE_DIR = os.path.join(DATA_DIR, "external_samples", "case-2026-mewat")
os.makedirs(CASE_DIR, exist_ok=True)

random.seed(1337)

SUSPECTS = {
    "KINGPIN": {
        "number": "9829019999",
        "name": "Arif Mewati (Syndicate Kingpin)",
        "imei": "354890123999001",
        "imsi": "404701234500001",
        "base_tower": "RAJ-DEG-603" # Deeg
    },
    "OPERATOR_1": {
        "number": "9829028888",
        "name": "Wasim Akram (OLX & Extortion Caller)",
        "imei": "354890123888002",
        "imsi": "404701234500002",
        "base_tower": "RAJ-KMN-604" # Kaman
    },
    "OPERATOR_2": {
        "number": "9829037777",
        "name": "Shahid Khan (SIM Provider & Tech Setup)",
        "imei": "864698066777003",
        "imsi": "405868123400003",
        "base_tower": "RAJ-JUR-606" # Jurhara Border
    },
    "MULE_JAIPUR": {
        "number": "9829046666",
        "name": "Pankaj Sharma (Mule Cashout Operative - Old SIM)",
        "imei": "352841104666004",
        "imsi": "404601234500004",
        "base_tower": "RAJ-JPR-101" # Jaipur Sindhi Camp
    },
    "MULE_JAIPUR_SWAP": {
        "number": "9829095555",
        "name": "Pankaj Sharma (Mule Cashout - Swapped SIM)",
        "imei": "352841104666004", # Same IMEI, swapped SIM
        "imsi": "404709999900005",
        "base_tower": "RAJ-JPR-103" # Malviya Nagar
    },
    "NIGHT_PHISHER": {
        "number": "9829054444",
        "name": "Imran Ali (Night Phishing Bulk Sender)",
        "imei": "861768084444005",
        "imsi": "405868555500006",
        "base_tower": "RAJ-GPL-607" # Gopalgarh
    }
}

COMMON_CONTACTS = [
    {"number": "9414011223", "name": "Hawala Courier - Jaipur Johri Bazar"},
    {"number": "9414022334", "name": "Forged SIM Wholesaler - Bharatpur"},
    {"number": "9414033445", "name": "Fake Aadhaar KYC Agent - Alwar"}
]

VICTIMS = [
    f"9829{random.randint(100000, 999999)}" for _ in range(30)
]

TOWERS = [
    "RAJ-DEG-603", "RAJ-KMN-604", "RAJ-JUR-606", "RAJ-GPL-607",
    "RAJ-BHP-601", "RAJ-BHP-602", "RAJ-ALW-701", "RAJ-BHW-703",
    "RAJ-JPR-101", "RAJ-JPR-102", "RAJ-JPR-103", "RAJ-JPR-104"
]

def generate_cdr():
    records = []
    base_date = datetime(2026, 2, 1, 0, 0, 0)

    # 1. Calls among syndicate members & Kingpin
    for day in range(25):
        cur_date = base_date + timedelta(days=day)
        
        # Kingpin coordinating with Operative 1 & 2
        for _ in range(random.randint(2, 6)):
            hour = random.randint(10, 21)
            minute = random.randint(0, 59)
            sec = random.randint(0, 59)
            dt = cur_date.replace(hour=hour, minute=minute, second=sec)
            dur = random.randint(30, 450)
            
            records.append({
                "calling_number": SUSPECTS["KINGPIN"]["number"],
                "called_number": SUSPECTS["OPERATOR_1"]["number"],
                "call_type": "OUT",
                "call_date": dt.strftime("%Y-%m-%d"),
                "call_time": dt.strftime("%H:%M:%S"),
                "duration_sec": dur,
                "imei_a": SUSPECTS["KINGPIN"]["imei"],
                "imsi_a": SUSPECTS["KINGPIN"]["imsi"],
                "tower_location": SUSPECTS["KINGPIN"]["base_tower"]
            })

            # Inbound reverse
            records.append({
                "calling_number": SUSPECTS["OPERATOR_1"]["number"],
                "called_number": SUSPECTS["KINGPIN"]["number"],
                "call_type": "IN",
                "call_date": dt.strftime("%Y-%m-%d"),
                "call_time": dt.strftime("%H:%M:%S"),
                "duration_sec": dur,
                "imei_a": SUSPECTS["OPERATOR_1"]["imei"],
                "imsi_a": SUSPECTS["OPERATOR_1"]["imsi"],
                "tower_location": SUSPECTS["OPERATOR_1"]["base_tower"]
            })

        # Night phishing calls (after 22:00 or before 05:00)
        for _ in range(random.randint(5, 12)):
            night_hour = random.choice([22, 23, 0, 1, 2, 3, 4])
            dt = cur_date.replace(hour=night_hour, minute=random.randint(0, 59), second=random.randint(0, 59))
            dur = random.randint(10, 90)
            vic = random.choice(VICTIMS)
            records.append({
                "calling_number": SUSPECTS["NIGHT_PHISHER"]["number"],
                "called_number": vic,
                "call_type": "OUT",
                "call_date": dt.strftime("%Y-%m-%d"),
                "call_time": dt.strftime("%H:%M:%S"),
                "duration_sec": dur,
                "imei_a": SUSPECTS["NIGHT_PHISHER"]["imei"],
                "imsi_a": SUSPECTS["NIGHT_PHISHER"]["imsi"],
                "tower_location": SUSPECTS["NIGHT_PHISHER"]["base_tower"]
            })

        # Common contacts: Hawala & Forged SIM dealer calls
        for comm in COMMON_CONTACTS:
            for susp_key in ["OPERATOR_1", "OPERATOR_2", "MULE_JAIPUR"]:
                if random.random() < 0.35:
                    dt = cur_date.replace(hour=random.randint(11, 18), minute=random.randint(0, 59), second=random.randint(0, 59))
                    records.append({
                        "calling_number": SUSPECTS[susp_key]["number"],
                        "called_number": comm["number"],
                        "call_type": "OUT",
                        "call_date": dt.strftime("%Y-%m-%d"),
                        "call_time": dt.strftime("%H:%M:%S"),
                        "duration_sec": random.randint(40, 200),
                        "imei_a": SUSPECTS[susp_key]["imei"],
                        "imsi_a": SUSPECTS[susp_key]["imsi"],
                        "tower_location": SUSPECTS[susp_key]["base_tower"]
                    })

    # 2. SIM Swap Event on Day 16 for Mule Operative
    swap_date = base_date + timedelta(days=16)
    for _ in range(15):
        dt = swap_date + timedelta(hours=random.randint(1, 12), minutes=random.randint(0, 59))
        records.append({
            "calling_number": SUSPECTS["MULE_JAIPUR_SWAP"]["number"],
            "called_number": SUSPECTS["KINGPIN"]["number"],
            "call_type": "OUT",
            "call_date": dt.strftime("%Y-%m-%d"),
            "call_time": dt.strftime("%H:%M:%S"),
            "duration_sec": random.randint(60, 300),
            "imei_a": SUSPECTS["MULE_JAIPUR_SWAP"]["imei"], # Same IMEI
            "imsi_a": SUSPECTS["MULE_JAIPUR_SWAP"]["imsi"], # New IMSI
            "tower_location": SUSPECTS["MULE_JAIPUR_SWAP"]["base_tower"]
        })

    # 3. Rendezvous / Meeting co-location on Day 18 at Jaipur Sindhi Camp
    meet_dt = base_date + timedelta(days=18, hours=15, minutes=30)
    for susp_key in ["OPERATOR_1", "OPERATOR_2", "MULE_JAIPUR_SWAP"]:
        dt = meet_dt + timedelta(minutes=random.randint(5, 25))
        records.append({
            "calling_number": SUSPECTS[susp_key]["number"],
            "called_number": SUSPECTS["KINGPIN"]["number"],
            "call_type": "OUT",
            "call_date": dt.strftime("%Y-%m-%d"),
            "call_time": dt.strftime("%H:%M:%S"),
            "duration_sec": 180,
            "imei_a": SUSPECTS[susp_key]["imei"],
            "imsi_a": SUSPECTS[susp_key]["imsi"],
            "tower_location": "RAJ-JPR-101" # Sindhi Camp Co-location!
        })

    # Sort by datetime
    records.sort(key=lambda r: r["call_date"] + " " + r["call_time"])
    return records

def generate_ipdr():
    records = []
    base_date = datetime(2026, 2, 1, 0, 0, 0)
    cgnat_pool = [f"100.64.{random.randint(10, 80)}.{random.randint(2, 250)}" for _ in range(10)]
    public_nat = "157.48.19.42"

    for day in range(25):
        cur_date = base_date + timedelta(days=day)
        
        # WhatsApp VoIP & STUN media sessions for extortion calls
        for _ in range(8):
            start = cur_date.replace(hour=random.randint(12, 23), minute=random.randint(0, 50), second=random.randint(0, 50))
            dur = random.randint(45, 900)
            end = start + timedelta(seconds=dur)
            
            records.append({
                "phone_number": SUSPECTS["OPERATOR_1"]["number"],
                "ip_address": random.choice(cgnat_pool),
                "source_port": random.randint(30000, 60000),
                "destination_ip": "157.240.22.54", # WhatsApp Media / Meta Server
                "destination_port": 3478, # STUN VoIP Port
                "session_start": start.strftime("%Y-%m-%d %H:%M:%S"),
                "session_end": end.strftime("%Y-%m-%d %H:%M:%S"),
                "bytes_transferred": random.randint(250000, 8500000),
                "app_hint": "WhatsApp VoIP Video/Audio Call"
            })

        # Banking Mule Cashout Sessions
        for _ in range(3):
            start = cur_date.replace(hour=random.randint(10, 16), minute=random.randint(0, 50), second=random.randint(0, 50))
            dur = random.randint(15, 120)
            end = start + timedelta(seconds=dur)
            records.append({
                "phone_number": SUSPECTS["MULE_JAIPUR"]["number"],
                "ip_address": random.choice(cgnat_pool),
                "source_port": random.randint(30000, 60000),
                "destination_ip": "104.18.25.101", # Banking Payment Gateway
                "destination_port": 443,
                "session_start": start.strftime("%Y-%m-%d %H:%M:%S"),
                "session_end": end.strftime("%Y-%m-%d %H:%M:%S"),
                "bytes_transferred": random.randint(12000, 85000),
                "app_hint": "YONO / IMPS Banking Gateway"
            })

    records.sort(key=lambda r: r["session_start"])
    return records

# Write files
cdr_rows = generate_cdr()
ipdr_rows = generate_ipdr()

import csv

with open(os.path.join(CASE_DIR, "cdr.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(cdr_rows[0].keys()))
    writer.writeheader()
    writer.writerows(cdr_rows)

with open(os.path.join(CASE_DIR, "ipdr.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(ipdr_rows[0].keys()))
    writer.writeheader()
    writer.writerows(ipdr_rows)

case_brief = {
    "case_id": "CASE-2026-MEWAT-001",
    "title": "Mewat-Bharatpur Cyber Extortion & OLX Fraud Syndicate",
    "description": "Cross-district organized cyber extortion ring based in Deeg/Kaman (Bharatpur Mewat region) with mule ATM cashouts in Jaipur and burner SIM rotations.",
    "suspects": SUSPECTS,
    "common_contacts": COMMON_CONTACTS,
    "cdr_count": len(cdr_rows),
    "ipdr_count": len(ipdr_rows),
    "rendezvous_location": "Jaipur - Sindhi Camp Central Bus Stand (RAJ-JPR-101)",
    "rendezvous_date": "2026-02-19 15:30:00"
}

with open(os.path.join(CASE_DIR, "case_brief.json"), "w", encoding="utf-8") as f:
    json.dump(case_brief, f, indent=2)

print(f"Generated Mewat Cyber Syndicate Case: {len(cdr_rows)} CDRs, {len(ipdr_rows)} IPDRs in {CASE_DIR}")
