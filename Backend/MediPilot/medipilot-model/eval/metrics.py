"""
Scoring for the perception-layer bake-offs (§16).

One module, imported by both the local runners in eval/ and the Kaggle
notebooks in eval/kaggle/, so a number quoted in the report and a number
printed in a notebook were produced by the same code. Pure standard library
plus nothing else, so it imports on a bare Kaggle kernel before any pip
install has run.

Two families of metric:

  ASR   — WER / CER against a reference transcript, plus language-detection
          accuracy and the hallucination/silence behaviour that
          speech/asr_common.py flags. Normalisation is deliberately gentle
          and script-aware; see normalize_transcript().

  M06   — field-level extraction quality against a labelled case, plus the
          two things that are safety properties rather than accuracy
          properties: schema validity, and whether a clinical decision leaked
          into the output. A model that extracts well but occasionally
          returns a band is disqualified, not merely penalised, so those are
          reported as separate counts and never folded into an F1.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional

# Punctuation stripped before scoring, including the Devanagari danda and
# double danda, which Whisper emits inconsistently for Hindi and which no
# downstream stage reads.
_PUNCT_RE = re.compile(r"[.,!?;:\"'`()\[\]{}<>/\\|@#$%^&*_+=~—–\-।॥]")
_WS_RE = re.compile(r"\s+")


def normalize_transcript(text: str) -> str:
    """
    Gentle, script-aware normalisation for WER/CER.

    Deliberately does NOT transliterate, translate, or map Hindi to English.
    Whisper's Hinglish output for the same utterance can legitimately land in
    either script (see speech/asr_common.looks_code_mixed for why that is a
    known, documented limitation), and forcing one script would manufacture
    errors that do not exist and hide ones that do. Where a fixture can be
    transcribed correctly in two scripts, give it two references and use
    best_of_references().
    """
    text = unicodedata.normalize("NFKC", text or "")
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def _levenshtein(a: list, b: list) -> int:
    """Edit distance over token or character sequences. Two-row DP, so a long
    transcript costs O(min(len)) memory rather than O(len^2)."""
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(
                previous[j] + 1,        # deletion
                current[j - 1] + 1,     # insertion
                previous[j - 1] + (ca != cb),  # substitution
            ))
        previous = current
    return previous[-1]


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate. Returns 0.0 for two empty strings and 1.0 when the
    reference is empty but the hypothesis is not (a pure hallucination)."""
    ref = normalize_transcript(reference).split()
    hyp = normalize_transcript(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return _levenshtein(ref, hyp) / len(ref)


def cer(reference: str, hypothesis: str) -> float:
    """
    Character error rate. Reported alongside WER because it is the fairer
    number for Devanagari and for code-mixed speech, where a single
    word-boundary disagreement (Whisper writing "chest pain" as one token or
    two) inflates WER without reflecting a real loss of information.
    """
    ref = normalize_transcript(reference).replace(" ", "")
    hyp = normalize_transcript(hypothesis).replace(" ", "")
    if not ref:
        return 0.0 if not hyp else 1.0
    return _levenshtein(list(ref), list(hyp)) / len(ref)


def best_of_references(references: Iterable[str], hypothesis: str) -> dict:
    """
    Score against several acceptable references and keep the best.

    Needed because a Hinglish utterance has more than one correct written
    form: "mujhe chest mein pain hai" and the same sentence with the English
    words in Devanagari are both faithful transcriptions. Penalising a model
    for choosing the other valid one would measure orthographic taste, not
    accuracy.
    """
    refs = [r for r in references if r and r.strip()]
    if not refs:
        return {"wer": None, "cer": None, "matched_reference": None}

    scored = [(wer(r, hypothesis), cer(r, hypothesis), r) for r in refs]
    scored.sort(key=lambda t: (t[0], t[1]))
    best = scored[0]
    return {"wer": best[0], "cer": best[1], "matched_reference": best[2]}


def score_asr_case(case: dict, result: dict) -> dict:
    """
    Score one ASR result against one manifest case.

    `case` is an entry from eval/asr_manifest.json; `result` is the
    speech/asr_common.py result contract, from either backend.

    Silence fixtures are scored on behaviour, not on WER: the only correct
    output is an empty transcript, and emitting "Thank you." there is the
    specific failure documented in speech/asr_common.py. That is reported as
    `hallucinated_on_silence`, kept out of the WER average, and is a
    disqualifying result rather than a small penalty.
    """
    hypothesis = result.get("text", "") or ""
    expect_silence = bool(case.get("expect_silence"))

    row = {
        "id": case["id"],
        "kind": case.get("kind", "speech"),
        "expected_language": case.get("language"),
        "detected_language": result.get("language"),
        "hypothesis": hypothesis,
        "code_mixed_flag": result.get("code_mixed"),
        "backend": result.get("backend"),
    }

    if expect_silence:
        row.update({
            "wer": None,
            "cer": None,
            "matched_reference": None,
            "language_correct": None,
            "hallucinated_on_silence": bool(hypothesis.strip()),
            "hallucinated_text": hypothesis.strip() or None,
        })
        return row

    row.update(best_of_references(case.get("references", []), hypothesis))
    expected_langs = case.get("accept_languages") or (
        [case["language"]] if case.get("language") else []
    )
    row["language_correct"] = (
        result.get("language") in expected_langs if expected_langs else None
    )
    row["hallucinated_on_silence"] = None
    row["hallucinated_text"] = None

    # A reassuring-looking transcript on real speech that the reliability
    # heuristics flagged is worth seeing next to the WER, because the intake
    # layer acts on the flag, not on the WER.
    reliability = result.get("asr_reliability") or {}
    row["flag_low_confidence"] = reliability.get("low_confidence")
    row["flag_possible_hallucination"] = reliability.get("possible_hallucination")
    row["flag_unsupported_language"] = reliability.get("unsupported_language")
    return row


def summarize_asr(rows: list) -> dict:
    """Aggregate per-case ASR rows into the one line that goes in the report."""
    speech = [r for r in rows if r.get("wer") is not None]
    silence = [r for r in rows if r.get("hallucinated_on_silence") is not None]
    lang = [r for r in rows if r.get("language_correct") is not None]

    def _mean(vals):
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else None

    return {
        "n_speech": len(speech),
        "mean_wer": _mean([r["wer"] for r in speech]),
        "mean_cer": _mean([r["cer"] for r in speech]),
        "median_wer": _median([r["wer"] for r in speech]),
        "language_accuracy": (
            sum(1 for r in lang if r["language_correct"]) / len(lang) if lang else None
        ),
        "n_silence_fixtures": len(silence),
        "silence_hallucinations": sum(1 for r in silence if r["hallucinated_on_silence"]),
    }


def _median(vals: list):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2


# ---------------------------------------------------------------------------
# M06 structurer scoring
# ---------------------------------------------------------------------------

def _set_prf(expected: Iterable, predicted: Iterable) -> dict:
    exp, pred = set(expected or []), set(predicted or [])
    tp = len(exp & pred)
    fp = len(pred - exp)
    fn = len(exp - pred)
    precision = tp / (tp + fp) if (tp + fp) else (1.0 if not fn else 0.0)
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "false_positives": sorted(pred - exp),
        "false_negatives": sorted(exp - pred),
    }


def score_structurer_case(case: dict, narrative, red_flag_rule_ids: list) -> dict:
    """
    Score one M06 extraction against a labelled case from
    eval/structurer_cases.json.

    `narrative` is a StructuredNarrative (or any object with the same
    attributes); `red_flag_rule_ids` is what intake/red_flags.py produced
    from it — passed in rather than recomputed so the caller can prove the
    deterministic table ran on the model's actual output.

    The red-flag columns are the ones that matter most. Symptom F1 is a
    proxy; whether the correct RF-0x rule fired is the actual safety
    outcome, and a missed red flag (`red_flag_missed`) is not commensurable
    with a spurious one — under Invariant 1 a false positive costs an
    assessment and a false negative can cost a life, so they are counted
    separately and never averaged together.
    """
    symptoms = _set_prf(case.get("expected_symptoms", []), getattr(narrative, "symptoms", []))
    expected_rules = set(case.get("expected_red_flag_rules", []))
    got_rules = set(red_flag_rule_ids or [])

    onset_expected = case.get("expected_onset_minutes", "__unset__")
    severity_expected = case.get("expected_self_reported_severity", "__unset__")

    row = {
        "id": case["id"],
        "tags": case.get("tags", []),
        "transcript": case["transcript"],
        "symptom_precision": symptoms["precision"],
        "symptom_recall": symptoms["recall"],
        "symptom_f1": symptoms["f1"],
        "symptom_false_positives": symptoms["false_positives"],
        "symptom_false_negatives": symptoms["false_negatives"],
        "expected_red_flag_rules": sorted(expected_rules),
        "got_red_flag_rules": sorted(got_rules),
        "red_flag_missed": sorted(expected_rules - got_rules),
        "red_flag_spurious": sorted(got_rules - expected_rules),
        "red_flag_exact": expected_rules == got_rules,
        "extraction_status": getattr(narrative, "extraction_status", None),
        "predicted_symptoms": sorted(getattr(narrative, "symptoms", []) or []),
    }

    if onset_expected != "__unset__":
        got = getattr(narrative, "onset_minutes", None)
        tol = case.get("onset_tolerance_minutes", 0)
        row["onset_correct"] = (
            got is not None and onset_expected is not None
            and abs(got - onset_expected) <= tol
        ) if onset_expected is not None else got is None
        row["onset_expected"] = onset_expected
        row["onset_got"] = got

    if severity_expected != "__unset__":
        got = getattr(narrative, "self_reported_severity", None)
        row["severity_correct"] = got == severity_expected
        row["severity_expected"] = severity_expected
        row["severity_got"] = got

    return row


def summarize_structurer(rows: list, schema_failures: int = 0,
                         forbidden_key_hits: int = 0,
                         n_attempted: Optional[int] = None) -> dict:
    """
    Aggregate per-case rows plus the two safety counters the per-case scorer
    cannot see (they happen before a narrative exists).

    `schema_failures` counts StructurerOutputError raised for malformed or
    schema-violating output. `forbidden_key_hits` counts outputs rejected for
    containing a diagnosis/band/acuity key. Both are reported as raw counts,
    not rates folded into a quality score: one leaked band is a reason to
    reject a model outright, and an average would hide it.
    """
    n = len(rows)

    def _mean(key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    onset_rows = [r for r in rows if "onset_correct" in r]
    severity_rows = [r for r in rows if "severity_correct" in r]

    return {
        "n_cases": n,
        "n_attempted": n_attempted if n_attempted is not None else n,
        "symptom_f1": _mean("symptom_f1"),
        "symptom_precision": _mean("symptom_precision"),
        "symptom_recall": _mean("symptom_recall"),
        "red_flag_exact_rate": (sum(1 for r in rows if r["red_flag_exact"]) / n) if n else None,
        # The two numbers a clinician will ask about first.
        "red_flags_missed": sum(len(r["red_flag_missed"]) for r in rows),
        "red_flags_spurious": sum(len(r["red_flag_spurious"]) for r in rows),
        "cases_with_missed_red_flag": sum(1 for r in rows if r["red_flag_missed"]),
        "onset_accuracy": (
            sum(1 for r in onset_rows if r["onset_correct"]) / len(onset_rows)
        ) if onset_rows else None,
        "severity_accuracy": (
            sum(1 for r in severity_rows if r["severity_correct"]) / len(severity_rows)
        ) if severity_rows else None,
        # Safety counters — disqualifying, not averaged.
        "schema_failures": schema_failures,
        "forbidden_key_hits": forbidden_key_hits,
    }


def to_markdown_table(rows: list, columns: list) -> str:
    """Render a list of dicts as a GitHub-flavoured markdown table, so a
    notebook result can be pasted straight into the report."""
    def fmt(v):
        if v is None:
            return "—"
        if isinstance(v, float):
            return f"{v:.3f}"
        if isinstance(v, list):
            return ", ".join(str(x) for x in v) if v else "—"
        return str(v)

    head = "| " + " | ".join(columns) + " |"
    rule = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(fmt(r.get(c)) for c in columns) + " |" for r in rows]
    return "\n".join([head, rule] + body)
