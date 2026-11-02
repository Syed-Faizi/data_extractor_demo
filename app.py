"""
Gradio UI: upload invoices (PDF or image, many at once) -> table + Excel download.
Run:  python app.py
"""

import json
import os
import tempfile
import time
from datetime import datetime

import gradio as gr
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
from extractor import LLM_MODEL, MAX_PAGES, OPENAI_BASE_URL, process_file  # noqa: E402

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "samples")
ENGINE = "Local model" if OPENAI_BASE_URL else "OpenAI"

# ---------- Demo limits (protect the paid API) ----------
RUNS_PER_USER = int(os.getenv("RUNS_PER_USER", "2"))      # runs per visitor per day
MAX_FILES_PER_RUN = int(os.getenv("MAX_FILES_PER_RUN", "3"))
DAILY_RUN_CAP = int(os.getenv("DAILY_RUN_CAP", "50"))      # all visitors together, per day
_usage = {"day": None, "total": 0, "users": {}}


def _visitor_id(request: gr.Request) -> str:
    if request is None:
        return "local"
    fwd = request.headers.get("x-forwarded-for", "")  # real IP behind Hugging Face proxy
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def _check_limit(request: gr.Request) -> str:
    """Raise a friendly error if over the limit; otherwise count this run."""
    today = datetime.now().date()
    if _usage["day"] != today:  # new day -> reset counters
        _usage.update(day=today, total=0, users={})
    who = _visitor_id(request)
    used = _usage["users"].get(who, 0)
    if _usage["total"] >= DAILY_RUN_CAP:
        raise gr.Error("The demo has reached today's limit. Please try again tomorrow, "
                       "or contact me for a full test on your documents.", duration=None)
    if used >= RUNS_PER_USER:
        raise gr.Error(f"You've used your {RUNS_PER_USER} free demo runs for today. "
                       "Want to test it on more of your documents? Get in touch and I'll "
                       "set up a proper trial.", duration=None)
    _usage["users"][who] = used + 1
    _usage["total"] += 1
    return f"{RUNS_PER_USER - used - 1} of {RUNS_PER_USER} free runs left today"


# ---------- UI pieces ----------
def stats_html(docs="—", clean="—", review="—", secs="—"):
    cards = [
        ("Documents", docs, "accent"),
        ("Clean", clean, "good"),
        ("Need review", review, "warn"),
        ("Time", secs, "accent"),
    ]
    inner = "".join(
        f'<div class="stat {cls}"><div class="stat-val">{val}</div>'
        f'<div class="stat-lbl">{lbl}</div></div>'
        for lbl, val, cls in cards
    )
    return f'<div class="stats">{inner}</div>'


HERO = f"""
<div class="hero">
  <div class="hero-badge">Document AI · OCR + LLM</div>
  <h1>Invoice &amp; Medical Bill <span>Data Extractor</span></h1>
  <p>Drop in invoices, medical bills or workers' comp EORs — digital PDFs, scans or phone photos.
     Get every field extracted, every number checked, and one clean Excel file.</p>
  <div class="chips">
    <span class="chip">🧠 {LLM_MODEL}</span>
    <span class="chip">⚙️ {ENGINE}</span>
    <span class="chip">📄 Up to {MAX_PAGES} pages / file</span>
    <span class="chip">🔒 Demo: {RUNS_PER_USER} runs/day, {MAX_FILES_PER_RUN} files/run</span>
  </div>
</div>
"""

STEPS = """
<div class="steps">
  <div class="step"><b>1</b><div><strong>Upload</strong><span>PDFs, scans, photos</span></div></div>
  <div class="step"><b>2</b><div><strong>OCR</strong><span>Every page read as an image</span></div></div>
  <div class="step"><b>3</b><div><strong>LLM extraction</strong><span>Fields + line items</span></div></div>
  <div class="step"><b>4</b><div><strong>Validation</strong><span>Totals &amp; dates checked</span></div></div>
</div>
"""

FOOTER = """
<div class="footer">Built by <b>Faizan Ali</b> · AI Engineer, Document AI &amp; OCR ·
<a href="https://syed-faizi.github.io/" target="_blank">Portfolio</a> ·
<a href="https://github.com/Syed-Faizi/data_extractor_demo" target="_blank">Source code</a></div>
"""

CSS = """
.gradio-container { max-width: 1360px !important; margin: auto; }
.table-wrap, .table-wrap * { font-family: Inter, system-ui, sans-serif !important; font-size: .86rem; }
.hero {
  border-radius: 18px; padding: 34px 34px 28px; color: #fff;
  background:
    radial-gradient(circle at 85% 15%, rgba(56,189,248,.35), transparent 40%),
    radial-gradient(circle at 10% 90%, rgba(167,139,250,.35), transparent 45%),
    linear-gradient(135deg, #0f172a 0%, #1e1b4b 55%, #312e81 100%);
  box-shadow: 0 18px 40px -18px rgba(49,46,129,.6);
}
.hero h1 { font-size: 2.1rem; font-weight: 800; margin: 10px 0 8px; color: #fff; letter-spacing: -.02em; }
.hero h1 span { background: linear-gradient(90deg,#38bdf8,#a78bfa);
  -webkit-background-clip: text; background-clip: text; color: transparent; }
.hero p { max-width: 640px; opacity: .85; font-size: 1rem; margin: 0; color: #e2e8f0; }
.hero-badge { display: inline-block; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase;
  padding: 5px 12px; border-radius: 999px; background: rgba(255,255,255,.12);
  border: 1px solid rgba(255,255,255,.2); color: #e0e7ff; }
.chips { margin-top: 18px; display: flex; gap: 8px; flex-wrap: wrap; }
.chip { font-size: .8rem; padding: 6px 12px; border-radius: 10px;
  background: rgba(15,23,42,.55); border: 1px solid rgba(148,163,184,.3); color: #e2e8f0; }

.steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 6px 0 4px; }
.step { display: flex; gap: 12px; align-items: center; padding: 14px 16px; border-radius: 14px;
  border: 1px solid var(--border-color-primary); background: var(--block-background-fill); }
.step b { flex: none; width: 32px; height: 32px; border-radius: 10px; display: grid; place-items: center;
  color: #fff; background: linear-gradient(135deg,#6366f1,#38bdf8); }
.step strong { display: block; font-size: .92rem; }
.step span { font-size: .78rem; opacity: .7; }

.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.stat { padding: 16px 18px; border-radius: 14px; border: 1px solid var(--border-color-primary);
  background: var(--block-background-fill); position: relative; overflow: hidden; }
.stat::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; }
.stat.accent::before { background: #6366f1; } .stat.good::before { background: #10b981; }
.stat.warn::before { background: #f59e0b; }
.stat-val { font-size: 1.7rem; font-weight: 800; line-height: 1.1; }
.stat-lbl { font-size: .78rem; opacity: .7; margin-top: 4px; text-transform: uppercase; letter-spacing: .05em; }

.panel { border-radius: 16px !important; }
#run-btn { height: 52px; font-size: 1.02rem; font-weight: 700; border-radius: 12px;
  background: linear-gradient(90deg,#6366f1,#3b82f6) !important; border: none !important; color: #fff !important;
  box-shadow: 0 10px 24px -10px rgba(99,102,241,.8); }
#run-btn:hover { filter: brightness(1.08); }
.status-msg { font-size: .95rem; }
.footer { text-align: center; font-size: .82rem; opacity: .7; padding: 14px 0 4px; }
.footer a { color: #6366f1; }

@media (max-width: 760px) {
  .steps, .stats { grid-template-columns: repeat(2, 1fr); }
  .hero { padding: 24px 20px; } .hero h1 { font-size: 1.6rem; }
}
"""


# ---------- Processing ----------
def run(files, request: gr.Request):
    if not files:
        raise gr.Error("Upload at least one PDF or image.")
    if len(files) > MAX_FILES_PER_RUN:
        raise gr.Error(f"Demo limit: up to {MAX_FILES_PER_RUN} files per run.")
    left = _check_limit(request)

    t0 = time.time()
    summary, items, details = [], [], {}
    for f in files:
        path = f if isinstance(f, str) else f.name
        name = os.path.basename(path)
        try:
            r = process_file(path)
        except Exception as e:  # keep the batch going if one file fails
            summary.append({"File": name, "Status": "❌ Error", "Issues": str(e)})
            continue

        inv = r["invoice"]
        status = "✅ OK" if not r["issues"] else "⚠️ Check"
        row = {"File": name, "Pages": r.get("pages", "1/1"), "Status": status}
        if inv:
            dos = sorted(li.date_of_service for li in inv.line_items if li.date_of_service)
            row.update({
                "Type": inv.document_type, "Issued by": inv.vendor_name,
                "Invoice / Statement #": inv.invoice_number, "Date": inv.invoice_date,
                "Due": inv.due_date, "Patient": inv.patient_name, "Provider": inv.provider_name,
                "Date of injury": inv.date_of_injury,
                "DOS": (dos[0] if dos and dos[0] == dos[-1] else f"{dos[0]} to {dos[-1]}") if dos else None,
                "Claim #": inv.claim_number, "Carrier": inv.payer_name, "Employer": inv.employer,
                "Currency": inv.currency,
                "Subtotal": inv.subtotal, "Tax": inv.tax, "Total": inv.total,
                "Allowed": inv.amount_allowed, "Paid": inv.amount_paid,
            })
            for li in inv.line_items:
                items.append({"File": name, "Invoice / Statement #": inv.invoice_number,
                              "Patient": inv.patient_name, **li.model_dump()})
            details[name] = inv.model_dump()
        row["Issues"] = "; ".join(r["issues"])
        summary.append(row)

    summary_df = pd.DataFrame(summary).dropna(axis=1, how="all")
    items_df = pd.DataFrame(items).rename(columns={
        "date_of_service": "DOS", "code": "Code", "description": "Description",
        "quantity": "Qty", "unit_price": "Unit price", "amount": "Amount",
        "allowed": "Allowed", "paid": "Paid", "reason_code": "Reason"}).dropna(axis=1, how="all")

    out = os.path.join(tempfile.gettempdir(),
                       f"extracted_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        summary_df.to_excel(xw, sheet_name="Summary", index=False)
        items_df.to_excel(xw, sheet_name="Line Items", index=False)
        for ws in xw.sheets.values():
            for col in ws.columns:
                width = max(len(str(c.value or "")) for c in col) + 2
                ws.column_dimensions[col[0].column_letter].width = min(width, 50)

    ok = sum(1 for s in summary if s["Status"].startswith("✅"))
    secs = f"{time.time() - t0:.1f}s"
    msg = (f"✅ Done — {len(summary)} document(s) processed, {ok} clean, "
           f"{len(summary) - ok} flagged for review.  ·  _{left}_")
    return (stats_html(len(summary), ok, len(summary) - ok, secs), msg,
            summary_df, items_df, json.dumps(details, indent=2), out)


# ---------- Layout ----------
theme = gr.themes.Soft(primary_hue="indigo", secondary_hue="sky", radius_size="lg",
                       font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"])

with gr.Blocks(title="Invoice & Document Data Extractor") as demo:
    gr.HTML(HERO)
    gr.HTML(STEPS)

    with gr.Row(equal_height=False):
        with gr.Column(scale=3, min_width=320, elem_classes="panel"):
            gr.Markdown("### 📤 Upload documents")
            files = gr.File(label=f"PDF, PNG, JPG — up to {MAX_FILES_PER_RUN} files", file_count="multiple",
                            file_types=[".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"])
            if os.path.isdir(SAMPLES_DIR):
                samples = sorted(os.path.join(SAMPLES_DIR, s) for s in os.listdir(SAMPLES_DIR))
                gr.Examples(examples=[[samples]], inputs=files,
                            label="No files handy? Load 3 sample medical documents")
            btn = gr.Button("⚡ Extract data", elem_id="run-btn")

        with gr.Column(scale=8):
            stats = gr.HTML(stats_html())
            status = gr.Markdown("Upload documents and click **Extract data**.",
                                 elem_classes="status-msg")
            with gr.Tabs():
                with gr.Tab("📊 Summary"):
                    summary = gr.Dataframe(wrap=True, elem_classes="table-wrap")
                with gr.Tab("🧾 Line items"):
                    items = gr.Dataframe(wrap=True, elem_classes="table-wrap")
                with gr.Tab("{ } JSON"):
                    js = gr.Code(language="json")
            xlsx = gr.File(label="📥 Download Excel")

    gr.HTML(FOOTER)

    btn.click(run, inputs=files, outputs=[stats, status, summary, items, js, xlsx])

if __name__ == "__main__":
    demo.launch(theme=theme, css=CSS)
