"""
Fully voice-driven MediPilot intake conversation. No tap-to-speak button:
recording starts automatically when you begin speaking and stops on its own
after ~1-1.5s of silence (or after ~25s regardless) -- see
speech/vad_recorder.py.

This reuses the EXISTING speech/vad_recorder.py (Silero VAD) and
speech/whisper_stt.py (WhisperSTT) exactly as they are; nothing in speech/
was changed for this script. It also reuses the EXISTING IntakePipeline
unchanged apart from one small additive method
(IntakePipeline.answer_voice_transcript) that lets an already-completed
transcript be handed in directly, instead of re-transcribing raw audio a
second time.

Flow, mirroring test_conversation.py:
    microphone -> Silero VAD -> completed utterance -> WhisperSTT
                -> transcript -> IntakePipeline.answer_voice_transcript()

Run from a terminal (see README below for VS Code steps):
    python voice_conversation.py
"""

import re

from intake.llm_structurer import GroqLLMStructurer
from intake.models import AgeInfo, AgeSource, AgeStatus
from intake.pipeline import IntakePipeline
from speech.vad_recorder import MicrophoneVADListener


def _extract_age_years(text: str):
    """Spoken age answers are rarely a bare digit string ("I'm 30 years
    old", "thirty two"); take the first integer found in the transcript,
    same "extract from natural phrasing" approach as
    intake/question_tree.py's _parse_severity."""
    match = re.search(r"\d+", text or "")
    return int(match.group(0)) if match else None


def main() -> int:
    print("Loading Whisper + Silero VAD (first run may take a moment)...")
    listener = MicrophoneVADListener()  # loads Silero VAD now; Whisper loads on first use

    pipeline = IntakePipeline(
        patient_id="voice-001",
        structurer=GroqLLMStructurer(),
    )

    while not pipeline.complete:
        print("\nMediPilot:", pipeline.current_prompt)
        print("(listening... speak now)")

        result = listener.start_listening()
        print("You:", result.text)

        if pipeline.session.state.value == "AGE_CONTEXT":
            age = _extract_age_years(result.text)
            if age is None:
                print("Could not understand the age -- please say it again as a number.")
            else:
                pipeline.record_age(
                    AgeInfo(value_days=age * 365, source=AgeSource.PATIENT, status=AgeStatus.KNOWN)
                )
            continue

        try:
            pipeline.answer_voice_transcript(
                text=result.text, language=result.language, asr_reliability=result.asr_reliability
            )
        except Exception as e:
            print("Invalid answer:", e)

    if pipeline.current_prompt:
        print("\nMediPilot:", pipeline.current_prompt)

    print("\n=== INTAKE COMPLETE ===")

    outcome = pipeline.finalize()

    print("\nStructured narrative:")
    print(outcome.record.narrative)

    print("\nRed flag result:")
    print(outcome.red_flag)

    print("\nState history:")
    print(outcome.record.state_history)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
