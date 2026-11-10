import whisper


class WhisperSTT:
    def __init__(self, model_name="turbo"):
        print(f"Loading Whisper model: {model_name}")
        self.model = whisper.load_model(model_name)
        print("Whisper loaded!")

    def transcribe(self, audio):
        """
        Transcribe a complete audio utterance.

        Parameters
        ----------
        audio:
            Audio file path or audio data supported by Whisper.

        Returns
        -------
        dict:
            Structured transcription result containing:
            - text: transcribed text
            - language: detected language
            - segments: timestamped segments
        """

        result = self.model.transcribe(
            audio,

            # We want transcription in the language spoken,
            # NOT translation to English.
            task="transcribe",

            # Automatically detect the language.
            # This allows English, Hindi and Hinglish.
            language=None,

            # Each user utterance is treated independently.
            # This is preferable when the frontend sends
            # separate Tap-to-Speak recordings.
            condition_on_previous_text=False,

            # Keep Whisper's default decoding behavior.
            temperature=0,

            # Don't print Whisper's internal progress.
            verbose=False
        )

        return {
            "text": result["text"].strip(),
            "language": result.get("language"),
            "segments": result.get("segments", [])
        }


if __name__ == "__main__":

    # Simple standalone test
    stt = WhisperSTT()

    result = stt.transcribe("test3.ogg")

    print("\nLanguage:", result["language"])
    print("Text:", result["text"])