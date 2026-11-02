"""
Richer fake documents for the demo video (all fictional):
  1. demo_docs/medsupply_invoice_2pages.pdf  - 2-page invoice, 24 line items, totals on page 2
  2. demo_docs/scanned_invoice.pdf           - invoice that was "scanned" (image-only PDF, tilted, noisy)
  3. demo_docs/purchase_order_grid.pdf       - grid-table layout, different labels
  4. demo_docs/medical_patient_statement.pdf - workers' comp patient statement: patient, provider, date of injury, claim #, DOS, CPT
  5. demo_docs/hospital_itemized_bill_scanned.pdf - scanned hospital itemized bill
Run:  python make_demo_docs.py
"""

import io
import os
import random

import pymupdf
from PIL import Image, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

OUT = os.path.join(os.path.dirname(__file__), "demo_docs")
os.makedirs(OUT, exist_ok=True)
W, H = A4


def money(x):
    return f"{x:,.2f}"


# ---------------------------------------------------------------- 1. two-page invoice
MED_ITEMS = [
    ("Nitrile exam gloves, M (box of 100)", 40, 8.95),
    ("Nitrile exam gloves, L (box of 100)", 35, 8.95),
    ("Surgical face masks, 3-ply (box of 50)", 60, 6.40),
    ("Alcohol prep pads (box of 200)", 25, 4.75),
    ("Sterile gauze pads 4x4 (pack of 25)", 48, 3.20),
    ("Adhesive bandages, assorted (box of 100)", 30, 5.60),
    ("Disposable syringes 5 ml (box of 100)", 12, 14.90),
    ("Hypodermic needles 23G (box of 100)", 12, 11.25),
    ("Digital thermometer, oral", 10, 18.50),
    ("Blood pressure cuff, adult", 6, 42.00),
    ("Pulse oximeter, fingertip", 8, 29.99),
    ("Hand sanitizer 500 ml", 36, 5.25),
    ("Exam table paper roll, 21 in", 20, 9.80),
    ("Cotton tipped applicators (pack of 1000)", 10, 7.45),
    ("Tongue depressors (box of 500)", 8, 6.90),
    ("Sharps container 2 qt", 15, 4.60),
    ("Specimen cups 4 oz (case of 100)", 5, 21.00),
    ("Elastic bandage 3 in", 24, 2.35),
    ("Cold packs, instant (case of 24)", 4, 28.80),
    ("Disinfectant wipes (canister of 160)", 30, 7.95),
    ("Patient gowns, disposable (pack of 50)", 6, 34.50),
    ("Ear thermometer probe covers (box of 200)", 7, 12.40),
    ("Medical tape 1 in (box of 12)", 10, 9.10),
    ("Shoe covers, non-slip (box of 100)", 9, 13.75),
]


def medsupply_invoice(path):
    sub = round(sum(q * p for _, q, p in MED_ITEMS), 2)
    tax = round(sub * 0.0725, 2)
    c = canvas.Canvas(path, pagesize=A4)

    def header(page):
        c.setFillColor(colors.HexColor("#0b5c4f"))
        c.rect(0, H - 30 * mm, W, 30 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(18 * mm, H - 17 * mm, "Clearwater Medical Supply Co.")
        c.setFont("Helvetica", 9)
        c.drawString(18 * mm, H - 24 * mm, "1450 Commerce Pkwy, Suite 200, Tampa, FL 33610  |  orders@clearwater-med.example  |  (813) 555-0142")
        c.drawRightString(W - 18 * mm, H - 17 * mm, f"Page {page} of 2")
        c.setFillColor(colors.black)

    def items_table(rows, y_top):
        data = [["#", "Item description", "Qty", "Unit price", "Amount"]] + rows
        t = Table(data, colWidths=[10 * mm, 95 * mm, 15 * mm, 25 * mm, 28 * mm])
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6f2ef")),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#bbbbbb")),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        _, h = t.wrap(0, 0)
        t.drawOn(c, 18 * mm, y_top - h)
        return y_top - h

    def row(i, d, q, p):
        return [str(i), d, str(q), money(p), money(q * p)]

    # page 1
    header(1)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(18 * mm, H - 44 * mm, "INVOICE")
    c.setFont("Helvetica", 10)
    info = [("Invoice #:", "CMS-INV-20931"), ("Invoice date:", "09/28/2026"),
            ("Due date:", "10/28/2026"), ("PO number:", "PO-7781"), ("Terms:", "Net 30")]
    y = H - 52 * mm
    for k, v in info:
        c.drawString(18 * mm, y, k); c.drawString(45 * mm, y, v); y -= 5.5 * mm
    c.setFont("Helvetica-Bold", 10); c.drawString(120 * mm, H - 52 * mm, "Bill to:")
    c.setFont("Helvetica", 10)
    for j, line in enumerate(["Riverside Family Health Clinic", "Attn: Accounts Payable",
                              "300 Riverside Dr", "Orlando, FL 32801"]):
        c.drawString(120 * mm, H - (57.5 + 5.5 * j) * mm, line)
    split = 14
    items_table([row(i + 1, *it) for i, it in enumerate(MED_ITEMS[:split])], H - 86 * mm)
    c.setFont("Helvetica-Oblique", 9)
    c.drawRightString(W - 18 * mm, 20 * mm, "Continued on next page")
    c.showPage()

    # page 2
    header(2)
    c.setFont("Helvetica", 10)
    c.drawString(18 * mm, H - 42 * mm, "Invoice # CMS-INV-20931 (continued)")
    y = items_table([row(i + 1 + split, *it) for i, it in enumerate(MED_ITEMS[split:])], H - 48 * mm)
    y -= 10 * mm
    for label, val, bold in [("Subtotal", sub, False), ("Sales tax (7.25%)", tax, False),
                             ("Total due (USD)", sub + tax, True)]:
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 11)
        c.drawString(120 * mm, y, label); c.drawRightString(W - 18 * mm, y, "$" + money(val))
        y -= 7 * mm
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, 30 * mm, "Please remit payment to: Clearwater Medical Supply Co., Account 4402-118, Routing 063100277")
    c.drawString(18 * mm, 25 * mm, "Questions about this invoice? Contact billing@clearwater-med.example")
    c.save()


# ---------------------------------------------------------------- 2. scanned invoice (image-only PDF)
def scanned_invoice(path):
    items = [("Pallet racking beam 96 in", 20, 48.50), ("Upright frame 42x144 in", 8, 189.00),
             ("Wire deck 42x46 in", 40, 32.75), ("Row spacer 12 in", 16, 6.20),
             ("Anchor bolt kit (box of 50)", 3, 44.00), ("Safety pins (pack of 100)", 2, 18.90),
             ("Installation labor (hours)", 12, 65.00), ("Delivery and freight", 1, 240.00)]
    sub = round(sum(q * p for _, q, p in items), 2)
    tax = round(sub * 0.0825, 2)
    pdf = io.BytesIO()
    c = canvas.Canvas(pdf, pagesize=A4)
    c.setFont("Times-Bold", 20); c.drawString(20 * mm, H - 25 * mm, "IRONGATE WAREHOUSE SYSTEMS")
    c.setFont("Times-Roman", 10)
    c.drawString(20 * mm, H - 31 * mm, "77 Industrial Blvd, Dallas, TX 75247   Tel (214) 555-0199")
    c.setFont("Times-Bold", 14); c.drawRightString(W - 20 * mm, H - 25 * mm, "TAX INVOICE")
    c.setFont("Times-Roman", 11)
    for j, (k, v) in enumerate([("Invoice No.", "IGW-55120"), ("Date", "October 12, 2026"),
                                ("Due", "November 11, 2026")]):
        c.drawString(130 * mm, H - (40 + 6 * j) * mm, f"{k}: {v}")
    c.drawString(20 * mm, H - 40 * mm, "Sold to: Lone Star Distribution LLC")
    c.drawString(20 * mm, H - 46 * mm, "4100 Market Center Dr, Fort Worth, TX 76106")
    y = H - 62 * mm
    c.setFont("Times-Bold", 11)
    c.drawString(20 * mm, y, "Description"); c.drawRightString(125 * mm, y, "Qty")
    c.drawRightString(155 * mm, y, "Rate"); c.drawRightString(190 * mm, y, "Amount")
    c.line(20 * mm, y - 2 * mm, 190 * mm, y - 2 * mm)
    c.setFont("Times-Roman", 11)
    y -= 9 * mm
    for d, q, p in items:
        c.drawString(20 * mm, y, d); c.drawRightString(125 * mm, y, str(q))
        c.drawRightString(155 * mm, y, money(p)); c.drawRightString(190 * mm, y, money(q * p))
        y -= 7 * mm
    c.line(110 * mm, y + 2 * mm, 190 * mm, y + 2 * mm)
    y -= 4 * mm
    for label, val in [("Subtotal", sub), ("Sales Tax 8.25%", tax), ("TOTAL USD", sub + tax)]:
        c.setFont("Times-Bold" if label.startswith("TOTAL") else "Times-Roman", 12)
        c.drawString(120 * mm, y, label); c.drawRightString(190 * mm, y, money(val)); y -= 7 * mm
    c.setFont("Times-Italic", 10)
    c.drawString(20 * mm, 30 * mm, "Thank you for your business. Late payments subject to 1.5% monthly charge.")
    c.save()

    # rasterize -> make it look scanned -> wrap back into an image-only PDF
    doc = pymupdf.open(stream=pdf.getvalue(), filetype="pdf")
    img = Image.open(io.BytesIO(doc[0].get_pixmap(dpi=200).tobytes("png"))).convert("L")
    img = img.rotate(-1.2, expand=False, fillcolor=245).filter(ImageFilter.GaussianBlur(0.7))
    random.seed(3)
    px = img.load()
    for _ in range(img.width * img.height // 80):
        x, y2 = random.randrange(img.width), random.randrange(img.height)
        px[x, y2] = random.choice([150, 190, 225])
    buf = io.BytesIO(); img.save(buf, format="PNG")
    out = pymupdf.open()
    page = out.new_page(width=W, height=H)
    page.insert_image(page.rect, stream=buf.getvalue())
    out.save(path)


# ---------------------------------------------------------------- 3. grid purchase order
def grid_po(path):
    items = [("LAP-14-PRO", "14\" business laptop, 16GB RAM, 512GB SSD", 10, 879.00),
             ("MON-27-QHD", "27\" QHD monitor, height adjustable", 10, 239.00),
             ("DOCK-USBC", "USB-C docking station, dual display", 10, 129.50),
             ("KB-MS-WL", "Wireless keyboard and mouse set", 12, 39.90),
             ("HS-ANC", "Noise-cancelling headset with mic", 12, 74.00),
             ("CBL-HDMI-2M", "HDMI cable 2 m", 20, 6.75),
             ("WARR-3Y", "3-year on-site warranty extension (laptop)", 10, 95.00)]
    sub = round(sum(q * p for _, _, q, p in items), 2)
    vat = round(sub * 0.20, 2)
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont("Helvetica-Bold", 16); c.drawString(18 * mm, H - 22 * mm, "Brightpath IT Solutions Ltd")
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, H - 28 * mm, "Unit 4, Kingsway Business Park, Manchester M19 1BB, United Kingdom  |  VAT Reg. GB 314 7765 21")
    meta = [["Document", "Sales Invoice"], ["Reference", "BP-2026-1187"], ["Issued", "2026-10-19"],
            ["Payment due", "2026-11-18"], ["Customer", "Northfield Accountancy Group"],
            ["Address", "22 Deansgate, Manchester M3 2BW"]]
    t = Table(meta, colWidths=[35 * mm, 100 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                           ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
                           ("FONT", (1, 0), (1, -1), "Helvetica", 9),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0"))]))
    _, h = t.wrap(0, 0); t.drawOn(c, 18 * mm, H - 38 * mm - h)
    data = [["SKU", "Description", "Qty", "Unit (GBP)", "Line total (GBP)"]]
    data += [[s, d, str(q), money(p), money(q * p)] for s, d, q, p in items]
    data += [["", "", "", "Net", money(sub)], ["", "", "", "VAT 20%", money(vat)],
             ["", "", "", "Amount due", money(sub + vat)]]
    t = Table(data, colWidths=[25 * mm, 80 * mm, 12 * mm, 26 * mm, 32 * mm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -4), 0.5, colors.grey),
        ("GRID", (3, -3), (-1, -1), 0.5, colors.grey),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9), ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
        ("FONT", (3, -1), (-1, -1), "Helvetica-Bold", 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
    ]))
    _, h2 = t.wrap(0, 0); t.drawOn(c, 18 * mm, H - 38 * mm - h - 12 * mm - h2)
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, 25 * mm, "Bank: Barclays  |  Sort code 20-45-77  |  Account 60391827  |  Please quote the reference with your payment.")
    c.save()


# ---------------------------------------------------------------- 4. medical patient statement (workers' comp, digital)
def patient_statement(path):
    lines = [("08/18/2026", "99204", "New patient visit, moderate complexity", "S39.012A", 1, 245.00),
             ("08/18/2026", "72100", "X-ray lumbar spine, 2-3 views", "S39.012A", 1, 135.00),
             ("08/25/2026", "97161", "Physical therapy evaluation, low complexity", "S39.012A", 1, 160.00),
             ("08/25/2026", "97110", "Therapeutic exercise, each 15 min", "S39.012A", 2, 48.00),
             ("09/01/2026", "97140", "Manual therapy, each 15 min", "S39.012A", 2, 52.00),
             ("09/01/2026", "97010", "Hot or cold packs therapy", "S39.012A", 1, 18.00),
             ("09/08/2026", "97110", "Therapeutic exercise, each 15 min", "S39.012A", 3, 48.00),
             ("09/15/2026", "99214", "Follow-up visit, established patient", "S39.012A", 1, 175.00),
             ("09/15/2026", "72148", "MRI lumbar spine without contrast", "M51.26", 1, 980.00)]
    total = round(sum(q * p for *_, q, p in lines), 2)
    ins_paid, adj = 1240.00, 395.00
    bal = round(total - ins_paid - adj, 2)
    c = canvas.Canvas(path, pagesize=A4)
    c.setFillColor(colors.HexColor("#1d4ed8")); c.rect(0, H - 4 * mm, W, 4 * mm, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#1e3a8a")); c.setFont("Helvetica-Bold", 17)
    c.drawString(18 * mm, H - 17 * mm, "Lakeview Orthopedic & Spine Center")
    c.setFillColor(colors.black); c.setFont("Helvetica", 9)
    c.drawString(18 * mm, H - 23 * mm, "2200 Lakeview Ave, Suite 310, Columbus, OH 43215  |  Billing: (614) 555-0177  |  Tax ID 31-7788120")
    c.line(18 * mm, H - 27 * mm, W - 18 * mm, H - 27 * mm)
    c.setFont("Helvetica-Bold", 14); c.drawString(18 * mm, H - 38 * mm, "PATIENT STATEMENT - WORKERS' COMPENSATION")
    c.setFont("Helvetica", 10)
    left = [("Statement #:", "LOS-ST-884512"), ("Statement date:", "10/30/2026"), ("Payment due:", "11/29/2026"),
            ("Account #:", "ACCT-00471923"), ("Rendering provider:", "Dr. Priya Raman, MD"), ("Provider NPI:", "1234567893")]
    for j, (k, v) in enumerate(left):
        c.drawString(18 * mm, H - (47 + 5.5 * j) * mm, k); c.drawString(55 * mm, H - (47 + 5.5 * j) * mm, v)
    right = [("Patient:", "Jordan T. Ellison"), ("DOB:", "04/17/1979"), ("Date of injury:", "08/14/2026"),
             ("Claim #:", "WC-2026-0451187"), ("Employer:", "Buckeye Freight Lines"), ("Carrier:", "Summit Mutual Insurance")]
    for j, (k, v) in enumerate(right):
        c.drawString(112 * mm, H - (47 + 5.5 * j) * mm, k); c.drawString(140 * mm, H - (47 + 5.5 * j) * mm, v)
    data = [["DOS", "CPT", "Description", "Dx", "Units", "Charge"]]
    data += [[d, cpt, desc, dx, str(q), money(q * p)] for d, cpt, desc, dx, q, p in lines]
    t = Table(data, colWidths=[24 * mm, 16 * mm, 76 * mm, 20 * mm, 13 * mm, 25 * mm])
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9), ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                           ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#bbbbbb"))]))
    _, h = t.wrap(0, 0); top = H - 87 * mm; t.drawOn(c, 18 * mm, top - h)
    y = top - h - 10 * mm
    for label, val, bold in [("Total charges", total, False), ("Carrier payments", -ins_paid, False),
                             ("Fee schedule adjustments", -adj, False), ("Balance due", bal, True)]:
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 11)
        c.drawString(112 * mm, y, label); c.drawRightString(W - 18 * mm, y, ("-$" if val < 0 else "$") + money(abs(val)))
        y -= 7 * mm
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, 28 * mm, "Diagnosis: S39.012A Strain of muscle of lower back, initial encounter; M51.26 Lumbar disc displacement")
    c.drawString(18 * mm, 23 * mm, "Workers' compensation claim. Please reference the claim number on all correspondence.")
    c.save()


# ---------------------------------------------------------------- 5. hospital itemized bill (scanned)
def hospital_bill_scanned(path):
    items = [("10/09/2026", "0450", "Emergency room visit, level 4", 1, 1240.00),
             ("10/09/2026", "0300", "Lab - CBC with differential", 1, 68.00),
             ("10/09/2026", "0300", "Lab - Basic metabolic panel", 1, 74.00),
             ("10/09/2026", "0320", "X-ray right wrist, 3 views", 1, 290.00),
             ("10/09/2026", "0350", "CT head without contrast", 1, 1850.00),
             ("10/09/2026", "0250", "Pharmacy - Ketorolac 30 mg inj", 1, 42.00),
             ("10/09/2026", "0270", "Splint, forearm, prefabricated", 1, 145.00),
             ("10/10/2026", "0450", "ER re-check, level 2", 1, 380.00),
             ("10/10/2026", "0320", "X-ray right wrist, follow-up", 1, 210.00),
             ("10/10/2026", "0250", "Pharmacy - Ibuprofen 800 mg", 2, 6.50)]
    total = round(sum(q * p for *_, q, p in items), 2)
    pdf = io.BytesIO()
    c = canvas.Canvas(pdf, pagesize=A4)
    c.setFont("Times-Bold", 18); c.drawString(20 * mm, H - 24 * mm, "ST. BRIDGET REGIONAL HOSPITAL")
    c.setFont("Times-Roman", 10)
    c.drawString(20 * mm, H - 30 * mm, "1800 Harbor View Rd, Portland, ME 04101   Patient Accounts (207) 555-0123")
    c.setFont("Times-Bold", 13); c.drawRightString(W - 20 * mm, H - 24 * mm, "ITEMIZED STATEMENT")
    c.setFont("Times-Roman", 11)
    for j, t in enumerate(["Patient: Morgan A. Reyes", "Account No.: SBRH-2026-778104", "Statement date: 10/24/2026",
                           "Attending physician: Dr. Alan Whitfield, DO"]):
        c.drawString(20 * mm, H - (42 + 6 * j) * mm, t)
    for j, t in enumerate(["Date of injury: 10/09/2026", "Claim No.: AMH-WC-339021", "Payer: Atlantic Mutual Health"]):
        c.drawString(120 * mm, H - (42 + 6 * j) * mm, t)
    y = H - 74 * mm
    c.setFont("Times-Bold", 11)
    for x, lbl, right in [(20, "Date", False), (42, "Rev", False), (55, "Description", False),
                          (145, "Qty", True), (167, "Unit", True), (190, "Total", True)]:
        (c.drawRightString if right else c.drawString)(x * mm, y, lbl)
    c.line(20 * mm, y - 2 * mm, 190 * mm, y - 2 * mm)
    c.setFont("Times-Roman", 11); y -= 9 * mm
    for d, rev, desc, q, p in items:
        c.drawString(20 * mm, y, d); c.drawString(42 * mm, y, rev); c.drawString(55 * mm, y, desc)
        c.drawRightString(145 * mm, y, str(q)); c.drawRightString(167 * mm, y, money(p))
        c.drawRightString(190 * mm, y, money(q * p)); y -= 7 * mm
    c.line(120 * mm, y + 2 * mm, 190 * mm, y + 2 * mm); y -= 5 * mm
    c.setFont("Times-Bold", 12)
    c.drawString(120 * mm, y, "TOTAL CHARGES"); c.drawRightString(190 * mm, y, money(total))
    c.setFont("Times-Italic", 10)
    c.drawString(20 * mm, 30 * mm, "This is not a bill. The claim has been submitted to your carrier. Questions? Call Patient Accounts.")
    c.save()
    doc = pymupdf.open(stream=pdf.getvalue(), filetype="pdf")
    img = Image.open(io.BytesIO(doc[0].get_pixmap(dpi=200).tobytes("png"))).convert("L")
    img = img.rotate(0.9, expand=False, fillcolor=245).filter(ImageFilter.GaussianBlur(0.6))
    random.seed(11); px = img.load()
    for _ in range(img.width * img.height // 90):
        x, y2 = random.randrange(img.width), random.randrange(img.height)
        px[x, y2] = random.choice([150, 190, 225])
    buf = io.BytesIO(); img.save(buf, format="PNG")
    out = pymupdf.open(); page = out.new_page(width=W, height=H)
    page.insert_image(page.rect, stream=buf.getvalue()); out.save(path)

if __name__ == "__main__":
    medsupply_invoice(os.path.join(OUT, "medsupply_invoice_2pages.pdf"))
    scanned_invoice(os.path.join(OUT, "scanned_invoice.pdf"))
    grid_po(os.path.join(OUT, "purchase_order_grid.pdf"))
    patient_statement(os.path.join(OUT, "medical_patient_statement.pdf"))
    hospital_bill_scanned(os.path.join(OUT, "hospital_itemized_bill_scanned.pdf"))
    print("Demo documents written to", OUT)


# ---------------------------------------------------------------- 6/7. workers' comp EORs (scanned mail, lockbox header)
from reportlab.lib.pagesizes import letter

LW, LH = letter
BOILER = ("IF YOU DISAGREE WITH THIS DECISION YOU MAY REQUEST A SECOND REVIEW WITHIN 90 DAYS OF SERVICE "
          "OF THIS EXPLANATION OF REVIEW. THE REQUEST MUST STATE THE BASIS FOR THE DISPUTE AND INCLUDE "
          "SUPPORTING DOCUMENTATION. PAYMENT IS BASED ON THE OFFICIAL MEDICAL FEE SCHEDULE. THE EMPLOYEE "
          "IS NOT LIABLE FOR ANY BALANCE ABOVE THE FEE SCHEDULE AMOUNT. THIS NOTICE IS PROVIDED FOR "
          "INFORMATION ONLY AND IS NOT A BILL.")


def _wrap_text(c, text, x, y, width_chars, leading, font=("Courier", 7.5)):
    import textwrap
    c.setFont(*font)
    for line in textwrap.wrap(text, width_chars):
        c.drawString(x, y, line); y -= leading
    return y


def _lockbox_header(c, page_no, batch, seq, source):
    c.setFont("Helvetica-Bold", 13); c.drawString(14 * mm, LH - 14 * mm, "GOLDEN STATE LOCKBOX SERVICES")
    c.setFont("Helvetica", 9)
    c.drawRightString(LW / 2 + 20 * mm, LH - 14 * mm, f"Page: {page_no}")
    c.drawRightString(LW - 14 * mm, LH - 14 * mm, "Date: 10/27/2026")
    rows = [("Processing Date :", "10/27/2026", "Batch Number :", batch, "Transaction No :", str(seq)),
            ("Sequence No :", str(seq * 3), "Paid Amount :", "$0.00", "Site :", "SACRAMENTO CA"),
            ("WorkSource :", source, "", "", "", "")]
    for j, r in enumerate(rows):
        y = LH - (21 + 4.5 * j) * mm
        for k, x in zip(r, (14, 45, 85, 115, 150, 180)):
            c.drawString(x * mm, y, k)
    c.setFont("Helvetica", 10); c.drawCentredString(LW / 2, LH - 37 * mm, "Front Image")
    c.rect(12 * mm, 10 * mm, LW - 24 * mm, LH - 50 * mm)


def _kv(c, x, y, label, value, lead=3.6 * mm):
    c.setFont("Helvetica-Bold", 8); c.drawString(x, y, label)
    c.setFont("Helvetica", 8.5)
    for i, v in enumerate(value.split("\n")):
        c.drawString(x, y - lead * (i + 1), v)
    return y - lead * (len(value.split("\n")) + 1.4)


def _scan_pages(pdf_bytes, path, seed):
    """Rasterize pages, make them look scanned, save as image-only PDF."""
    src = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    out = pymupdf.open()
    for n, pg in enumerate(src):
        img = Image.open(io.BytesIO(pg.get_pixmap(dpi=200).tobytes("png"))).convert("L")
        img = img.rotate(0.6 if n % 2 == 0 else -0.8, expand=False, fillcolor=246).filter(ImageFilter.GaussianBlur(0.55))
        random.seed(seed + n); px = img.load()
        for _ in range(img.width * img.height // 110):
            x, y = random.randrange(img.width), random.randrange(img.height)
            px[x, y] = random.choice([150, 195, 228])
        buf = io.BytesIO(); img.save(buf, format="PNG")
        page = out.new_page(width=LW, height=LH)
        page.insert_image(page.rect, stream=buf.getvalue())
    out.save(path)


def eor(path, d, seed):
    lines = d["lines"]
    billed = round(sum(l[4] for l in lines), 2)
    allowed = round(sum(l[5] for l in lines), 2)
    paid = round(sum(l[6] for l in lines), 2)
    pdf = io.BytesIO()
    c = canvas.Canvas(pdf, pagesize=letter)

    # ---- page 1: summary
    _lockbox_header(c, d["page"], d["batch"], d["seq"], d["provider"].split("\n")[0])
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(LW / 2, LH - 47 * mm, d["title"])
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(LW / 2, LH - 52 * mm, "THIS IS NOT A BILL")
    c.setFont("Helvetica", 8); c.drawRightString(LW - 16 * mm, LH - 47 * mm, "PAGE 1 OF 2")
    c.drawRightString(LW - 16 * mm, LH - 51 * mm, f"DATE {d['eor_date']}")
    L, R = 18 * mm, 118 * mm
    y = LH - 60 * mm
    y = _kv(c, L, y, "CARRIER:", d["carrier"])
    y = _kv(c, L, y, "PROVIDER INQUIRY CONTACT:", d["phone"])
    y = _kv(c, L, y, "EMPLOYER:", d["employer"])
    y = _kv(c, L, y, "PROVIDER:", d["provider"])
    y = _kv(c, L, y, "TAX ID NUMBER / FEIN:", d["fein"])
    y = _kv(c, L, y, "RENDERING PROVIDER:", d["rendering"])
    y = _kv(c, L, y, "PATIENT:", d["patient"])
    yr = LH - 60 * mm
    for lab, val in [("CLAIM NUMBER:", d["claim"]), ("DATE OF INJURY:", d["doi"]),
                     ("BILL CONTROL NUMBER:", d["bcn"]), ("DATE EOR GENERATED:", d["eor_date"]),
                     ("DATE OF BILL:", d["bill_date"]), ("DATE BILL RECEIVED:", d["recv_date"]),
                     ("PATIENT CONTROL NUMBER:", d["pcn"])]:
        yr = _kv(c, R, yr, lab, val)
    y = min(y, yr) - 2 * mm
    c.setFont("Helvetica-Bold", 9); c.drawString(L, y, "SUMMARY INFORMATION"); c.line(L, y - 1.5 * mm, LW - 16 * mm, y - 1.5 * mm)
    y -= 6 * mm
    c.setFont("Courier", 8.5)
    c.drawString(L, y, f"SERVICE DATES: {lines[0][0]} - {lines[-1][0]}"); y -= 6 * mm
    c.drawString(L, y, "   BILLED AMT      ALLOWED AMT      PAID AMT"); y -= 4.5 * mm
    c.drawString(L, y, f"   ${money(billed):>10}     ${money(allowed):>10}     ${money(paid):>10}"); y -= 8 * mm
    c.setFont("Helvetica-Bold", 9); c.drawString(L, y, "STATE REQUIRED INFORMATION"); c.line(L, y - 1.5 * mm, LW - 16 * mm, y - 1.5 * mm)
    y -= 6 * mm
    _wrap_text(c, f"JURISDICTIONAL CLAIM NUMBER: {d['adj']}   BILL PAYMENT STATUS CODE: {d['status']}. " + BOILER,
               L, y, 105, 3.3 * mm)
    c.showPage()

    # ---- page 2: line detail
    _lockbox_header(c, d["page"] + 1, d["batch"], d["seq"], d["provider"].split("\n")[0])
    c.setFont("Helvetica-Bold", 10); c.drawCentredString(LW / 2, LH - 47 * mm, d["title"] + " - DETAIL")
    c.setFont("Helvetica", 8); c.drawRightString(LW - 16 * mm, LH - 47 * mm, "PAGE 2 OF 2")
    c.drawString(18 * mm, LH - 54 * mm, f"CLAIM NUMBER: {d['claim']}    PATIENT: {d['patient'].splitlines()[0]}    BILL CONTROL NUMBER: {d['bcn']}")
    data = [["LN", "DOS", "PROC", "MOD", "UNITS", "BILLED", "ALLOWED", "PAID", "RSN"]]
    for i, (dos, proc, mod, units, b, a, p, rsn) in enumerate(lines, 1):
        data.append([str(i), dos, proc, mod, str(units), money(b), money(a), money(p), rsn])
    data.append(["", "", "", "", "TOTAL", money(billed), money(allowed), money(paid), ""])
    t = Table(data, colWidths=[9 * mm, 22 * mm, 16 * mm, 12 * mm, 14 * mm, 22 * mm, 22 * mm, 22 * mm, 14 * mm])
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5), ("FONT", (0, 1), (-1, -1), "Courier", 8.5),
                           ("FONT", (0, -1), (-1, -1), "Courier-Bold", 8.5),
                           ("ALIGN", (4, 0), (7, -1), "RIGHT"),
                           ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
                           ("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.black)]))
    _, h = t.wrap(0, 0); top = LH - 60 * mm; t.drawOn(c, 18 * mm, top - h)
    y = top - h - 10 * mm
    c.setFont("Helvetica-Bold", 9); c.drawString(18 * mm, y, "REASON CODE EXPLANATIONS"); y -= 5 * mm
    for code, txt in d["reasons"]:
        y = _wrap_text(c, f"{code} - {txt}", 18 * mm, y, 100, 3.4 * mm, ("Courier", 8)) - 1.5 * mm
    c.save()
    _scan_pages(pdf.getvalue(), path, seed)


EOR_A = dict(
    title="EXPLANATION OF REVIEW", page=412, batch="00417733", seq=7, eor_date="10/21/2026",
    carrier="PACIFIC CREST CASUALTY CO\nP O BOX 70412\nFRESNO, CA 93744",
    phone="800-555-0136", employer="SIERRA VALLEY PACKING LLC\n4410 E ASHLAN AVE\nFRESNO, CA 93726",
    provider="REDLANDS SPINE & REHAB MEDICAL GROUP\n1220 ORANGE TREE LN STE 4\nREDLANDS, CA 92374",
    fein="95-4417720", rendering="ELENA MARQUEZ, DC   NPI 1659900812",
    patient="DANIEL R. OKAFOR\n3317 WILLOW CREEK DR\nFRESNO, CA 93722",
    claim="PCC-26-0917744", doi="03/11/2026", bcn="7781004412", bill_date="09/30/2026",
    recv_date="10/06/2026", pcn="RSR-20419", adj="ADJ19004417", status="PARTIALLY PAID",
    lines=[("09/02/2026", "98941", "", 1, 95.00, 61.42, 61.42, "P1"),
           ("09/02/2026", "97140", "GP", 2, 120.00, 58.30, 58.30, "P1"),
           ("09/02/2026", "97110", "GP", 2, 110.00, 61.88, 61.88, "P1"),
           ("09/09/2026", "98941", "", 1, 95.00, 61.42, 61.42, "P1"),
           ("09/09/2026", "97112", "GP", 1, 65.00, 35.16, 35.16, "P1"),
           ("09/16/2026", "98941", "", 1, 95.00, 61.42, 61.42, "P1"),
           ("09/16/2026", "97010", "", 1, 30.00, 0.00, 0.00, "D4"),
           ("09/23/2026", "99213", "25", 1, 150.00, 82.15, 82.15, "P1"),
           ("09/23/2026", "97140", "GP", 2, 120.00, 58.30, 0.00, "D7")],
    reasons=[("P1", "PAID PER THE OFFICIAL MEDICAL FEE SCHEDULE."),
             ("D4", "SERVICE IS BUNDLED INTO ANOTHER PROCEDURE BILLED ON THE SAME DATE. NO SEPARATE PAYMENT."),
             ("D7", "VISIT EXCEEDS THE NUMBER OF AUTHORIZED THERAPY VISITS. REQUEST FOR AUTHORIZATION REQUIRED.")])

EOR_B = dict(
    title="EXPLANATION OF BILL REVIEW", page=96, batch="00417801", seq=22, eor_date="10/14/2026",
    carrier="GOLDEN BAY MUTUAL INSURANCE\nCLAIMS DEPT - P O BOX 33190\nOAKLAND, CA 94604",
    phone="888-555-0174", employer="BAYSIDE FREIGHT & LOGISTICS INC\n900 HARBOR WAY\nRICHMOND, CA 94801",
    provider="EAST BAY ADVANCED IMAGING\n2701 TELEGRAPH AVE\nBERKELEY, CA 94705",
    fein="94-3328105", rendering="SAMUEL CHO, MD (RADIOLOGY)   NPI 1447281935",
    patient="LUCIA FERNANDEZ\n618 SEMINARY AVE\nOAKLAND, CA 94621",
    claim="GBM-WC-55102938", doi="06/27/2026", bcn="5520039917", bill_date="09/22/2026",
    recv_date="09/29/2026", pcn="EBAI-77310", adj="ADJ19107265", status="PAID",
    lines=[("08/19/2026", "73221", "26", 1, 1450.00, 612.40, 612.40, "A1"),
           ("08/19/2026", "73221", "TC", 1, 1950.00, 821.75, 821.75, "A1"),
           ("08/19/2026", "72141", "", 1, 2100.00, 958.20, 958.20, "A1"),
           ("08/26/2026", "76882", "RT", 1, 420.00, 168.33, 168.33, "A1")],
    reasons=[("A1", "ALLOWED PER FEE SCHEDULE AND PAID IN FULL AT THE ALLOWED AMOUNT.")])

if __name__ == "__main__":
    eor(os.path.join(OUT, "wc_eor_chiropractic_scanned.pdf"), EOR_A, seed=21)
    eor(os.path.join(OUT, "wc_eor_imaging_scanned.pdf"), EOR_B, seed=31)
    print("EOR documents written")
