"""
Core pipeline: file -> text (native PDF text or OCR) -> LLM -> validated JSON.

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
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None


class Invoice(BaseModel):
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None   # YYYY-MM-DD
    due_date: Optional[str] = None       # YYYY-MM-DD
    bill_to: Optional[str] = None
    currency: Optional[str] = None
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    line_items: List[LineItem] = []


REQUIRED_FIELDS = ["vendor_name", "invoice_number", "invoice_date", "total"]

PROMPT = """You extract data from invoices and receipts.

The document text is given page by page. Each page is wrapped like this:
<<PAGE 1 START>>
...text of page 1...
<<PAGE 1 END>>
The markers are NOT part of the document; they only show where each page begins and ends.
The text may come from OCR and contain small errors (e.g. "O" for "0"); read it carefully.
An invoice can continue across pages: line items may be split over several pages, and the
totals are usually on the last page. Combine all pages into ONE result and do not
list the same line item twice.

Return ONLY a JSON object with exactly these keys:
vendor_name, invoice_number, invoice_date, due_date, bill_to, currency,
subtotal, tax, total, line_items (list of {description, quantity, unit_price, amount}).

Rules:
- Use null when a value is not in the document. Never guess or calculate missing values.
- Dates as YYYY-MM-DD.
- Numbers as plain numbers (no currency symbols, no thousands separators).
- currency as a 3-letter code (USD, EUR, PKR...) only if it is shown or clearly implied.

Document ({n_pages} page(s)):
{text}
"""


# ---------- Step 1: get text, page by page ----------
def _ocr_image(img: Image.Image) -> str:
    # psm 6 = treat page as one text block; keeps labels and amounts on the same line
    return pytesseract.image_to_string(img.convert("L"), config="--psm 6")


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
