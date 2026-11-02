"""
Core pipeline: file -> page images -> table-line removal -> OCR -> LLM -> validated JSON.

Works with the OpenAI API by default. Point OPENAI_BASE_URL at any
OpenAI-compatible server (Ollama, llama.cpp, vLLM) to run fully local.
"""

import io
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
import pymupdf
import pytesseract
from openai import OpenAI
from PIL import Image
from pydantic import BaseModel, ValidationError

# ---------- Settings ----------
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")  # e.g. http://localhost:11434/v1 for Ollama
OCR_DPI = 300
MONEY_TOLERANCE = 0.02  # allowed rounding difference in totals
MAX_PAGES = int(os.getenv("MAX_PAGES", "5"))  # demo limit: only the first N pages are read
MAX_CHARS = 30000  # hard safety cap on text sent to the LLM

if os.getenv("TESSERACT_CMD"):  # Windows users can point to tesseract.exe
    pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")


# ---------- Output schema ----------
class LineItem(BaseModel):
    date_of_service: Optional[str] = None  # YYYY-MM-DD (medical bills)
    code: Optional[str] = None             # CPT / HCPCS / revenue code / SKU
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None         # billed / charged amount
    allowed: Optional[float] = None        # EOR only
    paid: Optional[float] = None           # EOR only
    reason_code: Optional[str] = None      # EOR only


class Invoice(BaseModel):
    document_type: Optional[str] = None  # invoice | receipt | medical_bill | eor
    vendor_name: Optional[str] = None    # company / practice / hospital that issued it
    invoice_number: Optional[str] = None # invoice, statement or account number
    invoice_date: Optional[str] = None   # YYYY-MM-DD
    due_date: Optional[str] = None       # YYYY-MM-DD
    bill_to: Optional[str] = None
    # medical fields (null for normal invoices)
    patient_name: Optional[str] = None
    provider_name: Optional[str] = None  # treating doctor / rendering provider
    date_of_injury: Optional[str] = None # YYYY-MM-DD
    claim_number: Optional[str] = None
    payer_name: Optional[str] = None     # insurance carrier
    employer: Optional[str] = None       # workers' comp employer
    amount_allowed: Optional[float] = None  # EOR only
    amount_paid: Optional[float] = None     # EOR only
    currency: Optional[str] = None
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    line_items: List[LineItem] = []


REQUIRED_FIELDS = ["vendor_name", "invoice_number", "invoice_date", "total"]
REQUIRED_MEDICAL = ["patient_name", "provider_name"]

PROMPT = """You extract data from invoices, receipts, medical bills and workers' compensation
EORs (Explanation of Review / Explanation of Bill Review).

The document text is given page by page. Each page is wrapped like this:
<<PAGE 1 START>>
...text of page 1...
<<PAGE 1 END>>
The markers are NOT part of the document; they only show where each page begins and ends.
The text may come from OCR and contain small errors (e.g. "O" for "0", "1" for "I" in
diagnosis codes like I10); read it carefully.
A document can continue across pages: line items may be split over several pages, and the
totals are usually on the last page. Combine all pages into ONE result and do not
list the same line item twice.

Return ONLY a JSON object with exactly these keys:
document_type ("invoice", "receipt", "medical_bill" or "eor"),
vendor_name (company, practice or hospital that issued the document; for an EOR, the
  billing provider organization, NOT the carrier),
invoice_number (invoice, statement or account number),
invoice_date (invoice or statement date), due_date, bill_to,
patient_name, provider_name (the treating / rendering doctor, not the practice),
date_of_injury, claim_number, payer_name (insurance carrier), employer,
amount_allowed, amount_paid,
currency, subtotal, tax, total,
line_items (list of {date_of_service, code, description, quantity, unit_price, amount,
  allowed, paid, reason_code}).

Rules:
- Use null when a value is not in the document. Never guess or calculate missing values.
- Medical fields (patient_name, provider_name, date_of_injury, claim_number, payer_name,
  employer, date_of_service) are null for normal invoices and receipts.
- For an EOR: invoice_number = bill control number, invoice_date = date the EOR was
  generated, subtotal = total = total billed, amount_allowed = total allowed,
  amount_paid = total paid. Per line: amount = billed, allowed, paid, reason_code.
  In an EOR the BILLED column is already the line total for all units: copy it as
  amount, do NOT multiply it by units, and leave unit_price null.
  The lockbox / bank header at the top of a scanned page (processing date, batch number,
  etc.) is NOT part of the document; ignore it.
- code: CPT / HCPCS / revenue code for medical lines, SKU or item code otherwise.
- For medical bills: subtotal = total charges; total = the amount the patient or payer
  still owes (balance due), if shown, otherwise total charges.
- If unit price is missing but quantity and amount are shown, leave unit_price null.
- IDs (claim, account, statement, bill numbers): remove stray spaces that OCR inserted
  inside them (e.g. "WC-2026-0451 187" -> "WC-2026-0451187").
- Reason codes are short letter+digit codes (P1, D4); OCR may read "1" as "l" (e.g. "Pl"),
  fix that.
- Dates as YYYY-MM-DD.
- Numbers as plain numbers (no currency symbols, no thousands separators).
  Credits and payments shown as negative stay negative.
- currency as a 3-letter code (USD, EUR, PKR...) only if it is shown or clearly implied.

Document ({n_pages} page(s)):
{text}
"""


# ---------- Step 1: get text, page by page ----------
def _remove_table_lines(gray: np.ndarray) -> np.ndarray:
    """Erase long horizontal/vertical lines (table grids) so OCR doesn't break on them.
    Only the line pixels are whitened; the rest of the image is left untouched."""
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    k = max(40, gray.shape[1] // 30)  # a "line" is at least ~1/30 of the page width
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1)))
    vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, k)))
    lines = cv2.dilate(cv2.add(horiz, vert), np.ones((3, 3), np.uint8))
    out = gray.copy()
    out[lines > 0] = 255
    return out


def _ocr_image(img: Image.Image) -> str:
    gray = _remove_table_lines(np.array(img.convert("L")))
    # psm 6 = treat page as one text block; keeps labels and amounts on the same line
    return pytesseract.image_to_string(gray, config="--psm 6")


def _wrap(page_no: int, text: str) -> str:
    return f"<<PAGE {page_no} START>>\n{text.strip()}\n<<PAGE {page_no} END>>"


def get_text(path: str) -> dict:
    """
    PDF -> pages (first MAX_PAGES only) -> text per page (native text, or OCR if scanned)
    -> each page wrapped in <<PAGE n START>> / <<PAGE n END>> -> merged.
    Images are treated as a single page.
    """
    ext = Path(path).suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
        text = _ocr_image(Image.open(path))
        return {"text": _wrap(1, text), "method": "ocr", "pages_used": 1, "pages_total": 1}

    if ext != ".pdf":
        raise ValueError(f"Unsupported file type: {ext}")

    # Every page -> image -> OCR (same path for digital and scanned pages)
    pages = []
    with pymupdf.open(path) as doc:
        total = doc.page_count
        for i in range(min(total, MAX_PAGES)):
            pix = doc[i].get_pixmap(dpi=OCR_DPI)
            text = _ocr_image(Image.open(io.BytesIO(pix.tobytes("png"))))
            pages.append(_wrap(i + 1, text))

    return {"text": "\n\n".join(pages), "method": "ocr",
            "pages_used": len(pages), "pages_total": total}


# ---------- Step 2: LLM extraction ----------
_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        kwargs = {}
        if OPENAI_BASE_URL:
            kwargs["base_url"] = OPENAI_BASE_URL
            kwargs["api_key"] = os.getenv("OPENAI_API_KEY", "local")
        _client = OpenAI(**kwargs)
    return _client


def _parse_json(raw: str) -> dict:
    """Tolerant JSON parsing: strips code fences / reasoning text around the object."""
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model did not return JSON")
    return json.loads(raw[start:end + 1])


def build_prompt(text: str, n_pages: int) -> str:
    return PROMPT.replace("{n_pages}", str(n_pages)).replace("{text}", text[:MAX_CHARS])


def llm_extract(text: str, n_pages: int = 1) -> Invoice:
    resp = _get_client().chat.completions.create(
        model=LLM_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": build_prompt(text, n_pages)}],
    )
    data = _parse_json(resp.choices[0].message.content)
    try:
        return Invoice.model_validate(data)
    except ValidationError:
        # Drop fields the model filled with the wrong type instead of failing the whole doc
        clean = {}
        for key, field in Invoice.model_fields.items():
            if key in data:
                try:
                    Invoice.model_validate({key: data[key]})
                    clean[key] = data[key]
                except ValidationError:
                    pass
        return Invoice.model_validate(clean)


# ---------- Step 3: validation ----------
def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(MONEY_TOLERANCE, abs(b) * 0.001)


def validate(inv: Invoice) -> list[str]:
    issues = []
    for f in REQUIRED_FIELDS:
        if getattr(inv, f) in (None, ""):
            issues.append(f"Missing {f.replace('_', ' ')}")

    for f in ("invoice_date", "due_date"):
        val = getattr(inv, f)
        if val:
            try:
                datetime.strptime(val, "%Y-%m-%d")
            except ValueError:
                issues.append(f"{f.replace('_', ' ').capitalize()} not a valid date: {val}")

    if inv.invoice_date and inv.due_date and inv.due_date < inv.invoice_date:
        issues.append("Due date is before invoice date")

    if inv.document_type in ("medical_bill",):
        for f in REQUIRED_MEDICAL:
            if not getattr(inv, f):
                issues.append(f"Missing {f.replace('_', ' ')}")
        dos = [li.date_of_service for li in inv.line_items if li.date_of_service]
        for d in dos + ([inv.date_of_injury] if inv.date_of_injury else []):
            try:
                datetime.strptime(d, "%Y-%m-%d")
            except ValueError:
                issues.append(f"Not a valid date: {d}")
        if inv.date_of_injury and any(d < inv.date_of_injury for d in dos):
            issues.append("A date of service is before the date of injury")

    if inv.document_type == "eor":
        for f in ["patient_name", "claim_number", "date_of_injury", "payer_name"]:
            if not getattr(inv, f):
                issues.append(f"Missing {f.replace('_', ' ')}")
        dos = [li.date_of_service for li in inv.line_items if li.date_of_service]
        if inv.date_of_injury and any(d < inv.date_of_injury for d in dos):
            issues.append("A date of service is before the date of injury")
        paid = [li.paid for li in inv.line_items if li.paid is not None]
        if paid and inv.amount_paid is not None and not _close(sum(paid), inv.amount_paid):
            issues.append(f"Line payments add up to {sum(paid):.2f}, EOR says paid {inv.amount_paid:.2f}")
        for i, li in enumerate(inv.line_items, 1):
            if None not in (li.paid, li.allowed) and li.paid > li.allowed + MONEY_TOLERANCE:
                issues.append(f"Line {i}: paid more than allowed")

    for i, li in enumerate(inv.line_items, 1):
        if None not in (li.quantity, li.unit_price, li.amount):
            if not _close(li.quantity * li.unit_price, li.amount):
                issues.append(f"Line {i}: qty x price != amount")

    amounts = [li.amount for li in inv.line_items if li.amount is not None]
    if amounts and inv.subtotal is not None and not _close(sum(amounts), inv.subtotal):
        issues.append(f"Line items add up to {sum(amounts):.2f}, subtotal says {inv.subtotal:.2f}")

    if None not in (inv.subtotal, inv.tax, inv.total):
        if not _close(inv.subtotal + inv.tax, inv.total):
            issues.append(f"Subtotal + tax = {inv.subtotal + inv.tax:.2f}, total says {inv.total:.2f}")

    return issues


# ---------- Full pipeline ----------
def process_file(path: str) -> dict:
    doc = get_text(path)
    notes = []
    if doc["pages_total"] > doc["pages_used"]:
        notes.append(f"Demo limit: read first {doc['pages_used']} of {doc['pages_total']} pages")

    body = re.sub(r"<<PAGE \d+ (START|END)>>", "", doc["text"])
    if not body.strip():
        return {"file": Path(path).name, "method": doc["method"], "invoice": None,
                "issues": notes + ["No text found in document"], "raw_text": ""}

    inv = llm_extract(doc["text"], doc["pages_used"])
    return {
        "file": Path(path).name,
        "method": doc["method"],
        "pages": f"{doc['pages_used']}/{doc['pages_total']}",
        "invoice": inv,
        "issues": notes + validate(inv),
        "raw_text": doc["text"],
    }
