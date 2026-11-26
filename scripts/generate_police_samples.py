"""
Generates production-grade, highly realistic police forensic CDR, IPDR, and Cell Tower datasets
tailored for Indian Law Enforcement Agencies (LEA) with 100% field coverage.
"""
import csv
import random
from datetime import datetime, timedelta

# Realistic Rajasthan locations & towers
TOWERS = [
    {"cell_id": "RAJ-JPR-101", "lac": 4011, "lat": 26.9124, "lon": 75.7873, "area_name": "Jaipur - Sindhi Camp Central Bus Stand", "azimuth": 60, "operator": "Airtel"},
    {"cell_id": "RAJ-JPR-102", "lac": 4011, "lat": 26.9174, "lon": 75.8056, "area_name": "Jaipur - MI Road Commercial Arcade", "azimuth": 180, "operator": "Jio"},
    {"cell_id": "RAJ-JPR-103", "lac": 4012, "lat": 26.8532, "lon": 75.8052, "area_name": "Jaipur - Malviya Nagar World Trade Park", "azimuth": 300, "operator": "Airtel"},
    {"cell_id": "RAJ-JPR-104", "lac": 4012, "lat": 26.9030, "lon": 75.7420, "area_name": "Jaipur - Vaishali Nagar Amrapali Circle", "azimuth": 120, "operator": "Vi"},
    {"cell_id": "RAJ-JPR-105", "lac": 4013, "lat": 26.9239, "lon": 75.8267, "area_name": "Jaipur - Johari Bazaar Walled City", "azimuth": 240, "operator": "BSNL"},
    {"cell_id": "RAJ-JPR-106", "lac": 4013, "lat": 26.8920, "lon": 75.8260, "area_name": "Jaipur - Raja Park Market", "azimuth": 90, "operator": "Jio"},
    {"cell_id": "RAJ-JPR-107", "lac": 4014, "lat": 26.9855, "lon": 75.8513, "area_name": "Jaipur - Amer Fort Foothills", "azimuth": 0, "operator": "Airtel"},
    {"cell_id": "RAJ-JPR-108", "lac": 4014, "lat": 26.8289, "lon": 75.8056, "area_name": "Jaipur - Jaipur International Airport Terminal 2", "azimuth": 150, "operator": "Jio"},
    {"cell_id": "RAJ-AJM-201", "lac": 4021, "lat": 26.4499, "lon": 74.6399, "area_name": "Ajmer - Dargah Sharif Gateway", "azimuth": 45, "operator": "Airtel"},
    {"cell_id": "RAJ-AJM-202", "lac": 4021, "lat": 26.4691, "lon": 74.6390, "area_name": "Ajmer - Railway Junction Station", "azimuth": 180, "operator": "Vi"},
    {"cell_id": "RAJ-KOT-301", "lac": 4031, "lat": 25.1800, "lon": 75.8300, "area_name": "Kota - Vigyan Nagar Coaching Hub", "azimuth": 270, "operator": "Jio"},
    {"cell_id": "RAJ-JOD-401", "lac": 4041, "lat": 26.2900, "lon": 73.0200, "area_name": "Jodhpur - Clock Tower Sardar Market", "azimuth": 90, "operator": "Airtel"},
    {"cell_id": "RAJ-ALW-501", "lac": 4051, "lat": 27.5530, "lon": 76.6346, "area_name": "Alwar - Tijara Highway Junction", "azimuth": 330, "operator": "Jio"},
    {"cell_id": "RAJ-BHT-601", "lac": 4061, "lat": 27.2152, "lon": 77.5030, "area_name": "Bharatpur - Keoladeo National Park Road", "azimuth": 120, "operator": "Airtel"}
]

# Suspects & Syndicate profiles
TARGET_SUSPECTS = [
    {
        "phone": "9829012345",
        "name": "Devendra Singh (Kingpin)",
        "imeis": ["354890123456781", "864698066569960"],  # iPhone 15 Pro, Samsung
        "imsis": ["404450912345678", "404450912345679"],
        "home_tower": "RAJ-JPR-103", # Malviya Nagar
        "hideout_tower": "RAJ-ALW-501", # Alwar
        "circle": "RJ",
        "operator": "Airtel"
    },
    {
        "phone": "9414098765",
        "name": "Vikram Rathore (Lieutenant)",
        "imeis": ["861665070941529", "352722663101460"],  # OnePlus, Vivo
        "imsis": ["405867098946235"],
        "home_tower": "RAJ-JPR-104", # Vaishali Nagar
        "hideout_tower": "RAJ-ALW-501", # Alwar meeting
        "circle": "RJ",
        "operator": "Jio"
    },
    {
        "phone": "9828112233",
        "name": "Mohammad Aslam (Hawala/Courier)",
        "imeis": ["358774506248887"],
        "imsis": ["405865065347055"],
        "home_tower": "RAJ-JPR-105", # Johari Bazaar
        "hideout_tower": "RAJ-AJM-201",
        "circle": "RJ",
        "operator": "Vi"
    }
]

# Frequent contacts & associates
ASSOCIATES = [
    "9829155555", "9414266666", "9828377777", "9413488888",
    "9829599999", "9829000011", "9829000022", "9829000033",
    "9829000044", "9829000055"
]

# Special / Service / International numbers
SERVICE_NUMBERS = ["1901", "139", "100", "112", "1930", "56161"] # Cyber helpline 1930, Railway 139, Police 112
INTERNATIONAL_NUMBERS = ["+971501234567", "+447911123456", "+12025550199"] # Dubai, UK, US

def generate_cdr_file(filename="sample_data/sample_cdr_comprehensive.csv", total_rows=1200):
    start_date = datetime(2026, 1, 10, 8, 0, 0)
    rows = []

    for i in range(total_rows):
        # Choose suspect or associate
        target = random.choice(TARGET_SUSPECTS)
        is_target_calling = random.choice([True, True, False])
        
        # Determine counterpart
        r_type = random.random()
        if r_type < 0.25:
            # Call to other suspect (Syndicate link)
            other = [s for s in TARGET_SUSPECTS if s != target][0]
            counterpart = other["phone"]
        elif r_type < 0.65:
            # Call to frequent associate
            counterpart = random.choice(ASSOCIATES)
        elif r_type < 0.72:
            # Service / helpline number
            counterpart = random.choice(SERVICE_NUMBERS)
        elif r_type < 0.78:
            # International number
            counterpart = random.choice(INTERNATIONAL_NUMBERS)
        else:
            # Random regular number
            counterpart = f"9829{random.randint(100000, 999999)}"

        a_num = target["phone"] if is_target_calling else counterpart
        b_num = counterpart if is_target_calling else target["phone"]

        # Call type & duration
        c_type_rnd = random.random()
        if c_type_rnd < 0.60:
            call_type = "OUT" if is_target_calling else "IN"
            duration = random.randint(12, 1450)
        elif c_type_rnd < 0.85:
            call_type = "SMS-OUT" if is_target_calling else "SMS-IN"
            duration = 0
        elif c_type_rnd < 0.95:
            call_type = "MISSED"
            duration = 0
        else:
            call_type = "ROAM-IN" if not is_target_calling else "ROAM-OUT"
            duration = random.randint(30, 480)

        # Realistic time simulation (day/night patterns)
        day_offset = random.randint(0, 45)
        # Night calls spike between 23:00 and 04:00 for suspects
        if random.random() < 0.35:
            hour = random.choice([23, 0, 1, 2, 3, 4])
        else:
            hour = random.randint(8, 22)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        event_dt = start_date + timedelta(days=day_offset, hours=hour, minutes=minute, seconds=second)
        
        # Location logic: night time usually at home tower, occasional hideout or transit
        if hour in [23, 0, 1, 2, 3, 4, 5]:
            chosen_tower = next(t for t in TOWERS if t["cell_id"] == target["home_tower"])
        elif day_offset in [14, 15, 28]: # Meeting days!
            chosen_tower = next(t for t in TOWERS if t["cell_id"] == "RAJ-ALW-501") # Alwar Meeting!
        else:
            chosen_tower = random.choice(TOWERS)

        # Device handling (IMEI switching)
        imei = target["imeis"][0] if day_offset < 25 or len(target["imeis"]) == 1 else target["imeis"][1]
        imsi = target["imsis"][0]

        first_cgi = f"404-45-{chosen_tower['lac']}-{chosen_tower['cell_id'].replace('-', '')}"
        last_cgi = first_cgi
        lat_lon = f"{chosen_tower['lat']}/{chosen_tower['lon']}"

        rows.append({
            "Target No": target["phone"],
            "Calling Party Telephone Number": a_num,
            "Called Party Telephone Number": b_num,
            "Call Type": call_type,
            "Call Date": event_dt.strftime("%d/%m/%Y"),
            "Call Time": event_dt.strftime("%H:%M:%S"),
            "Call Date Time": event_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "Call Duration": duration,
            "Dur(s)": duration,
            "First Cell ID": chosen_tower["cell_id"],
            "First CGI": first_cgi,
            "First CGI Lat/Long": lat_lon,
            "Last Cell ID": chosen_tower["cell_id"],
            "Last CGI": last_cgi,
            "Last CGI Lat/Long": lat_lon,
            "Tower Address": chosen_tower["area_name"],
            "IMEI": imei,
            "IMSI": imsi,
            "Call Forwarding No": "" if random.random() > 0.05 else "9829999111",
            "SMS Center Number": "+919829000001",
            "Roaming Circle": "Rajasthan" if chosen_tower["lac"] < 4060 else "Haryana",
            "Service Provider": target["operator"],
            "Disconnect Cause": "NORMAL_CLEARING" if duration > 0 else "NO_ANSWER"
        })

    # Sort rows by timestamp
    rows.sort(key=lambda x: x["Call Date Time"])

    with open(filename, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated comprehensive CDR dataset: {filename} ({len(rows)} records)")
    return rows


def generate_ipdr_file(filename="sample_data/sample_ipdr_comprehensive.csv", total_rows=800):
    start_date = datetime(2026, 1, 10, 8, 0, 0)
    rows = []

    # Common criminal & communication destinations
    DESTINATIONS = [
        {"ip": "157.240.23.174", "port": 443, "hint": "WhatsApp VoIP/Messaging", "app": "WhatsApp"},
        {"ip": "149.154.167.92", "port": 443, "hint": "Telegram Messenger Core", "app": "Telegram"},
        {"ip": "104.244.42.1", "port": 443, "hint": "Signal Private Messenger", "app": "Signal"},
        {"ip": "185.220.101.5", "port": 9001, "hint": "TOR Darknet Node", "app": "Tor Browser"},
        {"ip": "103.208.220.12", "port": 8443, "hint": "Offshore VPN Tunnel", "app": "ExpressVPN"},
        {"ip": "142.250.193.206", "port": 443, "hint": "Google Services / Drive", "app": "Google"},
        {"ip": "104.16.249.249", "port": 443, "hint": "Cloudflare CDN / Cyber Endpoint", "app": "Web HTTPS"}
    ]

    for i in range(total_rows):
        target = random.choice(TARGET_SUSPECTS)
        dest = random.choice(DESTINATIONS)
        
        day_offset = random.randint(0, 45)
        if random.random() < 0.40:
            hour = random.choice([23, 0, 1, 2, 3, 4])
        else:
            hour = random.randint(8, 22)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        
        sess_start = start_date + timedelta(days=day_offset, hours=hour, minutes=minute, seconds=second)
        sess_dur = random.randint(3, 1800)
        sess_end = sess_start + timedelta(seconds=sess_dur)

        tower = next(t for t in TOWERS if t["cell_id"] == target["home_tower"]) if hour in [23,0,1,2,3,4] else random.choice(TOWERS)
        
        up_bytes = random.randint(1200, 450000)
        down_bytes = random.randint(4500, 2500000)
        total_bytes = up_bytes + down_bytes

        # CGNAT Allocation: Private IP maps to Public Translated IP + Port range
        src_port = random.randint(1024, 65530)
        trans_port = random.randint(20000, 60000)
        
        # Standard Jio/Airtel CGNAT Public IPs
        public_nat_ip = random.choice(["157.48.8.103", "157.48.8.108", "157.48.9.129", "122.160.144.15", "106.215.88.42"])
        private_ip = f"100.64.{random.randint(1, 254)}.{random.randint(1, 254)}"
        imei = target["imeis"][0]
        imsi = target["imsis"][0]

        rows.append({
            "Subscriber MSISDN": target["phone"],
            "Source IP": private_ip,
            "Source Port": src_port,
            "Translated IP": public_nat_ip,
            "Translated Port": trans_port,
            "Destination IP": dest["ip"],
            "Destination Port": dest["port"],
            "Protocol": "UDP" if "VoIP" in dest["hint"] or "VPN" in dest["hint"] else "TCP",
            "Session Start Time": sess_start.strftime("%Y-%m-%d %H:%M:%S"),
            "Session End Time": sess_end.strftime("%Y-%m-%d %H:%M:%S"),
            "Session Duration": sess_dur,
            "Data Volume Up Link": up_bytes,
            "Data Volume Down Link": down_bytes,
            "Total Bytes Transferred": total_bytes,
            "Access Point Name": "jionet" if target["operator"] == "Jio" else "airtelgprs.com",
            "App Protocol Hint": dest["hint"],
            "Application": dest["app"],
            "IMEI": imei,
            "IMSI": imsi,
            "First Cell ID": tower["cell_id"],
            "Last Cell ID": tower["cell_id"],
            "Tower Address": tower["area_name"],
            "Roaming Circle": "Rajasthan",
            "PGW IP Address": "2405:0200:520B:20:3903:110:2:24"
        })

    rows.sort(key=lambda x: x["Session Start Time"])

    with open(filename, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated comprehensive IPDR dataset: {filename} ({len(rows)} records)")
    return rows


def generate_cell_towers_file(filename="sample_data/sample_cell_towers.csv"):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["cell_id", "lac", "lat", "lon", "area_name", "azimuth", "operator"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(TOWERS)
    print(f"Generated comprehensive Cell Towers dataset: {filename} ({len(TOWERS)} towers)")


if __name__ == "__main__":
    generate_cdr_file("sample_data/sample_cdr_comprehensive.csv", 1500)
    generate_ipdr_file("sample_data/sample_ipdr_comprehensive.csv", 1000)
    generate_cell_towers_file("sample_data/sample_cell_towers.csv")
    
    # Also mirror into data/sample_police_data/
    import shutil
    shutil.copy("sample_data/sample_cdr_comprehensive.csv", "data/sample_police_data/sample_cdr_comprehensive.csv")
    shutil.copy("sample_data/sample_ipdr_comprehensive.csv", "data/sample_police_data/sample_ipdr_comprehensive.csv")
    shutil.copy("sample_data/sample_cell_towers.csv", "data/sample_police_data/sample_cell_towers.csv")
    print("All sample datasets successfully generated and mirrored!")
