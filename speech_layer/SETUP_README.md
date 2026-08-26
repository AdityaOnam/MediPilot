# 🎙️ MediPilot Speech Layer — Live Transcription with Colab + ngrok

This bundle lets you run a **GPU-powered Whisper live transcription server** on Google Colab (free T4 GPU) and stream audio from your local microphone to it in real time.

---

## 📦 What's in this Bundle

```
whisper-live-bundle/
├── README.md                        ← You are here
├── colab_whisper_server.ipynb       ← Run this on Google Colab
├── mic_client.py                    ← Run this on your local machine
└── whisper_streaming/               ← Core transcription engine
    ├── whisper_online.py            ← Patched for GPU (cuda float16)
    ├── whisper_online_server.py     ← TCP streaming server
    ├── silero_vad_iterator.py       ← Voice activity detection
    └── line_packet.py               ← Network packet utils
```

---

## 🚀 Step-by-Step Setup

### PART 1 — Set Up ngrok (One Time Only)

ngrok creates a secure public tunnel so Colab can receive your mic audio.

1. Go to **https://ngrok.com/signup** and create a free account
2. After logging in, click **"Your Authtoken"** in the left sidebar
3. Copy the token (looks like: `2abc123xyz...`)
4. Keep it handy for Step 3 below

---

### PART 2 — Launch the Server on Google Colab

1. Go to **https://colab.research.google.com**
2. Click **File → Upload notebook**
3. Upload **`colab_whisper_server.ipynb`** from this bundle
4. Set the GPU: **Runtime → Change runtime type → T4 GPU → Save**
5. Now run the cells **one by one from top to bottom**:

   | Cell | What it does |
   |------|-------------|
   | Cell 1 | Checks GPU is available |
   | Cell 2 | Installs faster-whisper, librosa, pyngrok |
   | Cell 3 | Clones whisper_streaming from GitHub |
   | Cell 4 | Patches the code to use GPU |
   | Cell 5 | **Paste your ngrok token here** |
   | Cell 6 | Starts the server + creates public URL |
   | Cell 7 | Shows live transcription logs |

6. After Cell 6 runs, you will see output like:
   ```
   =====================================================
     WHISPER SERVER IS LIVE!
     Public URL : tcp://0.tcp.ngrok.io:19832

     In your LOCAL mic_client.py, update:
       HOST = "0.tcp.ngrok.io"
       PORT = 19832
   =====================================================
   ```
7. **Copy the HOST and PORT values** — you need them in Part 3.

---

### PART 3 — Connect Your Microphone (Local Machine)

1. Open `mic_client.py` in any text editor
2. At the top, update these two lines with the values from Colab:
   ```python
   HOST = "0.tcp.ngrok.io"   # ← paste your ngrok host here
   PORT = 19832               # ← paste your ngrok port here
   ```
3. Install the mic dependency if not already done:
   ```bash
   pip install pyaudio
   ```
4. Run the client:
   ```bash
   python mic_client.py
   ```
5. You will see:
   ```
   Connecting to 0.tcp.ngrok.io:19832...
   Connected! Recording... (Speak now. Press Ctrl+C to stop)
   --------------------------------------------------
   ```
6. **Speak into your microphone** — transcribed text appears after ~3-5 seconds
7. Press `Ctrl+C` to stop recording

---

## ⚠️ Important Notes

- **Colab session timeout**: Free Colab disconnects after ~90 minutes of idle. Keep Cell 7 running to stay active.
- **ngrok free tier**: Only 1 tunnel at a time. Each new Colab session gives a different URL — update `mic_client.py` each time.
- **Model loading**: Whisper `base.en` takes ~30-60 seconds to load on first run. Wait for "Listening on..." before running the client.
- **Transcription delay**: Expect 3-7 seconds of latency. This is normal for Whisper streaming.
- **Windows users**: If `pyaudio` install fails, use: `pip install pipwin && pipwin install pyaudio`

---

## 🔧 Troubleshooting

| Problem | Fix |
|---------|-----|
| `ConnectionRefusedError` | Colab server not running yet — check Cell 6 is complete |
| No text appearing | Speak louder / closer to mic; wait 5+ seconds |
| `ModuleNotFoundError: pyaudio` | Run `pip install pyaudio` |
| Colab shows CUDA error | Runtime → Restart and run all |
| ngrok token invalid | Re-copy from dashboard.ngrok.com |

---

## 📐 Architecture

```
Your Microphone
      │
      │ raw PCM audio (16kHz mono)
      ▼
mic_client.py  ──── TCP ────► ngrok tunnel ──── TCP ────► Colab
(local machine)                                          whisper_online_server.py
                                                                │
                                                         Whisper base.en (T4 GPU)
                                                                │
                                                     transcribed text sent back
                                                                │
                                                         mic_client.py prints:
                                                         > Hello, this is a test.
```

---

## 📞 Support

If something breaks, share the error message from your terminal and the Colab logs (Cell 7 output).
