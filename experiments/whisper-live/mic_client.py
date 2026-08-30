import socket
import pyaudio
import threading

# Connection configuration
HOST = 'localhost'
PORT = 43007

# Audio configuration
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

def receive_text(sock):
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                break
            text = data.decode('utf-8').strip()
            if text:
                print(f"> {text}", flush=True)
        except Exception:
            break

def main():
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print(f"Connecting to {HOST}:{PORT}...")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            print("Connected! Recording... (Speak now. Press Ctrl+C to stop)")
            print("-" * 50)
            
            # Start a background thread to listen for live transcription text
            threading.Thread(target=receive_text, args=(s,), daemon=True).start()
            
            try:
                while True:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    s.sendall(data)
            except KeyboardInterrupt:
                print("\nStopped recording.")
    except ConnectionRefusedError:
        print(f"Error: Could not connect to {HOST}:{PORT}. Make sure the whisper server is running.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    main()
