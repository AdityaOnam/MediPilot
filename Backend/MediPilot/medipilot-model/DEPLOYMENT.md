# Where the models run

Three tiers, in preference order. The system walks down this list at startup and on failure, and
`GET /v1/config` reports which tier is actually serving — so the demo can never claim local
inference, or LLM extraction, that it is not currently performing.

| Tier | M05 speech | M06 structurer | Patient data leaves the machine? |
| --- | --- | --- | --- |
| **1 · Local** | `faster-whisper` (CTranslate2, int8) | Ollama / llama.cpp / LM Studio | **No** |
| **2 · Hosted free tier** | Groq `whisper-large-v3-turbo` | Groq LLM, schema-constrained | Yes |
| **3 · Floor** | *(none — returns 503)* | `RuleBasedStructurer` — keywords, not an LLM | No |

There is deliberately **no paid cloud GPU tier**. Renting inference is not on the table, and the
architecture is built so it never becomes necessary.

## Why local is the destination, not an optimisation

`round2-implementation-plan.html` §13 states, under India's DPDP Act 2023, that *"Raw patient data
stays at the institution; only model updates leave."* An intake conversation is the most sensitive
thing this system touches — it is the patient describing their symptoms in their own voice. Sending
that audio and that transcript to a third-party API is a real, defensible-only-as-a-prototype
compromise, and the plan's own ladder (§17) puts federated, data-local operation at V5.

So the honest framing, and the one to give judges:

> The prototype runs on free hosted APIs so it works reliably in this room. The architecture is
> local-first — the same interface serves a model running on this laptop, and we can show you that.
> If this is taken forward, inference moves inside the hospital, because under DPDP that is where
> patient data has to stay.

That claim is only worth making if it is demonstrable. It is: flip one environment variable.

## Running tier 1 locally

### M06 — the LLM structurer, via Ollama

```bash
ollama pull qwen2.5:3b-instruct
ollama serve
```

```bash
MEDIPILOT_STRUCTURER=local,groq,rules uvicorn backend.orchestrator.app:app --port 8000
```

Ollama exposes an OpenAI-compatible API at `http://localhost:11434/v1`, which is what
`LocalOpenAICompatStructurer` talks to. Any other server speaking that API works too — point
`MEDIPILOT_LOCAL_LLM_URL` at it.

**Pick the model from the bake-off, not from this page.** `eval/kaggle/llm_structurer_bakeoff.ipynb`
ranks candidates and marks which ones fit the target hardware; `qwen2.5:3b-instruct` is a sensible
starting default, not a finding.

### M05 — speech, via faster-whisper

```bash
pip install -r requirements-speech-local.txt
```

```bash
MEDIPILOT_ASR_BACKEND=local,groq uvicorn backend.orchestrator.app:app --port 8000
```

Runs in-process on CPU. No server to start.

## Hardware reality on the target machine

The development and demo laptop is a **Ryzen 5 5600H, 16 GB RAM, AMD Radeon RX 6500M (4 GB
VRAM)**. This shapes every local choice:

- **There is no CUDA, and ROCm has no Windows support.** PyTorch is CPU-only on this machine. Any
  guidance that assumes an NVIDIA card does not apply.
- **Use runtimes that work on AMD under Windows.** llama.cpp (Vulkan backend) and Ollama can use
  the 6500M; CTranslate2 (`faster-whisper`) is CPU-first and fast enough there. Plain
  `transformers` + `bitsandbytes` cannot use this GPU at all.
- **4 GB VRAM caps the model.** A 7B at Q4 is ~4.5 GB of weights before context, so it does not
  fit. Stay in the **1B–4B** range for full or near-full offload; that is why the bake-off tags
  candidates with `fits_locally` and reports the 7B tier separately as a ceiling.
- **`whisper small` int8 is the practical ASR size.** `large-v3` on this CPU is not a kiosk.

## Choosing what to actually deploy

1. Run both notebooks in `eval/kaggle/` on a T4. Kaggle is the measuring instrument — nothing is
   ever served from it.
2. Take the top-ranked candidate **that is marked `fits_locally`**.
3. Pull it in Ollama on the laptop and re-check latency there. The Kaggle quality ranking transfers
   between 4-bit runtimes; the speed does not. A model that wins on a T4 and takes nine seconds a
   turn on the 6500M has not solved the problem.
4. Set it in `.env` and leave the hosted tier configured behind it as the fallback.

## Verifying which tier is live

```bash
curl -s localhost:8000/v1/config | python -m json.tool
```

```json
{
  "perception": {
    "asrActive": "local",
    "structurerActive": "local",
    "structurerIsLLM": true,
    "dataLeavesMachine": false
  }
}
```

`dataLeavesMachine` is the field to point at on stage. It is `true` whenever a hosted API is
serving either stage, `false` when both are local, and `null` before anything has run — a status
endpoint should not assert where data is going before any data has gone anywhere.

Every fallback is also logged at WARNING and named on the `/v1/structure` response
(`extraction.structurer`), so a silent degradation from local to hosted is not possible.
