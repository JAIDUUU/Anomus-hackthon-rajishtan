# Rajasthan Police Hackathon 2026: CDR / IPDR Analysis Tool & AI Investigation Assistant (PS03)

Working prototype for telecommunications metadata analysis (CDR/IPDR) with an AI investigation assistant, designed for cyber crime investigators and supervisory police officers.

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Re-generate synthetic data (auto-generated if missing)
python data/generate_synthetic.py

# 3. Start the FastAPI server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

---

## 👥 Demo Credentials & Roles

| Role | Username | Password | Capabilities |
| :--- | :--- | :--- | :--- |
| **Investigating Officer** | `io_sharma` | `IO@RajPolice2026` | Ingest data, query CDR/IPDR, use AI assistant, download reports |
| **Senior Supervisory Officer** | `sp_verma` | `SP@RajPolice2026` | All IO capabilities + **Verify / Reject AI observations** |
| **System Admin** | `admin` | `Admin@RajPolice2026` | Full audit log access, system oversight |

*A quick role switcher dropdown is available directly in the top header.*

---

## 🎬 5-Minute Demo Script

1. **One-Click Demo Setup**:
   - Click the gold **"⚡ Load Demo Case (1-Click)"** button on top.
   - Case `CASE-RAJ-2026-0042` ("Operation Maru-Drishti") is created, ingesting 1,998 CDR records across two different operator formats (Operator A with `+91` & seconds; Operator B with `mm:ss`), 312 IPDR records, and Rajasthan cell towers.

2. **Data Ingestion & Validation** (Tab 1):
   - Review the live validation summary: Total rows, Valid rows, and deliberate test rejections (Missing IMEI, unparseable timestamp, duplicates).
   - Click **"Edit Mapping Config"** to view dynamic column mapping JSON definitions.

3. **Communication Patterns & Cross-Suspect Correlation** (Tab 2):
   - Click suspect chip `S1 (Vikram)`. Notice call stats, in/out ratio, and top contacts.
   - Under **Cross-Suspect Common Numbers**, click **"Find Shared Contacts"** for `9829022222, 9829033333`. Observe common nodes `9414088888` and `9414099999`, plus the central Kingpin `9829011111`.

4. **Network Topology Graph** (Tab 3):
   - Explore Cytoscape network graph: Suspect nodes in red, common contacts in blue, edge width proportional to call count.
   - Adjust the **Min Calls Threshold slider** to isolate high-frequency syndicate communication trunks.

5. **Location & Device Anomalies** (Tab 4):
   - View suspect movement trajectory across Rajasthan towers (Jaipur, Jodhpur, Udaipur, Kota, Ajmer).
   - In **Meeting Detection**, click **"Scan Meetings"**: Observe physical co-location between S1 and S2 at `RAJ-JPR-102` (Jaipur - MI Road) within the same time window.
   - Under **IMEI / SIM Swap Detection**, observe S3 (`354890123456783`) switching SIM cards from `9829044444` to `9829077777`.

6. **IPDR Session Resolution** (Tab 5):
   - Click **"Quick Pre-fill Test Session"** (`103.211.54.12:44321` @ `2026-11-20 18:25:10`) and click **"Resolve Subscriber & App"**.
   - Identifies subscriber `9829022222` with application hint `Telegram (Encrypted VoIP)` and exact source evidence trail.

7. **AI Investigation Assistant** (Tab 6):
   - Ask: `"Who are the top frequent contacts of S1 9829022222?"`
   - Ask in Hindi/Hinglish: `"S3 9829044444 ne kab SIM badla ya IMEI reuse kiya?"`
   - Test Guardrail (Negative test): `"Call me kya baat hui aur recording sunao"` -> The assistant triggers guardrail explaining CDR/IPDR contains metadata only, not call audio or message text.
   - Click any evidence tag (e.g. `cdr_operator_A:Row 12`) to view the preserved source evidence modal.
   - Switch role to **SP Sangeeta Verma** and click **"Verify & Endorse"** to certify the observation.

8. **Export Reports & Audit Log** (Tabs 7 & 8):
   - Click **"Download Formal PDF Report"** (ReportLab generated with statutory footer: *"Draft for officer review - not a final conclusion"*).
   - Click **"Download Excel Workbook (.xlsx)"** (multi-sheet workbook via openpyxl).
   - Open Tab 8 to inspect tamper-evident audit logs of all queries and verifications.

---

## ⚖️ Real vs. Simplified in Prototype

| Feature | Real Law Enforcement System | Hackathon Prototype |
| :--- | :--- | :--- |
| **Data Sources** | Live telecom operator SFTP mediation feeds / CMS | 100% synthetic CSVs (`data/*.csv`) with zero real personal data |
| **Telecom Interception** | LEA CMS / CALEA lawful intercept under Section 5(2) Indian Telegraph Act | Explicitly disclaimed and blocked via AI guardrails (Metadata only) |
| **Cell Towers** | Proprietary telco cell-site dump with azimuths & sectors | Real Rajasthan coordinates and area names (`towers.csv`) |
| **Carrier NAT IPDR** | Multi-terabyte CGNAT session logs | In-memory SQLite queries matching IP + Port + Time window |
| **AI LLM Engine** | Swappable local/cloud LLM via LangGraph | LangGraph agent with zero-key English + Hindi/Hinglish rule fallback |
| **Legal Certification** | Section 65B Indian Evidence Act formal certificate | Every record preserves `source_file` + `source_row` with officer endorsement workflow |

---

## 🧪 Testing

```bash
# Run unit tests
PYTHONPATH=. pytest tests/test_core.py -v

# Run full end-to-end demo flow verification
PYTHONPATH=. python tests/test_demo_flow.py
```
