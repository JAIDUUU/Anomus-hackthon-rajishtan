import io
import json
from datetime import datetime
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from app.db import Case, CDRRecord, IPDRRecord, ImportBatch, AIObservation
from app.analysis import (
    analyze_communication_patterns,
    find_common_numbers,
    detect_meetings,
    detect_imei_sim_changes,
    get_ordered_suspects_for_case
)


def generate_pdf_report(case_id: str, db: Session) -> io.BytesIO:
    case = db.query(Case).filter(Case.id == case_id).first()
    batches = db.query(ImportBatch).filter(ImportBatch.case_id == case_id).all()
    observations = db.query(AIObservation).filter(AIObservation.case_id == case_id).all()

    # Extract suspect numbers dynamically from case brief or top active CDR targets
    suspect_nums = [s["phone"] for s in get_ordered_suspects_for_case(case_id, db) if s.get("phone")]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        alignment=1,  # Center
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#475569"),
        alignment=1,
        spaceAfter=15
    )

    h2_style = ParagraphStyle(
        "Heading2Custom",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=12,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        "BodyCustom",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1e293b")
    )

    warning_box_style = ParagraphStyle(
        "WarningBox",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#991b1b")
    )

    story = []

    # Title & Header
    story.append(Paragraph("RAJASTHAN POLICE CYBER CRIME CELL", title_style))
    story.append(Paragraph("CYBER SYNDICATE CDR / IPDR INVESTIGATION REPORT (PROTOTYPE DEMO)", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1e3a8a"), spaceAfter=10))

    # Case Overview Table
    overview_data = [
        [Paragraph("<b>Case ID:</b>", body_style), Paragraph(case.id if case else "N/A", body_style),
         Paragraph("<b>Date Generated:</b>", body_style), Paragraph(datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"), body_style)],
        [Paragraph("<b>Case Title:</b>", body_style), Paragraph(case.title if case else "N/A", body_style),
         Paragraph("<b>Investigating Unit:</b>", body_style), Paragraph("State Cyber PS, Jaipur", body_style)],
        [Paragraph("<b>Total CDR Records:</b>", body_style), Paragraph(str(db.query(CDRRecord).filter(CDRRecord.case_id == case_id).count()), body_style),
         Paragraph("<b>Total IPDR Records:</b>", body_style), Paragraph(str(db.query(IPDRRecord).filter(IPDRRecord.case_id == case_id).count()), body_style)]
    ]
    t_overview = Table(overview_data, colWidths=[100, 160, 110, 160])
    t_overview.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_overview)
    story.append(Spacer(1, 10))

    # Import Validation Summary
    story.append(Paragraph("1. Data Import & Ingestion Validation Summary", h2_style))
    val_data = [["Filename", "Type", "Mapping", "Total Rows", "Valid Rows", "Rejected Rows"]]
    for b in batches:
        val_data.append([
            b.filename, b.file_type, b.mapping_name or "Default",
            str(b.total_rows), str(b.valid_rows), str(b.rejected_rows)
        ])
    if len(val_data) == 1:
        val_data.append(["No uploads logged", "-", "-", "0", "0", "0"])

    t_val = Table(val_data, colWidths=[130, 60, 110, 75, 75, 80])
    t_val.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("PADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_val)
    story.append(Spacer(1, 10))

    # Cross-Suspect Common Numbers
    story.append(Paragraph("2. Cross-Suspect Common Number Correlation", h2_style))
    common_res = find_common_numbers(suspect_nums[:3], case_id, db)
    common_list = common_res.get("common_contacts", [])
    comm_data = [["Common Number", "Connected Suspects", "Target Count", "Sample Evidence File / Row"]]
    for c in common_list[:6]:
        ev = c.get("evidence", [{}])[0]
        ev_str = f"{ev.get('source_file', '')} (Row {ev.get('source_row', '')})"
        comm_data.append([
            c["common_number"], ", ".join(c["connected_to_targets"]),
            str(c["target_count"]), ev_str
        ])
    if len(comm_data) == 1:
        comm_data.append(["None detected", "-", "-", "-"])

    t_comm = Table(comm_data, colWidths=[110, 160, 80, 180])
    t_comm.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdfa")]),
        ("PADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_comm)
    story.append(Spacer(1, 10))

    # IMEI & SIM Swap Analysis
    story.append(Paragraph("3. IMEI / SIM Swap Anomaly Detection", h2_style))
    imei_res = detect_imei_sim_changes(case_id, db)
    imei_data = [["IMEI Number", "Numbers Used", "Observation", "Date Range"]]
    for item in imei_res.get("multi_number_imeis", [])[:5]:
        first_d = item["history"][0]["first_seen"] if item["history"] else ""
        last_d = item["history"][-1]["last_seen"] if item["history"] else ""
        imei_data.append([
            item["imei"], ", ".join(item["numbers"]),
            f"Handset shared / SIM swapped ({item['distinct_numbers_count']} numbers)",
            f"{first_d[:10]} to {last_d[:10]}"
        ])
    if len(imei_data) == 1:
        imei_data.append(["No IMEI swaps detected", "-", "-", "-"])

    t_imei = Table(imei_data, colWidths=[120, 130, 160, 120])
    t_imei.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#b45309")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fffbeb")]),
        ("PADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_imei)
    story.append(Spacer(1, 10))

    # Physical Meeting Detection
    story.append(Paragraph("4. Physical Co-Location / Meeting Detection", h2_style))
    meetings = detect_meetings(suspect_nums[0], suspect_nums[1], case_id, db) if len(suspect_nums) >= 2 else []
    meet_data = [["Cell ID", "Location Name", "Time Window", "Delta (sec)", "Evidence Records"]]
    for m in meetings[:4]:
        meet_data.append([
            m["cell_id"], m["area_name"],
            f"{m['event_target_1']['timestamp'][11:19]} vs {m['event_target_2']['timestamp'][11:19]}",
            str(m["time_diff_sec"]),
            f"S1: {m['event_target_1']['source_file']} (R{m['event_target_1']['source_row']})"
        ])
    if len(meet_data) == 1:
        meet_data.append(["No co-location events found", "-", "-", "-", "-"])

    t_meet = Table(meet_data, colWidths=[90, 130, 120, 60, 130])
    t_meet.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("PADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_meet)
    story.append(Spacer(1, 10))

    # AI Assistant Observations & Verification Status
    story.append(Paragraph("5. AI Assistant Observations & Officer Verification Status", h2_style))
    ai_data = [["Query", "Summary Observation", "Status", "Verified By"]]
    for obs in observations[:8]:
        status_label = obs.status.upper().replace("_", " ")
        ai_data.append([
            Paragraph(obs.query_text[:50] + ("..." if len(obs.query_text) > 50 else ""), body_style),
            Paragraph(obs.answer_text[:120].replace("**", "") + "...", body_style),
            status_label,
            obs.verified_by or "Pending"
        ])
    if len(ai_data) == 1:
        ai_data.append(["No assistant observations logged", "-", "N/A", "-"])

    t_ai = Table(ai_data, colWidths=[120, 230, 90, 90])
    t_ai.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("PADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_ai)
    story.append(Spacer(1, 25))

    # Footer Disclaimer
    disclaimer = Paragraph(
        "<b>LEGAL NOTICE & STATUTORY DISCLAIMER:</b> Draft for officer review - not a final conclusion. "
        "All analytical findings, co-location correlations, and AI observations are computer-generated investigative leads "
        "subject to Section 65B Indian Evidence Act certification and mandatory supervisory verification prior to judicial submission.",
        warning_box_style
    )
    story.append(disclaimer)

    def add_page_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(colors.HexColor("#dc2626"))
        canvas.drawString(40, 25, "Draft for officer review - not a final conclusion | Synthetic Hackathon Demo Data Only")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawRightString(570, 25, f"Page {doc.page} | Rajasthan Police Cyber Wing")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_footer, onLaterPages=add_page_footer)
    buffer.seek(0)
    return buffer


def generate_excel_report(case_id: str, db: Session) -> io.BytesIO:
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    disclaimer_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    disclaimer_font = Font(name="Calibri", size=10, bold=True, color="991B1B")

    # Sheet 1: Case Summary
    ws_summary = wb.create_sheet(title="Case Summary")
    case = db.query(Case).filter(Case.id == case_id).first()
    summary_rows = [
        ["RAJASTHAN POLICE CYBER CRIME INVESTIGATION REPORT", ""],
        ["Status", "Draft for officer review - not a final conclusion"],
        ["Case ID", case.id if case else "N/A"],
        ["Case Title", case.title if case else "N/A"],
        ["Generated At", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")],
        ["Total CDR Records", db.query(CDRRecord).filter(CDRRecord.case_id == case_id).count()],
        ["Total IPDR Records", db.query(IPDRRecord).filter(IPDRRecord.case_id == case_id).count()],
    ]
    for r in summary_rows:
        ws_summary.append(r)
    ws_summary.column_dimensions["A"].width = 25
    ws_summary.column_dimensions["B"].width = 50

    # Sheet 2: CDR Records
    ws_cdr = wb.create_sheet(title="CDR Normalized Data")
    cdr_headers = ["ID", "A_Number", "B_Number", "Call_Type", "Start_Time", "Duration_Sec", "IMEI", "IMSI", "Cell_ID", "Source_File", "Source_Row"]
    ws_cdr.append(cdr_headers)
    for col_idx in range(1, len(cdr_headers) + 1):
        cell = ws_cdr.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font

    cdrs = db.query(CDRRecord).filter(CDRRecord.case_id == case_id).limit(1000).all()
    for r in cdrs:
        ws_cdr.append([
            r.id, r.a_number, r.b_number, r.call_type, r.start_time,
            r.duration_sec, r.imei, r.imsi, r.cell_id, r.source_file, r.source_row
        ])
    for col in ws_cdr.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws_cdr.column_dimensions[col[0].column_letter].width = max(max_len + 2, 10)

    # Sheet 3: IPDR Records
    ws_ipdr = wb.create_sheet(title="IPDR Sessions")
    ipdr_headers = ["ID", "Subscriber", "Source_IP", "Source_Port", "Dest_IP", "Dest_Port", "Session_Start", "Session_End", "Bytes", "App_Hint", "Source_File", "Source_Row"]
    ws_ipdr.append(ipdr_headers)
    for col_idx in range(1, len(ipdr_headers) + 1):
        cell = ws_ipdr.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font

    ipdrs = db.query(IPDRRecord).filter(IPDRRecord.case_id == case_id).limit(500).all()
    for r in ipdrs:
        ws_ipdr.append([
            r.id, r.subscriber_number, r.source_ip, r.source_port,
            r.destination_ip, r.destination_port, r.session_start,
            r.session_end, r.bytes_transferred, r.app_hint, r.source_file, r.source_row
        ])
    for col in ws_ipdr.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws_ipdr.column_dimensions[col[0].column_letter].width = max(max_len + 2, 10)

    # Sheet 4: AI Observations
    ws_ai = wb.create_sheet(title="AI Observations & Verification")
    ai_headers = ["Obs_ID", "Query", "AI_Observation", "Confidence_Note", "Verification_Status", "Verified_By", "Timestamp"]
    ws_ai.append(ai_headers)
    for col_idx in range(1, len(ai_headers) + 1):
        cell = ws_ai.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font

    obs_list = db.query(AIObservation).filter(AIObservation.case_id == case_id).all()
    for o in obs_list:
        ws_ai.append([
            o.id, o.query_text, o.answer_text, o.confidence_note,
            o.status, o.verified_by or "Unverified",
            o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else ""
        ])
    for col in ws_ai.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws_ai.column_dimensions[col[0].column_letter].width = min(max(max_len + 2, 12), 40)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
