## ASR bake-off

| backend | mean_wer | median_wer | mean_cer | language_accuracy | silence_hallucinations | n_speech | mean_latency_s | vram_peak_gb |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| whisper-local:turbo | 0.000 | 0.000 | 0.000 | 1.000 | 0 | 2 | 1.206 | 4.940 |
| groq:whisper-large-v3-turbo | 0.000 | 0.000 | 0.000 | 1.000 | 0 | 2 | 0.298 | — |
| whisper-local:large-v3 | 0.583 | 0.583 | 0.684 | 1.000 | 0 | 2 | 2.392 | 9.410 |
| faster-whisper:large-v3/int8_float16 | 0.583 | 0.583 | 0.684 | 1.000 | 0 | 2 | 1.076 | — |
| faster-whisper:large-v3/float16 | 0.583 | 0.583 | 0.684 | 1.000 | 0 | 2 | 1.074 | — |
| groq:whisper-large-v3 | 0.583 | 0.583 | 0.684 | 1.000 | 0 | 2 | 0.367 | — |
| whisper-local:medium | 0.750 | 0.750 | 0.737 | 1.000 | 0 | 2 | 2.309 | 4.590 |
| whisper-local:tiny | 0.833 | 0.833 | 0.786 | 0.833 | 0 | 2 | 0.554 | 0.230 |
| whisper-local:base | 0.833 | 0.833 | 0.786 | 0.833 | 0 | 2 | 0.343 | 0.450 |
| whisper-local:small | 3.750 | 3.750 | 3.190 | 1.000 | 0 | 2 | 1.690 | 1.480 |
| faster-whisper:small/int8 | 3.750 | 3.750 | 3.167 | 1.000 | 0 | 2 | 0.562 | — |
| vasista22/whisper-hindi-large-v2 | — | — | — | — | 0 | 0 | 0.002 | — |
| vasista22/whisper-hindi-large-v2 | — | — | — | — | 0 | 0 | 0.002 | — |
