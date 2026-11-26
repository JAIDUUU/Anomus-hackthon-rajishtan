# 🚔 Rajasthan Police Cyber Forensic Command Center
### `Next-Gen Telecom CDR/IPDR Intelligence & AI Forensic Copilot (PS03)`

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic%20AI-FF6F00?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Pytest Suite](https://img.shields.io/badge/Tests-47%2F47%20Passing-success?logo=pytest&logoColor=white)](tests/)
[![Statutory Compliance](https://img.shields.io/badge/Court%20Admissible-Sec%2065B(4)%20%2F%20BSA%20Sec%2063-crimson)](docs/security_audit_chain.md)
[![GIS Engine](https://img.shields.io/badge/Leaflet-7%20Tactical%20Modes-green?logo=leaflet&logoColor=white)](docs/geospatial_tracking.md)
[![Graph Analytics](https://img.shields.io/badge/Cytoscape.js-Syndicate%20Topology-purple)](docs/network_topology.md)

---

## 🎬 Live Platform Walkthrough

> **Instant Visual Overview**: High-speed walkthrough of the Rajasthan Police Cyber Forensic Command Center showcasing the dual-sidebar command interface, 28 investigation modules, 4-quadrant syndicate graph, and 7-mode GIS engine.

![Command Center Walkthrough](docs/assets/forensic_walkthrough.gif)

*Direct Video File:* [▶ Watch High-Definition MP4 Demo](docs/assets/forensic_walkthrough.mp4)

---

## 🎯 Executive Problem Statement & Solution

| The Investigation Challenge | How This Platform Solves It |
| :--- | :--- |
| **Heterogeneous Telecom Dumps** (Jio, Airtel, Vi, BSNL with conflicting column formats) | **Dynamic Schema-Agnostic Ingestion Engine** that auto-detects 100+ telecom header variants, auto-upserts cell towers, and normalizes timestamps. |
| **Syndicate Obfuscation & SIM Swaps** (Burner phones, IMEI swaps, multi-SIM devices) | **Automated SIM Swap / IMEI Hopping Engine** that traces SIM cards jumping across handsets and flags sudden handset swaps within seconds. |
| **Carrier-Grade NAT (CGNAT) IPDR Logs** (Shared public IPs concealing cyber criminals) | **Deterministic Triple-Key IPDR NAT Resolver** (`Public IP + Port + UTC Timestamp`) with bulk 1930 portal batch matching. |
| **Complex Geographic Movements** (Millions of GPS/tower pings with manual plotting) | **7-Mode Tactical GIS Map** with animated trajectory playback, antenna azimuth sector cones (65°), spatial co-location meetings, and supersonic velocity alerts. |
| **Court Inadmissibility Risks** (Evidence tampering claims under Indian Evidence Act) | **Cryptographic SHA-256 Chained Audit Trail** with automated **Section 65B(4) IEA & Section 63 BSA 2023 certificates**. |

---

## 🏗️ System Architecture & Forensic Data Flow

Every metric, network node, and geospatial coordinate in this system is computed **100% dynamically** from real uploaded evidence—with zero hardcoded demo values.

```mermaid
flowchart TD
    subgraph Evidence["📁 Evidence Ingestion Layer"]
        CSV["Heterogeneous Telecom Dumps<br/>(.csv, .tsv, .xlsx, .xls)"]
        IPDR_File["ISP CGNAT Logs & 1930 Complaints"]
        Tower_Master["Cell Tower Master DB / Auto-Upsert"]
    end

    subgraph Core["⚙️ Forensic Processing & Core Engine (FastAPI 0.115+)"]
        HeaderNorm["Schema Normalizer & Column Mapper"]
        ORM["SQLAlchemy ORM + SQLite Ledger"]
        Analytics["Analytical Engines<br/>• Most Frequent Contacts (MFC)<br/>• Threat Scoring (0-100)<br/>• 24x7 Activity Matrix<br/>• IMEI/IMSI Hopping Tracker"]
        GIS_Engine["Geospatial Engine<br/>• Haversine Distance<br/>• Impossible Travel Velocity (>120 km/h)<br/>• Spatial Co-Location Resolver"]
        NAT_Resolver["IPDR CGNAT Triple-Key Resolver<br/>[IP + Port + Timestamp Window]"]
        Audit["SHA-256 Cryptographic Audit Ledger"]
    end

    subgraph AI["🧠 Agentic AI Layer (LangGraph)"]
        LangGraph["LangGraph StateGraph Workflow"]
        Guardrails["Section 5(2) Statutory Guardrails"]
        NLP["Bilingual Assistant (English / Hindi / Hinglish)"]
    end

    subgraph UI["🖥️ Modern Tactical Web Command Center"]
        Dash["Executive Command Dashboard"]
        Mods["28 Investigation Analytics Modules"]
        Map["7-Mode Leaflet GIS Engine"]
        Graph["Cytoscape.js Syndicate Graph"]
        Dossier["Export Engine (PDF Sec 65B, Excel, KML/KMZ)"]
    end

    CSV & IPDR_File & Tower_Master --> HeaderNorm --> ORM
    ORM --> Analytics & GIS_Engine & NAT_Resolver & Audit
    ORM --> LangGraph --> Guardrails --> NLP
    Analytics & GIS_Engine & NAT_Resolver --> Dash & Mods & Map & Graph
    Audit & Analytics --> Dossier
```

---

## 📸 Comprehensive Visual Walkthrough & Core Capabilities

---

### 1. 🎖️ Executive Command Center & Active FIR Oversight
The primary operational cockpit for Supervisory Officers (SP, DySP, Inspector) providing instantaneous visibility over open FIRs, total CDR records, common cross-case numbers, and suspect threat rankings.

![Command Dashboard](docs/assets/screenshots/01_command_dashboard.png)

#### 🔍 Key Capabilities:
- **Real-Time Forensic KPIs:** Total CDRs ingested, analyzed mobile numbers, cross-suspect common bridges, and physical towers mapped.
- **FIR Registry & Context Switcher:** Switch seamlessly between active cases (e.g., *FIR-RAJ-2026-108: Operation Hawk-Eye*) with full state isolation.
- **Immediate Target Inspection:** One-click drill down into individual target suspect profiles with threat scoring.

---

### 2. 🗂️ 28 Deep Forensics Investigation Modules
A specialized dual-sidebar interface categorizes 28 investigation modules into logical forensic domains, eliminating UI clutter while giving analysts surgical access to telecom records.

![Analysis Modules Overview](docs/assets/screenshots/02_analysis_modules_overview.png)

#### 📊 Module Matrix:
| Forensic Domain | Core Modules Included |
| :--- | :--- |
| **Call & Contact Forensics** | Advanced CDR Analysis, Most Frequent Contacts (MFC), Raw Data Grid, First/Last Call Chronology, Missing Dates Gap Analysis |
| **Identity & Hardware Forensics** | IMEI Summary & Patterns, IMSI Summary & Patterns, SIM Swap & IMEI Change Hopping, Ownership Intelligence |
| **Geospatial & Towers** | Location Summary, Day vs. Night Location Clusters, Movement Charts, Cell ID Changes, Geo Intelligence GIS |
| **Syndicate & Cross-Case** | Graph Analytics, Common Numbers Matrix, Cross-Suspect Shared Contacts, Co-Location Meetings |
| **IPDR & Cyber NAT** | Carrier NAT IPDR Resolver, Batch 1930 Portal NAT Correlation |
| **Statutory & Audit** | AI Forensic Copilot, Section 65B Chained Audit Trail, Multi-Format Dossier Generator |

---

### 3. 🕸️ 4-Quadrant Cytoscape Syndicate Network Topology
Detects criminal conspirators, kingpins, and money mules by visualizing multi-hop communication networks using force-directed graph theory.

![Syndicate Graph Analytics](docs/assets/screenshots/03_syndicate_graph_analytics.png)

#### 🔍 Key Capabilities:
- **Force-Directed Interactive Layout:** Drag, zoom, filter by call frequency, and isolate call clusters.
- **Centrality & Degree Metrics:** Automatically highlights high-centrality bridge nodes operating between multiple suspect cells.
- **Cross-Suspect Calling Pairs:** Filter mutual high-frequency communications between prime accused individuals.

---

### 4. 🗺️ 7-Mode Tactical Police GIS Geospatial Engine
Pinpoints suspect physical movement, tower handoffs, safehouse clusters, and impossible travel velocity anomalies across Rajasthan and national borders.

![Geospatial GIS Tracking](docs/assets/screenshots/04_geospatial_gis_tracking.png)

#### 🛰️ 7 Dedicated Map Modes:
1. **Cell Towers Pin Mode:** Tower locations with Azimuth, CGI, Operator, and physical address lookup.
2. **Signal Density Heatmap:** Visualizes frequency hotspots and base camps.
3. **Route Trajectory & Time Scrubber:** Step-by-step chronological animation of suspect movement with interactive time slider.
4. **Day vs. Night Split Clusters:** Separates daytime activity from night-time roosting towers (00:00 - 05:00 hrs) to identify suspect residences.
5. **65° Tri-Sector Azimuth Cones:** Renders directional antenna radiation patterns from tower CGIs.
6. **Spatial-Temporal Co-Location:** Identifies distinct suspects present under the same tower within a configurable time window (e.g., 30 minutes).
7. **Impossible Travel Velocity Alerts:** Flags travel speeds exceeding 120 km/h between non-consecutive cell tower hops.

---

### 5. 🌐 Carrier-Grade NAT (CGNAT) IPDR De-Anonymizer
Resolves shared public IPv4 addresses used by cyber syndicates to identify the exact physical subscriber using source port and microsecond timestamps.

![IPDR CGNAT Resolution](docs/assets/screenshots/05_ipdr_cgnat_resolution.png)

#### 🔍 Forensic Resolution Logic:
$$\text{CGNAT Match} = f(\text{Public IP}, \text{Source Port}, \text{Incident UTC Timestamp}) \longrightarrow \text{Private IP} + \text{MSISDN} + \text{Subscriber Identity}$$

- **Single Query Resolver:** Instant lookup for cyber fraud incidents reported with source port and timestamp.
- **Bulk 1930 Portal Batch Ingestion:** Correlates hundreds of National Cyber Crime Reporting Portal (NCRP / 1930) tickets against ISP IPDR logs simultaneously.

---

### 6. 🤖 LangGraph Bilingual AI Forensic Copilot
An intelligent agentic assistant that answers natural-language queries from Investigating Officers in **English, Hindi, and Hinglish**, adhering strictly to Section 5(2) of the Indian Telegraph Act.

![AI Forensic Copilot](docs/assets/screenshots/06_ai_forensic_copilot.png)

#### 💬 Example Inquiries:
- *"Kaunse 3 numbers pe suspect ne sabse zyada raat ko call kiya hai?"*
- *"Show me all IMEI numbers linked to target 9414098765 during the crime window."*
- *"Kya suspect A aur suspect B ek hi location pe the 15 November ko?"*

---

### 7. ⚖️ Section 65B(4) / Section 63 BSA Dossier & Audit Ledger
Generates tamper-proof, court-admissible forensic packages with cryptographic verification.

![Statutory Dossiers Export](docs/assets/screenshots/07_statutory_dossiers_export.png)

- **Court-Ready PDF Dossier:** 8 structured sections complete with SHA-256 hash seals and electronic signature blocks under Section 65B(4) IEA / Section 63 BSA 2023.
- **6-Sheet Forensic Excel Workbook:** Formatted tables for Raw CDRs, Top Contacts, Cell Towers, IMEI History, Night Activity, and Meeting Matrix.
- **Google Earth KML/KMZ:** 3D flight paths, tower polygons, and animated chronological tours for courtroom visual presentation.
- **Chained Audit Trail:** Verifies every officer interaction and query using SHA-256 state hashing (`/api/audit/verify`).

---

### 8. 📥 Universal Evidence Ingestion Engine
Handles arbitrary telecom CSV, TSV, and Excel files with automated column mapping and smart tower auto-upsert.

![Evidence Ingestion](docs/assets/screenshots/08_evidence_ingestion_upload.png)

---

## ⚡ Quick Start & Deployment Guide

### Prerequisites
- **Operating System:** Linux (Debian, Ubuntu, Kali), macOS, or Windows WSL2
- **Python:** Version `3.11` or higher
- **Browser:** Chromium, Google Chrome, Firefox, or Safari

### 1. Clone & Set Up Virtual Environment
```bash
git clone https://github.com/your-org/rajasthan-police-cdr-forensic.git
cd Rajistanhackathon

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Launch the Application Server
```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

On server startup, the system automatically:
1. Initializes SQLite schema and cryptographic audit tables (`init_db()`).
2. Seeds default law enforcement credentials (`seed_default_users()`).
3. Seeds Rajasthan tower master records (`seed_towers_from_csv()`).

### 3. Access Command Center & Docs
- **Main Command UI:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive OpenAPI/Swagger Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Local Forensic CodeWiki:** [http://127.0.0.1:8080](docs/index.html) *(run `python3 -m http.server 8080 -d docs`)*

---

## 🧪 Automated Testing & Verification

The platform maintains 100% test pass rates across statutory compliance, analytics engines, and API endpoints.

```bash
# Run complete test suite with verbose output
pytest -v
```

```
============================== test session starts ==============================
platform linux -- Python 3.11.x, pytest-8.x.x
rootdir: /home/kali/prototype/Rajistanhackathon
collected 47 items

tests/test_ai_agent.py ...........                                        [ 23%]
tests/test_analytics.py ................                                  [ 57%]
tests/test_audit_ledger.py .......                                        [ 72%]
tests/test_ipdr_nat.py .........                                          [ 91%]
tests/test_reports.py ....                                                [100%]

============================== 47 passed in 4.12s ===============================
```

---

## 🏛️ Statutory Compliance & Legal Framework

This software has been engineered in alignment with Indian legal and constitutional standards:

- **Section 65B(4) Indian Evidence Act, 1872 / Section 63 Bharatiya Sakshya Adhiniyam (BSA), 2023:** Automatic generation of device metadata, hash certification, and investigator declarations.
- **Section 5(2) Indian Telegraph Act, 1885:** Built-in AI guardrails preventing unauthorized surveillance or unlawful interception inquiries.
- **Tamper-Evident SHA-256 Ledger:** Chained block-style logging ensuring evidence provenance cannot be altered post-seizure.

---

## 👥 Authors & Acknowledgments

- **Developed for:** Rajasthan Police Cyber Crime Wing (PS03)
- **Core Technology:** FastAPI, LangGraph, Cytoscape.js, Leaflet.js, ReportLab
- **License:** Proprietary Law Enforcement Analytical Software. Restricted to authorized agencies.
