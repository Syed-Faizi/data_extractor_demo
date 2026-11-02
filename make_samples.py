"""
Generates fake sample invoices for the demo (no real data):
  - 2 digital PDFs (different layouts)
  - 1 'scanned' PNG (rotated, noisy, grayscale) to show OCR
Run:  python make_samples.py
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

OUT = os.path.join(os.path.dirname(__file__), "demo_docs")
os.makedirs(OUT, exist_ok=True)
W, H = A4


def table(c, x, y, rows, widths):
    for r, row in enumerate(rows):
        c.setFont("Helvetica-Bold" if r == 0 else "Helvetica", 10)
        cx = x
        for val, w in zip(row, widths):
            c.drawString(cx, y, str(val))
            cx += w
        y -= 7 * mm
    return y


def invoice_a(path):
    """Clean modern layout, USD, with tax."""
    items = [("Website maintenance (Oct)", 1, 450.00),
             ("Cloud hosting - standard plan", 3, 39.00),
             ("SSL certificate renewal", 1, 65.50)]
    sub = sum(q * p for _, q, p in items)
    tax = round(sub * 0.08, 2)
    c = canvas.Canvas(path, pagesize=A4)
    c.setFillColor(colors.HexColor("#1f3a5f"))
    c.rect(0, H - 35 * mm, W, 35 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(20 * mm, H - 20 * mm, "Northwind Web Services LLC")
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, H - 27 * mm, "220 Harbor St, Portland, OR 97201  |  billing@northwind-web.example")
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, H - 50 * mm, "INVOICE")
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, H - 58 * mm, "Invoice No: NW-2026-0418")
    c.drawString(20 * mm, H - 64 * mm, "Invoice Date: October 3, 2026")
    c.drawString(20 * mm, H - 70 * mm, "Due Date: November 2, 2026")
    c.drawString(120 * mm, H - 58 * mm, "Bill To:")
    c.drawString(120 * mm, H - 64 * mm, "Greenleaf Dental Clinic")
    c.drawString(120 * mm, H - 70 * mm, "88 Pine Ave, Salem, OR")
    rows = [("Description", "Qty", "Unit Price", "Amount")]
    rows += [(d, q, f"${p:,.2f}", f"${q * p:,.2f}") for d, q, p in items]
    y = table(c, 20 * mm, H - 90 * mm, rows, [90 * mm, 20 * mm, 30 * mm, 30 * mm])
    y -= 5 * mm
    for label, val in [("Subtotal", sub), ("Sales Tax (8%)", tax), ("TOTAL DUE", sub + tax)]:
        c.setFont("Helvetica-Bold" if label == "TOTAL DUE" else "Helvetica", 11)
        c.drawString(120 * mm, y, label)
        c.drawRightString(190 * mm, y, f"${val:,.2f}")
        y -= 7 * mm
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(20 * mm, 20 * mm, "Payment terms: Net 30. Thank you for your business!")
    c.save()


def invoice_b(path):
    """Plain, different layout, EUR, labels named differently."""
    items = [("Office chairs (ergonomic)", 4, 189.90),
             ("Standing desk frame", 2, 310.00)]
    sub = round(sum(q * p for _, q, p in items), 2)
    vat = round(sub * 0.19, 2)
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(190 * mm, H - 20 * mm, "Bauer Bueroausstattung GmbH")
    c.setFont("Helvetica", 9)
    c.drawRightString(190 * mm, H - 26 * mm, "Lindenstrasse 12, 10969 Berlin, Germany")
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, H - 45 * mm, "Customer: Atlas Logistics Ltd, 5 Quay Road, Dublin")
    c.drawString(20 * mm, H - 55 * mm, "Bill number: RE-77310")
    c.drawString(20 * mm, H - 61 * mm, "Date of issue: 14.10.2026")
    c.drawString(20 * mm, H - 67 * mm, "Payable by: 28.10.2026")
    rows = [("Item", "Units", "Price", "Line total")]
    rows += [(d, q, f"{p:.2f} EUR", f"{q * p:.2f} EUR") for d, q, p in items]
    y = table(c, 20 * mm, H - 85 * mm, rows, [85 * mm, 20 * mm, 35 * mm, 35 * mm])
    y -= 5 * mm
    c.drawString(110 * mm, y, f"Net amount:        {sub:.2f} EUR"); y -= 6 * mm
    c.drawString(110 * mm, y, f"VAT 19%:            {vat:.2f} EUR"); y -= 6 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(110 * mm, y, f"Gross amount:     {sub + vat:.2f} EUR")
    c.save()


def receipt_scan(path):
    """Small store receipt rendered to an image, then made to look scanned."""
    items = [("Printer paper A4 x5", 5, 6.49), ("Ink cartridge black", 2, 24.99),
             ("Stapler", 1, 8.75)]
    sub = round(sum(q * p for _, q, p in items), 2)
    tax = round(sub * 0.0625, 2)
    pdf = io.BytesIO()
    c = canvas.Canvas(pdf, pagesize=(90 * mm, 140 * mm))
    y = 130 * mm
    c.setFont("Courier-Bold", 12); c.drawCentredString(45 * mm, y, "QUICKSTOP OFFICE SUPPLY"); y -= 6 * mm
    c.setFont("Courier", 8); c.drawCentredString(45 * mm, y, "41 Main St, Austin TX"); y -= 8 * mm
    c.setFont("Courier", 9)
    for line in ["Receipt #: 0093-4471", "Date: 10/21/2026  14:32", "-" * 34]:
        c.drawString(6 * mm, y, line); y -= 5 * mm
    for d, q, p in items:
        c.drawString(6 * mm, y, f"{d}"); y -= 4 * mm
        c.drawString(10 * mm, y, f"{q} x {p:.2f}"); c.drawRightString(84 * mm, y, f"{q * p:.2f}"); y -= 6 * mm
    c.drawString(6 * mm, y, "-" * 34); y -= 5 * mm
    for label, val in [("SUBTOTAL", sub), ("TAX 6.25%", tax), ("TOTAL USD", sub + tax)]:
        c.drawString(6 * mm, y, label); c.drawRightString(84 * mm, y, f"{val:.2f}"); y -= 5 * mm
    c.save()

    doc = pymupdf.open(stream=pdf.getvalue(), filetype="pdf")
    img = Image.open(io.BytesIO(doc[0].get_pixmap(dpi=220).tobytes("png"))).convert("L")
    img = img.rotate(1.5, expand=True, fillcolor=255).filter(ImageFilter.GaussianBlur(0.6))
    random.seed(7)
    px = img.load()
    for _ in range(img.width * img.height // 60):  # speckle noise
        x, y2 = random.randrange(img.width), random.randrange(img.height)
        px[x, y2] = random.choice([170, 200, 230])
    img.save(path)


if __name__ == "__main__":
    invoice_a(os.path.join(OUT, "invoice_northwind.pdf"))
    invoice_b(os.path.join(OUT, "invoice_bauer_eur.pdf"))
    receipt_scan(os.path.join(OUT, "receipt_scanned.png"))
    print("Samples written to", OUT)
