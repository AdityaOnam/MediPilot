"""
Builds docs/interview/MediPilot_Interview_Prep.pdf

    python docs/interview/build_interview_pdf.py

Part A is a deep architecture reference. Part B is interview questions grouped
by topic, each with a model answer. Every number is taken from a committed file
in this repo (config/*.yaml, model/artifacts/*/manifest.json, docs/benchmarks/,
docs/notes/RISK_ENGINE.md, the business proposal). Change the source first,
then this script.
"""

from __future__ import annotations

import pathlib

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, CondPageBreak, Frame, KeepTogether, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

OUT = pathlib.Path(__file__).with_name("MediPilot_Interview_Prep.pdf")

# --------------------------------------------------------------------------
# Fonts and palette
# --------------------------------------------------------------------------
FONTS = pathlib.Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Body", str(FONTS / "segoeui.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", str(FONTS / "segoeuib.ttf")))
pdfmetrics.registerFont(TTFont("Body-Italic", str(FONTS / "ariali.ttf")))
pdfmetrics.registerFont(TTFont("Mono", str(FONTS / "consola.ttf")))
pdfmetrics.registerFont(TTFont("Mono-Bold", str(FONTS / "consolab.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold",
                              italic="Body-Italic", boldItalic="Body-Bold")
pdfmetrics.registerFontFamily("Mono", normal="Mono", bold="Mono-Bold",
                              italic="Mono", boldItalic="Mono-Bold")

INK = colors.HexColor("#1b1f24")
MUTED = colors.HexColor("#5b6470")
ACCENT = colors.HexColor("#0f5e9c")
ACCENT_SOFT = colors.HexColor("#e8f1f9")
RULE_C = colors.HexColor("#b42318")       # rules layer
RULE_SOFT = colors.HexColor("#fdecea")
MODEL_C = colors.HexColor("#1a7f37")      # learned model
MODEL_SOFT = colors.HexColor("#e9f6ec")
PERC_C = colors.HexColor("#8a5a00")       # perception
PERC_SOFT = colors.HexColor("#fff4dc")
GRID = colors.HexColor("#d0d7de")
ZEBRA = colors.HexColor("#f6f8fa")

# --------------------------------------------------------------------------
# Styles
# --------------------------------------------------------------------------
BASE = dict(fontName="Body", textColor=INK)
S = {
    "title": ParagraphStyle("title", fontName="Body-Bold", fontSize=26, leading=32,
                            textColor=ACCENT, alignment=TA_CENTER, spaceAfter=6),
    "subtitle": ParagraphStyle("subtitle", fontName="Body", fontSize=13, leading=18,
                               textColor=MUTED, alignment=TA_CENTER, spaceAfter=4),
    "part": ParagraphStyle("part", fontName="Body-Bold", fontSize=22, leading=28,
                           textColor=ACCENT, spaceBefore=4, spaceAfter=10),
    "h1": ParagraphStyle("h1", fontName="Body-Bold", fontSize=16, leading=21,
                         textColor=ACCENT, spaceBefore=12, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName="Body-Bold", fontSize=12.5, leading=17,
                         textColor=INK, spaceBefore=9, spaceAfter=4),
    "body": ParagraphStyle("body", fontSize=9.6, leading=13.6, spaceAfter=5, **BASE),
    "small": ParagraphStyle("small", fontSize=8.2, leading=11, textColor=MUTED, fontName="Body"),
    "bullet": ParagraphStyle("bullet", fontSize=9.6, leading=13.4, leftIndent=12,
                             bulletIndent=2, spaceAfter=2, **BASE),
    "cell": ParagraphStyle("cell", fontSize=8.4, leading=11, **BASE),
    "cellb": ParagraphStyle("cellb", fontName="Body-Bold", fontSize=8.4, leading=11,
                            textColor=colors.white),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=8.2, leading=10.6,
                           textColor=INK, backColor=ZEBRA, borderPadding=(5, 6, 5, 6),
                           leftIndent=4, rightIndent=4, spaceBefore=3, spaceAfter=8),
    "q": ParagraphStyle("q", fontName="Body-Bold", fontSize=10, leading=13.6,
                        textColor=INK, spaceBefore=7, spaceAfter=2),
    "a": ParagraphStyle("a", fontSize=9.3, leading=13.2, leftIndent=12, spaceAfter=2,
                        **BASE),
    "fu": ParagraphStyle("fu", fontName="Body", fontSize=8.6, leading=12, leftIndent=12,
                         textColor=MUTED, spaceAfter=3),
    "callout": ParagraphStyle("callout", fontSize=9.3, leading=13, backColor=ACCENT_SOFT,
                              borderPadding=(6, 8, 6, 8), spaceBefore=4, spaceAfter=9,
                              leftIndent=4, rightIndent=4, **BASE),
    "warn": ParagraphStyle("warn", fontSize=9.3, leading=13, backColor=RULE_SOFT,
                           borderPadding=(6, 8, 6, 8), spaceBefore=4, spaceAfter=9,
                           leftIndent=4, rightIndent=4, **BASE),
    "toc0": ParagraphStyle("toc0", fontName="Body-Bold", fontSize=10.5, leading=15,
                           textColor=ACCENT),
    "toc1": ParagraphStyle("toc1", fontName="Body", fontSize=9.4, leading=12.6,
                           leftIndent=14, textColor=INK),
}

LEVEL_COLOUR = {"Basic": "#1a7f37", "Intermediate": "#8a5a00", "Advanced": "#b42318"}


def c(text: str) -> str:
    """Inline code."""
    return f'<font name="Mono" size="8.6" color="#0b4f86">{text}</font>'


# --------------------------------------------------------------------------
# Flowable helpers
# --------------------------------------------------------------------------
story: list = []


def part(text):
    story.append(PageBreak())
    p = Paragraph(text, S["part"])
    p._toc = (0, text)
    story.append(p)


def h1(text):
    story.append(CondPageBreak(60 * mm))
    p = Paragraph(text, S["h1"])
    p._toc = (1, text)
    story.append(p)


def h2(text):
    story.append(CondPageBreak(30 * mm))
    story.append(Paragraph(text, S["h2"]))


def para(text, style="body"):
    story.append(Paragraph(text, S[style]))


def bullets(items):
    for it in items:
        story.append(Paragraph(it, S["bullet"], bulletText="•"))
    story.append(Spacer(1, 3))


def code(text):
    esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    esc = esc.replace(" ", "&nbsp;").replace("\n", "<br/>")
    story.append(Paragraph(esc, S["code"]))


def table(rows, widths, header=True, font=8.4):
    cell = ParagraphStyle("c", parent=S["cell"], fontSize=font, leading=font * 1.3)
    cellb = ParagraphStyle("cb", parent=S["cellb"], fontSize=font, leading=font * 1.3)
    data = []
    for i, r in enumerate(rows):
        st = cellb if (header and i == 0) else cell
        data.append([Paragraph(str(x), st) for x in r])
    total = sum(widths)
    avail = 174 * mm
    w = [x / total * avail for x in widths]
    t = Table(data, colWidths=w, repeatRows=1 if header else 0)
    ts = [
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        ts.append(("BACKGROUND", (0, 0), (-1, 0), ACCENT))
    for i in range(1 if header else 0, len(data)):
        if i % 2 == 0:
            ts.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    t.setStyle(TableStyle(ts))
    story.append(t)
    story.append(Spacer(1, 7))


QN = [0]


def qa(level, q, a, follow=None):
    QN[0] += 1
    col = LEVEL_COLOUR[level]
    head = Paragraph(
        f'Q{QN[0]}. {q} &nbsp;<font name="Body" size="7.6" color="{col}">[{level}]</font>',
        S["q"])
    parts = [head]
    if isinstance(a, str):
        a = [a]
    for i, chunk in enumerate(a):
        prefix = '<font name="Body-Bold" color="#0f5e9c">A.</font> ' if i == 0 else ""
        parts.append(Paragraph(prefix + chunk, S["a"]))
    if follow:
        parts.append(Paragraph("<b>Likely follow-up:</b> " + follow, S["fu"]))
    story.append(KeepTogether(parts))


# --------------------------------------------------------------------------
# Diagram helpers
# --------------------------------------------------------------------------
W_PT = 174 * mm


def _arrow(d, x1, y1, x2, y2, col=MUTED, w=1.1):
    d.add(Line(x1, y1, x2, y2, strokeColor=col, strokeWidth=w))
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    L, s = 6, 3.2
    p1 = (x2 - L * math.cos(ang) + s * math.sin(ang), y2 - L * math.sin(ang) - s * math.cos(ang))
    p2 = (x2 - L * math.cos(ang) - s * math.sin(ang), y2 - L * math.sin(ang) + s * math.cos(ang))
    d.add(Polygon([x2, y2, p1[0], p1[1], p2[0], p2[1]], fillColor=col, strokeColor=col))


def _box(d, x, y, w, h, title, lines=(), fill=ACCENT_SOFT, stroke=ACCENT, tsize=8.2, lsize=6.8):
    d.add(Rect(x, y, w, h, rx=4, ry=4, fillColor=fill, strokeColor=stroke, strokeWidth=0.9))
    d.add(String(x + w / 2, y + h - 11, title, fontName="Body-Bold", fontSize=tsize,
                 fillColor=INK, textAnchor="middle"))
    for i, ln in enumerate(lines):
        d.add(String(x + w / 2, y + h - 22 - i * 9, ln, fontName="Body", fontSize=lsize,
                     fillColor=MUTED, textAnchor="middle"))


def diagram_tracks():
    d = Drawing(W_PT, 250)
    cw, gap = 155, 20
    xs = [5, 5 + cw + gap, 5 + 2 * (cw + gap)]
    heads = [("PERCEPTION — may only REPORT", PERC_SOFT, PERC_C),
             ("INTERFACE — may only RENDER", ACCENT_SOFT, ACCENT),
             ("EVALUATION — alone may DECIDE", MODEL_SOFT, MODEL_C)]
    for x, (h, f, s) in zip(xs, heads):
        d.add(Rect(x, 8, cw, 235, rx=6, ry=6, fillColor=f, strokeColor=s, strokeWidth=1.2))
        d.add(String(x + cw / 2, 229, h, fontName="Body-Bold", fontSize=7.8, fillColor=s,
                     textAnchor="middle"))
    col1 = [("Browser STT", ["webkitSpeechRecognition", "hi-IN / en-IN"]),
            ("Groq Whisper ASR", ["whisper-large-v3-turbo", "/v1/speech/transcribe"]),
            ("LLM structurer", ["gpt-oss-120b (observe)", "gpt-oss-20b (match/classify)"]),
            ("Deterministic floor", ["RuleBasedStructurer", "Tier-A red-flag phrase table"])]
    col2 = [("Next.js 16 · React 19", ["8 routes: / intake counter board", "card hall control audit"]),
            ("lib/api/client.ts", ["NEXT_PUBLIC_MP_SOURCE", "mock (default) | live"]),
            ("Clinical components", ["AcuityCard throws w/o confidence", "AbstentionCard: no GREEN type"]),
            ("SSE consumer", ["/v1/stream → board updates", "OverrideDialog everywhere"])]
    col3 = [("Orchestrator FastAPI", ["/v1/* — 21 routes", "World + 1 Hz tick loop"]),
            ("risk_model.py", ["9-stage pipeline", "rules before & after GBDT"]),
            ("band_engine.py", ["escalate freely", "lower → AsymmetricAutonomyViolation"]),
            ("Scheduler · Surge · Audit", ["two clocks, 3× surge", "SHA-256 hash-chained ledger"])]
    for x, col, (_, f, s) in zip(xs, [col1, col2, col3], heads):
        for i, (t, ls) in enumerate(col):
            _box(d, x + 8, 168 - i * 52, cw - 16, 44, t, ls, fill=colors.white, stroke=s)
    _arrow(d, xs[0] + cw, 120, xs[1], 120, col=PERC_C)
    _arrow(d, xs[1] + cw, 120, xs[2], 120, col=ACCENT)
    _arrow(d, xs[2], 95, xs[1] + cw, 95, col=MODEL_C)
    d.add(String(xs[0] + cw + 10, 124, "facts", fontName="Body", fontSize=6.5, fillColor=MUTED,
                 textAnchor="middle"))
    d.add(String(xs[1] + cw + 10, 124, "REST", fontName="Body", fontSize=6.5, fillColor=MUTED,
                 textAnchor="middle"))
    d.add(String(xs[1] + cw + 10, 86, "bands", fontName="Body", fontSize=6.5, fillColor=MUTED,
                 textAnchor="middle"))
    story.append(d)
    para("Figure A1 — The three tracks cannot borrow each other's authority. The language model "
         "reports facts; the UI renders; only the Python evaluation track assigns a band.", "small")
    story.append(Spacer(1, 6))


def diagram_vertical(steps, caption, height_each=26, width=330):
    n = len(steps)
    h = n * (height_each + 10) + 10
    d = Drawing(W_PT, h)
    x = (W_PT - width) / 2
    kind_fill = {"rule": (RULE_SOFT, RULE_C), "model": (MODEL_SOFT, MODEL_C),
                 "perc": (PERC_SOFT, PERC_C), "io": (ACCENT_SOFT, ACCENT)}
    for i, (kind, title, note) in enumerate(steps):
        y = h - (i + 1) * (height_each + 10)
        f, s = kind_fill[kind]
        d.add(Rect(x, y, width, height_each, rx=4, ry=4, fillColor=f, strokeColor=s,
                   strokeWidth=0.9))
        d.add(String(x + 8, y + height_each - 11, title, fontName="Body-Bold", fontSize=8,
                     fillColor=INK))
        d.add(String(x + 8, y + 5, note, fontName="Body", fontSize=6.8, fillColor=MUTED))
        tag = {"rule": "RULE", "model": "MODEL", "perc": "LLM", "io": "I/O"}[kind]
        d.add(String(x + width - 6, y + height_each - 11, tag, fontName="Body-Bold", fontSize=6.8,
                     fillColor=s, textAnchor="end"))
        if i < n - 1:
            _arrow(d, x + width / 2, y, x + width / 2, y - 10 + 1)
    story.append(d)
    para(caption, "small")
    story.append(Spacer(1, 6))


def diagram_runtime():
    d = Drawing(W_PT, 215)
    bw, bh = 108, 40
    row1 = [("Patient @ kiosk", ["/intake · voice/tap", "Hindi + English"], PERC_SOFT, PERC_C),
            ("Next.js /api/intake", ["classify · match", "observe (Groq, server)"], PERC_SOFT, PERC_C),
            ("lib/api/client.ts", ["mock adapter (default)", "live adapter → :8000"], ACCENT_SOFT, ACCENT),
            ("POST /v1/intake/submit", ["structured record", "→ encounter + token"], MODEL_SOFT, MODEL_C)]
    row2 = [("risk_model.score", ["red flags → GBDT", "→ floors → conformal"], MODEL_SOFT, MODEL_C),
            ("band_engine", ["assign_band()", "up only, unless human"], RULE_SOFT, RULE_C),
            ("World tick (1 Hz)", ["RecheckScheduler", "SurgeController"], MODEL_SOFT, MODEL_C),
            ("SSE /v1/stream", ["board · card · hall", "override → audit"], ACCENT_SOFT, ACCENT)]
    gap = (W_PT - 4 * bw) / 3
    for i, (t, ls, f, s) in enumerate(row1):
        x = i * (bw + gap)
        _box(d, x, 160, bw, bh, t, ls, fill=f, stroke=s)
        if i < 3:
            _arrow(d, x + bw, 180, x + bw + gap, 180)
    for i, (t, ls, f, s) in enumerate(reversed(row2)):
        x = i * (bw + gap)
        _box(d, x, 60, bw, bh, t, ls, fill=f, stroke=s)
        if i < 3:
            _arrow(d, x + bw + gap, 80, x + bw, 80)
    _arrow(d, 3 * (bw + gap) + bw / 2, 160, 3 * (bw + gap) + bw / 2, 100)
    # feedback loops
    d.add(Rect(0, 4, W_PT, 40, rx=4, ry=4, fillColor=colors.white, strokeColor=GRID))
    d.add(String(W_PT / 2, 30, "Loop A: every encounter re-scored every 5 min (Red: 60 s) — "
                 "re-measure on band cadence — wait ceilings breach on time alone",
                 fontName="Body", fontSize=7, fillColor=INK, textAnchor="middle"))
    d.add(String(W_PT / 2, 16, "Loop B: override + back-filled outcome_ref in the audit ledger "
                 "become the next training labels", fontName="Body", fontSize=7, fillColor=INK,
                 textAnchor="middle"))
    story.append(d)
    para("Figure A2 — Runtime path of one patient, and the two feedback loops that keep the "
         "queue observed after triage.", "small")
    story.append(Spacer(1, 6))


# ==========================================================================
# COVER + TOC
# ==========================================================================
story.append(Spacer(1, 50 * mm))
story.append(Paragraph("MediPilot — PatientTriage.ai", S["title"]))
story.append(Paragraph("Interview Preparation Guide", S["subtitle"]))
story.append(Paragraph("Deep architecture reference · Segregated interview questions with model answers",
                       S["subtitle"]))
story.append(Spacer(1, 12 * mm))
story.append(Paragraph("Team 01 BIT · IIT Patna · Accenture Innovation Challenge 2026, Round 2<br/>"
                       "Aditya Onam · Aditya Gupta · Varada Patel", S["subtitle"]))
story.append(Spacer(1, 18 * mm))
story.append(Paragraph(
    "<b>How to use this document.</b> Part A is the system as built, from the kiosk microphone "
    "to the audit ledger, with the numbers you will be asked to defend. Part B is the question "
    "bank, grouped by the kind of interviewer who will ask it (ML, backend, frontend, LLM, "
    "product, regulatory, and the hostile \"poke holes in it\" round). Each answer is short "
    "enough to say out loud. Difficulty tags: "
    '<font color="#1a7f37"><b>Basic</b></font> · <font color="#8a5a00"><b>Intermediate</b></font> · '
    '<font color="#b42318"><b>Advanced</b></font>. Part C is a one-page numbers cheat-sheet.',
    S["callout"]))
story.append(Paragraph(
    "<b>Ground rule for every answer:</b> all data in this system is synthetic. Never claim "
    "clinical performance. The strongest move in any interview about this project is to "
    "say what it does <i>not</i> prove before the interviewer does.", S["warn"]))

story.append(PageBreak())
story.append(Paragraph("Contents", S["h1"]))
toc = TableOfContents()
toc.levelStyles = [S["toc0"], S["toc1"]]
toc.dotsMinLevel = 0
story.append(toc)

# ==========================================================================
# PART A — ARCHITECTURE
# ==========================================================================
part("Part A — Deep Architecture")

h1("A1. The project in one minute")
para("<b>Problem.</b> Emergency-department triage assigns acuity once, at arrival. The queue that "
     "results is static while the patient's physiology is not — a Yellow chest-discomfort patient "
     "can become unstable twenty minutes later while the nurse is registering new arrivals. "
     "This is a structural defect of the single-point assessment model, not an individual error.")
para("<b>Solution.</b> MediPilot is a <i>continuous re-triage</i> decision-support system for Indian "
     "EDs. A patient talks to a kiosk in Hindi or English; a branching conversation captures a "
     "structured history; a trained gradient-boosted model scores them against their age stratum; "
     "and the queue keeps re-scoring them for as long as they wait.")
para("<b>The one contract everything is built around:</b> the system may <b>raise</b> a waiting "
     "patient's priority autonomously and may <b>never lower</b> it below a human-assigned level. "
     "Escalation costs one nurse assessment; de-escalation can cost a life, so it stays with a human.")
story.append(Paragraph(
    "<b>30-second pitch:</b> \"Most triage demos show a language model producing an acuity level. "
    "Ours shows a language model that structurally cannot. The model reports what was said, a "
    "fixed table decides what it means, and the band engine assigns — and can only escalate. "
    "Everything else, the two clocks, six age strata, conformal sets and abstention, exists to make "
    "that split survive contact with a real department.\"", S["callout"]))

h1("A2. Three tracks with separated authority")
diagram_tracks()
table([
    ["Track", "Permitted to", "Never permitted to", "Lives in"],
    ["Perception (ASR + LLM)", "Transcribe speech, extract volunteered facts, pick one of the offered "
     "options, emit red-flag codes from a closed list of 8", "Emit an acuity, a band, or a diagnosis",
     f"{c('web/app/api/intake/')}, {c('web/intake/server/')}, {c('backend/speech/')}, {c('backend/intake/llm_structurer.py')}"],
    ["Interface (Next.js)", "Render bands, confidence, factors; capture overrides", "Lower a band "
     "(no downward code path exists); show a score without confidence", f"{c('web/')}"],
    ["Evaluation (Python)", "Score, assign bands, schedule rechecks, detect surge, write audit",
     "Lower a band without a human action attached", f"{c('backend/model/')}, {c('backend/triage/')}, {c('backend/rules/')}"],
], [1.3, 2.4, 2.0, 2.2])
para("Every model has a deterministic layer beneath it, so a missing API key or an absent GPU "
     "<i>degrades</i> the demonstration rather than stopping it.")

h1("A3. Technology stack")
table([
    ["Layer", "Technology", "Why it was chosen"],
    ["Web", "Next.js 16.3 (App Router), React 19.2, TypeScript strict, Tailwind v4, motion, "
     "@react-three/fiber + drei + three", "One codebase for kiosk, nurse board, public hall display; "
     "server route handlers keep the Groq key off the client"],
    ["API", "FastAPI 0.111 + uvicorn, Pydantic 2.7, Server-Sent Events", "Typed contracts, async tick "
     "loop in the lifespan hook, SSE is one-way and proxy-friendly"],
    ["ML", "scikit-learn 1.4.2 HistGradientBoosting, numpy/scipy, joblib artifacts", "Native NaN "
     "handling, already a dependency, ms-latency on CPU; torch DLL failed on the AMD dev box"],
    ["Config", "PyYAML — 6 clinical YAML files", "Clinical behaviour is tuned and signed off without "
     "touching code"],
    ["Perception", "Groq: whisper-large-v3-turbo, gpt-oss-120b, gpt-oss-20b", "Chosen from measured "
     "bake-offs; one credential buys both ASR and LLM"],
    ["Tests", "pytest 8.2 — 282 tests (278 pass); web intake self-test with 118 fixtures",
     "Invariants are tests that fail the build, not review checklist items"],
    ["Deploy", "AWS EC2 t3.micro (ap-south-1), Ubuntu 24.04, systemd, nginx", "Mumbai region for "
     "data locality; both FastAPI apps behind one nginx on port 80"],
], [0.9, 2.6, 2.8])

h1("A4. Repository layout")
code("""MediPilot/
├── web/                     Next.js app — every screen
│   ├── app/                 / /intake /board /counter /hall /control /audit /card/[id]
│   │   └── api/intake/      server-only Groq handlers: classify, match, observe, selftest
│   ├── intake/              kiosk conversation: tree/ (16 branches), match/, redflags/, voice/
│   ├── components/          clinical/ (AcuityCard, AbstentionCard, OverrideDialog, ...), mascot/, 3d/
│   └── lib/                 api/ (types, client, adapters/mock|live), clinical/, seed/
├── backend/                 Python service — packages are top-level import roots
│   ├── triage/              band_engine, audit_log, recheck_scheduler, surge_controller, api.py
│   │   └── orchestrator/    app.py, world.py, clock.py, dto.py, seed.py, tree_session.py ...
│   ├── model/               features, freshness, feature_registry, train, calibration,
│   │                        conformal, thresholds, artifact, predictor, risk_model, artifacts/
│   ├── intake/              state machine, question tree, LLM structurer, red flags, reliability
│   ├── rules/               red_flag_engine, vital_thresholds, spo2_bias_guard
│   ├── speech/              Groq ASR, Whisper, VAD recorder
│   ├── data/                generator/ + corpus_20.json + train_set_100k.zip (LFS)
│   ├── eval/                ASR, structurer and risk-engine bake-offs, time_to_detection
│   ├── config/              age_strata, band_cadence, red_flags, surge_policy,
│   │                        feature_registry, label_spec  (YAML)
│   └── tests/               pytest suite
├── docs/                    paper/ benchmarks/ diagrams/ notes/ submission/
├── infra/aws/               EC2 deployment notes + user-data.sh
└── experiments/             whisper-live (Colab + mic client, not part of the service)""")

h1("A5. Stage 1 — Intake: patient to structured record")
para(f"The kiosk is a ten-step state machine driven by {c('web/intake/IntakeApp.tsx')} over the "
     f"session state in {c('web/intake/session.ts')}:")
code("Welcome → Companion → HumanOffer → Consent → Basics → Conversation → Pain → Readback → Token\n"
     "                                         ↘ HumanLane  (bail out to a human at any step)")
h2("The branching conversation")
bullets([
    f"Opens with \"tell me what's wrong\" and classifies the answer into one of <b>16 clinical branches</b> "
    f"({c('chestPain, breathing, abdominal, neuro, fever, trauma, bleeding, gi, obstetric, poisoning, burn, allergy, urinary, mental, paedsGeneral, other')}).",
    f"Branch choice: a local keyword table first ({c('localClassify.ts')}); Groq refines it via "
    f"{c('/api/intake/classify')} <b>only if the patient has not yet answered inside the branch</b> — "
    "the conversation never switches under the patient's feet.",
    "Each branch asks 3–6 questions plus a universal tail, and drops any question the patient "
    "already answered on their own.",
    f"Adding a question is a row edit in {c('intake/tree/branches/*')}, never a component edit — "
    "\"what about dialysis patients?\" is answered by pointing at a file.",
])
h2("Three-tier answer matching — Groq is the exception path")
table([
    ["Tier", "What", "Cost"],
    ["0", "Exact lexicon — yes/no and 0–10 in English, Devanagari and romanised Hinglish", "instant, offline"],
    ["1", "Similarity over labels, value slugs and per-option synonyms, plus an edit-distance rescue for "
          "ASR near-misses", "instant, offline"],
    ["2", f"{c('/api/intake/match')} — the model picks one of the offered option values, or NONE",
     "network, rarely reached"],
], [0.4, 4.5, 1.2])
para("The tier-2 vocabulary is <b>closed by construction</b>: anything returned that is not one of "
     f"the offered values is read as NONE ({c('web/intake/server/validate.ts')} enforces it; the prompt "
     "only asks). The model can never invent an option and is never asked what an answer means clinically.")
h2("Red flags — two tiers, continuous")
table([
    ["Code", "Observation"],
    ["RF-01", "Altered consciousness / not responding"],
    ["RF-02", "Active labour, or bleeding in pregnancy"],
    ["RF-03", "Chest pain with sweating, radiation, or breathlessness (compound rule)"],
    ["RF-04", "Difficulty speaking in full sentences"],
    ["RF-05", "Sudden one-sided weakness, facial droop, or speech change"],
    ["RF-06", "Uncontrolled bleeding, or penetrating injury"],
    ["RF-07", "Poisoning, overdose, or snakebite"],
    ["RF-08", "Infant not feeding, floppy, or inconsolable"],
], [0.8, 5])
bullets([
    "<b>Tier A</b> — a bilingual phrase table over these 8 codes, deterministic and offline, with a "
    "negation set (\"no chest pain at all\" must not fire). Never delayed by wifi.",
    f"<b>Tier B</b> — {c('/api/intake/observe')} (gpt-oss-120b) returns a subset of the same closed "
    "8-code list and nothing else.",
    "When one fires: every clinical question stops, a nurse is called, and <b>no acuity word appears "
    "on the patient's screen</b>. Each maps straight to Red, overridable downward only by a clinician.",
])
h2("Offline by design")
para(f"No {c('GROQ_API_KEY')} → classification falls back to keywords, matching falls back to "
     "\"please pick one below\", and red flags still fire from tier A. The key buys the exception "
     f"paths, not the safety net. {c('MEDIPILOT_INTAKE_OFFLINE=1')} forces this state for rehearsal. "
     f"The key has no {c('NEXT_PUBLIC_')} prefix, so it can never reach a client bundle.")
para(f"The backend mirrors this flow in {c('backend/intake/pipeline.py')} (state machine → question tree "
     "→ speech adapter → LLM structurer → red-flag pass, with age stratification and reliability "
     "signals) and <b>makes no clinical decision</b> beyond the deterministic red-flag table.")

h1("A6. Stage 2 — Scoring: record to band")
para(f"{c('backend/model/risk_model.py')} runs a fixed pipeline. It returns either a "
     f"{c('ScoreObject')} or an {c('AbstentionObject')} — <b>never a partial object</b>. Red boxes "
     "are rules, green is the learned model; the model runs <i>behind</i> every hard safety "
     "guarantee, never in front of one.")
diagram_vertical([
    ("io", "PatientRecord (from intake)", "vitals {value, takenAt, source}, age, observations, flags, consent"),
    ("rule", "1. resolve_stratum", "age → one of 6 strata; unknown age → widest-safety stratum (child), flagged inferred"),
    ("rule", "2. RED-FLAG PASS", "deterministic → Red, EARLY RETURN — the model never runs"),
    ("rule", "3. OOD gate", "→ AbstentionObject, held at the Yellow floor"),
    ("rule", "4. Freshness", ">2× cadence = stale (discounted), >3× cadence = missing"),
    ("rule", "5. All vitals missing?", "→ AbstentionObject"),
    ("rule", "6. Per-stratum vital thresholds", "abnormality per stratum's own normal range → ThresholdResult[]"),
    ("rule", "7. Asymmetric reliability weighting", "widens uncertainty only — never lowers risk"),
    ("model", "8b. Features → HistGBDT → per-stratum calibration", "59 features (fx-v4) → p(critical within 180 min)"),
    ("rule", "8c/8d/8e. Floors", "vulnerable-stratum floor · ≥4 abnormal → Yellow · GCS≤8 | SpO2<85 | SBP<70 | ≥6 abnormal → Red"),
    ("model", "9. Thresholds + Mondrian conformal", "band from cost-sensitive cuts; set width → confidence / abstention"),
], "Figure A3 — The scoring pipeline. Steps 2, 3, 5, 8c, 8d, 8e are rules, never model.",
    height_each=24, width=420)
h2("Fallback")
para(f"If the artifact is missing, its sklearn version mismatches, or its feature contract has drifted "
     f"from the live extractor, {c('model/artifact.py')} degrades to the frozen AIIMS-ATP rule card and "
     f"stamps {c('score_source=\"fallback_heuristic\"')}. It never raises into the triage API.")
h2("Band engine — Invariant 1 in code")
code("""def assign_band(patient_id, scored_band, current_band, last_human_action=None, spo2_value=None, ...):
    if current_band is None:            -> initial, allowed
    if new_idx > current_idx:           -> escalation, autonomous, allowed
    if new_idx < current_idx:
        if last_human_action is None:   -> raise AsymmetricAutonomyViolation   # hard error
        check_spo2_alone_deescalation() -> raise SpO2AloneDeescalationError if SpO2 is the only reason
        -> de-escalation, attributed to the human""")
para("A normal SpO<sub>2</sub> alone can never justify a downward move — even with a human attached — "
     "because pulse oximetry under-detects occult hypoxaemia in darker-skinned patients "
     "(11.7% vs 3.6%; 17% vs 6.2% in the multicentre cohort).")

h1("A7. Age stratification")
table([
    ["Stratum", "Age", "HR", "RR", "SBP", "SpO2 min", "Calib. weight", "Reassurance decay", "Abnormal-vital floor"],
    ["Neonate", "0–27 d", "100–180", "30–60", "60–90", "95", "1.8", "0.50", "0.36"],
    ["Infant", "28–364 d", "100–160", "25–50", "70–100", "95", "1.5", "0.55", "0.36"],
    ["Child", "1–11 y", "70–140", "18–30", "80–120", "95", "1.3", "0.65", "0.36"],
    ["Adolescent", "12–17 y", "60–110", "14–22", "90–130", "95", "1.0", "0.80", "—"],
    ["Adult", "18–64 y", "60–100", "12–20", "90–140", "95", "1.0", "0.85", "—"],
    ["Geriatric", "65 y+", "60–100", "12–20", "90–150", "94", "1.6", "0.25", "0.36"],
], [1.1, 0.9, 0.8, 0.7, 0.8, 0.8, 0.9, 1.0, 1.1], font=7.8)
para("Unknown age falls back to <b>child</b> — wide thresholds plus elevated calibration weight — and "
     "the UI says so. No threshold is applied before a stratum resolves (Invariant 3). The worked "
     "example: a 3-year-old with HR 138 is normal-for-age but reads as severe tachycardia on an adult "
     "scale, while a 75-year-old's RR 22.9 and SpO<sub>2</sub> 93.5 look unremarkable on an adult scale "
     "but are out of range for age. A single adult model errs in both directions at once.")

h1("A8. Stage 3 — The waiting loop: two clocks")
para("<b>Re-scoring</b> is the model running again: milliseconds, never rationed. <b>Re-measurement</b> "
     "is a human taking fresh vitals: the scarcest resource in the department, rationed by band. "
     "<b>The wait ceiling</b> is a third, independent trigger — time in queue alone forces action.")
table([
    ["Band", "Re-score", "Re-measure", "Ceiling", "On breach"],
    ["Red", "60 s", "5 min", "0 (should not wait)", "Still queued at 5 min → page senior clinician + flag board"],
    ["Yellow", "5 min", "30 min (45 in surge)", "60 min", "Forced re-measure; not done in 15 min → Red on time alone"],
    ["Green", "5 min", "60 min (90 in surge)", "120 min", "Re-measure + wellbeing contact; 2 missed rechecks → Yellow"],
    ["Abstained", "5 min", "on human review", "15 min", "Unmet-review breach; floor band is Yellow — never Green"],
], [0.9, 0.8, 1.3, 1.1, 3.2])
h2("Recheck trust (Indian EDs: families participate in care)")
table([
    ["Who", "Trust", "Can close"],
    ["Recheck station / nurse", "full", "Red, Yellow, Green"],
    ["Accompanying family", "partial", "Green only — and doing so raises a flag for staff"],
    ["Patient self-service", "signal only", "Can escalate; can never de-escalate or satisfy a recheck"],
], [1.6, 0.8, 3.2])
h2("Surge controller")
bullets([
    "Detects <b>3× the site's normal arrival rate</b> (default 8/h) over a 20-min rolling window; exits below 2×.",
    "Yellow re-measure stretches 30→45 min, Green 60→90. <b>Red never stretches.</b>",
    f"Three actions raise {c('SurgeViolation')} instead of being discouraged: raising the cost ratio R to "
    "quieten alarms, resolving an abstention by guessing, de-escalating anyone to free capacity.",
    "Alerts are ranked by <b>risk × minutes waiting</b> and are never suppressed.",
])

h1("A9. Stage 4 — The human closes it: override and audit")
para(f"Override is one touch from every surface that shows a band ({c('OverrideDialog.tsx')}). "
     f"{c('backend/triage/audit_log.py')} appends a record that is <b>append-only</b> and "
     "<b>SHA-256 hash-chained</b> — each record carries the hash of the previous one, so any retroactive "
     "edit breaks the chain. Consent withdrawal is a new event, never a deletion.")
table([
    ["Field group", "Fields"],
    ["Who and when", "patient_id, timestamp_utc, clinician_id, clinician_role"],
    ["What changed", "system_band, clinician_band, direction, reason_code (fixed list), reason_text (free)"],
    ["What the clinician saw", "score, confidence, factors_shown (card as displayed)"],
    ["Reproducibility", "inputs_hash, model_version, calibration_version"],
    ["Governance", "consent_state; outcome_ref (back-filled later — the training signal)"],
    ["Chain", "record_hash, previous_record_hash"],
], [1.5, 5])
story.append(Paragraph(
    "<b>Field-count trap:</b> 16 required fields + outcome_ref = 17 substantive, + 2 chain fields = 19 "
    "stored. The module docstring says \"15 from §9\", the root README says 16, the proposal says "
    "\"17 substantive plus two hash-chain\". If asked, count from the dataclass.", S["warn"]))

h1("A10. Runtime: the orchestrator and the world")
diagram_runtime()
bullets([
    f"{c('triage/orchestrator/app.py')} — what the web app calls. Its lifespan hook bootstraps a "
    f"{c('World')} (encounters, R, surge state, audit log, scheduler) and starts a <b>1 Hz tick loop</b> "
    "advancing each encounter against a simulated clock.",
    f"{c('triage/api.py')} — the Track A/B contract app: {c('/score /override /queue /recheck/{id} /surge-status /audit/{id} /demo/arrival')}. "
    "Both apps are live; booting only one and calling the backend verified is a known past mistake.",
    f"{c('web/lib/api/client.ts')} chooses an adapter from {c('NEXT_PUBLIC_MP_SOURCE')}: {c('mock')} (default, "
    f"seeded, in-browser, runs the whole demo offline) or {c('live')} ({c('NEXT_PUBLIC_API_BASE')}). "
    "No page talks to the backend except through this one boundary.",
])
h2("Orchestrator routes (/v1, 21)")
table([
    ["Area", "Routes"],
    ["Status", "GET /v1/config (which perception tier is live, dataLeavesMachine), GET /v1/census, GET /v1/encounter/{id}"],
    ["Scoring", "POST /v1/score, GET /v1/rechecks, POST /v1/decision, POST /v1/encounter/{id}/measurement"],
    ["Surge / control", "GET+POST /v1/surge, POST /v1/control/r, POST /v1/control/clock"],
    ["Audit / live", "GET /v1/audit, GET /v1/stream (SSE)"],
    ["Intake", "POST /v1/intake/submit, POST /v1/intake/tree/start, POST /v1/intake/tree/answer, "
               "GET /v1/intake/tree/structure, GET /v1/intake/tree/{session_id}/answers, POST /v1/intake/tree/match-option"],
    ["Perception", "POST /v1/speech/transcribe, POST /v1/structure"],
], [1.2, 5])

h1("A11. The ML model in depth")
h2("Synthetic data and the label")
bullets([
    f"{c('data/generator/')} produces vitals time series per patient: 15 condition archetypes, restricted "
    "to <b>32 explicitly-defined (condition × stratum) pairs</b> so it never mints e.g. a neonate with "
    "adult trauma physiology. ~163 trajectories/s. 20k-patient training set at seed 1337; a 100k corpus is "
    "zipped in LFS.",
    "<b>Trap avoided:</b> using the per-step severity latent directly as the label gave <b>AUROC 0.988</b> — "
    "the model inverted the generator (each condition's trajectory shape is a constant).",
    "<b>Three structural fixes:</b> (1) the label lives strictly in the future — features use steps ≤ k, "
    "k ~ U[6,18] (30–90 min), label from severity after k; (2) a <b>frailty</b> latent enters the "
    "outcome and never touches a vital, putting a hard floor under Bayes error; (3) the outcome is a "
    "Bernoulli draw, not a threshold.",
])
code("critical_composite_h180 ~ Bernoulli( sigmoid( b0 + 10·s_max_future + 4·s_mean_future + 0.4·frailty ) )\n"
     "b0 solved by bisection for 10% prevalence.  Secondary head: derangement_h60 (continuous).")
para("β values were tuned against a <b>severity-oracle ceiling</b> (a model given the true future peak "
     "severity), not against model performance: β1=10, β3=0.4 → oracle AUROC 0.869.")
h2("Features — 59 columns, fx-v4")
bullets([
    "Per vital (7 vitals × 6 = 42): value, z_stratum, age_minutes, slope_per_hour (OLS, trailing 30 min), "
    "delta_30min, n_readings.",
    "17 global: age, stratum one-hot + ordinal + inferred flag, present/missing/stale counts, reading-age "
    "stats, sensor-failure fraction, aux_derangement_oof.",
    f"<b>One extractor, two adapters</b> — {c('build_feature_row()')} is used by both training "
    f"({c('from_trajectory_snapshot')}) and serving ({c('from_patient_record')}), sharing "
    f"{c('freshness.py')}. A test asserts they agree.",
    "Missing values are <b>NaN, never sentinels</b> — a −999 would turn \"unknown\" into \"extremely "
    "abnormal\". A test proves the NaN branch is actually used.",
    "<b>Modality dropout 40%</b>: trend features were present in 94% of training rows but 0% at serve "
    "time. 40% of rows are now built with history=None. Cost AUROC 0.705→0.689 — a deliberate trade.",
])
h2("Leakage registry — fails closed")
para(f"{c('config/feature_registry.yaml')} classifies every field SAFE / CONDITIONAL / PROHIBITED; "
     f"{c('assert_features_permitted()')} runs at import, and an <b>unregistered name is PROHIBITED</b>, "
     "so adding a generator field without classifying it breaks the build.")
table([
    ["Class", "Examples", "Why"],
    ["PROHIBITED", "condition_id, trajectory_shape, frailty, labels, s_max_future, red_flag_observations, current_band",
     "Generator causes, the label, clinician suspicion (the Epic Sepsis failure), the system's own prior output"],
    ["CONDITIONAL", "spo2_bias_risk (de-escalation guard only), reliability_flags (uncertainty inflation only)",
     "As a risk feature, skin tone would set risk; reliability flags would let a stoic elder's risk fall"],
    ["SAFE", "vital values, z-scores, reading age, slopes, counts, aux_derangement_oof", "Observable at the bench at scoring time"],
], [1.1, 3.0, 3.0])
h2("Model, calibration, thresholds")
bullets([
    f"{c('HistGradientBoostingClassifier')} with a <b>two-stage stack</b>: a regressor predicts "
    "derangement_h60; its out-of-fold prediction is an input to the classifier (sklearn has no multi-task "
    "GBDT — described honestly as a stack, not a shared trunk).",
    "Positives up-weighted <b>3×</b> — deliberately modest; extreme weights wreck calibration. The clinical "
    "asymmetry lives in the threshold, not the loss.",
    "Splits: train 12,000 · calib_iso 2,000 · calib_conf 1,999 · test 4,001. Calibration and conformal "
    "splits are kept apart — reusing rows makes conformal scores in-sample and voids the guarantee.",
    "<b>Platt per stratum</b> (isotonic only above 2,000 rows). Isotonic on small splits gave ECE 0.025 but "
    "reliability slope 0.612; Platt → slope 0.954, ECE 0.011.",
    "<b>Thresholds from a recall budget</b>: p*_yellow from the 10th percentile of predictions among "
    "positives (max green-miss 0.10). Over-triage is reported, never targeted.",
    "<b>Per-stratum Yellow cuts</b> — equalising FNR mathematically requires group-differential thresholds. "
    "Child FNR 0.212→0.077; spread 0.52→0.195. Strata with <20 calibration positives fall back to the global cut "
    "(adolescent, 17).",
])
code("Escalate when  c_FN · p  ≥  c_FP · (1 − p)   ⇒   p* = 1 / (1 + R),   R = c_FN / c_FP\n"
     "Shipped: p*_yellow = 0.076 (R ≈ 12.2),  p*_red = 0.147 (R ≈ 5.8)\n"
     "Default R = USE_TRAINED_R (None): use exactly the operating point solved at training time.")
h2("Conformal uncertainty")
para("Mondrian (per-stratum) split-conformal at α = 0.10. Nonconformity s<sub>1</sub> = 1 − p, "
     "s<sub>0</sub> = p; label set = {y : s<sub>y</sub> ≤ q̂<sub>stratum</sub>}. If both labels survive, "
     "the model cannot rule either out at 90% coverage → abstain. The <b>band</b> is the point decision "
     "from thresholds; the conformal set drives <b>confidence and abstention only</b> (using the set's "
     "highest band once pushed 46% of the department into Red). Paediatric strata with q̂ > 0.5 would "
     "abstain universally, so they fall back to the pooled quantile.")

h1("A12. Evaluation and results")
h2("The eight go-live gates")
table([
    ["#", "Gate", "Rule", "Own split (n=4,001)", "Fresh split (n=20,000, seed 4242)"],
    ["1", "Prevalence in range", "0.05–0.20", "0.098 pass", "0.103 pass"],
    ["2", "AUROC in range (leakage canary)", "0.60–0.95", "0.689 pass", "0.669 pass"],
    ["3", "AUPRC beats prevalence", ">1.5× prev.", "0.174 pass", "0.164 pass"],
    ["4", "Conformal coverage", "≥ 0.90", "0.910 pass", "0.906 pass"],
    ["5", "ECE where reportable", "< 0.05", "0.011 pass", "0.011 pass"],
    ["6", "Green-miss in budget", "≤ 0.15", "0.115 pass", "0.095 pass"],
    ["7", "Equalised FNR spread", "≤ 0.25", "0.195 pass", "0.205 pass"],
    ["8", "Beats hand-coded rule card", "≥1 win, 0 losses", "win @0.50 pass", "win @0.50, loss @0.20 FAIL"],
], [0.3, 2.0, 1.1, 1.4, 1.9])
h2("Risk-engine bake-off (common fresh split, nothing retrained)")
table([
    ["Model", "Train n", "AUPRC", "AUROC", "Green-miss", "FNR spread", "ECE", "Calib slope", "Cov.", "Gates"],
    ["gbdt-v0.2.0 (shipped)", "20k", "0.164", "0.669", "0.095", "0.205", "0.011", "1.16", "0.906", "7/8"],
    ["hist-100k", "100k", "0.157", "0.649", "0.038", "0.145", "0.043", "1.76", "0.899", "6/8"],
    ["hist-mono-100k", "100k", "0.157", "0.667", "0.021", "0.080", "0.035", "1.79", "0.896", "6/8"],
    ["xgboost-100k", "100k", "0.155", "0.647", "0.008", "0.028", "0.073", "0.62", "0.897", "5/8"],
], [1.8, 0.6, 0.6, 0.6, 0.8, 0.8, 0.6, 0.8, 0.6, 0.6], font=7.8)
para("Oracle ceiling on this split: AUPRC 0.408 / AUROC 0.870; prevalence floor 0.103. The shipped "
     "model is the only one that holds conformal coverage ≥ 0.90. XGBoost's beautiful safety numbers are "
     "bought with over-confidence (slope 0.62, ECE 0.073). A fifth artifact (last-obs sequence model) "
     "could not be scored because torch fails to initialise on the dev machine — recorded as excluded.")
h2("Time to detection — the number the product exists for")
bullets([
    "Each of the 20 corpus patients has a 37-step trajectory (T=0…180 min, 5-min steps), re-scored with the "
    "shipped artifact through the same extractor.",
    "16/20 cross Yellow during the wait; continuous re-scoring gets there a <b>mean 21.6 min</b> earlier than "
    "the next scheduled re-measurement (median 17.5, max 55). At Red, mean gain 6.9 min.",
    "Risk engine latency: <b>p50 3 ms</b>, p95 4.3 ms, p99 8.0 ms. Effectively all intake latency is perception.",
])
h2("Honest verdict")
story.append(Paragraph(
    "This is a <b>validated pipeline, not a validated model</b>. AUROC 0.689 against a 0.988 leaked "
    "ceiling and a 0.869 oracle is the signature of a model that learned something real and incomplete "
    "(~42% of achievable AUPRC). Most of the safety gain (green-miss 0.422 → 0.115) came from "
    "threshold design and hard floors, not from the model. No learned model reliably beats the rule card "
    "on a snapshot — which is exactly why the rule card is the floor of the architecture and the model "
    "earns its place by watching trajectories over time.", S["callout"]))

h1("A13. Perception layer — measured, not assumed")
table([
    ["Structurer candidate", "Symptom F1", "Red flags missed", "Schema failures", "Latency (s)"],
    ["groq:openai/gpt-oss-120b (observe)", "0.962", "0", "0", "7.59"],
    ["groq:openai/gpt-oss-20b (match/classify)", "0.816", "4", "4", "8.89"],
    ["local Qwen2.5-7B", "0.653", "7", "0", "5.46"],
    ["local Qwen2.5-3B", "0.650", "8", "0", "6.42"],
    ["local Phi-4-mini", "0.608", "3", "0", "5.65"],
    ["RuleBasedStructurer (not an LLM)", "0.510", "12", "0", "0.00"],
    ["llama-3.3-70b / llama-3.1-8b / kimi-k2", "0.325", "18", "40", "~0.1"],
], [3, 1, 1.1, 1.1, 0.9])
para("Slices: adversarial, ambiguous, negation, Hinglish, prompt-injection, obstetric, paediatric, "
     "stroke, reliability. Key lesson: the biggest instruction-tuned models had 40 schema failures each — "
     "capability and constrained-output compliance are different properties.")
para("<b>ASR (12 backends):</b> groq whisper-large-v3-turbo and local turbo both reach WER 0.000; hosted "
     "0.30 s vs local 1.21 s and 4.94 GB VRAM. faster-whisper large-v3 scored WER 0.583. Caveat: only 2 "
     "reference utterances — it separates the field but does not settle it. Zero silence hallucinations, "
     "guaranteed by a pre-flight RMS silence gate.")
h2("Where the models run")
table([
    ["Tier", "Speech", "Structurer", "Data leaves machine?"],
    ["1 · Local", "faster-whisper (CTranslate2, int8)", "Ollama / llama.cpp (OpenAI-compatible)", "No"],
    ["2 · Hosted free tier", "Groq whisper-large-v3-turbo", "Groq, schema-constrained", "Yes"],
    ["3 · Floor", "none — returns 503", "RuleBasedStructurer — keywords", "No"],
], [1.2, 2, 2.2, 1.2])
para(f"{c('GET /v1/config')} reports the active tier and {c('dataLeavesMachine')} (null before anything "
     "has run), so the demo can never claim local inference it is not performing. There is deliberately "
     "no paid cloud GPU tier: under DPDP 2023, raw patient data should stay at the institution.")

h1("A14. The six invariants and where they are enforced")
table([
    ["#", "Invariant", "Enforcement"],
    ["1", "Asymmetric autonomy — raise freely, never lower below a human band",
     "band_engine raises AsymmetricAutonomyViolation; no downward path in the UI; /control reports moved.down = 0"],
    ["2", "No naked scores — every risk carries confidence and inputs used",
     "AcuityCard throws in dev without confidence / conformalSet / inputsUsed"],
    ["3", "Age is never assumed", "VitalChip refuses a band comparison without a resolved stratum"],
    ["4", "Freshness is part of the value — {value, takenAt, source, validity}",
     "world.py computes validity server-side; >3× cadence renders as missing"],
    ["5", "Abstention is loud, and never Green", "AbstentionCard makes GREEN unrepresentable in the type + runtime guard"],
    ["6", "The human closes every loop", "OverrideDialog one touch from every band; record rendered verbatim on /audit"],
], [0.3, 2.6, 3.6])

h1("A15. Frontend surfaces")
table([
    ["Route", "Surface", "Notes"],
    ["/", "Launcher + showcase", "Dark, mascot allowed"],
    ["/intake", "Patient kiosk", "Warm paper theme, voice + tap, mascot allowed"],
    ["/counter", "Vitals station", "Enter the readings intake asked for (mock-only today)"],
    ["/board", "Nurse board", "Queue, three time facts per card, breaches"],
    ["/card/[id]", "Nurse card", "Band, 2 supporting + 1 opposing factor, confidence; accept / override / discharge"],
    ["/control", "Judge panel", "Live R slider, surge toggle, simulation clock"],
    ["/audit", "Audit ledger", "Override records verbatim, hash chain"],
    ["/hall", "Public waiting display", "Token numbers only — no names, no acuity, no decodable colour"],
], [1, 1.4, 4])
para(f"<b>Mascot law:</b> MediPilot is a pilot, not a nurse — permitted on patient surfaces and banned "
     f"from every clinical decision surface, enforced by a runtime throw in {c('components/mascot/Mascot.tsx')}. "
     "Voice uses webkitSpeechRecognition (Chrome only); every question is also answerable by tap or type.")

h1("A16. Deployment and scalability")
bullets([
    "<b>Serving:</b> one EC2 t3.micro in ap-south-1 (Mumbai), Ubuntu 24.04. Both FastAPI apps run under "
    "systemd (orchestrator :8000, contract :8001); nginx on :80 routes both since paths don't collide; "
    "SSE proxied with buffering off and a 24 h read timeout. Deploy = git pull + pip install + restart.",
    "<b>Known gaps:</b> CORS is hard-coded to localhost:3000; no TLS yet, so an https frontend cannot call "
    "the http backend (mixed content).",
    "<b>Scaling constraint, stated honestly:</b> both apps hold state in process (the World and its tick "
    "loop). Horizontal replication requires externalising state to Postgres + Redis first — adding workers "
    "before that gives a system that looks scaled and silently disagrees with itself.",
    "<b>Tiers a hospital adopts independently:</b> bench box only (offline edge, SQLite, PWA) → + hospital "
    "network tier → + FHIR / CDS Hooks bridge → + regional cloud for federated rounds.",
])

h1("A17. Business case, users, roadmap")
table([
    ["User", "What they get"],
    ["Triage nurse (primary)", "One card: band, two supporting factors, one opposing factor, confidence. One-touch accept/override"],
    ["Patient", "Speaks Hindi/English or taps; never told a colour aloud; real wait estimate"],
    ["Family / attendant", "Can close a Green recheck only; raises a flag for staff"],
    ["Counter staff", "Registration and tokens; sees queue position, never risk"],
    ["Clinical governance", "Audit ledger, override patterns, drift alarms, YAML sign-off"],
], [1.6, 5])
bullets([
    "<b>Wedge:</b> ship the deterioration-while-waiting module alone — highest clinical value, lowest "
    "regulatory exposure, because it never assigns initial acuity; it watches a queue a human already ordered.",
    "<b>Unit economics (illustrative):</b> design target under Rs 5 per encounter at the edge — no GPU, no "
    "per-token cost on the required path. 100 visits/day ≈ Rs 1.8 L/yr; 500/day ≈ Rs 9.1 L/yr.",
    "<b>Value:</b> deterioration caught during the wait; fewer left-without-being-seen; a defensible audit "
    "trail; compounding per-site calibration. Moat = the data relationship, not the model.",
    "<b>Roadmap (exit gates are measurements, not dates):</b> P1 prototype (done) → P2 shadow mode at one "
    "site, externalise state, consent instrument, 8/8 gates on site data → P3 assistive at 5–10 sites, "
    "FHIR bridge, CDSCO SaMD with change-control plan, stepped-wedge trial → P4 federated network.",
    "<b>Regulatory:</b> India — DPDP Act 2023, ABDM consent, ICMR 2023 AI ethics, CDSCO SaMD Class B/C. "
    "ABDM consent for care does not by itself satisfy DPDP for using data as model input.",
])

h1("A18. Known gaps — say them before you're asked")
bullets([
    "No real patient data; every number is measured on a generator built from the team's own assumptions.",
    "Gate 8 fails on the fresh split — no learned model reliably beats the rule card on a snapshot.",
    "Neonate FNR 0.195 on 41 positives, CI 0.075–0.325 — overlaps adult; underpowered, not proven unfair.",
    f"{c('PatientRecord.vitals_history')} is not yet wired through the live API, so trend features are "
    "mostly absent at serve time — the highest-value next lever.",
    f"{c('/queue')} in the contract API sorts on 1 − confidence, not on risk — flagged for re-audit.",
    "OOD gate is currently driven by a seeded flag (force_ood), not a learned density/distance detector.",
    "/counter vitals and discharge endpoints exist in the mock adapter only.",
    "4 of 282 tests fail (3 need a training artifact not in the tree; 1 census-count assertion); "
    "npm run lint hangs.",
    "Two corpus numberings: backend corpus_20.json / proposal (P-01 = deteriorates while waiting) vs "
    "web seed / README (P-05 = hero case). Know which one you are quoting.",
    "Proposal text says per-stratum isotonic; the shipped manifest uses Platt for every stratum (isotonic only "
    "for the pooled calibrator). Quote the manifest.",
])

# ==========================================================================
# PART B — QUESTION BANK
# ==========================================================================
part("Part B — Interview Question Bank")
para("Grouped by interviewer type. Answers are written to be spoken in 30–60 seconds. Where a likely "
     "follow-up exists, it is listed so you can pre-empt it.")

# ---------------------------------------------------------------- B1
h1("B1. Opening and project overview")
qa("Basic", "Walk me through your project in two minutes.",
   ["MediPilot is a continuous re-triage system for Indian emergency departments. Triage today is a single "
    "assessment at the door; the patient then waits in a static queue while their physiology changes. "
    "We built three things: a bilingual talking kiosk that takes a structured history, a risk engine that "
    "scores each patient against their age stratum with a calibrated probability and a conformal confidence "
    "set, and a waiting loop that re-scores everyone every five minutes and escalates automatically.",
    "The core design contract is asymmetric autonomy: the system can raise priority on its own but can never "
    "lower it without a human. The LLM is confined to reporting what the patient said; deterministic rules "
    "and a trained GBDT decide. On our synthetic corpus, continuous re-scoring reaches the Yellow threshold "
    "about 21.6 minutes earlier than the next scheduled vitals check."],
   "\"What was your personal contribution?\" — prepare a concrete 3-item answer.")
qa("Basic", "What problem are you solving, and why does it matter?",
   "Mistriage and deterioration while waiting. Around a third of US ED visits are mistriaged under ESI, and "
   "Indian EDs see 100–500 visits a day, mostly staffed by generalists. The dangerous patient isn't the one "
   "who arrives critical — it's the Yellow who becomes critical twenty minutes later while the nurse is "
   "registering new arrivals. Nobody is watching the corridor; our system is that watcher.")
qa("Basic", "Who is the user?",
   "Primarily the triage nurse, who gets one card per patient with the band, two supporting factors, one "
   "opposing factor and a confidence indicator, plus a one-touch override. Secondary users: the patient at "
   "the kiosk, the family who can close a Green recheck only, counter staff who see tokens not risk, and "
   "clinical governance who own the audit ledger and the YAML config.")
qa("Intermediate", "What is the single most important design decision?",
   "Asymmetric autonomy, enforced in code. An attempt to lower a band without an attached human action "
   "raises AsymmetricAutonomyViolation — a hard error, not a log line. The cost asymmetry justifies it: a "
   "false escalation costs one nurse assessment, a false de-escalation can cost a life. The same asymmetry "
   "shows up everywhere: reliability weighting can only widen uncertainty, SpO2 alone can't justify a "
   "downgrade, patient self-service can escalate but never de-escalate.")
qa("Intermediate", "What makes this different from \"ChatGPT does triage\"?",
   "Our language model structurally cannot produce an acuity. Its output vocabulary is closed — option "
   "values, a fixed set of observation fields, or one of eight red-flag codes. A fixed table maps "
   "observations to meaning, and a calibrated model plus rules assign the band. If the LLM is down, the "
   "system degrades to keyword matching and a deterministic phrase table; it never stops, and it never "
   "lets a generative model decide how sick someone is.")
qa("Basic", "What does the demo show?",
   "Seven clinical surfaces plus a launcher: kiosk, vitals counter, nurse board, nurse card, judge control "
   "panel with a live cost-ratio slider and surge toggle, audit ledger, and a public hall display that "
   "shows token numbers only. A 20-patient synthetic corpus exercises every mandated case: deterioration "
   "while waiting, the paediatric/geriatric 38.5 °C pair, ambiguous epigastric pain, zero history, SpO2 "
   "bias, stale vitals, OOD abstention, a nurse override, and missed rechecks under surge.")

# ---------------------------------------------------------------- B2
h1("B2. Clinical domain and problem framing")
qa("Basic", "What triage scale do you use and why?",
   "The 3-tier AIIMS Triage Protocol — Red, Yellow, Green — because it's the Indian standard adopted by "
   "AIIMS, CMC Vellore, GTB Delhi and Kerala DHS. Internally there's a five-point mapping so the system can "
   "export to ESI-speaking hospitals without retraining.")
qa("Intermediate", "Why do you need six age strata? Isn't age just a feature?",
   ["Because the same number means different things at different ages, in both directions. A 3-year-old "
    "with HR 138 is normal; an adult scale calls it severe tachycardia. A 75-year-old with RR 22.9 and SpO2 "
    "93.5 looks unremarkable on an adult scale but is out of range for age. A single adult model "
    "over-triages children and under-triages elders simultaneously.",
    "So each stratum has its own normal ranges, z-scores computed against those ranges, its own calibrator, "
    "its own conformal quantile and its own Yellow threshold. Age enters through the clinical stratum, never "
    "as a raw demographic discount."],
   "\"What happens when age is unknown?\" — it falls back to the child stratum (widest safety) and the UI "
   "says the stratum is inferred.")
qa("Intermediate", "What are the red flags and why are they rules rather than model features?",
   "Eight observations — altered consciousness, labour or bleeding in pregnancy, chest pain with sweating/"
   "radiation/breathlessness, can't speak full sentences, stroke signs, uncontrolled bleeding or penetrating "
   "injury, poisoning/overdose/snakebite, and an infant not feeding or floppy. They fire before the model "
   "and return Red immediately. They're prohibited as model features because they pre-empt the model "
   "anyway, and because they're the local analogue of what broke the Epic Sepsis Model — learning "
   "clinician suspicion instead of physiology.")
qa("Advanced", "Tell me about the Epic Sepsis Model failure and how you avoid it.",
   "In external validation it scored AUC 0.63 against a marketed 0.76–0.83, with 33% sensitivity and 109 "
   "alerts per true positive. A key reason was leakage: it learned from antibiotic-order timing, i.e. "
   "clinician suspicion, so it detected the process it was meant to augment. We avoid it mechanically: "
   "every field is registered as SAFE, CONDITIONAL or PROHIBITED with its earliest availability time, "
   "unregistered fields are treated as prohibited at import time, and an AUROC above 0.95 fails a go-live "
   "gate as a leakage canary.")
qa("Intermediate", "Why is SpO2 treated specially?",
   "Pulse oximeters under-detect occult hypoxaemia in darker-skinned patients — 11.7% vs 3.6% in one study, "
   "17% vs 6.2% in a multicentre cohort. So a normal SpO2 alone carries no de-escalation authority anywhere "
   "in the system. The guard runs in band_engine before any downward move, even when a human is attached. "
   "And spo2_bias_risk is CONDITIONAL in the registry — usable only by the guard, never as a risk feature, "
   "because then risk would become a function of skin tone.")
qa("Intermediate", "What is the reliability weighting?",
   "Self-report is less reliable for some patients — stoic presentation, communication barrier, low health "
   "literacy, analgesia already given, arriving alone, geriatric stratum. Each has a discount magnitude "
   "(e.g. analgesia 0.45, stoic 0.40). The rule: a discount reduces the weight of a <i>reassuring</i> answer "
   "by widening uncertainty and pushing toward abstention; it never reduces the weight of an alarming "
   "answer. Every applied discount is named on the card so the clinician can reject it. Stoic presentation "
   "is clinician-set only, never inferred.")
qa("Basic", "What is \"freshness\"?",
   "A measurement is {value, takenAt, source, validity}, not just a number. Beyond 2× the band's re-measure "
   "cadence a reading is discounted; beyond 3× it is treated as missing and rendered as missing — a stale "
   "normal reading must never act as reassurance. Reading age is also a SAFE model feature, so staleness is "
   "learned, not only penalised.")

# ---------------------------------------------------------------- B3
h1("B3. System architecture and design")
qa("Basic", "Draw the high-level architecture.",
   "Three tracks with separated authority. Perception (browser STT, Groq Whisper, gpt-oss structurer) may "
   "only report. Interface (Next.js) may only render, talking to the backend through one client with a mock "
   "and a live adapter. Evaluation (FastAPI orchestrator) alone decides: risk_model scores, band_engine "
   "assigns, a 1 Hz World tick loop runs the recheck scheduler and surge controller, the audit log records, "
   "and SSE pushes updates to the board. Two feedback loops close it: five-minute re-scoring, and overrides "
   "plus outcomes becoming training labels.")
qa("Intermediate", "Why a hybrid of rules and ML rather than pure ML?",
   "Because the model is legitimately uncertain exactly where certainty matters most — single-snapshot "
   "extremes it rarely saw in training. We found a peri-arrest patient (HR 190, SBP 60, SpO2 72, GCS 4) that "
   "the model scored Yellow. So rules sit both before the model (red flags, OOD, missing vitals) and after "
   "it (vulnerable-stratum floor, multi-vital floor, critical-derangement floor to Red). The model runs "
   "behind every hard safety guarantee, never in front of one.")
qa("Intermediate", "Why are there two FastAPI apps?",
   "History and separation of concerns. triage/api.py is the original Track A/B contract — /score, "
   "/override, /queue, /recheck, /surge-status, /audit, /demo/arrival. The orchestrator under /v1 is what "
   "the web app actually calls; it owns a simulated World with a tick loop, intake tree sessions, SSE and "
   "control endpoints. Their paths don't collide, so one nginx serves both. The lesson we learned: booting "
   "only one and declaring the backend verified is wrong.")
qa("Intermediate", "Why a mock adapter, and isn't that cheating?",
   "It's insurance and a contract test. The whole demo runs offline in the browser on seeded data, so wifi "
   "or a cold backend can't kill a live presentation. Every page goes through lib/api/client.ts and the "
   "shared types, so switching NEXT_PUBLIC_MP_SOURCE to live changes no UI code. The honest caveat: a "
   "mock-mode screenshot proves nothing about the backend, and a few endpoints — vitals entry and "
   "disposition — exist only in the mock today.")
qa("Advanced", "How does the waiting loop work technically?",
   "The orchestrator's lifespan hook creates a World and an asyncio task that ticks once per second against "
   "a SimClock that the control panel can speed up. Each tick, RecheckScheduler checks every encounter's two "
   "clocks — re-score due, re-measure due — plus its wait ceiling. Re-scores call score_patient_verbose and "
   "pass the result through assign_band, which can only escalate. Breaches emit events; the SurgeController "
   "adjusts cadences; state changes are pushed over SSE to the board.")
qa("Intermediate", "Why Server-Sent Events rather than WebSockets?",
   "Updates are one-directional — server to board. SSE runs over plain HTTP, reconnects automatically in "
   "the browser, and is easy to proxy; we just turn nginx buffering off and set a long read timeout. "
   "Client actions like overrides are ordinary POSTs, which also makes each one an auditable request.")
qa("Advanced", "Where is the configuration surface and why YAML?",
   "backend/config: red_flags, band_cadence, age_strata, surge_policy, feature_registry, label_spec. These "
   "are clinical decisions, and in a real deployment each would be signed off by clinical governance, so "
   "they shouldn't require a code change or redeploy of logic. label_spec is hashed into the artifact "
   "manifest, so changing it invalidates every trained model — intentionally.")
qa("Advanced", "What's a subtle engineering trap in this codebase?",
   "Config paths are __file__-relative with hard-coded parent counts. Moving one .py file to a different "
   "depth breaks config loading at runtime, not import time, so green imports and passing collection prove "
   "nothing. We moved whole subtrees during the restructure, never lone files. Another: Python packages are "
   "top-level import roots under backend/, so pytest and uvicorn must run from backend/.")

# ---------------------------------------------------------------- B4
h1("B4. Safety invariants")
qa("Basic", "List the six invariants.",
   "1) Asymmetric autonomy. 2) No naked scores — every risk value carries confidence and the inputs used. "
   "3) Age is never assumed. 4) Freshness is part of the value. 5) Abstention is loud and never Green. "
   "6) The human closes every loop — override is one touch from every band.")
qa("Intermediate", "How do you guarantee \"no naked scores\" on the frontend?",
   "AcuityCard throws in development if it's rendered without confidence, conformalSet or inputsUsed, so a "
   "bare number can't reach a screen even by mistake. AbstentionCard's type makes GREEN unrepresentable, "
   "with a runtime guard behind it. And the mascot component throws if it's rendered on a clinical route.")
qa("Intermediate", "What does abstention look like and why is it never Green?",
   "When the conformal set contains both outcomes at 90% coverage, or the patient is out of distribution, "
   "or all vitals are missing, the system returns an AbstentionObject: no colour offered, the patient held "
   "at the Yellow floor, routed to a human, and a 15-minute unmet-review breach. Green would mean "
   "\"safe to wait\" — a claim the system just said it can't make.")
qa("Advanced", "Could a bug still lower a band? How would you know?",
   "The only path that changes a band is assign_band, and a downward move without last_human_action raises. "
   "There are invariant tests that try exactly that and expect the exception; the /control panel reports "
   "moved.down which is structurally zero. Residual risk: code that bypasses assign_band and writes state "
   "directly — mitigated by keeping band writes inside the World and covering them with contract tests. "
   "I'd add a property-based test that random event sequences never produce a downward autonomous transition.")
qa("Intermediate", "What happens under surge that you refuse to do?",
   "Three things raise SurgeViolation: raising the cost ratio R to reduce alarm volume, resolving an "
   "abstention by guessing, and de-escalating anyone to free capacity. What we do allow: Yellow re-measure "
   "stretches 30→45 min and Green 60→90; Red never stretches; alerts are ranked by risk × minutes waiting "
   "and never suppressed.")

# ---------------------------------------------------------------- B5
h1("B5. Machine learning — data, features, model")
qa("Basic", "What model do you use?",
   "scikit-learn HistGradientBoostingClassifier, version medipilot-gbdt-v0.2.0, trained on 20,000 synthetic "
   "patients with 59 features. It's a two-stage stack: a regressor predicts a 60-minute derangement score, "
   "and its out-of-fold prediction becomes one input to the classifier predicting a critical event within "
   "180 minutes. It's followed by per-stratum Platt calibration, per-stratum thresholds and Mondrian "
   "conformal prediction.")
qa("Intermediate", "Why gradient-boosted trees and not a neural network?",
   "Tabular data with missing values, a small positive count (~1,170 training positives), a need for "
   "millisecond CPU inference at the edge, and good calibration behaviour. HistGBDT handles NaN natively by "
   "learning a missing direction per split, which matters because a missing vital must not be imputed as "
   "abnormal. Practically, torch also failed to initialise on our AMD dev machine, and a GRU/TCN sequence "
   "track exists but couldn't be scored there.")
qa("Advanced", "How did you generate labels without real data, and how did you avoid making it trivial?",
   ["The naive label — the generator's own severity latent — gave AUROC 0.988 because the model just "
    "inverted the generator; each condition's trajectory shape is a constant. Three fixes: the label is "
    "strictly in the future of the features (features up to step k, k between 30 and 90 minutes; label from "
    "severity after k); a frailty latent affects the outcome but never touches a vital, so Bayes error has a "
    "hard floor; and the outcome is a Bernoulli draw from a logistic of future peak and mean severity plus "
    "frailty.",
    "β coefficients were tuned against a severity-oracle ceiling — a model given the true future severity — "
    "not against our model's score. The oracle reaches AUROC 0.869, so that's the realistic ceiling."],
   "\"Isn't synthetic evaluation circular?\" — yes for clinical claims; it validates the pipeline, not the "
   "model. See B14.")
qa("Intermediate", "Describe the features.",
   "Six per vital for seven vitals: raw value, z-score against the stratum's own normal range, reading age "
   "in minutes, slope per hour over the trailing 30 minutes, 30-minute delta, and count of readings. Plus 17 "
   "global features — age, stratum one-hot, present/missing/stale counts, reading-age statistics, "
   "sensor-failure fraction, and the auxiliary head's out-of-fold prediction. The trend block is what "
   "makes deterioration visible at all.")
qa("Advanced", "You tried shock index, ROX and NEWS-style aggregates. What happened?",
   ["All three variants were net negative: the 68-feature set dropped AUPRC 0.174→0.155 and calibration "
    "slope 0.954→0.826. My first hypothesis — the generator lacks HR/SBP coupling — was wrong; corr(HR, SBP) "
    "was −0.74. The real cause was collinearity: shock index correlates +0.91 with HR and −0.85 with SBP, so "
    "it re-expressed information the trees already had and added variance on a small positive count.",
    "In real cohorts those indices earn their place because the risk surface is non-linear in the components. "
    "So the standing instruction is: don't re-add them against this generator; revisit on real data."])
qa("Advanced", "What is train/serve skew in your system and how did you fix it?",
   "Two kinds. Code skew: solved by one feature extractor with two adapters and a test that they agree. "
   "Distribution skew, which the single extractor didn't catch: trend features were populated in 94% of "
   "training rows but 0% at serve time, because intake usually sends a single snapshot. We added 40% "
   "history dropout during training. AUROC fell 0.705→0.689, but the model now beats the baseline in both "
   "regimes. The real fix is wiring vitals_history through the live API.")
qa("Intermediate", "How do you handle missing data?",
   "As NaN, never a sentinel. A −999 or 0 would be split on as an extreme value, turning \"unknown\" into "
   "\"severely abnormal\" or \"normal\". HistGBDT learns which way missing values should go at each split, "
   "and a test proves that branch is actually exercised. Counts of missing and stale vitals are also "
   "explicit features.")
qa("Advanced", "Feature pruning improved your validation score. Why didn't you ship it?",
   "Permutation importance on the ~2,000-row calibration split showed half the features at ≤0 importance; "
   "pruning raised calibration-split AP 0.183→0.211 but lowered test AUPRC 0.174→0.165 and wrecked the "
   "calibration slope. Selecting features on 2,000 rows with ~195 positives selects noise, and the gain was "
   "measured on the same split the selection overfit to. An improvement measured on the split used to make "
   "the decision isn't proven; it must be confirmed on untouched test data. Pruning is now an off-by-default flag.")
qa("Intermediate", "Why only 3× positive weighting if a missed critical is 100× worse?",
   "Because extreme sample weights destroy probability calibration, and both the conformal layer and the "
   "thresholds depend on calibrated probabilities. We keep the loss mildly asymmetric and put the clinical "
   "asymmetry in the decision threshold, p* = 1/(1+R), where it's explicit, auditable and tunable per site.")
qa("Intermediate", "How do you prevent data leakage between patients across splits?",
   "patient_id is registered as PROHIBITED with permitted use split_key — splits are by patient. The bake-off "
   "also uses a freshly generated population at a different seed (4242 vs training 1337), so no artifact has "
   "ever seen any evaluation row.")

# ---------------------------------------------------------------- B6
h1("B6. Calibration, thresholds and uncertainty")
qa("Intermediate", "Why does calibration matter here?",
   "The nurse sees a probability and a confidence band, and the thresholds are defined on probabilities. If "
   "0.2 doesn't mean a 20% chance, the cost-ratio maths is wrong and the confidence is decorative. It's also "
   "why each site re-fits calibration during shadow mode — a model calibrated in Patna isn't calibrated in "
   "a district hospital in Bihar.")
qa("Advanced", "Why Platt rather than isotonic?",
   "Isotonic regression is non-parametric and overfits below roughly 2,000 calibration cases; our "
   "per-stratum splits are far smaller. The symptom was subtle: ECE looked fine at 0.025, but the reliability "
   "slope was 0.612 — systematic over-dispersion that ECE hides. Two-parameter Platt fixed it: slope 0.954, "
   "ECE 0.011. Isotonic is only used when a split clears 2,000 rows, which today is the pooled calibrator.",
   "\"Why look at slope as well as ECE?\" — ECE averages absolute error across bins and can hide a "
   "systematic tilt; slope and intercept expose it.")
qa("Advanced", "Explain the cost ratio R.",
   "Escalating is the right call when the expected cost of missing, c_FN·p, exceeds the expected cost of a "
   "false alarm, c_FP·(1−p). That gives p* = 1/(1+R) with R = c_FN/c_FP. R is a per-hospital parameter set "
   "by clinical leadership, not a vendor constant. Our trained operating point solves p*_yellow = 0.076 "
   "(R ≈ 12) and p*_red = 0.147 (R ≈ 5.8). The control panel slider changes R and the queue re-sorts live.")
qa("Advanced", "Your first model left 42% of critical patients in Green. What went wrong?",
   "Three separate bugs, each enough on its own. One: thresholds were set from the band mix — the 70th "
   "percentile of all predictions — instead of a recall budget; now p*_yellow comes from the 10th percentile "
   "among positives. Two: the band was taken as the highest label in the conformal set, which pushed 46% of "
   "patients to Red; now the band is the point decision and the set only drives confidence. Three: the "
   "R-to-threshold function inverted the ordering, and a hard-coded default R = 2 silently overrode the "
   "trained operating point. Green-miss went 0.422 → 0.115, mostly through thresholds, not modelling.")
qa("Advanced", "Why per-stratum thresholds? Isn't that unfair?",
   "It's the opposite. If score distributions differ between groups — and they do, each stratum has its own "
   "calibrator — a single global cut gives equal scores but unequal miss rates. Equalising false-negative "
   "rate mathematically requires group-specific thresholds. Child FNR went 0.212 → 0.077 and the spread "
   "0.52 → 0.195. Strata with fewer than 20 calibration positives fall back to the global cut.")
qa("Advanced", "Explain your conformal prediction setup.",
   ["Mondrian split-conformal at α = 0.10, meaning the coverage guarantee holds within each age stratum, not "
    "just on average. On a held-out conformal split we compute nonconformity scores — 1−p for a true "
    "positive, p for a true negative — and take the stratum's (1−α) quantile q̂. At serve time the label "
    "set is every class whose nonconformity is ≤ q̂. If both classes survive, the model can't rule either "
    "out at 90% and it abstains.",
    "Coverage 0.910 with mean set size 1.08 — the guarantee holds while the set stays informative. Coverage "
    "alone is gameable: always returning every band gives perfect coverage and zero value."],
   "\"What assumption does conformal need?\" — exchangeability between calibration and test data; that "
   "breaks across sites and over time, hence per-site recalibration and drift watchdogs.")
qa("Intermediate", "What's the difference between confidence, calibration and abstention in your system?",
   "Calibration makes the probability honest. Confidence on the card is derived from the conformal set width "
   "and how close the probability sits to a threshold, inflated by reliability discounts, stale readings or "
   "an inferred stratum. Abstention is the terminal state when the conformal set can't exclude either outcome "
   "or the patient is OOD — no recommendation, routed to a human.")

# ---------------------------------------------------------------- B7
h1("B7. Evaluation and metrics")
qa("Basic", "Why not report accuracy?",
   "At ~10% prevalence, predicting \"not critical\" for everyone is 90% accurate and kills every critical "
   "patient. The governing metric is under-triage at a fixed over-triage rate — how many critical patients "
   "stay below Yellow at the false-alarm load the department can tolerate. We also report AUPRC, which is "
   "sensitive to the rare class, alongside AUROC.")
qa("Intermediate", "What are the eight go-live gates?",
   "Prevalence in range; AUROC in 0.60–0.95, where above 0.95 is a leakage alarm; AUPRC above 1.5× "
   "prevalence; conformal coverage ≥ 0.90; ECE < 0.05 where reportable; green-miss ≤ 0.15; FNR spread across "
   "strata ≤ 0.25; and beating the hand-coded rule card with at least one significant win and no losses. "
   "The shipped model passes 8/8 on its own 4,001-row split and 7/8 on the fresh 20,000-row split.")
qa("Intermediate", "Your AUROC is 0.67–0.69. Isn't that bad?",
   "Against what ceiling? The oracle that knows the true future severity gets 0.869, the leaked label gets "
   "0.988, and prevalence is ~0.10. We capture about 40–42% of achievable AUPRC. That's the signature of a "
   "model that learned something real but incomplete on a deliberately hard generator — and anything above "
   "0.95 would fail our own gate as leakage. We'd rather show an honest 0.69 than a suspicious 0.98.")
qa("Advanced", "How do you compare against the baseline rigorously?",
   "Under-triage is compared at four matched over-triage rates (0.10, 0.20, 0.30, 0.50) with bootstrap 95% "
   "CIs; a win or loss counts only where the intervals separate, otherwise it's a tie. On the shipped split "
   "the model wins at 0.50 (0.210 vs 0.399 misses) and ties elsewhere; on the five-times-larger fresh split "
   "the intervals tighten and a loss at 0.20 becomes significant, so gate 8 fails. We report the stricter result.")
qa("Advanced", "Why did you build a fresh evaluation split for the bake-off?",
   "Each artifact had held out a different sample — 4,001 rows from 20k for the shipped model, 20,001 from "
   "100k for the others — so comparing them on their own splits isn't a leaderboard. Replaying the training "
   "seed would hand models back their own rows. A new population at seed 4242 means every row is unseen by "
   "every model.")
qa("Intermediate", "The 100k XGBoost has a green-miss of 0.008. Why didn't you ship it?",
   "It buys that by being systematically over-confident: calibration slope 0.62 and ECE 0.073, roughly seven "
   "times ours, and its conformal coverage falls below the 90% it promises. It escalates nearly "
   "indiscriminately, which lowers misses and destroys the meaning of the number on the card. A confidence "
   "band that doesn't cover at its stated rate is worse than no band.")
qa("Intermediate", "How did you measure the product's actual value — earlier detection?",
   "Every corpus patient has a 37-step trajectory. We rebuilt the feature row at each 5-minute step through "
   "the same extractor, scored it with the shipped artifact, and compared the first tick crossing the "
   "threshold with the first scheduled physical re-measurement after it. 16 of 20 cross Yellow; mean head "
   "start 21.6 minutes, median 17.5, max 55. Patients who crossed at T=0 gain nothing and we don't claim them.")
qa("Intermediate", "How do you measure fairness?",
   "Equalised false-negative rate across the six age strata, with bootstrap CIs and positive counts, never a "
   "bare max-minus-min gap. Spread is 0.195; neonate is worst at 0.195 on 41 positives with CI 0.075–0.325, "
   "which overlaps adult's 0.097–0.210. So the neonate gap isn't yet statistically distinguishable — the "
   "honest claim is \"underpowered\", and the Phase 2 exit gate is narrowing that interval.")
qa("Basic", "How is the system tested?",
   "282 pytest tests, of which 278 pass. They encode clinical constraints: 15 invariant tests, 10 on age "
   "stratification, 10 replaying corpus acceptance cases, 8 surge, 7 band engine, 6 audit log, 6 reliability, "
   "plus a leakage canary and train/serve agreement tests. The four failures are pre-existing — three need "
   "a training artifact that isn't committed, one is a stale census-count assertion. The web intake has a "
   "118-fixture self-test endpoint covering multilingual matching, negation and adversarial model responses.")

# ---------------------------------------------------------------- B8
h1("B8. LLM, NLP and speech")
qa("Basic", "Which LLMs do you use, and for what?",
   "Via Groq: gpt-oss-120b for observation extraction — pulling volunteered facts and red-flag codes from "
   "free text — and the cheaper gpt-oss-20b for branch classification and option matching. Both chosen from "
   "a ten-candidate bake-off. gpt-oss-120b had symptom F1 0.962 with zero red flags missed; the 20b missed "
   "two on paediatric cases, which is exactly why it's confined to matching and classification.")
qa("Intermediate", "How do you stop the LLM from making clinical judgements?",
   "Three layers. The prompt asks for a closed vocabulary. The server validator enforces it — any value "
   "that isn't one of the offered options becomes NONE, and red flags must be from the fixed eight codes. "
   "And architecturally nothing downstream reads an acuity from the LLM — there's no field for it. The LLM "
   "is never asked what an answer means clinically.")
qa("Advanced", "How do you handle prompt injection?",
   "Injection is one of the bake-off slices; gpt-oss-120b missed no red flags there. But the real defence is "
   "structural: even a fully hijacked model can only return an option value, NONE, or a subset of eight "
   "codes. A red-flag code can only escalate. It cannot lower a band, produce a band, or reach the scorer "
   "as anything other than a validated field. The worst case is a spurious escalation, which costs a nurse "
   "assessment.")
qa("Intermediate", "Why did the biggest models do worst in your bake-off?",
   "llama-3.3-70b, llama-3.1-8b and kimi-k2 each had 40 schema failures — they wouldn't emit the constrained "
   "format at all, so F1 collapsed to 0.325. Capability and constrained-decoding compliance are different "
   "properties. Buying the biggest model would have been the wrong decision; measuring was the right one.")
qa("Intermediate", "How does Hindi / Hinglish support work?",
   "Browser speech recognition with Hindi and English locales, then three-tier matching. Tier 0 is an exact "
   "lexicon for yes/no and 0–10 in English, Devanagari and romanised Hinglish. Tier 1 is similarity over "
   "labels, value slugs and per-option synonyms plus edit-distance rescue for ASR near-misses. Only then "
   "tier 2 calls the LLM. The red-flag phrase table is bilingual too, with a negation set.")
qa("Intermediate", "How did you choose the speech model?",
   "A 12-backend bake-off measuring WER, CER, language accuracy, silence hallucinations, latency and VRAM. "
   "Groq whisper-large-v3-turbo and local turbo both scored WER 0; hosted was 0.30 s vs 1.21 s local with "
   "4.94 GB VRAM. faster-whisper large-v3 scored 0.583 despite looking good on paper. The honest caveat is "
   "only two reference utterances — it separates the field but doesn't settle it.")
qa("Advanced", "What happens when Groq is down or the key is missing?",
   "Everything degrades, nothing stops. Classification falls back to the keyword table, matching asks the "
   "patient to pick from buttons, and tier-A red flags still fire deterministically offline. On the backend, "
   "the structurer chain falls back to RuleBasedStructurer, which is explicitly labelled as not an LLM, and "
   "/v1/config reports which tier is live. Every fallback is logged at WARNING and named in the response.")
qa("Intermediate", "Why not run the LLM locally for privacy?",
   "That's the destination — tier 1 runs faster-whisper and an Ollama/llama.cpp model with no data leaving "
   "the machine, switched by one environment variable. But the dev laptop has a 4 GB AMD GPU with no CUDA "
   "and no Windows ROCm, so 7B models don't fit and local candidates had F1 around 0.65 versus 0.96 hosted. "
   "For a prototype demo we use the free hosted tier; in a hospital, inference moves inside under DPDP.")

# ---------------------------------------------------------------- B9
h1("B9. Backend engineering")
qa("Basic", "Why FastAPI?",
   "Pydantic-typed request/response contracts that double as documentation, native async for the tick loop "
   "and SSE, automatic OpenAPI, and it's Python — the same language as the model, so scoring is an in-process "
   "function call with 3 ms p50 latency rather than a network hop.")
qa("Intermediate", "How is the audit log tamper-evident?",
   "Each record stores the SHA-256 hash of its own content and the hash of the previous record. Changing any "
   "past record changes its hash and breaks every link after it, so verification is a linear walk. It's "
   "append-only: consent withdrawal and outcome back-fill are new events, never edits. inputs_hash freezes "
   "the input state so any decision is reproducible.")
qa("Advanced", "Hash-chaining detects tampering, but what stops someone rewriting the whole chain?",
   "Nothing, on its own — a chain proves internal consistency, not authenticity. In production you'd anchor "
   "the head hash externally: periodically sign it with a key held by governance, publish it to a write-once "
   "store or a separate system, or use an append-only database with restricted credentials. That's a known "
   "next step, not something the prototype claims.")
qa("Intermediate", "How does the backend fail when the model artifact is broken?",
   "model/artifact.py checks the artifact exists, the sklearn version matches the manifest, and the feature "
   "spec matches the live extractor's FEATURE_VERSION. On any mismatch it degrades to the frozen AIIMS-ATP "
   "rule card and stamps score_source as fallback_heuristic. The predictor never raises into the triage "
   "path. There's a test procedure: delete the artifacts folder and confirm all tests still pass on fallback.")
qa("Advanced", "Is the orchestrator's in-memory state a problem?",
   "Yes, for scale and durability. The World — encounters, scheduler, surge state, audit log — lives in one "
   "process with an asyncio tick loop. Two uvicorn workers would each have their own World and silently "
   "disagree. Phase 2 starts by externalising state to Postgres for durable records and Redis for the "
   "scheduler and pub/sub, and making the tick loop a single leader-elected worker.")
qa("Intermediate", "How do you version models?",
   "Each artifact directory has a manifest: model version, calibration version, conformal version, feature "
   "version, sklearn version, dataset hash and seed, split sizes, calibration method per stratum, solved "
   "thresholds and the label spec. current.txt points to the live one. Every audit record stores the model "
   "and calibration versions in effect, so any decision can be traced to the exact model.")

# ---------------------------------------------------------------- B10
h1("B10. Frontend engineering")
qa("Basic", "What's the frontend stack?",
   "Next.js 16 App Router, React 19, strict TypeScript, Tailwind v4, motion for animation, and react-three-"
   "fiber/drei for the 3D kiosk and mascot scenes. Groq calls go through server-only route handlers under "
   "app/api/intake so the key never reaches the browser.")
qa("Intermediate", "How is the intake conversation structured in code?",
   "As data, not components. Each of 16 branches is a typed question list; engine.ts walks it, skips "
   "questions already answered, and appends a universal tail. IntakeApp.tsx drives ten steps over a reducer-"
   "style session. Voice, matching and red-flag detection are separate modules. Adding a question is a row "
   "edit in a branch file.")
qa("Intermediate", "How do you keep the Groq key secret?",
   "It's read only in server route handlers and has no NEXT_PUBLIC_ prefix — Next.js inlines only "
   "NEXT_PUBLIC_ variables into client bundles. The browser calls our own /api/intake/* endpoints, which "
   "validate inputs and outputs before anything returns.")
qa("Intermediate", "What design choices protect patients on the public screens?",
   "The hall board shows token numbers only — no names, no acuity, no colour a family could decode. The "
   "kiosk never announces a band aloud. When a red flag fires, clinical questions stop and a nurse is called, "
   "but no acuity word appears on the patient's screen. The mascot is banned from clinical surfaces by a "
   "runtime throw — a friendly avatar must not manufacture clinical authority.")
qa("Intermediate", "What about browsers without speech recognition?",
   "Voice uses webkitSpeechRecognition, which only Chrome implements. Every question is answerable by tap or "
   "typing, so Firefox, Safari or a denied microphone degrades the experience rather than blocking it.")
qa("Intermediate", "How do you explain a score to the nurse?",
   "Three explainability channels on the card: the two strongest supporting factors, one opposing factor, "
   "and the confidence band with the inputs used and any reliability discounts. The opposing factor is "
   "deliberate — it forces the nurse to engage with reasoning rather than a number, the standard defence "
   "against automation bias.")

# ---------------------------------------------------------------- B11
h1("B11. Deployment, DevOps and scalability")
qa("Basic", "How is it deployed?",
   "Backend on a single AWS EC2 t3.micro in ap-south-1 (Mumbai), Ubuntu 24.04. Both FastAPI apps run as "
   "systemd services, and nginx on port 80 routes to both since their paths don't overlap. SSE is proxied "
   "with buffering off. The frontend can run locally pointing NEXT_PUBLIC_API_BASE at the instance.")
qa("Intermediate", "Why such a small instance?",
   "The required path has no GPU and no heavy inference: the risk engine is millisecond-latency trees on CPU, "
   "and perception runs on Groq. Two Python processes with numpy/scipy/sklearn fit, which also demonstrates "
   "the economic claim — the decision core runs on commodity hardware.")
qa("Intermediate", "What would block production use of that deployment today?",
   "No TLS, so an https frontend hits mixed-content errors; CORS hard-coded to localhost; in-process state; "
   "no auth on clinician endpoints; and a single instance with no redundancy. All known and listed.")
qa("Advanced", "How would you scale to 50 hospitals?",
   "Per-site deployment is the default, not a giant central service: each hospital runs its own bench box or "
   "hospital tier, with its own calibration and thresholds, so latency and privacy stay local. Within a site, "
   "externalise state to Postgres + Redis and run stateless API workers with one scheduler leader. Across "
   "sites, federated learning with secure aggregation shares only model updates, with per-site drift "
   "watchdogs. Integration via FHIR and CDS Hooks so the card appears inside the existing EHR.")
qa("Intermediate", "How would you monitor the model in production?",
   "Override rate and direction by stratum and reason code; abstention rate; band mix; calibration drift "
   "once outcome_ref is back-filled; input distribution drift per feature; and fallback rate. The eight gates "
   "re-run on rolling site data become alarms. Shadow mode first — score silently for weeks before showing "
   "anything.")

# ---------------------------------------------------------------- B12
h1("B12. Privacy, security and regulation")
qa("Basic", "Which jurisdiction and regulations did you design for?",
   "India: the DPDP Act 2023, ABDM/ABHA consent framework, ICMR's 2023 AI ethics guidance, and CDSCO's "
   "Software-as-a-Medical-Device pathway, likely Class B/C, with a predetermined change control plan so "
   "retraining doesn't require resubmission.")
qa("Intermediate", "Isn't ABDM consent enough for training?",
   "No. ABDM consent for care delivery doesn't by itself satisfy DPDP for using the same data as model input "
   "— different purposes require separate, revocable consent. That's the largest regulatory item on our "
   "roadmap. In the prototype, a patient who declines to share history is triaged without penalty.")
qa("Intermediate", "Where does patient data go?",
   "In the local tier, nowhere — local ASR, offline matching, deterministic structurer, no outbound request. "
   "In the hosted demo tier, audio and transcript go to Groq, which /v1/config reports as "
   "dataLeavesMachine: true. Cross-site learning would be federated: weights travel, patient data doesn't. "
   "Also, no personal data is ever placed in URL parameters, and the hall display shows tokens only.")
qa("Advanced", "Is this a medical device? How would you get it approved?",
   "Yes — software that influences triage priority is SaMD. Our wedge reduces exposure: the deterioration-"
   "while-waiting module never assigns initial acuity; it only watches a queue a human already ordered and "
   "can only escalate. Path: retrospective validation, ethics approval, shadow mode, then an assistive "
   "deployment with a stepped-wedge cluster-randomised trial — not a pre/post comparison — and a CDSCO "
   "submission with a change control plan.")
qa("Intermediate", "What security issues would you fix first?",
   "Authentication and role-based authorisation on override and control endpoints (the audit record already "
   "stores clinician_role), TLS everywhere, configurable CORS, secrets management instead of .env files, "
   "external anchoring of the audit chain head, and rate limiting on the LLM proxy routes.")

# ---------------------------------------------------------------- B13
h1("B13. Product and business")
qa("Basic", "What's your go-to-market wedge?",
   "Ship the deterioration-while-waiting module alone. It has the highest clinical value and the lowest "
   "regulatory exposure, requires zero workflow change because it never assigns initial acuity, and is "
   "measurable from day one through left-without-being-seen rates and in-queue deterioration.")
qa("Intermediate", "What does it cost?",
   "An illustrative model, not measured revenue: the design target is under Rs 5 per encounter at the edge, "
   "because the required path has no GPU and no per-token cost. That's about Rs 1.8 lakh a year for a "
   "100-visit district hospital and Rs 9.1 lakh for a 500-visit tertiary centre.")
qa("Intermediate", "Where does the value come from if you don't replace staff?",
   "Deterioration caught during the wait, avoiding ICU escalations; fewer patients leaving without being seen "
   "because Green patients get honest wait estimates; a defensible audit trail as a liability asset; and "
   "compounding calibration across sites.")
qa("Intermediate", "What's the moat? Someone could rebuild this in a year.",
   "The stack, yes. Not years of site-specific calibration and federated override history across many Indian "
   "EDs. Every override with a back-filled outcome is a training label competitors can't buy. The moat is the "
   "data relationship, not the model.")
qa("Intermediate", "How do you get nurses to trust and adopt it?",
   "Zero workflow change to start; shadow mode where they compare its judgement with theirs before it shows "
   "anything; an opposing factor on every card; visible abstention on the cases it can't judge; one-touch "
   "override that is never punished; and no virtual-nurse persona.")
qa("Intermediate", "How would you adapt it to a new hospital?",
   "Site parameters, not code: cost ratio R (tertiary centres nearer 500, district hospitals nearer 100), "
   "normal arrival rate for surge detection, band cadences, the red-flag table, stratum normal ranges, "
   "per-site calibration re-fitted in shadow mode, and SpO2 pallor calibration. Go-live requires 8/8 gates "
   "on that site's own data.")

# ---------------------------------------------------------------- B14
h1("B14. Hard, critical and trap questions")
qa("Advanced", "Everything is synthetic. Why should I believe any of it?",
   "You shouldn't believe any clinical claim, and we make none — SIMULATED DATA is on every screen. What the "
   "synthetic work validates is the pipeline: that leakage controls, calibration, conformal abstention, "
   "cost-sensitive thresholds, the safety invariants and the waiting loop are wired correctly end to end. "
   "The generator is physiologically parameterised and deliberately hard, with an oracle ceiling reported. "
   "Real validation is MIMIC-IV-ED for architecture, then partner-hospital shadow mode.")
qa("Advanced", "Your model fails to beat the hand-coded rule card. Why have a model at all?",
   "That's our most important result, and we report it rather than hide it. On a snapshot, a good rule card "
   "is hard to beat — so it's the floor of the architecture, and a model that adds nothing subtracts nothing. "
   "The model earns its place temporally: re-scoring trends every five minutes, which a rule card applied at "
   "the door structurally can't do. The time-to-detection result is the model's real contribution, and "
   "Phase 3 must prove it in a trial.")
qa("Advanced", "Most of your safety improvement came from thresholds, not the model. Isn't the ML decorative?",
   "It's accurate that green-miss fell 0.422 → 0.115 mostly through threshold design and floors. That's a "
   "lesson worth stating: in safety-critical ML, the decision layer matters as much as the score. But the "
   "thresholds need a calibrated, ranked probability to act on, and the per-stratum fairness gain depends on "
   "per-stratum calibrators. They're complementary.")
qa("Advanced", "Your OOD gate is a flag in the seed data. Isn't that fake?",
   "In the prototype, yes — the OOD path is wired end to end (abstention object, Yellow floor, 15-minute "
   "breach, UI) but the trigger is a seeded flag rather than a learned detector. The right detector would be "
   "a density or distance score on the feature space — e.g. Mahalanobis or isolation forest per stratum, "
   "calibrated so a fixed fraction of in-distribution data is flagged. I'd rather say that than imply it exists.")
qa("Advanced", "Your docs disagree with each other. Which is right?",
   "The code and committed artifacts. Examples: the audit record is 16 required + outcome_ref + 2 chain "
   "fields — docs say 15, 16 or \"17 plus 2\" depending on which field set they count; the shipped "
   "calibration is Platt per stratum per the manifest even though some prose says isotonic; and there are two "
   "corpus numberings — backend corpus_20.json versus the web seed. Every quantitative claim in the "
   "proposal traces to a file in docs/benchmarks or the artifact folder for exactly this reason.")
qa("Advanced", "What if the system over-escalates and floods the nurses?",
   "Over-triage is the price we explicitly accept, but it's measured and bounded. R is set by clinical "
   "leadership; the threshold is solved for a green-miss budget and over-triage is reported. Under surge we "
   "stretch Yellow and Green re-measure cadences and rank alerts by risk × wait, rather than raising R — "
   "raising R to quieten alarms is forbidden. The honest weakness: escalation-only means a single noisy "
   "high reading ratchets priority up and only a human can bring it back down. That's safe but costs nurse "
   "time; a fix I'd test is requiring two consecutive above-threshold re-scores for model-only escalations, "
   "while red flags and critical floors stay instant.")
qa("Advanced", "What's the worst failure mode you can think of?",
   "Automation bias in the other direction: a nurse trusting a Green and not looking. Mitigations are the "
   "opposing factor, visible confidence, abstention, and the fact that Green still has a 60-minute re-measure "
   "and 120-minute ceiling. The second is silent drift at a new site — handled by per-site calibration and "
   "gates on site data. The third is a perception miss of a red flag, which is why tier A runs offline and "
   "deterministically regardless of the LLM.")
qa("Advanced", "Neonates have the worst FNR. Isn't that a fairness failure?",
   "The point estimate is worst, 0.195, but on 41 positives the CI is 0.075–0.325 and overlaps the adult "
   "interval. Claiming a gap would overstate the data as much as denying one. Mitigations today: neonates "
   "have the highest calibration weight, an abnormal-vital floor to Yellow, RF-08 for floppy/not-feeding, and "
   "a per-stratum threshold. The Phase 2 exit gate is narrowing that CI below the adult point estimate via a "
   "paediatric data partnership.")
qa("Intermediate", "What would you do differently if you started again?",
   "Wire the vitals history through the live API from day one so trend features are present at serve time; "
   "externalise state before building features on top of an in-memory World; build a real ASR reference "
   "corpus earlier — two utterances is too thin; and keep docs generated from artifacts so counts can't drift.")
qa("Advanced", "How would you validate on real data?",
   "Phase A: MIMIC-IV-ED to validate the architecture — leakage controls, calibration, conformal coverage, "
   "fairness reporting — with no claim about Indian patients. Phase B: a partner hospital's retrospective "
   "export with an outcome label from admission, discharge and billing records. Phase C: shadow mode to "
   "re-fit calibration and thresholds and pass 8/8 gates on site data. Phase D: stepped-wedge cluster-"
   "randomised trial of in-queue deterioration.")
qa("Advanced", "Why train on outcomes rather than nurse-assigned triage labels?",
   "With ~32% mistriage under ESI, roughly one nurse label in three is wrong; training to reproduce them "
   "encodes the error. A composite outcome — ICU, death, critical intervention — is extractable from "
   "admission, discharge and billing records without a chart-review project, and is what we actually care "
   "about.")

# ---------------------------------------------------------------- B15
h1("B15. Behavioural and teamwork")
qa("Basic", "What was the hardest bug you found?",
   "The 42% green-miss. The model passed every gate that existed at the time, yet left 42% of critical "
   "patients in Green. It turned out to be three independent threshold bugs, each sufficient on its own. "
   "The lesson: add the gate that measures what you actually care about — green-miss — before trusting the "
   "others. (Alternative: the stable_sudden generator bug, where an inflection point was re-sampled every "
   "timestep, so a third of patients oscillated instead of deteriorating, silently erasing the product thesis.)")
qa("Basic", "Tell me about a time your hypothesis was wrong.",
   "I expected shock index and ROX to help paediatric detection because the literature says so. They hurt "
   "every metric. My first explanation — no HR/SBP coupling in the generator — was checked and disproven "
   "(correlation −0.74). The real cause was collinearity. I documented it and left a standing instruction "
   "not to re-add them against synthetic data.")
qa("Basic", "How did the team divide work?",
   "Three tracks with separated authority mapped naturally to ownership: perception and intake, the web "
   "interface, and the evaluation/risk engine. The shared contract was lib/api/types.ts mirrored by the "
   "backend DTOs, which let the frontend build against the mock adapter while the backend matured. "
   "(Personalise this with what you owned.)")
qa("Intermediate", "How do you handle disagreements on clinical design?",
   "By pushing decisions into the signed-off config and into measurable gates. If we disagree on a cadence or "
   "threshold, it's a YAML value with a stated reason, and the change is evaluated against the gates on "
   "held-out data — never tuned to make a gate pass.")
qa("Basic", "What did you learn?",
   "That in safety-critical ML the contract matters more than the score: who is allowed to decide, in which "
   "direction, and what happens when the model doesn't know. And that honest reporting — oracle ceilings, "
   "failed gates, wide CIs — is more persuasive than a high AUROC.")

# ==========================================================================
# PART C — CHEAT SHEET
# ==========================================================================
part("Part C — Numbers Cheat-Sheet")
table([
    ["Area", "Number", "Source"],
    ["Intake", "10 steps · 16 branches · 3–6 Qs per branch · 3 match tiers · 8 red flags · 118 self-test fixtures", "web/intake"],
    ["Strata", "6 (neonate, infant, child, adolescent, adult, geriatric); unknown → child", "config/age_strata.yaml"],
    ["Training data", "20,000 patients, seed 1337, prevalence 9.76%, 32 condition×stratum pairs; 100k corpus in LFS", "manifest.json"],
    ["Splits", "train 12,000 · calib_iso 2,000 · calib_conf 1,999 · test 4,001", "manifest.json"],
    ["Label", "critical_composite_h180; β = (−4 fallback, 10, 4, 0.4); k ∈ [30, 90] min", "config/label_spec.yaml"],
    ["Features", "59 (fx-v4): 7 vitals × 6 + 17 global; 40% history dropout; 3× positive weight", "model/features.py"],
    ["Thresholds", "p*_yellow 0.076 (R≈12.2) · p*_red 0.147 (R≈5.8) · max green-miss 0.10", "manifest.json"],
    ["Conformal", "Mondrian split, α = 0.10; coverage 0.910, mean set size 1.08", "metrics"],
    ["Own split", "AUROC 0.689 · AUPRC 0.174 · ECE 0.011 · slope 0.954 · green-miss 0.115 · FNR spread 0.195 · 8/8", "RISK_ENGINE.md"],
    ["Fresh split", "n 20,000 seed 4242 · AUROC 0.669 · AUPRC 0.164 · green-miss 0.095 · 7/8 (gate 8 fails)", "risk_engine_bakeoff_table.md"],
    ["Ceilings", "oracle AUPRC ~0.41 / AUROC ~0.87; leaked label AUROC 0.988; prevalence floor ~0.10", "RISK_ENGINE.md"],
    ["Before → after", "green-miss 0.422→0.115 · slope 0.612→0.954 · FNR spread 0.52→0.195 · child FNR 0.212→0.077", "RISK_ENGINE.md"],
    ["Detection", "16/20 cross Yellow · mean 21.6 min earlier · median 17.5 · max 55 · Red mean 6.9", "time_to_detection.json"],
    ["Latency", "risk engine p50 3 ms · p95 4.3 ms · p99 8.0 ms", "time_to_detection.json"],
    ["Structurer", "gpt-oss-120b F1 0.962, 0 RF missed · 20b 0.816, 4 missed · rules 0.510, 12 missed", "structurer_bakeoff_table.md"],
    ["ASR", "whisper-large-v3-turbo (Groq) WER 0.000, 0.298 s · local turbo 1.206 s, 4.94 GB", "asr_bakeoff_table.md"],
    ["Cadence", "Red 60 s / 5 min / 0 · Yellow 5 / 30 / 60 · Green 5 / 60 / 120 · Abstained 5 / review / 15", "band_cadence.yaml"],
    ["Surge", "baseline 8/h · enter 3× over 20 min · exit < 2× · Yellow 45 · Green 90 · Red never", "surge_policy.yaml"],
    ["Audit", "16 required + outcome_ref + 2 chain = 19 stored fields, SHA-256 chained", "audit_log.py"],
    ["APIs", "Orchestrator /v1: 21 routes · contract app: 7 routes · SSE /v1/stream · tick 1 Hz", "app.py, api.py"],
    ["Tests", "282 total, 278 pass, 4 pre-existing failures", "backend/tests"],
    ["Economics", "< Rs 5 / encounter · 100 visits/day ≈ Rs 1.8 L/yr · 500/day ≈ Rs 9.1 L/yr", "business proposal"],
    ["Context stats", "ESI mistriage 32.2% · Epic Sepsis AUC 0.63, 33% sensitivity, 109 alerts/TP · occult hypoxaemia 11.7% vs 3.6%", "business proposal"],
], [1.1, 4.4, 1.6], font=7.9)

story.append(Spacer(1, 6))
story.append(Paragraph(
    "<b>Closing line for any interview:</b> \"The contribution isn't a better score, it's a better "
    "contract — a machine that's allowed to raise an alarm on its own, never allowed to lower one, "
    "abstains out loud when it doesn't know, and is evaluated on the patients it misses rather than the "
    "average it gets right.\"", S["callout"]))


# ==========================================================================
# BUILD
# ==========================================================================
class Doc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, **kw)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=_decorate)])

    def afterFlowable(self, flowable):
        toc = getattr(flowable, "_toc", None)
        if toc:
            self.notify("TOCEntry", (toc[0], toc[1], self.page))


def _decorate(canv, doc):
    if doc.page == 1:
        return
    canv.saveState()
    canv.setFont("Body", 7.5)
    canv.setFillColor(MUTED)
    canv.drawString(18 * mm, 10 * mm, "MediPilot · Interview Preparation · synthetic data — no clinical claim")
    canv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}")
    canv.setStrokeColor(GRID)
    canv.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
    canv.restoreState()


if __name__ == "__main__":
    doc = Doc(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
              topMargin=16 * mm, bottomMargin=18 * mm,
              title="MediPilot — Interview Preparation Guide",
              author="Team 01 BIT, IIT Patna")
    doc.multiBuild(story)
    print(f"wrote {OUT}  ({QN[0]} questions)")
