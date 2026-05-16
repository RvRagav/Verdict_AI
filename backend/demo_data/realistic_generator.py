"""Realistic synthetic tender + bidder document generator.

Produces a complete demo data set that exercises every part of the
pipeline — typed PDFs, scanned images, photographed certificates,
corrigenda — with figures that genuinely PASS, FAIL or REVIEW against
extracted criteria.

Output (relative to this module's directory):

    real/
      nit_crpf_patrol_vehicles.pdf            ← 4-page typed NIT
      corrigendum_1.pdf                       ← 1-page typed amendment
      bidders/
        acme/
          01_cover_letter.pdf
          02_turnover_certificate_ca.pdf      ← typed
          03_gst_certificate.pdf              ← typed
          04_pan_card.pdf                     ← typed
          05_iso_9001_certificate.pdf         ← typed (NABCB-accredited)
          06_completion_certificates.pdf      ← typed list of 4 projects
          07_udyam_msme.pdf                   ← typed
        bravo/
          01_cover_letter.pdf
          02_turnover_certificate_ca.pdf      ← typed (turnover BELOW threshold)
          03_gst_certificate.pdf              ← typed (EXPIRED validity)
          04_pan_card.pdf                     ← typed
          05_iso_9001_certificate.pdf         ← typed (non-NABCB body)
          06_completion_certificates.pdf      ← typed list of only 2 projects
        charlie/
          01_cover_letter.pdf                 ← typed
          02_turnover_certificate_scan.jpg    ← phone-photographed (TILTED + STAMPED)
          03_gst_certificate.pdf              ← typed
          04_pan_card.pdf                     ← typed
          05_completion_certificates.pdf      ← typed list of 3 projects

Bidder behaviour summary — what the system should infer:

    Acme Defence       → fully qualified (PASS on every criterion)
    Bravo Industries   → multiple FAILs (low turnover, expired GST, weak ISO,
                          insufficient projects)
    Charlie Auto       → REVIEW-leaning (CA cert is a phone photo with stamp
                          partly covering the figure → low OCR confidence)

Run:
    python -m backend.demo_data.realistic_generator
"""

from __future__ import annotations

import io
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEMO_DIR.parent.parent
OUT = REPO_ROOT / "sample_docs"


# ─── PDF utilities (reportlab) ──────────────────────────────────────


def _styles():
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"],
            fontSize=14, leading=18, alignment=1,
            textColor=colors.HexColor("#0a2856"),
            spaceAfter=8,
        ),
        "h": ParagraphStyle(
            "h", parent=base["Heading2"],
            fontSize=11, leading=15,
            textColor=colors.HexColor("#0a2856"),
            spaceBefore=10, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"],
            fontSize=10, leading=13.5,
            spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"],
            fontSize=8, leading=11, textColor=colors.HexColor("#444"),
        ),
        "right": ParagraphStyle(
            "right", parent=base["BodyText"],
            fontSize=10, leading=13.5, alignment=2,
        ),
    }


def _new_doc(out_path: Path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )


def _table(rows, col_widths_cm=None, header=True):
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Table, TableStyle
    if col_widths_cm:
        col_widths = [c * cm for c in col_widths_cm]
    else:
        col_widths = None
    t = Table(rows, colWidths=col_widths, hAlign="LEFT")
    style = [
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#888")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bbb")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style.extend([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0a2856")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])
    t.setStyle(TableStyle(style))
    return t


# ─── 1. NIT (Notice Inviting Tender) — 4 pages ──────────────────────


def make_nit() -> Path:
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph, Spacer, PageBreak,
    )

    out = OUT / "nit_crpf_patrol_vehicles.pdf"
    doc = _new_doc(out)
    s = _styles()
    flow = []

    # Page 1 — cover
    flow.append(Paragraph("CENTRAL RESERVE POLICE FORCE", s["title"]))
    flow.append(Paragraph("MINISTRY OF HOME AFFAIRS, GOVERNMENT OF INDIA", s["title"]))
    flow.append(Spacer(1, 0.3 * cm))
    flow.append(Paragraph("NOTICE INVITING e-TENDER", s["title"]))
    flow.append(Paragraph("(Two-Bid System under GFR 2017 Rule 162)", s["small"]))
    flow.append(Spacer(1, 0.6 * cm))

    flow.append(_table([
        ["Tender No.", "CRPF/PROC/2026/PV-15-A"],
        ["Description", "Supply and delivery of Armoured Patrol Vehicles for CRPF Operations (qty: 12 nos.)"],
        ["Estimated value", "Rs. 15,00,00,000 (Rupees Fifteen Crore only)"],
        ["EMD", "Rs. 15,00,000 (Rupees Fifteen Lakh only)"],
        ["Bid submission deadline", "15 May 2026, 1500 hrs IST"],
        ["Technical bid opening", "16 May 2026, 1100 hrs IST"],
        ["Tender fee", "Rs. 1,000 (non-refundable; MSE exempt)"],
        ["Performance security", "3% of contract value, valid 60 days beyond warranty"],
        ["Place of delivery", "CRPF Group Centre, Pinjore, Haryana"],
        ["Warranty", "24 months from date of acceptance"],
    ], col_widths_cm=[5, 11], header=False))

    flow.append(Spacer(1, 0.4 * cm))
    flow.append(Paragraph(
        "1. Bids are invited from manufacturers/authorised distributors meeting the eligibility "
        "criteria stated below. Bids must be submitted online on the Central Public Procurement "
        "Portal (https://eprocure.gov.in) before the deadline. The technical and financial bids "
        "shall be submitted in two separate covers / encrypted envelopes as per Rule 162 of GFR "
        "2017. Financial bids of only those bidders found technically eligible shall be opened.",
        s["body"]))

    flow.append(PageBreak())

    # Page 2 — eligibility criteria (the heart of the document)
    flow.append(Paragraph("Section 4 — Eligibility Criteria", s["h"]))
    flow.append(Paragraph(
        "All criteria listed below are MANDATORY unless explicitly marked optional. "
        "Non-compliance with any mandatory criterion shall lead to rejection at the "
        "preliminary examination stage.",
        s["body"]))
    flow.append(Spacer(1, 0.2 * cm))

    flow.append(Paragraph("Clause 4.1(a) — Annual turnover", s["h"]))
    flow.append(Paragraph(
        "The bidder shall have an annual turnover of not less than Rs. 10 (Ten) Crore in each of the "
        "last 3 (three) financial years (FY 2022-23, FY 2023-24, FY 2024-25). The turnover shall be "
        "computed from the standalone audited financial statements of the bidder, certified by a "
        "Chartered Accountant in practice. Consolidated figures of the bidder's parent or holding "
        "company shall NOT be considered.",
        s["body"]))
    flow.append(Paragraph("Mandatory. GFR Rule 173(iii). Override NOT permitted.", s["small"]))

    flow.append(Paragraph("Clause 4.1(b) — Net worth", s["h"]))
    flow.append(Paragraph(
        "The bidder shall have a positive net worth of not less than Rs. 3 (Three) Crore as per "
        "the audited balance sheet of the immediately preceding financial year (FY 2024-25).",
        s["body"]))
    flow.append(Paragraph("Mandatory. GFR Rule 173(iii). Override NOT permitted.", s["small"]))

    flow.append(Paragraph("Clause 4.2(a) — GST registration", s["h"]))
    flow.append(Paragraph(
        "The bidder shall possess a valid GST registration certificate issued under the CGST Act, "
        "2017. The certificate shall be active and current as on the date of bid submission.",
        s["body"]))
    flow.append(Paragraph("Mandatory.", s["small"]))

    flow.append(Paragraph("Clause 4.2(b) — Permanent Account Number (PAN)", s["h"]))
    flow.append(Paragraph(
        "The bidder shall furnish a copy of the valid PAN allotted by the Income Tax Department, "
        "Government of India.",
        s["body"]))
    flow.append(Paragraph("Mandatory.", s["small"]))

    flow.append(PageBreak())

    # Page 3 — more criteria
    flow.append(Paragraph("Clause 4.3 — Past performance", s["h"]))
    flow.append(Paragraph(
        "The bidder shall have successfully completed a minimum of 3 (three) similar supply orders "
        "in the last 5 (five) financial years. Each order shall be for armoured or specialised "
        "vehicles of value not less than Rs. 3 (Three) Crore. Completion certificates shall be "
        "issued by the ordering authority on its letterhead.",
        s["body"]))
    flow.append(Paragraph("Mandatory.", s["small"]))

    flow.append(Paragraph("Clause 4.4 — ISO 9001 certification", s["h"]))
    flow.append(Paragraph(
        "The bidder shall possess a valid ISO 9001:2015 certification for Quality Management "
        "Systems issued by a body accredited by the National Accreditation Board for Certification "
        "Bodies (NABCB) or an equivalent international accreditation body.",
        s["body"]))
    flow.append(Paragraph("Optional but desirable; carries 10 marks in technical scoring.", s["small"]))

    flow.append(Paragraph("Clause 4.5 — Bidders registered under MSME / Udyam", s["h"]))
    flow.append(Paragraph(
        "Bidders registered under the MSME / Udyam Registration scheme shall be eligible for the "
        "exemptions and preferences under the Public Procurement Policy for MSEs, 2012, including "
        "exemption from EMD and tender fee.",
        s["body"]))
    flow.append(Paragraph("Optional. Apply only if claiming preference.", s["small"]))

    flow.append(Paragraph("Clause 4.6 — Manufacturing capacity", s["h"]))
    flow.append(Paragraph(
        "The bidder shall demonstrate adequate manufacturing capacity to deliver the full quantity "
        "within the contractual delivery period. The bidder may submit details of plant area, "
        "production lines, and recent supply orders as evidence of capacity.",
        s["body"]))
    flow.append(Paragraph(
        "Qualitative assessment by the Tender Evaluation Committee. GFR Rule 173 — committee "
        "discretion permitted. Override permitted with second-officer concurrence.",
        s["small"]))

    flow.append(PageBreak())

    # Page 4 — bid format + signatures
    flow.append(Paragraph("Section 5 — Required Documents", s["h"]))
    flow.append(Paragraph(
        "The bidder shall submit the following documents in the technical bid envelope. Failure "
        "to submit any mandatory document shall lead to rejection at the preliminary examination "
        "stage:",
        s["body"]))
    flow.append(_table([
        ["#", "Document", "Mandatory?"],
        ["1", "Bid cover letter on company letterhead", "Yes"],
        ["2", "Audited Balance Sheets / CA-certified turnover for last 3 FYs", "Yes"],
        ["3", "Bank solvency certificate (≥ 6 months old)", "Yes"],
        ["4", "Valid GST Registration Certificate", "Yes"],
        ["5", "Permanent Account Number (PAN) card", "Yes"],
        ["6", "Completion certificates for ≥ 3 similar supply orders (Clause 4.3)", "Yes"],
        ["7", "ISO 9001:2015 certificate", "Optional"],
        ["8", "Udyam / MSME registration certificate (if claiming preference)", "Optional"],
        ["9", "Power of Attorney for the signatory", "Yes"],
        ["10", "EMD instrument (DD / Bank Guarantee / e-payment receipt)", "Yes"],
        ["11", "Non-blacklisting affidavit on Rs. 100 stamp paper", "Yes"],
        ["12", "Make-in-India self-declaration (Class-I / Class-II)", "Yes"],
        ["13", "Manufacturing capacity certificate (Clause 4.6)", "Yes"],
    ], col_widths_cm=[1.2, 11, 3], header=True))

    flow.append(Spacer(1, 0.6 * cm))
    flow.append(Paragraph(
        "<i>Issued under the authority of the Director General, Central Reserve Police Force, "
        "vide office order dated 15 March 2026.</i>",
        s["small"]))
    flow.append(Spacer(1, 0.3 * cm))
    flow.append(Paragraph("(Sd/-) Inspector A. Sharma", s["right"]))
    flow.append(Paragraph("Procurement Officer", s["right"]))
    flow.append(Paragraph("CRPF, Block-1, CGO Complex, New Delhi", s["right"]))

    doc.build(flow)
    return out


# ─── 2. Corrigendum ─────────────────────────────────────────────────


def make_corrigendum() -> Path:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer

    out = OUT / "corrigendum_1.pdf"
    doc = _new_doc(out)
    s = _styles()
    flow = []
    flow.append(Paragraph("CORRIGENDUM No. 1", s["title"]))
    flow.append(Paragraph("To Tender No. CRPF/PROC/2026/PV-15-A", s["small"]))
    flow.append(Paragraph("Issued: 28 April 2026", s["small"]))
    flow.append(Spacer(1, 0.5 * cm))
    flow.append(Paragraph(
        "Reference: Notice Inviting e-Tender No. CRPF/PROC/2026/PV-15-A dated 15 March 2026 for "
        "Supply of Armoured Patrol Vehicles.",
        s["body"]))
    flow.append(Paragraph("The following amendments are hereby notified to all prospective bidders:", s["body"]))
    flow.append(Spacer(1, 0.3 * cm))

    flow.append(Paragraph("Amendment 1 — Clause 4.1(a) Annual turnover", s["h"]))
    flow.append(_table([
        ["", "Earlier text", "Amended text"],
        ["Clause 4.1(a)",
         "Annual turnover not less than Rs. 10 (Ten) Crore in each of the last 3 financial years.",
         "Annual turnover not less than Rs. 15 (Fifteen) Crore in each of the last 3 financial years."],
    ], col_widths_cm=[3, 6, 6]))

    flow.append(Spacer(1, 0.3 * cm))
    flow.append(Paragraph("Amendment 2 — Bid submission deadline", s["h"]))
    flow.append(Paragraph(
        "The bid submission deadline stands extended from <b>15 May 2026</b> to <b>22 May 2026</b>, "
        "1500 hrs IST. Technical bid opening rescheduled to <b>23 May 2026</b>, 1100 hrs IST.",
        s["body"]))

    flow.append(Spacer(1, 0.5 * cm))
    flow.append(Paragraph(
        "All other terms and conditions of the original NIT shall remain unchanged. Bidders are "
        "advised to download the latest version of the bid forms from the CPP Portal.",
        s["body"]))
    flow.append(Spacer(1, 0.5 * cm))
    flow.append(Paragraph("(Sd/-) Inspector A. Sharma, Procurement Officer", s["right"]))

    doc.build(flow)
    return out


# ─── 3. Bidder document generators ──────────────────────────────────


def _bidder_dir(name: str) -> Path:
    p = OUT / "bidders" / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def make_cover_letter(bidder_dir: Path, bidder: dict) -> Path:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer
    out = bidder_dir / "01_cover_letter.pdf"
    doc = _new_doc(out)
    s = _styles()
    flow = [
        Paragraph(bidder["company_name"].upper(), s["title"]),
        Paragraph(bidder["address"], s["small"]),
        Paragraph(f"Phone: {bidder['phone']} · Email: {bidder['email']}", s["small"]),
        Spacer(1, 0.5 * cm),
        Paragraph(f"Date: {bidder['letter_date']}", s["right"]),
        Spacer(1, 0.4 * cm),
        Paragraph("To,", s["body"]),
        Paragraph("The Procurement Officer", s["body"]),
        Paragraph("Central Reserve Police Force", s["body"]),
        Paragraph("Block-1, CGO Complex, New Delhi", s["body"]),
        Spacer(1, 0.3 * cm),
        Paragraph(
            "<b>Subject:</b> Submission of Technical and Financial Bid against Tender "
            "No. CRPF/PROC/2026/PV-15-A for Supply of Armoured Patrol Vehicles.",
            s["body"]),
        Spacer(1, 0.3 * cm),
        Paragraph("Sir,", s["body"]),
        Paragraph(
            f"With reference to your above tender notice, we, M/s {bidder['company_name']}, "
            f"having our registered office at {bidder['address']}, hereby submit our technical "
            f"and financial bid as per the requirements set forth therein.",
            s["body"]),
        Paragraph(
            "We confirm that we have read and understood all terms and conditions of the tender "
            "and the corrigendum (if any) issued therewith. The bid is valid for a period of 90 "
            "days from the date of bid opening.",
            s["body"]),
        Paragraph(
            f"Our PAN: <b>{bidder['pan']}</b> · GSTIN: <b>{bidder['gstin']}</b>"
            + (f" · Udyam: <b>{bidder['udyam']}</b>" if bidder.get("udyam") else ""),
            s["body"]),
        Spacer(1, 0.5 * cm),
        Paragraph("Yours faithfully,", s["body"]),
        Spacer(1, 0.6 * cm),
        Paragraph(f"For {bidder['company_name']}", s["body"]),
        Paragraph(f"({bidder['signatory']})", s["body"]),
        Paragraph(bidder['signatory_title'], s["body"]),
    ]
    doc.build(flow)
    return out


def make_turnover_cert(bidder_dir: Path, bidder: dict, fy_amounts: dict) -> Path:
    """CA-certified turnover statement (typed PDF)."""
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer
    out = bidder_dir / "02_turnover_certificate_ca.pdf"
    doc = _new_doc(out)
    s = _styles()
    flow = [
        Paragraph(bidder["ca_firm"], s["title"]),
        Paragraph("CHARTERED ACCOUNTANTS", s["small"]),
        Paragraph(bidder["ca_address"], s["small"]),
        Paragraph(f"Firm Reg. No.: {bidder['ca_frn']}", s["small"]),
        Spacer(1, 0.5 * cm),
        Paragraph("CERTIFICATE OF ANNUAL TURNOVER", s["title"]),
        Spacer(1, 0.5 * cm),
        Paragraph(
            f"This is to certify that M/s <b>{bidder['company_name']}</b>, having its registered "
            f"office at {bidder['address']} and PAN <b>{bidder['pan']}</b>, has reported the "
            f"following <b>annual turnover (standalone)</b> for the last three financial years, "
            f"as per the audited financial statements of the company:",
            s["body"]),
        Spacer(1, 0.3 * cm),
        _table([
            ["Financial Year", "Annual Turnover (INR)", "Annual Turnover (in words)"],
            ["FY 2022-23",
             f"Rs. {fy_amounts['2022-23']:,}",
             _amount_in_words(fy_amounts['2022-23'])],
            ["FY 2023-24",
             f"Rs. {fy_amounts['2023-24']:,}",
             _amount_in_words(fy_amounts['2023-24'])],
            ["FY 2024-25",
             f"Rs. {fy_amounts['2024-25']:,}",
             _amount_in_words(fy_amounts['2024-25'])],
        ], col_widths_cm=[3.5, 5, 8]),
        Spacer(1, 0.4 * cm),
        Paragraph(
            "The above figures have been extracted from the audited annual reports of the "
            "company prepared in accordance with applicable Indian Accounting Standards (Ind AS) "
            "and the Companies Act, 2013. The certificate is issued for the specific purpose of "
            "submission to the Central Reserve Police Force in connection with Tender No. "
            "CRPF/PROC/2026/PV-15-A.",
            s["body"]),
        Spacer(1, 0.6 * cm),
        Paragraph(f"Place: {bidder['ca_place']}", s["body"]),
        Paragraph(f"Date: {bidder['letter_date']}", s["body"]),
        Spacer(1, 0.6 * cm),
        Paragraph(f"For <b>{bidder['ca_firm']}</b>", s["body"]),
        Paragraph("Chartered Accountants", s["body"]),
        Paragraph(f"({bidder['ca_partner']})", s["body"]),
        Paragraph(f"Partner — Membership No. {bidder['ca_membership']}", s["body"]),
        Paragraph(f"UDIN: {bidder['ca_udin']}", s["body"]),
    ]
    doc.build(flow)
    return out


def make_gst_cert(bidder_dir: Path, bidder: dict, valid_until: str) -> Path:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer
    out = bidder_dir / "03_gst_certificate.pdf"
    doc = _new_doc(out)
    s = _styles()
    flow = [
        Paragraph("GOVERNMENT OF INDIA", s["title"]),
        Paragraph("GOODS AND SERVICES TAX REGISTRATION CERTIFICATE", s["title"]),
        Paragraph("Form GST REG-06 [See Rule 10(1)]", s["small"]),
        Spacer(1, 0.5 * cm),
        _table([
            ["Registration Number (GSTIN)", bidder['gstin']],
            ["Legal Name", bidder['company_name']],
            ["Trade Name", bidder.get('trade_name', bidder['company_name'])],
            ["Constitution of Business", "Private Limited Company"],
            ["Address of Principal Place of Business", bidder['address']],
            ["Date of Liability", "01/07/2017"],
            ["Date of Validity", f"From 01/07/2017 to {valid_until}"],
            ["Type of Registration", "Regular"],
            ["PAN", bidder['pan']],
        ], col_widths_cm=[6, 10], header=False),
        Spacer(1, 0.5 * cm),
        Paragraph("Issued by: GST Common Portal, gst.gov.in", s["small"]),
        Paragraph(f"Issued on: {bidder['letter_date']}", s["small"]),
        Spacer(1, 0.4 * cm),
        Paragraph(
            "This is a system-generated certificate. Verify at https://services.gst.gov.in/services/searchtp "
            "using GSTIN.",
            s["small"]),
    ]
    doc.build(flow)
    return out


def make_pan_card(bidder_dir: Path, bidder: dict) -> Path:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer
    out = bidder_dir / "04_pan_card.pdf"
    doc = _new_doc(out)
    s = _styles()
    flow = [
        Paragraph("INCOME TAX DEPARTMENT", s["title"]),
        Paragraph("Government of India", s["title"]),
        Paragraph("PERMANENT ACCOUNT NUMBER (PAN) CARD", s["h"]),
        Spacer(1, 0.4 * cm),
        _table([
            ["Permanent Account Number (PAN)", bidder['pan']],
            ["Name", bidder['company_name']],
            ["Date of Incorporation / Formation", bidder['incorp_date']],
            ["Status", "Company"],
        ], col_widths_cm=[6, 10], header=False),
        Spacer(1, 0.5 * cm),
        Paragraph(
            "This card is issued by the Income Tax Department under Section 139A of the "
            "Income-tax Act, 1961.",
            s["small"]),
    ]
    doc.build(flow)
    return out


def make_iso_cert(bidder_dir: Path, bidder: dict, accreditor: str = "NABCB") -> Path:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer
    out = bidder_dir / "05_iso_9001_certificate.pdf"
    doc = _new_doc(out)
    s = _styles()
    flow = [
        Paragraph(bidder["iso_body"], s["title"]),
        Paragraph(f"Accredited by: {accreditor}", s["small"]),
        Spacer(1, 0.5 * cm),
        Paragraph("CERTIFICATE OF REGISTRATION", s["title"]),
        Paragraph("ISO 9001:2015 — Quality Management System", s["h"]),
        Spacer(1, 0.4 * cm),
        Paragraph(
            f"This is to certify that the Quality Management System of "
            f"<b>{bidder['company_name']}</b>, located at {bidder['address']}, has been assessed "
            f"and is in compliance with the requirements of <b>ISO 9001:2015</b> for the scope:",
            s["body"]),
        Spacer(1, 0.2 * cm),
        Paragraph(
            "<i>Design, manufacture and supply of armoured vehicles and security equipment "
            "for defence and paramilitary applications.</i>",
            s["body"]),
        Spacer(1, 0.4 * cm),
        _table([
            ["Certificate No.", bidder['iso_cert_no']],
            ["Date of Issue", bidder['iso_issue_date']],
            ["Date of Expiry", bidder['iso_expiry_date']],
            ["Accreditation", accreditor],
        ], col_widths_cm=[5, 11], header=False),
    ]
    doc.build(flow)
    return out


def make_completion_certs(bidder_dir: Path, bidder: dict, projects: list[dict]) -> Path:
    """Compile project completion certificates as one multi-section PDF."""
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, Paragraph, Spacer
    out = bidder_dir / "06_completion_certificates.pdf"
    doc = _new_doc(out)
    s = _styles()
    flow = [
        Paragraph(f"{bidder['company_name']}", s["title"]),
        Paragraph("Past Performance — Project Completion Certificates", s["h"]),
        Spacer(1, 0.3 * cm),
        Paragraph(
            f"M/s {bidder['company_name']} has successfully completed the following supply orders "
            f"of similar nature in the last 5 (five) financial years. Completion certificates "
            f"issued by the respective ordering authorities are reproduced verbatim below:",
            s["body"]),
        Spacer(1, 0.4 * cm),
    ]
    for i, p in enumerate(projects, start=1):
        flow.append(Paragraph(f"Project {i} — {p['title']}", s["h"]))
        flow.append(_table([
            ["Ordering authority", p['authority']],
            ["Order reference", p['order_ref']],
            ["Order date", p['order_date']],
            ["Completion date", p['completion_date']],
            ["Order value", f"Rs. {p['value']:,}"],
            ["Quantity", p['quantity']],
        ], col_widths_cm=[5, 11], header=False))
        flow.append(Spacer(1, 0.2 * cm))
        flow.append(Paragraph(
            f"<i>\"This is to certify that M/s {bidder['company_name']} has supplied "
            f"{p['quantity']} {p['title'].lower()} to {p['authority']} as per the said order, "
            f"and the supply has been completed satisfactorily on {p['completion_date']} "
            f"in accordance with the specifications.\"</i>",
            s["body"]))
        flow.append(Paragraph(f"(Sd/-) {p['issuer_name']}, {p['issuer_title']}", s["right"]))
        flow.append(Spacer(1, 0.4 * cm))
        if i < len(projects):
            flow.append(PageBreak())
    doc.build(flow)
    return out


def make_udyam(bidder_dir: Path, bidder: dict) -> Path:
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer
    out = bidder_dir / "07_udyam_msme.pdf"
    doc = _new_doc(out)
    s = _styles()
    flow = [
        Paragraph("Government of India", s["title"]),
        Paragraph("Ministry of Micro, Small and Medium Enterprises", s["title"]),
        Paragraph("UDYAM REGISTRATION CERTIFICATE", s["h"]),
        Spacer(1, 0.4 * cm),
        _table([
            ["Udyam Registration Number", bidder['udyam']],
            ["Name of Enterprise", bidder['company_name']],
            ["Type of Enterprise", "Medium"],
            ["Date of Registration", "12/04/2021"],
            ["Major Activity", "Manufacturing — armoured vehicles"],
            ["NIC code", "29104 — Manufacture of motor vehicles"],
        ], col_widths_cm=[6, 10], header=False),
    ]
    doc.build(flow)
    return out


# ─── Scanned/photographed CA certificate (Charlie's case) ────────────


def make_scanned_turnover_cert(bidder_dir: Path, bidder: dict, fy_amounts: dict) -> Path:
    """A turnover certificate as a JPG that looks like a phone photo:
    rotated, JPEG-compressed, with a rubber stamp partly over the figure."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
    out = bidder_dir / "02_turnover_certificate_scan.jpg"

    W, H = 1700, 2400
    canvas = Image.new("RGB", (W, H), color=(252, 250, 240))  # cream paper
    draw = ImageDraw.Draw(canvas)

    # Try to load a serifed system font, fall back to default
    try:
        big = ImageFont.truetype("/System/Library/Fonts/Supplemental/Times New Roman.ttf", 56)
        med = ImageFont.truetype("/System/Library/Fonts/Supplemental/Times New Roman.ttf", 36)
        smol = ImageFont.truetype("/System/Library/Fonts/Supplemental/Times New Roman.ttf", 28)
    except Exception:
        big = med = smol = ImageFont.load_default()

    y = 120
    draw.text((W // 2 - 380, y), bidder["ca_firm"], font=big, fill=(20, 30, 60))
    y += 90
    draw.text((W // 2 - 240, y), "Chartered Accountants", font=med, fill=(60, 60, 60))
    y += 60
    draw.text((W // 2 - 360, y), bidder["ca_address"], font=smol, fill=(60, 60, 60))
    y += 50
    draw.text((W // 2 - 200, y), f"FRN: {bidder['ca_frn']}", font=smol, fill=(60, 60, 60))

    y += 130
    draw.text((W // 2 - 420, y), "CERTIFICATE OF ANNUAL TURNOVER", font=big, fill=(15, 25, 50))

    y += 130
    body = (
        f"This is to certify that M/s {bidder['company_name']}, having its registered\n"
        f"office at {bidder['address']}, with PAN {bidder['pan']}, has reported the\n"
        "following annual turnover for the last three financial years as per the\n"
        "audited standalone financial statements:"
    )
    draw.multiline_text((140, y), body, font=med, fill=(20, 20, 20), spacing=12)
    y += 240

    # Turnover table
    rows = [
        ("FY 2022-23", f"Rs. {fy_amounts['2022-23']:,}"),
        ("FY 2023-24", f"Rs. {fy_amounts['2023-24']:,}"),
        ("FY 2024-25", f"Rs. {fy_amounts['2024-25']:,}"),
    ]
    for label, amt in rows:
        draw.line([(140, y + 50), (W - 140, y + 50)], fill=(120, 120, 120), width=1)
        draw.text((180, y), label, font=med, fill=(20, 20, 20))
        draw.text((900, y), amt, font=med, fill=(20, 20, 20))
        y += 90
    draw.line([(140, y), (W - 140, y)], fill=(120, 120, 120), width=1)

    y += 100
    draw.multiline_text(
        (140, y),
        "Issued for submission to Central Reserve Police Force\n"
        "in connection with Tender No. CRPF/PROC/2026/PV-15-A.",
        font=smol, fill=(40, 40, 40), spacing=8,
    )

    y += 160
    draw.text((W - 600, y), f"For {bidder['ca_firm']}", font=smol, fill=(20, 20, 20))
    y += 50
    draw.text((W - 600, y), f"({bidder['ca_partner']})", font=smol, fill=(20, 20, 20))
    y += 50
    draw.text((W - 600, y), f"Partner — M.No. {bidder['ca_membership']}", font=smol, fill=(20, 20, 20))
    y += 50
    draw.text((W - 600, y), f"UDIN: {bidder['ca_udin']}", font=smol, fill=(20, 20, 20))

    # Rubber stamp partially over the FY 2024-25 figure
    stamp = Image.new("RGBA", (480, 480), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stamp)
    sd.ellipse((10, 10, 470, 470), outline=(180, 30, 30), width=8)
    sd.ellipse((50, 50, 430, 430), outline=(180, 30, 30), width=4)
    sd.text((130, 140), bidder["ca_firm"][:12].upper(), font=med, fill=(180, 30, 30))
    sd.text((150, 220), "CHARTERED", font=smol, fill=(180, 30, 30))
    sd.text((140, 260), "ACCOUNTANTS", font=smol, fill=(180, 30, 30))
    sd.text((175, 320), "* INDIA *", font=smol, fill=(180, 30, 30))
    stamp = stamp.rotate(-15, resample=Image.BICUBIC, expand=True)
    canvas.paste(stamp, (820, 1170), stamp)

    # Wavy hand-signed line under "Partner"
    sig_y = 2050
    pts = []
    import math
    for i in range(0, 360, 8):
        x = W - 580 + i
        y2 = sig_y + int(20 * math.sin(i / 28.0)) + int(8 * math.sin(i / 7.0))
        pts.append((x, y2))
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=(20, 20, 80), width=3)

    # Slightly tilt the whole page (3°) and add JPEG noise
    canvas = canvas.rotate(3, resample=Image.BICUBIC, fillcolor=(240, 238, 228), expand=True)

    # Soft blur to mimic phone-camera focus drop
    canvas = canvas.filter(ImageFilter.GaussianBlur(radius=0.6))

    # JPEG quality 78
    canvas.save(out, "JPEG", quality=78, optimize=True)
    return out


# ─── Helpers ─────────────────────────────────────────────────────────


def _amount_in_words(rupees: int) -> str:
    """Approximate Indian-format amount in words (rupees)."""
    crore = rupees // 10_000_000
    lakh = (rupees % 10_000_000) // 100_000
    if crore == 0 and lakh == 0:
        return f"Rupees {rupees}"
    parts = []
    if crore:
        parts.append(f"{crore} Crore")
    if lakh:
        parts.append(f"{lakh} Lakh")
    return f"Rupees {' '.join(parts)} only"


# ─── Bidder registries ──────────────────────────────────────────────


def acme() -> dict:
    return {
        "company_name": "Acme Defence Manufacturing Pvt Ltd",
        "address": "Plot 42, Sector 18, Industrial Area, Gurugram, Haryana 122015",
        "phone": "+91 124 4040501",
        "email": "tenders@acmedefence.in",
        "letter_date": "20 April 2026",
        "pan": "AAACA1234B",
        "gstin": "06AAACA1234B1Z5",
        "udyam": "UDYAM-HR-05-0001234",
        "trade_name": "Acme Defence",
        "incorp_date": "15 June 2009",
        "signatory": "Vikram Mehta",
        "signatory_title": "Director (Sales)",
        "ca_firm": "M/s Khanna & Associates",
        "ca_address": "12, Ansal Bhawan, Connaught Place, New Delhi 110001",
        "ca_frn": "012345N",
        "ca_partner": "CA Sandeep Khanna",
        "ca_membership": "098765",
        "ca_udin": "26098765BJKLMN1234",
        "ca_place": "New Delhi",
        "iso_body": "Bureau Veritas (India) Pvt Ltd",
        "iso_cert_no": "IND.QMS.4521-9001-2024",
        "iso_issue_date": "10 January 2024",
        "iso_expiry_date": "09 January 2027",
    }


def bravo() -> dict:
    return {
        "company_name": "Bravo Industries Ltd",
        "address": "Plot 42, Sector 18, Industrial Area, Gurugram, Haryana 122015",  # SHARED w/ Acme — collision!
        "phone": "+91 124 4040502",
        "email": "bid@bravoindustries.in",
        "letter_date": "20 April 2026",
        "pan": "BBBCB2345C",
        "gstin": "06BBBCB2345C1Z3",
        "trade_name": "Bravo Industries",
        "incorp_date": "02 February 2014",
        "signatory": "Asha Pillai",
        "signatory_title": "General Manager",
        "ca_firm": "M/s Verma & Co.",
        "ca_address": "8B, Civil Lines, New Delhi 110054",
        "ca_frn": "022134N",
        "ca_partner": "CA Mahesh Verma",
        "ca_membership": "111122",
        "ca_udin": "26111122ABCDEF5678",
        "ca_place": "New Delhi",
        "iso_body": "QualityCert Solutions",  # NON-NABCB — should fail Clause 4.4
        "iso_cert_no": "QCS-9001-22-1188",
        "iso_issue_date": "12 March 2022",
        "iso_expiry_date": "11 March 2025",  # EXPIRED
    }


def charlie() -> dict:
    return {
        "company_name": "Charlie Auto Components",
        "address": "12 MG Road, Bengaluru, Karnataka 560001",
        "phone": "+91 80 22220900",
        "email": "tenders@charlieauto.in",
        "letter_date": "21 April 2026",
        "pan": "CCCAC3456D",
        "gstin": "29CCCAC3456D1Z8",
        "udyam": "UDYAM-KA-03-0009912",
        "trade_name": "Charlie Auto",
        "incorp_date": "20 May 2017",
        "signatory": "Ramesh Iyer",
        "signatory_title": "Managing Director",
        "ca_firm": "M/s Hegde & Rao",
        "ca_address": "21, Brigade Road, Bengaluru 560025",
        "ca_frn": "030099S",
        "ca_partner": "CA Nivedita Hegde",
        "ca_membership": "077733",
        "ca_udin": "26077733GHIJKL9012",
        "ca_place": "Bengaluru",
        "iso_body": "—",
        "iso_cert_no": "—",
        "iso_issue_date": "—",
        "iso_expiry_date": "—",
    }


def acme_projects() -> list[dict]:
    return [
        {
            "title": "Armoured Patrol Vehicles (12 nos.)",
            "authority": "Border Security Force, Ministry of Home Affairs",
            "order_ref": "BSF/PROC/2024/AV-44", "order_date": "10 March 2024",
            "completion_date": "22 November 2024", "value": 18_50_00_000, "quantity": "12 vehicles",
            "issuer_name": "Comdt. R. Singh", "issuer_title": "Commandant, BSF Procurement",
        },
        {
            "title": "MRAP Vehicles (6 nos.)",
            "authority": "Indo-Tibetan Border Police",
            "order_ref": "ITBP/CAP/2023/MR-19", "order_date": "12 July 2023",
            "completion_date": "30 January 2024", "value": 12_00_00_000, "quantity": "6 vehicles",
            "issuer_name": "DIG K. Mahanta", "issuer_title": "DIG Logistics, ITBP",
        },
        {
            "title": "Bullet-Proof Light Vehicles (15 nos.)",
            "authority": "Sashastra Seema Bal",
            "order_ref": "SSB/MV/2023/BP-08", "order_date": "01 March 2023",
            "completion_date": "08 December 2023", "value": 9_75_00_000, "quantity": "15 vehicles",
            "issuer_name": "AC J. Tirkey", "issuer_title": "Asst. Commandant, SSB",
        },
        {
            "title": "Specialised Convoy Vehicles (10 nos.)",
            "authority": "Central Industrial Security Force",
            "order_ref": "CISF/PR/2022/CV-12", "order_date": "15 May 2022",
            "completion_date": "30 December 2022", "value": 7_60_00_000, "quantity": "10 vehicles",
            "issuer_name": "DC N. Kumari", "issuer_title": "Deputy Commandant, CISF",
        },
    ]


def bravo_projects() -> list[dict]:
    # Only TWO projects → fails Clause 4.3
    return [
        {
            "title": "Light Armoured Vehicles (4 nos.)",
            "authority": "Delhi Police",
            "order_ref": "DP/MT/2023/LAV-21", "order_date": "10 January 2023",
            "completion_date": "15 August 2023", "value": 3_25_00_000, "quantity": "4 vehicles",
            "issuer_name": "Insp. P. Saxena", "issuer_title": "Inspector, MT Branch",
        },
        {
            "title": "Convoy Support Vehicles (3 nos.)",
            "authority": "Haryana Police",
            "order_ref": "HP/PR/2022/CSV-04", "order_date": "08 February 2022",
            "completion_date": "30 September 2022", "value": 2_10_00_000, "quantity": "3 vehicles",
            "issuer_name": "ASP M. Gulati", "issuer_title": "Asst. Superintendent",
        },
    ]


def charlie_projects() -> list[dict]:
    # 3 projects, each ≥ Rs 3 Cr, in last 5 yrs — would PASS but turnover scan is degraded
    return [
        {
            "title": "Armoured Auto Components (Lot 22)",
            "authority": "Karnataka State Reserve Police",
            "order_ref": "KSRP/PR/2024/AC-06", "order_date": "12 May 2024",
            "completion_date": "28 December 2024", "value": 4_75_00_000, "quantity": "Lot 22 (assorted)",
            "issuer_name": "DSP H. Naidu", "issuer_title": "DSP (Stores)",
        },
        {
            "title": "Light Armoured Modules (Phase II)",
            "authority": "Tamil Nadu Special Task Force",
            "order_ref": "TNSTF/MV/2023/LAM-15", "order_date": "01 August 2023",
            "completion_date": "20 March 2024", "value": 5_20_00_000, "quantity": "12 modules",
            "issuer_name": "SP V. Ramesh", "issuer_title": "Superintendent of Police",
        },
        {
            "title": "Vehicle Armour Kits (Set of 8)",
            "authority": "Andhra Pradesh Police HQ",
            "order_ref": "APP/HQ/2022/VAK-09", "order_date": "20 November 2022",
            "completion_date": "10 July 2023", "value": 3_45_00_000, "quantity": "8 kits",
            "issuer_name": "AC L. Reddy", "issuer_title": "Asst. Commandant",
        },
    ]


# ─── Driver ──────────────────────────────────────────────────────────


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Writing realistic demo docs to: {OUT}")

    nit = make_nit()
    print(f"  ✓ NIT: {nit.relative_to(DEMO_DIR)}")

    corr = make_corrigendum()
    print(f"  ✓ corrigendum: {corr.relative_to(DEMO_DIR)}")

    # ── Acme — fully qualified, well above thresholds
    a = acme()
    ad = _bidder_dir("acme")
    a_amounts = {"2022-23": 14_50_00_000, "2023-24": 16_20_00_000, "2024-25": 18_45_00_000}
    make_cover_letter(ad, a)
    make_turnover_cert(ad, a, a_amounts)
    make_gst_cert(ad, a, valid_until="31/03/2027")
    make_pan_card(ad, a)
    make_iso_cert(ad, a, accreditor="NABCB")
    make_completion_certs(ad, a, acme_projects())
    make_udyam(ad, a)
    print(f"  ✓ Acme bidder pack ({len(list(ad.iterdir()))} files)")

    # ── Bravo — multiple FAILs
    b = bravo()
    bd = _bidder_dir("bravo")
    b_amounts = {"2022-23": 8_20_00_000, "2023-24": 9_10_00_000, "2024-25": 11_50_00_000}  # below ₹15 Cr threshold
    make_cover_letter(bd, b)
    make_turnover_cert(bd, b, b_amounts)
    make_gst_cert(bd, b, valid_until="14/12/2024")  # EXPIRED
    make_pan_card(bd, b)
    make_iso_cert(bd, b, accreditor="(unaccredited self-issued)")
    make_completion_certs(bd, b, bravo_projects())
    print(f"  ✓ Bravo bidder pack ({len(list(bd.iterdir()))} files)")

    # ── Charlie — borderline; turnover comes as a phone photo
    c = charlie()
    cd = _bidder_dir("charlie")
    c_amounts = {"2022-23": 12_80_00_000, "2023-24": 14_60_00_000, "2024-25": 16_20_00_000}
    make_cover_letter(cd, c)
    make_scanned_turnover_cert(cd, c, c_amounts)  # phone photo
    make_gst_cert(cd, c, valid_until="30/06/2027")
    make_pan_card(cd, c)
    make_completion_certs(cd, c, charlie_projects())
    print(f"  ✓ Charlie bidder pack ({len(list(cd.iterdir()))} files)")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
