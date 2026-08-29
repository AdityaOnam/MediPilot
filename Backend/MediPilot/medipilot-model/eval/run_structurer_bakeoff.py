"""
M06 structurer bake-off — which LLM should do the extraction.

Runs every candidate structurer over eval/structurer_cases.json and reports
extraction quality alongside the two safety counters that decide the choice
regardless of quality: schema failures, and clinical-decision keys leaking
into the output.

Run locally (Groq-hosted candidates):
    set GROQ_API_KEY=...
    .venv/Scripts/python.exe -m eval.run_structurer_bakeoff --candidates groq
    .venv/Scripts/python.exe -m eval.run_structurer_bakeoff --check-labels

Run on Kaggle (open-weight candidates on the T4s): see
eval/kaggle/llm_structurer_bakeoff.ipynb, which imports the same scoring
code from eval/metrics.py so notebook numbers and reported numbers agree.

Reading the results
-------------------
Rank on `red_flags_missed` first, then `symptom_f1`. A model with the best F1
and one missed red flag loses to a model with worse F1 and none: under
Invariant 1 those two errors are not commensurable, so they are never
averaged into a single score here.

`schema_failures` and `forbidden_key_hits` are disqualifying, not weighted.
A single band or diagnosis reaching the output means the perception-only
guarantee did not hold for that model.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from eval import metrics  # noqa: E402
from intake.llm_structurer import (  # noqa: E402
    GroqLLMStructurer,
    RuleBasedStructurer,
    StructurerOutputError,
)
from intake.models import ObservationCode, StructuredNarrative  # noqa: E402
from intake.red_flags import evaluate_all_red_flags  # noqa: E402

CASES_PATH = os.path.join(_HERE, "structurer_cases.json")

# Groq-hosted candidates. All support JSON-schema-constrained ("strict")
# structured outputs, which is what makes the perception-only guarantee
# structural rather than a matter of prompt compliance -- the schema has no
# property for a band, so the model cannot emit one.
GROQ_CANDIDATES = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    # llama-3.3-70b-versatile, llama-3.1-8b-instant and
    # moonshotai/kimi-k2-instruct were removed 2026-08-28: all three now
    # 404 ("model_not_found") on Groq's API. Hosted-model catalogs change
    # without notice, so check https://console.groq.com/docs/models for
    # current IDs before adding replacements back -- a stale ID here costs
    # 40 wasted API calls (one per case) before the run even gets going.
]

VALID_CODES = {c.value for c in ObservationCode}
FORBIDDEN_SUBSTRINGS = (
    "red", "yellow", "green", "triage", "acuity", "band",
    "diagnosis", "myocardial infarction", "priority",
)
# Whole-word match only, case-insensitive. A naive `token in text` substring
# check false-positives constantly: "red" matches inside "slurred",
# "prepared", "altered_consciousness"; earlier runs reported exactly this
# (S-14's "slurred" and S-06's "altered_consciousness" both wrongly flagged
# as a leaked band). \b anchors this to real words, so "myocardial
# infarction" still matches as a phrase but "red" only matches the word
# "red" on its own.
_FORBIDDEN_PATTERNS = [
    re.compile(r"\b" + re.escape(token) + r"\b", re.IGNORECASE)
    for token in FORBIDDEN_SUBSTRINGS
]


def load_cases(path: str = CASES_PATH) -> list:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["cases"]


def check_labels(cases: list) -> int:
    """
    Verify that every expected_red_flag_rules value is what
    intake/red_flags.py actually produces from that case's
    expected_symptoms.

    This exists because the two fields must never be authored independently.
    §10's whole design is that the model extracts observations and a fixed
    table decides Red; if this file hand-wrote a red-flag expectation that
    the table would not produce, the bake-off would be scoring models against
    a rule that does not exist in the system.
    """
    problems = []
    for case in cases:
        symptoms = case.get("expected_symptoms", [])
        unknown = [s for s in symptoms if s not in VALID_CODES]
        if unknown:
            problems.append(f"{case['id']}: symptoms outside the closed vocabulary: {unknown}")

        derived = [r.rule_id for r in evaluate_all_red_flags(
            StructuredNarrative(symptoms=list(symptoms))
        )]
        declared = case.get("expected_red_flag_rules", [])
        if sorted(derived) != sorted(declared):
            problems.append(
                f"{case['id']}: expected_red_flag_rules {declared} but the fixed table "
                f"derives {derived} from {symptoms}"
            )

    if problems:
        print("LABEL CHECK FAILED:")
        for p in problems:
            print("  -", p)
        return 1
    print(f"Label check passed: {len(cases)} cases, red-flag expectations all derive "
          f"from the fixed table.")
    return 0


def _leaked_clinical_decision(narrative: StructuredNarrative) -> Optional[str]:
    """
    Look for a clinical decision that survived into a free-text field.

    validate_structured_narrative() already rejects forbidden KEYS. This
    catches the other route: a band or a diagnosis written into the VALUE of
    chief_complaint or relevant_history. Only free-text fields are inspected;
    `symptoms` is a closed vocabulary and cannot carry one.

    Deliberately narrow. It reports a candidate leak for a human to read, and
    the runner prints the offending text -- it is not treated as ground truth,
    because "the patient's face went red" is not a triage band.
    """
    haystacks = [narrative.chief_complaint or ""] + list(narrative.relevant_history or [])
    for text in haystacks:
        for token, pattern in zip(FORBIDDEN_SUBSTRINGS, _FORBIDDEN_PATTERNS):
            if pattern.search(text):
                return f"{token!r} in {text!r}"
    return None


def run_candidate(name: str, structurer, cases: list, verbose: bool = False) -> dict:
    """Run one structurer over every case and return its summary row."""
    rows, latencies = [], []
    schema_failures = 0
    forbidden_hits = 0
    leak_details = []

    for case in cases:
        started = time.perf_counter()
        try:
            narrative = structurer.structure(case["transcript"])
        except StructurerOutputError as exc:
            # Malformed JSON, a schema violation, or a forbidden key. Counted,
            # then scored as an empty extraction -- which is the honest
            # consequence: the pipeline gets nothing from this turn.
            schema_failures += 1
            if "forbidden" in str(exc).lower():
                forbidden_hits += 1
            if verbose:
                print(f"    {case['id']}: STRUCTURER ERROR — {exc}")
            narrative = StructuredNarrative(
                raw_transcript=case["transcript"], extraction_status="error"
            )
        latencies.append(time.perf_counter() - started)

        leak = _leaked_clinical_decision(narrative)
        if leak:
            forbidden_hits += 1
            leak_details.append(f"{case['id']}: {leak}")

        rule_ids = [r.rule_id for r in evaluate_all_red_flags(narrative)]
        row = metrics.score_structurer_case(case, narrative, rule_ids)
        rows.append(row)

        if verbose and (row["red_flag_missed"] or row["red_flag_spurious"]):
            print(f"    {case['id']}: missed={row['red_flag_missed']} "
                  f"spurious={row['red_flag_spurious']} "
                  f"got_symptoms={row['predicted_symptoms']}")

    summary = metrics.summarize_structurer(
        rows, schema_failures=schema_failures, forbidden_key_hits=forbidden_hits
    )
    summary["candidate"] = name
    summary["mean_latency_s"] = sum(latencies) / len(latencies) if latencies else None
    summary["_rows"] = rows
    summary["_leaks"] = leak_details
    return summary


def build_candidates(which: str) -> list:
    """
    (name, structurer) pairs to evaluate.

    RuleBasedStructurer is always included and is not a candidate for the job
    -- it is the floor. Any LLM that does not clearly beat a keyword matcher
    on the negation and adversarial families is not worth the API call, and
    quoting that comparison is stronger than quoting an F1 alone.
    """
    candidates = [("RuleBasedStructurer (baseline, not an LLM)", RuleBasedStructurer())]
    if which in ("groq", "all"):
        if not os.environ.get("GROQ_API_KEY"):
            print("GROQ_API_KEY not set — skipping the Groq-hosted candidates.\n"
                  "Set it to evaluate them: set GROQ_API_KEY=...\n")
        else:
            for model in GROQ_CANDIDATES:
                candidates.append((f"groq:{model}", GroqLLMStructurer(model)))
    return candidates


SUMMARY_COLUMNS = [
    "candidate", "red_flags_missed", "red_flags_spurious", "symptom_f1",
    "symptom_precision", "symptom_recall", "red_flag_exact_rate",
    "onset_accuracy", "severity_accuracy",
    "schema_failures", "forbidden_key_hits", "mean_latency_s",
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidates", default="groq", choices=["groq", "rules", "all"],
                    help="which family to evaluate (default: groq)")
    ap.add_argument("--check-labels", action="store_true",
                    help="verify the eval set's red-flag labels derive from the "
                         "fixed table, then exit")
    ap.add_argument("--tags", default=None,
                    help="comma-separated tag filter, e.g. negation,adversarial")
    ap.add_argument("--out", default=None, help="write full results to this JSON path")
    ap.add_argument("--verbose", action="store_true",
                    help="print every red-flag miss and structurer error as it happens")
    args = ap.parse_args()

    cases = load_cases()
    if args.check_labels:
        return check_labels(cases)

    if check_labels(cases) != 0:
        print("\nRefusing to run a bake-off against labels that do not derive from "
              "the fixed table — fix eval/structurer_cases.json first.")
        return 1

    if args.tags:
        wanted = {t.strip() for t in args.tags.split(",")}
        cases = [c for c in cases if wanted & set(c.get("tags", []))]
        print(f"Filtered to {len(cases)} cases with tags {sorted(wanted)}")

    summaries = []
    for name, structurer in build_candidates(args.candidates):
        print(f"\n=== {name} ({len(cases)} cases) ===")
        try:
            summaries.append(run_candidate(name, structurer, cases, verbose=args.verbose))
        except Exception as exc:
            print(f"  candidate failed entirely: {exc}")

    # Rank by the safety counter first, then quality -- see the module docstring.
    summaries.sort(key=lambda s: (
        s["forbidden_key_hits"], s["red_flags_missed"], s["schema_failures"],
        -(s["symptom_f1"] or 0),
    ))

    print("\n\n## M06 structurer bake-off\n")
    print(metrics.to_markdown_table(summaries, SUMMARY_COLUMNS))
    print("\nRanked by forbidden-key hits, then missed red flags, then schema "
          "failures, then symptom F1. Missed and spurious red flags are reported "
          "separately and never averaged: escalation costs one assessment, "
          "de-escalation can cost a life (Invariant 1).")

    for s in summaries:
        if s["_leaks"]:
            print(f"\nPossible clinical-decision leaks — {s['candidate']}:")
            for leak in s["_leaks"]:
                print("  -", leak)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(summaries, fh, indent=2, ensure_ascii=False)
        print(f"\nFull per-case results written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
