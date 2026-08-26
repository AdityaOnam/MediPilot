"""
Stage 2 pipeline: wires state machine (M03) -> question tree (M04) ->
speech adapter (M05) -> LLM structurer (M06) -> structured IntakeRecord ->
red-flag pass (M07), with age stratification (M08) and reliability signal
collection (M09-interface) folded in at the right points.

Orchestration only. Nothing here makes a clinical decision beyond the
deterministic red-flag table it calls — no acuity band, no risk score, no
scoring-model invocation. Those are explicitly out of scope for Stage 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from intake.age_stratification import AgeResolution, resolve_age_stratum
from intake.llm_structurer import LLMStructurer, StructurerOutputError
from intake.models import AgeInfo, IntakeRecord, ReliabilitySignals
from intake.question_tree import QuestionTreeSession, build_plan
from intake.red_flags import RedFlagResult, evaluate_red_flags
from intake.reliability import collect_reliability_signals
from intake.speech_adapter import SpeechAdapter, TypedInputAdapter, Utterance
from intake.state_machine import IntakeSession, IntakeState


@dataclass
class IntakeOutcome:
    record: IntakeRecord
    red_flag: RedFlagResult


class IntakePipeline:
    """
    Drives one patient through the Stage 2 flow. Callers supply answers
    turn by turn — `answer_text()` for typed input (always available),
    `answer_voice()` for a completed audio recording — matching whatever
    question the pipeline is currently asking (`current_prompt`). Age is
    supplied structurally via `record_age()`, since it is not a free-text
    turn.
    """

    def __init__(
        self,
        patient_id: Optional[str],
        structurer: LLMStructurer,
        speech_adapter: Optional[SpeechAdapter] = None,
    ):
        self.session = IntakeSession(patient_id=patient_id)
        self.session.start()
        self.structurer = structurer
        self.speech_adapter = speech_adapter or SpeechAdapter()
        self.typed_adapter = TypedInputAdapter()
        self.tree_session: Optional[QuestionTreeSession] = None
        self._age_resolution: Optional[AgeResolution] = None
        self._last_utterance: Optional[Utterance] = None

    # -- what to ask next -------------------------------------------------

    @property
    def current_prompt(self) -> Optional[str]:
        state = self.session.state
        if state == IntakeState.ASSISTANCE_CHECK:
            return "Is anyone with you?"
        if state == IntakeState.HUMAN_PREFERENCE:
            return "Would you prefer a person?"
        if state == IntakeState.HUMAN_ASSISTANCE_REQUESTED:
            # Acknowledge explicitly rather than terminating silently -- no
            # clinical questions follow this state (the state machine has no
            # further transition out of it).
            return "Okay, we'll get someone to help you. Please make your way to the help desk, or a staff member will come to you shortly."
        if state == IntakeState.CONSENT:
            return "May we use your medical information for this visit?"
        if state == IntakeState.AGE_CONTEXT:
            return "How old is the patient?"
        if state == IntakeState.CLINICAL_QUESTIONS and self.tree_session and self.tree_session.current_node:
            return self.tree_session.current_node.prompt
        if self.tree_session and self.tree_session.stopped_for_red_flag:
            # Intake stopped early because red_flags.py already confirmed a
            # time-critical presentation (see QuestionTreeSession._maybe_stop_
            # for_confirmed_red_flag). By the time this is checked, the state
            # machine has already moved on to COMPLETE (see pipeline.py's
            # _answer_clinical_question), not CLINICAL_QUESTIONS -- acknowledge
            # the handoff rather than going quiet, regardless of state.
            return "Thank you — based on what you've told us, we're moving you straight to the clinical team now."
        return None

    # -- answering ----------------------------------------------------------

    def answer_text(self, text: str) -> None:
        self._advance(self.typed_adapter.read(text))

    def answer_voice(self, audio) -> None:
        self._advance(self.speech_adapter.listen(audio))

    def answer_voice_transcript(
        self, text: str, language: Optional[str] = None, asr_reliability: Optional[dict] = None
    ) -> None:
        """
        Same as answer_voice(), for a caller that already has a completed
        transcript (e.g. speech/vad_recorder.py's MicrophoneVADListener,
        which does its own VAD capture + WhisperSTT transcription) rather
        than raw audio. Avoids a redundant second transcription pass
        through self.speech_adapter while still recording
        interaction_mode="voice" and the ASR metadata exactly as
        answer_voice() would -- this is what lets communication_barrier
        detection (question_tree.py, checking asr_reliability) work the
        same way for a fully voice-driven conversation as it already does
        for answer_voice().
        """
        self._advance(Utterance(text=text, interaction_mode="voice", language=language, asr_reliability=asr_reliability))

    def record_age(self, age_info: AgeInfo) -> None:
        if self.session.state != IntakeState.AGE_CONTEXT:
            raise RuntimeError(f"not awaiting age (state={self.session.state})")
        self.session.record_age(age_info)
        self._age_resolution = resolve_age_stratum(age_info)
        plan = build_plan(self._age_resolution.stratum, self.session.medical_information_consent)
        self.tree_session = QuestionTreeSession(plan=plan)

    def _advance(self, utterance: Utterance) -> None:
        self._last_utterance = utterance
        state = self.session.state

        if state == IntakeState.ASSISTANCE_CHECK:
            self.session.answer_assistance_check(utterance.text)
        elif state == IntakeState.HUMAN_PREFERENCE:
            self.session.answer_human_preference(utterance.text)
            # If the patient wants a person, the state machine moves to
            # HUMAN_ASSISTANCE_REQUESTED and there is nothing further to do:
            # clinical questions stop here, per M03.
        elif state == IntakeState.CONSENT:
            self.session.answer_consent(utterance.text)
            if self.session.state == IntakeState.LIMITED_INFORMATION_INTAKE:
                self.session.acknowledge_limited_information_intake()
        elif state == IntakeState.AGE_CONTEXT:
            raise RuntimeError("call record_age() with a structured AgeInfo, not answer_text/answer_voice")
        elif state == IntakeState.CLINICAL_QUESTIONS:
            self._answer_clinical_question(utterance)
        else:
            raise RuntimeError(f"no answer expected in state {state}")

    def _answer_clinical_question(self, utterance: Utterance) -> None:
        if self.tree_session is None:
            raise RuntimeError("record_age() must be called before clinical questions can be answered")
        try:
            self.tree_session.record_answer(utterance, self.structurer)
        except StructurerOutputError:
            # Malformed extraction or a structurer/API failure: skip this
            # node explicitly rather than fabricate an answer. The field
            # stays missing (see StructuredNarrative.missing_fields
            # convention) and the conversation moves on.
            self.tree_session.skip_current(reason="structurer_failed")
        if self.tree_session.complete:
            self.session.complete()

    @property
    def complete(self) -> bool:
        return self.session.state in (IntakeState.COMPLETE, IntakeState.HUMAN_ASSISTANCE_REQUESTED)

    # -- output -------------------------------------------------------------

    def finalize(self) -> IntakeOutcome:
        """
        Produce the Stage 2 output contract. Callable from any terminal
        state (including HUMAN_ASSISTANCE_REQUESTED, where clinical
        questions never ran) — unanswered fields stay explicitly missing,
        never fabricated.
        """
        narrative = self.tree_session.narrative if self.tree_session else None

        if self.tree_session is not None and self._age_resolution is not None:
            reliability = collect_reliability_signals(self.session, self.tree_session, self._age_resolution)
        else:
            reliability = ReliabilitySignals()

        record = IntakeRecord(
            patient_id=self.session.patient_id,
            assisted=self.session.assisted,
            human_assistance_requested=self.session.human_assistance_requested,
            medical_information_consent=self.session.medical_information_consent,
            interaction_mode=self._last_utterance.interaction_mode if self._last_utterance else None,
            language=self._last_utterance.language if self._last_utterance else None,
            communication_barrier=reliability.communication_barrier,
            age=self.session.age,
            narrative=narrative,
            reliability_signals=reliability,
            state_history=list(self.session.state_history),
        )

        red_flag = evaluate_red_flags(narrative) if narrative else RedFlagResult(
            red_flag=False, rule_id=None, matched_observations=[], description=None
        )
        return IntakeOutcome(record=record, red_flag=red_flag)
