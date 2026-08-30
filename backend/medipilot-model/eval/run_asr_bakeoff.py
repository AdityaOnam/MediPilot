"""
ASR bake-off — which Whisper should transcribe the intake conversation.

Satisfies the §15 stack commitment ("Whisper-class ASR, quantised, evaluated
on Indian-accented and code-mixed speech before we depend on it") and gives
§16's "speech integration slips" risk a number instead of an adjective.

Run locally against the hosted backend (no GPU needed):
    set GROQ_API_KEY=...
    .venv/Scripts/python.exe -m eval.run_asr_bakeoff --backends groq

Run on Kaggle across local Whisper sizes on a T4: see
eval/kaggle/asr_bakeoff.ipynb, which imports this module's scoring so
notebook numbers and reported numbers agree.

A note on what is being measured
--------------------------------
The silence fixtures are not a WER test and are not averaged into one. They
ask a yes/no question: did the model put words in a silent patient's mouth?
A model that does is rejected however good its WER is, because in this
pipeline a hallucinated sentence becomes a patient's own reported symptoms
and feeds the red-flag table.

By default every backend runs with its energy gate active, which is how it
runs in production. Pass --no-silence-gate to find out whether the gate is
carrying a model that would otherwise hallucinate — worth knowing before
depending on one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from eval import metrics  # noqa: E402

MANIFEST_PATH = os.path.join(_HERE, "asr_manifest.json")

# Local Whisper sizes worth comparing. "turbo" is the current default in
# speech/whisper_stt.py; the smaller sizes matter because they are the only
# ones that could ever run on the demo laptop's CPU, and the point of the
# bake-off is to know what that costs in accuracy.
LOCAL_WHISPER_SIZES = ["tiny", "base", "small", "medium", "turbo", "large-v3"]

# Hosted candidates on Groq.
GROQ_ASR_MODELS = ["whisper-large-v3-turbo", "whisper-large-v3"]


def load_manifest(path: str = MANIFEST_PATH) -> list:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["cases"]


def _resolve(case: dict) -> str:
    return os.path.join(_ROOT, case["path"])


def run_backend(name: str, transcribe, cases: list, verbose: bool = False) -> dict:
    """
    Run one backend over every manifest case.

    `transcribe` takes an absolute audio path and returns the
    speech/asr_common.py result contract.
    """
    rows, latencies = [], []
    for case in cases:
        path = _resolve(case)
        if not os.path.exists(path):
            print(f"  {case['id']}: MISSING {path} — skipped")
            continue

        started = time.perf_counter()
        try:
            result = transcribe(path)
        except Exception as exc:
            print(f"  {case['id']}: FAILED — {exc}")
            continue
        elapsed = time.perf_counter() - started
        latencies.append(elapsed)

        row = metrics.score_asr_case(case, result)
        row["latency_s"] = elapsed
        rows.append(row)

        if verbose:
            marker = ""
            if row.get("hallucinated_on_silence"):
                marker = "  <-- HALLUCINATED ON SILENCE"
            elif row.get("wer") is not None:
                marker = f"  (WER {row['wer']:.3f})"
            print(f"  {case['id']}: {row['hypothesis'][:70]!r}{marker}")

    summary = metrics.summarize_asr(rows)
    summary["backend"] = name
    summary["mean_latency_s"] = sum(latencies) / len(latencies) if latencies else None
    summary["_rows"] = rows
    return summary


def groq_backends(models: list) -> list:
    from speech.groq_asr import GroqWhisperSTT

    out = []
    for model in models:
        stt = GroqWhisperSTT(model)
        out.append((f"groq:{model}", lambda p, s=stt: s.transcribe(p)))
    return out


def local_whisper_backends(sizes: list, silence_gate: bool = True) -> list:
    """
    Local openai-whisper backends, one per model size.

    Models are loaded lazily, one at a time, and released before the next is
    loaded — on a 16 GB Kaggle T4 that is the difference between comparing
    six sizes and running out of memory on the fourth.
    """
    out = []
    for size in sizes:
        def _run(path, size=size):
            import gc

            import torch  # noqa: F401  (imported for the cache release below)

            from speech.whisper_stt import WhisperSTT

            stt = WhisperSTT(size)
            try:
                if silence_gate:
                    return stt.transcribe(path)
                return _transcribe_without_gate(stt, path)
            finally:
                del stt
                gc.collect()
                try:
                    torch.cuda.empty_cache()
                except Exception:
                    pass

        out.append((f"whisper-local:{size}", _run))
    return out


def _transcribe_without_gate(stt, path: str) -> dict:
    """
    Decode with the RMS energy gate bypassed, to see the raw model behaviour
    on silence. This is a diagnostic, never the production path — the gate
    exists precisely because Whisper's own no_speech_prob does not catch its
    silence hallucinations.
    """
    import whisper

    from speech import asr_common

    waveform = whisper.load_audio(path)
    result = stt.model.transcribe(
        waveform, task="transcribe", language=None,
        condition_on_previous_text=False, temperature=0, verbose=False,
    )
    return asr_common.build_result(
        text=result["text"].strip(),
        language=result.get("language"),
        segments=result.get("segments", []),
        backend=f"{stt._backend_name()}[gate-off]",
    )


def write_reference_template(summaries: list, out_path: str) -> None:
    """
    Emit a template of hypotheses for the fixtures that still owe a reference
    transcript, so they can be corrected by ear and pasted into
    eval/asr_manifest.json.

    Every entry is written as a CANDIDATE with the backend that produced it
    named alongside. Nothing here should be accepted unheard: a model's own
    output promoted to ground truth scores that model against itself and
    reports a free 0.000 WER, which would make this whole bake-off decorative.
    """
    template = {}
    for summary in summaries:
        for row in summary["_rows"]:
            if row.get("matched_reference") or row["kind"] == "silence":
                continue
            template.setdefault(row["id"], {"candidates": {}})
            template[row["id"]]["candidates"][summary["backend"]] = row["hypothesis"]

    payload = {
        "_instructions": (
            "LISTEN to each fixture and write the correct transcript into "
            "`references`, then paste the entry into eval/asr_manifest.json. "
            "The `candidates` below are model OUTPUT, shown only to save typing. "
            "Accepting one unheard scores that model against itself. For a "
            "code-mixed utterance, list every faithful orthography as a "
            "separate reference — metrics.py takes the best match."
        ),
        "fixtures": {k: {**v, "references": []} for k, v in template.items()},
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    print(f"\nReference template written to {out_path} ({len(template)} fixtures).")


SUMMARY_COLUMNS = [
    "backend", "mean_wer", "median_wer", "mean_cer", "language_accuracy",
    "silence_hallucinations", "n_speech", "mean_latency_s",
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backends", default="groq", choices=["groq", "local", "all"])
    ap.add_argument("--sizes", default=None,
                    help=f"comma-separated local Whisper sizes "
                         f"(default: {','.join(LOCAL_WHISPER_SIZES)})")
    ap.add_argument("--no-silence-gate", action="store_true",
                    help="bypass the RMS energy gate on local backends, to see "
                         "whether the gate is carrying the model")
    ap.add_argument("--write-reference-template", default=None, metavar="PATH",
                    help="emit a template for fixtures still owing a reference transcript")
    ap.add_argument("--out", default=None, help="write full results to this JSON path")
    ap.add_argument("--verbose", action="store_true", help="print every transcript")
    args = ap.parse_args()

    cases = load_manifest()
    backends = []
    if args.backends in ("groq", "all"):
        if not os.environ.get("GROQ_API_KEY"):
            print("GROQ_API_KEY not set — skipping hosted backends.\n")
        else:
            backends += groq_backends(GROQ_ASR_MODELS)
    if args.backends in ("local", "all"):
        sizes = args.sizes.split(",") if args.sizes else LOCAL_WHISPER_SIZES
        backends += local_whisper_backends(sizes, silence_gate=not args.no_silence_gate)

    if not backends:
        print("No backends to run. Set GROQ_API_KEY, or pass --backends local.")
        return 1

    summaries = []
    for name, fn in backends:
        print(f"\n=== {name} ===")
        summaries.append(run_backend(name, fn, cases, verbose=args.verbose))

    # Any silence hallucination sinks a backend regardless of WER.
    summaries.sort(key=lambda s: (
        s["silence_hallucinations"],
        s["mean_wer"] if s["mean_wer"] is not None else 1e9,
    ))

    print("\n\n## ASR bake-off\n")
    print(metrics.to_markdown_table(summaries, SUMMARY_COLUMNS))
    print("\nRanked by silence hallucinations first, then mean WER. A backend that "
          "speaks over silence is rejected however good its WER is: in this "
          "pipeline a hallucinated sentence becomes the patient's own reported "
          "symptoms and is fed to the red-flag table.")

    unscored = [r["id"] for s in summaries for r in s["_rows"]
                if r["kind"] == "speech" and r.get("matched_reference") is None]
    if unscored:
        print(f"\nNot scored for WER (no reference transcript yet): "
              f"{sorted(set(unscored))}. Run with --write-reference-template to "
              f"generate one, then correct it by ear.")

    if args.write_reference_template:
        write_reference_template(summaries, args.write_reference_template)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(summaries, fh, indent=2, ensure_ascii=False)
        print(f"\nFull per-case results written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
