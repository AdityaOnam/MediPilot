"""
M04 — Question tree.

A structured, deterministic, age-stratum-aware conversation tree. It
collects observations and patient/attendant-reported information and hands
free-text answers to the M06 LLM structurer for field extraction. It never
assigns Red/Yellow/Green and never touches acuity.

Also situation-specific: after the chief complaint is answered, the plan is
extended with a complaint-specific block of follow-up questions (chest
pain, abdominal pain, fever, headache, injury, or a generic fallback) —
see classify_complaint() / COMPLAINT_BRANCHES below. Still deterministic:
the branch taken is a fixed function of what was extracted, not a model
decision at conversation-flow time.

Voice-first: designed to be driven by transcribed Utterances (M05), but
every node also accepts typed text directly — there is no node that
requires speech.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from enum import Enum
from typing import Callable, Optional

from intake.complaint_classifier import (
    ComplaintClassifier,
    ComplaintClassifierError,
    GroqComplaintClassifier,
    KeywordComplaintClassifier,
)
from intake.llm_structurer import LLMStructurer, StructurerOutputError
from intake.red_flags import evaluate_red_flags
from intake.models import (
    AgeStratum,
    ConsentState,
    Observation,
    ObservationCode,
    ReliabilitySignals,
    StructuredNarrative,
    TriState,
)
from intake.speech_adapter import Utterance
from intake.state_machine import InvalidAnswerError


class AnswerKind(str, Enum):
    FREE_TEXT = "free_text"       # routed through the LLM structurer
    YES_NO = "yes_no"
    NUMERIC_0_10 = "numeric_0_10"


@dataclass(frozen=True)
class Option:
    """One choice in a closed-answer set, for UI rendering and for the
    voice option-matcher (semantic match of a spoken answer against
    `label_en`/`label_hi` to decide auto-advance vs. ask-again)."""
    value: str
    label_en: str
    label_hi: str


# The only bilingual option set defined so far. Every YES_NO node in this
# tree shares it (see QuestionNode.options below) rather than each node
# repeating "Yes"/"No" -- this is not a clinical translation, just the
# same haan/nahi vocabulary _YES_KEYWORDS/_NO_KEYWORDS already parse.
# FREE_TEXT nodes have no fixed answer set and so get no options; their
# prompts are also not yet translated to Hindi (see prompt_hi below) --
# hand-translating ~140 clinical prompts needs a reviewer, not a guess.
_YES_NO_OPTIONS = (
    Option("yes", "Yes", "हाँ"),
    Option("no", "No", "नहीं"),
)


@dataclass
class QuestionNode:
    node_id: str
    prompt: str
    kind: AnswerKind
    prompt_hi: Optional[str] = None  # not yet populated for most nodes -- see note above
    target_field: Optional[str] = None  # for structured (non-free-text) nodes
    requires_consent: bool = False  # skipped (not fabricated) when consent is declined
    implies_symptom: Optional[str] = None  # ObservationCode this question is "about"; if
    # already present in narrative.symptoms before this node is reached, it is skipped.
    implied_by_keywords: tuple = ()  # bilingual keywords; if any already appear anywhere
    # in the conversation's accumulated raw transcript, this question is treated as
    # already answered and skipped rather than re-asked. Covers the common case where
    # the patient volunteers the answer as part of a richer sentence -- "crushing pain
    # in my chest that spreads to my arm" already answers character AND radiation, not
    # just location -- without needing a closed ObservationCode for every concept.
    # Together with implies_symptom, this is what makes the next question depend on
    # what was actually said rather than walking a fixed list: a good triage nurse
    # does not repeat a question the patient already answered unprompted.

    # -- Level-2 branching within a category -----------------------------
    #
    # (follow_up_triggers, follow_ups) are the "levels" of the tree: extra
    # questions that fire only when the ANSWER to THIS question matches.
    # This is the difference between a flat questionnaire (ask every
    # follow-up, then filter) and a triage conversation (ask what the
    # last answer made relevant). "Any bleeding?" -> yes -> then and only
    # then, "where?" and "since when?" get asked.
    #
    # Semantics:
    #   * follow_up_triggers empty AND parent yes/no answer was YES -> fire
    #   * follow_up_triggers non-empty -> fire when any substring appears
    #                  in the normalized answer text (case-insensitive)
    # follow_ups may themselves carry follow_ups; the walker nests them
    # the same way it splices the top level.
    #
    # Declarative rather than a callback so a reviewer can audit branching
    # against the plan document without reading arbitrary Python.
    follow_up_triggers: tuple = ()
    follow_ups: tuple = ()

    @property
    def options(self) -> tuple:
        """Closed answer set for UI buttons / the voice option-matcher.
        Only YES_NO currently has one -- NUMERIC_0_10 is a scale, not a
        discrete choice, and FREE_TEXT has no fixed set by definition."""
        if self.kind == AnswerKind.YES_NO:
            return _YES_NO_OPTIONS
        return ()

    def to_dict(self) -> dict:
        """Serialization for a tree-driving API. `promptHi` is None for the
        great majority of nodes today (see the module-level note by
        _YES_NO_OPTIONS) -- callers must handle a missing Hindi prompt
        rather than assume every node has one."""
        return {
            "nodeId": self.node_id,
            "prompt": self.prompt,
            "promptHi": self.prompt_hi,
            "kind": self.kind.value,
            "options": [
                {"value": o.value, "label": {"en": o.label_en, "hi": o.label_hi}}
                for o in self.options
            ],
        }


# Ordered per-branch plans. Mirrors intake_architecture_part2.svg:
#   Adult/Adolescent: CC, onset, severity, pregnancy/last period, medications
#   Paediatric:        CC via carer, feeding/behaviour, immunisation status
#   Geriatric:          baseline function, falls/confusion, polypharmacy

_COMMON_OPENING = [
    QuestionNode("chief_complaint", "What is bothering you today?", AnswerKind.FREE_TEXT),
    QuestionNode("onset", "When did this start?", AnswerKind.FREE_TEXT),
    QuestionNode("severity", "On a scale of 0 to 10, how bad is it right now?", AnswerKind.NUMERIC_0_10),
]

_ADULT_ADOLESCENT_TAIL = [
    QuestionNode("pregnancy_status", "Could you be pregnant?", AnswerKind.YES_NO),
    QuestionNode("analgesia_given", "Have you already taken any pain-relief medicine?", AnswerKind.YES_NO),
    QuestionNode(
        "medications", "Are you taking any regular medications?", AnswerKind.FREE_TEXT,
        requires_consent=True,
    ),
    QuestionNode(
        "relevant_history", "Any past medical history we should know?", AnswerKind.FREE_TEXT,
        requires_consent=True,
    ),
]

_PAEDIATRIC_TAIL = [
    QuestionNode("feeding_normally", "Is the child feeding/drinking normally?", AnswerKind.YES_NO),
    QuestionNode("behaviour", "How is the child behaving right now?", AnswerKind.FREE_TEXT),
]

_GERIATRIC_TAIL = [
    QuestionNode("baseline_function", "Compared to usual, how is their movement and alertness today?", AnswerKind.FREE_TEXT),
    QuestionNode("falls_or_confusion", "Any falls, or any new confusion?", AnswerKind.YES_NO),
    QuestionNode(
        "medications", "What medications do they take regularly?", AnswerKind.FREE_TEXT,
        requires_consent=True,
    ),
]

_PAEDIATRIC_STRATA = {AgeStratum.NEONATE, AgeStratum.INFANT, AgeStratum.CHILD}


# ---------------------------------------------------------------------------
# Complaint-specific branching.
#
# The base plan above (chief_complaint -> onset -> severity -> stratum tail)
# is the same for every patient. What follows makes the middle of the
# conversation situation-specific: right after chief_complaint is answered,
# classify_complaint() looks at what was actually reported and a matching
# block of follow-up questions is spliced into the plan, ahead of onset.
# onset/severity stay the single shared questions asked once, so no
# category's question list repeats them.
#
# Architecture: ONE declarative registry (CATEGORIES), not a hand-written
# if/elif chain or one dict per category. Each ComplaintCategory bundles a
# name, the bilingual keywords/symptom-codes that select it, and its
# question list. classify_complaint() and _insert_branch_questions() are
# both small, fixed loops over this single list -- adding a 28th category
# later means appending one ComplaintCategory entry, not touching any
# function body. All branch questions are FREE_TEXT, handed to the SAME,
# unmodified LLM structurer as every other free-text node -- this file only
# decides which question to ask next, never what the answer means
# clinically.
#
# Question sets are deliberately short (3-6 follow-ups): high-value,
# situation-specific questions, not an exhaustive review of systems.
# ---------------------------------------------------------------------------

# Reusable bilingual "already mentioned" keyword sets, shared across
# categories wherever the same associated-symptom question recurs (e.g.
# "any fever along with it?" appears in half a dozen categories). Defined
# once so they stay consistent and are easy to extend in one place.
_FEVER_MENTIONED = ("fever", "bukhar", "bukhaar", "temperature")
_VOMIT_MENTIONED = ("vomit", "throwing up", "threw up", "ulti")
_DIARRHEA_MENTIONED = ("diarrhea", "diarrhoea", "loose motion", "loose stool", "dast")
_BREATHING_DIFFICULTY_MENTIONED = (
    "breathless", "short of breath", "cant breathe", "difficulty breathing",
    "trouble breathing", "saans phool", "saans lene mein",
)
_SWEATING_MENTIONED = ("sweat", "paseena", "pasina")
_BLEEDING_MENTIONED = ("bleeding", "blood", "khoon")
_SWELLING_MENTIONED = ("swelling", "swollen", "sujan")
_NUMBNESS_WEAKNESS_MENTIONED = ("numbness", "numb", "weakness", "tingling", "kamzori")
_PAIN_CHARACTER_MENTIONED = (
    "crushing", "sharp pain", "dull ache", "burning pain", "stabbing", "cramping",
    "throbbing",
)


@dataclass(frozen=True)
class ComplaintCategory:
    name: str
    keywords: tuple = ()       # bilingual substring keywords against chief_complaint text
    symptom_codes: tuple = ()  # ObservationCode values whose presence also selects this category
    questions: tuple = ()      # ordered QuestionNode follow-ups (onset/severity are shared, not repeated)


CATEGORIES = [
    # --- time-critical / safety-relevant presentations first -------------
    ComplaintCategory(
        "choking",
        keywords=(
            "choking", "something stuck in throat", "stuck in throat", "stuck in my throat",
            "stuck in", "cant swallow", "swallowed something", "gale mein kuch phas gaya",
            "dum ghut raha hai",
        ),
        symptom_codes=(ObservationCode.CHOKING_OR_AIRWAY_OBSTRUCTION.value,),
        questions=(
            QuestionNode("what_happened", "What got stuck, or what did they swallow, and when?", AnswerKind.FREE_TEXT),
            QuestionNode("breathing_now", "Can they breathe or make any sound right now?", AnswerKind.FREE_TEXT),
            QuestionNode("able_to_cough", "Are they able to cough or speak at all?", AnswerKind.FREE_TEXT),
        ),
    ),
    ComplaintCategory(
        "seizure",
        keywords=("seizure", "fit", "convulsion", "convulsions", "behosh", "daura pada", "jhatke"),
        symptom_codes=(
            ObservationCode.SEIZURE.value, ObservationCode.ALTERED_CONSCIOUSNESS.value,
            ObservationCode.NOT_RESPONDING.value,
        ),
        questions=(
            QuestionNode("what_happened", "Can you describe exactly what happened?", AnswerKind.FREE_TEXT),
            QuestionNode("episode_duration", "About how long did it last?", AnswerKind.FREE_TEXT),
            QuestionNode("responsive_now", "Are they responding normally now?", AnswerKind.FREE_TEXT),
            QuestionNode("prior_history", "Has anything like this happened before?", AnswerKind.FREE_TEXT),
        ),
    ),
    ComplaintCategory(
        "sudden_weakness_speech",
        keywords=(
            "sudden weakness", "one side weak", "left side weak", "right side weak", "went weak",
            "numbness", "cant speak properly", "slurred speech", "speech is slurred",
            "face drooping", "ek taraf kamzori", "chehra tedha",
        ),
        symptom_codes=(
            ObservationCode.SUDDEN_ONE_SIDED_WEAKNESS.value, ObservationCode.FACIAL_DROOP.value,
            ObservationCode.SUDDEN_SPEECH_CHANGE.value,
        ),
        questions=(
            QuestionNode("exact_onset_time", "Exactly when did this start?", AnswerKind.FREE_TEXT),
            QuestionNode("which_side", "Which side is affected?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "speech_check", "Any trouble speaking or understanding speech?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.SUDDEN_SPEECH_CHANGE.value,
            ),
            QuestionNode(
                "face_check", "Does one side of the face look different?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.FACIAL_DROOP.value,
            ),
        ),
    ),
    ComplaintCategory(
        "poisoning_bite",
        keywords=(
            "poison", "overdose", "snake bite", "snakebite", "insect bite", "animal bite", "dog bite",
            "scorpion", "zeher", "saanp ne kata", "keede ne kata",
        ),
        symptom_codes=(ObservationCode.POISONING_OR_OVERDOSE.value, ObservationCode.SNAKEBITE.value),
        questions=(
            QuestionNode("substance_or_creature", "What was taken or swallowed, or what bit them?", AnswerKind.FREE_TEXT),
            QuestionNode("time_since", "How long ago did this happen?", AnswerKind.FREE_TEXT),
            QuestionNode("symptoms_since", "Any symptoms since then, like vomiting, dizziness, or swelling?", AnswerKind.FREE_TEXT),
        ),
    ),
    ComplaintCategory(
        "chest_pain",
        keywords=(
            "chest pain", "chest mein pain", "chest me pain", "chest me dard", "seene mein dard",
            "palpitations", "heart racing", "dil dhadakna", "dil ki dhadkan",
        ),
        symptom_codes=(ObservationCode.CHEST_PAIN.value,),
        questions=(
            QuestionNode("pain_location", "Where exactly is the pain?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "pain_character", "What does the pain feel like — sharp, dull, crushing, or burning?", AnswerKind.FREE_TEXT,
                implied_by_keywords=_PAIN_CHARACTER_MENTIONED,
            ),
            QuestionNode(
                "pain_radiation", "Does the pain spread anywhere, like your arm, neck, or jaw?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.RADIATING_PAIN.value,
                implied_by_keywords=("radiat", "spreads to", "spreading to", "goes down my arm", "goes to my jaw"),
                # Level 2: only asked when the patient actually said the pain radiates.
                follow_up_triggers=("arm", "jaw", "neck", "back", "shoulder", "haath", "gardan", "kandhe"),
                follow_ups=(
                    QuestionNode("radiation_side", "Which side, or is it both sides?", AnswerKind.FREE_TEXT),
                    QuestionNode("radiation_intensity", "Is the spreading pain as bad as the chest pain, or milder?", AnswerKind.FREE_TEXT),
                ),
            ),
            QuestionNode(
                "breathing_difficulty", "Are you having any difficulty breathing?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.BREATHLESSNESS.value,
                implied_by_keywords=_BREATHING_DIFFICULTY_MENTIONED,
                # Level 2: if breathless, ask the two things that separate
                # cardiac from pulmonary. Deliberately no diagnosis here --
                # both go into the narrative and the model plus rules decide.
                follow_up_triggers=("yes", "haan", "cant", "difficult", "hard to breathe", "taklif", "phool"),
                follow_ups=(
                    QuestionNode("breath_worsens_lying", "Does it get worse when you lie down flat?", AnswerKind.YES_NO),
                    QuestionNode("cough_phlegm", "Any cough, or bringing up phlegm?", AnswerKind.FREE_TEXT),
                ),
            ),
            QuestionNode(
                "sweating_nausea", "Are you sweating, or feeling nauseous?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.SWEATING.value,
                implied_by_keywords=_SWEATING_MENTIONED,
            ),
        ),
    ),
    ComplaintCategory(
        "pregnancy_labour",
        keywords=("labour", "labor", "contractions", "pregnant and pain", "prasav", "contractions shuru"),
        symptom_codes=(ObservationCode.ACTIVE_LABOUR.value, ObservationCode.BLEEDING_IN_PREGNANCY.value),
        questions=(
            QuestionNode("gestational_age", "How many weeks pregnant are you, if known?", AnswerKind.FREE_TEXT),
            QuestionNode("contraction_pattern", "How often are the contractions coming?", AnswerKind.FREE_TEXT),
            QuestionNode("fluid_leakage", "Has your water broken, or any fluid leakage?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "pregnancy_bleeding", "Any bleeding?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.BLEEDING_IN_PREGNANCY.value,
                implied_by_keywords=_BLEEDING_MENTIONED,
            ),
            QuestionNode("fetal_movement", "Have you felt the baby moving?", AnswerKind.FREE_TEXT),
        ),
    ),
    ComplaintCategory(
        "vaginal_bleeding",
        keywords=("vaginal bleeding", "bleeding down there", "heavy bleeding period", "spotting"),
        symptom_codes=(ObservationCode.VAGINAL_BLEEDING.value,),
        questions=(
            QuestionNode("bleeding_onset", "When did the bleeding start?", AnswerKind.FREE_TEXT),
            QuestionNode("bleeding_amount", "How heavy is the bleeding?", AnswerKind.FREE_TEXT),
            QuestionNode("possible_pregnancy", "Is there any chance you could be pregnant?", AnswerKind.FREE_TEXT),
            QuestionNode("pain_check", "Any pain along with the bleeding?", AnswerKind.FREE_TEXT),
        ),
    ),
    ComplaintCategory(
        "breathing_difficulty",
        keywords=(
            "difficulty breathing", "breathless", "cant breathe", "short of breath",
            "saans lene mein taklif", "saans phool rahi hai",
        ),
        symptom_codes=(ObservationCode.BREATHLESSNESS.value, ObservationCode.DIFFICULTY_SPEAKING_FULL_SENTENCES.value),
        questions=(
            QuestionNode("onset_pattern", "Did this come on suddenly, or gradually?", AnswerKind.FREE_TEXT),
            QuestionNode("triggers", "Does anything bring it on, like exertion or lying down?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "chest_pain_check", "Any chest pain along with it?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.CHEST_PAIN.value,
                implied_by_keywords=("chest pain",),
            ),
            QuestionNode("noisy_breathing", "Any wheezing or noisy breathing?", AnswerKind.FREE_TEXT),
        ),
    ),
    ComplaintCategory(
        "bleeding_wound",
        keywords=("cut", "wound", "bleeding", "laceration", "gehra ghav", "khoon beh raha hai"),
        symptom_codes=(ObservationCode.UNCONTROLLED_BLEEDING.value, ObservationCode.PENETRATING_INJURY.value),
        questions=(
            QuestionNode("wound_cause", "How did the cut or wound happen?", AnswerKind.FREE_TEXT),
            QuestionNode("bleeding_control", "Is the bleeding controlled, or still ongoing?", AnswerKind.FREE_TEXT),
            QuestionNode("wound_size", "How deep or large is the wound, roughly?", AnswerKind.FREE_TEXT),
        ),
    ),
    ComplaintCategory(
        "burns",
        keywords=("burn", "burned", "burnt", "scald", "jal gaya", "jal gayi"),
        symptom_codes=(ObservationCode.BURN_INJURY.value,),
        questions=(
            QuestionNode("burn_cause", "What caused the burn — fire, hot liquid, chemical, or electricity?", AnswerKind.FREE_TEXT),
            QuestionNode("burn_area", "Roughly how large an area is affected?", AnswerKind.FREE_TEXT),
            QuestionNode("blistering", "Is there blistering or broken skin?", AnswerKind.FREE_TEXT),
        ),
    ),
    ComplaintCategory(
        "injury",
        keywords=("injury", "injured", "accident", "fell", "fall", "chot", "gir gaya", "gir gayi"),
        symptom_codes=(),
        questions=(
            QuestionNode(
                "mechanism", "How did the injury happen?", AnswerKind.FREE_TEXT,
                # Level 2: a road accident or a fall from height is a
                # different problem from a kitchen cut, so the follow-ups
                # depend on what the patient actually described. The
                # classification stays in the narrative -- no rule here
                # decides acuity.
                follow_up_triggers=(
                    "road", "accident", "bike", "car", "truck", "hit by", "run over",
                    "fell from", "fell down stairs", "height", "chhat se", "gir gaya",
                    "fight", "beaten", "assault", "attack",
                ),
                follow_ups=(
                    QuestionNode("loss_of_consciousness", "Did they lose consciousness at any point, even briefly?", AnswerKind.YES_NO),
                    QuestionNode("head_neck_pain", "Any pain in the head, neck, or back?", AnswerKind.FREE_TEXT),
                    QuestionNode("multiple_injuries", "Is there more than one place injured?", AnswerKind.YES_NO),
                ),
            ),
            QuestionNode("injury_location", "Where is the injury?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "bleeding", "Is there any bleeding, and is it under control?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.UNCONTROLLED_BLEEDING.value,
                implied_by_keywords=_BLEEDING_MENTIONED,
                # Level 2: bleeding only earns follow-ups if it is ongoing.
                follow_up_triggers=("not stopping", "still bleeding", "wont stop", "cant stop", "heavy", "gushing", "beh raha", "band nahi"),
                follow_ups=(
                    QuestionNode("bleeding_duration", "About how long has it been bleeding?", AnswerKind.FREE_TEXT),
                    QuestionNode("pressure_applied", "Have you been able to apply pressure to it?", AnswerKind.YES_NO),
                ),
            ),
            QuestionNode(
                "deformity_swelling", "Does it look out of shape, or is there swelling?", AnswerKind.FREE_TEXT,
                implied_by_keywords=_SWELLING_MENTIONED,
            ),
            QuestionNode("function", "Can you move and use the area normally?", AnswerKind.FREE_TEXT),
        ),
    ),
    ComplaintCategory(
        "abdominal_pain",
        keywords=(
            "abdominal pain", "abdomen pain", "abdomen hurts",
            "stomach pain", "stomach ache", "stomach hurts", "my stomach",
            "belly pain", "belly hurts", "tummy pain", "tummy hurts",
            "pet mein dard", "pet me dard", "pet dard", "pet dukh raha hai",
        ),
        symptom_codes=(ObservationCode.ABDOMINAL_PAIN.value,),
        questions=(
            QuestionNode("pain_location", "Where exactly is the pain?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "pain_character", "What does the pain feel like — cramping, sharp, or a dull ache?", AnswerKind.FREE_TEXT,
                implied_by_keywords=_PAIN_CHARACTER_MENTIONED,
            ),
            QuestionNode(
                "vomit_check", "Have you had any vomiting?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.VOMITING.value, implied_by_keywords=_VOMIT_MENTIONED,
            ),
            QuestionNode(
                "bowel_symptoms", "Any diarrhea or change in your bowel movements?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.DIARRHEA.value, implied_by_keywords=_DIARRHEA_MENTIONED,
            ),
            QuestionNode(
                "associated_fever", "Do you have a fever along with this?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.FEVER.value, implied_by_keywords=_FEVER_MENTIONED,
            ),
            QuestionNode(
                "urinary_check", "Any burning or pain when you urinate?", AnswerKind.FREE_TEXT,
                implied_by_keywords=("burning urination", "peshab mein jalan", "burning when i pee", "painful urination"),
            ),
        ),
    ),
    ComplaintCategory(
        "vomiting",
        keywords=("vomiting", "throwing up", "nausea", "nauseous", "ulti", "ulti aa rahi hai", "jee michlana"),
        symptom_codes=(ObservationCode.VOMITING.value,),
        questions=(
            QuestionNode("vomit_duration", "How long have you been vomiting?", AnswerKind.FREE_TEXT),
            QuestionNode("vomit_frequency", "About how many times so far?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "vomit_blood", "Any blood in the vomit?", AnswerKind.FREE_TEXT,
                implied_by_keywords=_BLEEDING_MENTIONED,
            ),
            QuestionNode(
                "fluids_tolerance", "Are you able to keep any fluids down?", AnswerKind.FREE_TEXT,
                implied_by_keywords=("cant keep anything down", "keeping fluids down", "cant keep fluids down"),
            ),
            QuestionNode(
                "vomit_assoc_pain", "Any pain in your stomach?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.ABDOMINAL_PAIN.value,
                implied_by_keywords=("stomach pain", "abdominal pain", "pet dard", "pet mein dard"),
            ),
            QuestionNode(
                "vomit_assoc_fever_diarrhea", "Any fever or loose motions along with this?", AnswerKind.FREE_TEXT,
                implied_by_keywords=_FEVER_MENTIONED + _DIARRHEA_MENTIONED,
            ),
        ),
    ),
    ComplaintCategory(
        "diarrhea",
        keywords=("diarrhea", "diarrhoea", "loose motion", "loose motions", "dast", "dast lag rahe hain", "food poisoning"),
        symptom_codes=(ObservationCode.DIARRHEA.value,),
        questions=(
            QuestionNode("diarrhea_duration", "How long has this been going on?", AnswerKind.FREE_TEXT),
            QuestionNode("diarrhea_frequency", "About how many times a day?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "stool_blood", "Any blood in your stools?", AnswerKind.FREE_TEXT,
                implied_by_keywords=_BLEEDING_MENTIONED,
            ),
            QuestionNode(
                "fluids_tolerance", "Are you able to keep any fluids down?", AnswerKind.FREE_TEXT,
                implied_by_keywords=("cant keep anything down", "keeping fluids down", "cant keep fluids down"),
            ),
            QuestionNode(
                "diarrhea_assoc_symptoms", "Any vomiting or fever along with this?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.VOMITING.value,
                implied_by_keywords=_VOMIT_MENTIONED + _FEVER_MENTIONED,
            ),
        ),
    ),
    ComplaintCategory(
        "fever",
        keywords=("fever", "bukhar", "bukhaar", "temperature"),
        symptom_codes=(ObservationCode.FEVER.value,),
        questions=(
            QuestionNode("measured_temperature", "Do you know your temperature, if it was measured?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "fever_duration", "How many days has the fever been there?", AnswerKind.FREE_TEXT,
                # Level 2: a fever more than 5 days puts dengue/typhoid on
                # the differential a clinician will want to think about.
                # The narrative gets the length; the follow-ups get the
                # specifics that make those illnesses distinguishable.
                follow_up_triggers=("5", "6", "7", "8", "9", "10", "week", "weeks", "hafta", "din se"),
                follow_ups=(
                    QuestionNode("fever_pattern", "Is the fever there all the time, or does it come and go?", AnswerKind.FREE_TEXT),
                    QuestionNode("rash_bleeding", "Any rash, or bleeding from the gums, nose, or in urine or stool?", AnswerKind.FREE_TEXT),
                    QuestionNode("recent_travel", "Any recent travel, or mosquito bites you remember?", AnswerKind.FREE_TEXT),
                ),
            ),
            QuestionNode(
                "chills", "Any chills or shivering?", AnswerKind.FREE_TEXT,
                implied_by_keywords=("chills", "shivering", "thand lag rahi"),
            ),
            QuestionNode(
                "cough_check", "Do you have a cough?", AnswerKind.FREE_TEXT,
                implied_by_keywords=("cough", "khansi", "khaansi"),
                # Level 2: only if there IS a cough.
                follow_up_triggers=("yes", "haan", "cough", "khansi", "khaansi"),
                follow_ups=(
                    QuestionNode("cough_type", "Dry cough, or are you bringing up phlegm?", AnswerKind.FREE_TEXT),
                    QuestionNode("cough_blood", "Any blood in what you are coughing up?", AnswerKind.YES_NO),
                ),
            ),
            QuestionNode(
                "breathing_difficulty", "Any difficulty breathing?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.BREATHLESSNESS.value,
                implied_by_keywords=_BREATHING_DIFFICULTY_MENTIONED,
            ),
        ),
    ),
    ComplaintCategory(
        "cough_cold",
        keywords=("cough", "cold", "khansi", "khaansi", "sardi", "runny nose", "blocked nose", "congestion"),
        symptom_codes=(),
        questions=(
            QuestionNode("cough_duration", "How long have you had this?", AnswerKind.FREE_TEXT),
            QuestionNode("cough_type", "Is it a dry cough, or are you bringing up phlegm?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "associated_fever", "Any fever along with it?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.FEVER.value, implied_by_keywords=_FEVER_MENTIONED,
            ),
            QuestionNode(
                "breathing_difficulty", "Any difficulty breathing?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.BREATHLESSNESS.value,
                implied_by_keywords=_BREATHING_DIFFICULTY_MENTIONED,
            ),
        ),
    ),
    ComplaintCategory(
        "sore_throat",
        keywords=("sore throat", "throat pain", "throat hurts", "gala dukh raha hai", "gale mein dard"),
        symptom_codes=(),
        questions=(
            QuestionNode("throat_duration", "How long has your throat been hurting?", AnswerKind.FREE_TEXT),
            QuestionNode("swallowing_difficulty", "Is it hard or painful to swallow?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "associated_fever", "Any fever along with it?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.FEVER.value, implied_by_keywords=_FEVER_MENTIONED,
            ),
        ),
    ),
    ComplaintCategory(
        "headache",
        keywords=(
            "headache", "head pain", "sar dard", "sar mein dard", "sardard", "head hurts",
            "dizzy", "dizziness", "fainting", "fainted", "chakkar", "chakkar aana",
        ),
        symptom_codes=(),
        questions=(
            QuestionNode("onset_character", "Did this come on suddenly, or build up gradually?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "neuro_symptoms", "Any weakness, numbness, or trouble speaking?", AnswerKind.FREE_TEXT,
                implied_by_keywords=_NUMBNESS_WEAKNESS_MENTIONED + ("cant speak", "slurred speech"),
            ),
            QuestionNode(
                "vomit_check", "Any vomiting along with it?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.VOMITING.value, implied_by_keywords=_VOMIT_MENTIONED,
            ),
            QuestionNode(
                "vision_changes", "Any changes in your vision?", AnswerKind.FREE_TEXT,
                implied_by_keywords=("blurry vision", "vision changed", "cant see properly"),
            ),
            QuestionNode(
                "fainting_episode", "Did you actually lose consciousness, even briefly?", AnswerKind.FREE_TEXT,
                implied_by_keywords=("fainted", "lost consciousness", "unconscious", "behosh"),
            ),
        ),
    ),
    ComplaintCategory(
        "weakness_fatigue",
        keywords=("weakness", "fatigue", "tired", "tiredness", "kamzori", "kamzor", "thakan"),
        symptom_codes=(ObservationCode.WEAKNESS_GENERAL.value,),
        questions=(
            QuestionNode("weakness_duration", "How long has this been going on?", AnswerKind.FREE_TEXT),
            QuestionNode("weakness_distribution", "Is the weakness on one side, or all over?", AnswerKind.FREE_TEXT),
            QuestionNode("appetite_sleep", "How has your appetite and sleep been?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "associated_fever", "Any fever along with it?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.FEVER.value, implied_by_keywords=_FEVER_MENTIONED,
            ),
        ),
    ),
    ComplaintCategory(
        "back_neck_pain",
        keywords=("back pain", "neck pain", "backache", "peeth dard", "gardan dard", "kamar dard"),
        symptom_codes=(),
        questions=(
            QuestionNode("pain_location", "Where exactly is the pain?", AnswerKind.FREE_TEXT),
            QuestionNode("injury_onset", "Did this start after any injury or strain?", AnswerKind.FREE_TEXT),
            QuestionNode("radiating_to_limb", "Does the pain spread down your arm or leg?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "limb_numbness_weakness", "Any numbness or weakness in your arms or legs?", AnswerKind.FREE_TEXT,
                implied_by_keywords=_NUMBNESS_WEAKNESS_MENTIONED,
            ),
        ),
    ),
    ComplaintCategory(
        "limb_joint_pain",
        keywords=("joint pain", "knee pain", "shoulder pain", "ankle pain", "wrist pain", "jodo mein dard", "haath mein dard", "pair mein dard"),
        symptom_codes=(),
        questions=(
            QuestionNode("pain_location", "Where exactly is the pain?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "swelling_redness", "Any swelling or redness in the joint?", AnswerKind.FREE_TEXT,
                implied_by_keywords=_SWELLING_MENTIONED,
            ),
            QuestionNode("injury_onset", "Did this start after any injury?", AnswerKind.FREE_TEXT),
            QuestionNode("function", "Can you move and use it normally?", AnswerKind.FREE_TEXT),
        ),
    ),
    ComplaintCategory(
        "rash_allergy",
        keywords=("rash", "itching", "itchy", "allergic reaction", "allergy", "khujli", "chakatte"),
        symptom_codes=(),
        questions=(
            QuestionNode("rash_location", "Where is the rash?", AnswerKind.FREE_TEXT),
            QuestionNode("rash_onset", "When did it start?", AnswerKind.FREE_TEXT),
            QuestionNode("rash_spreading", "Is it spreading?", AnswerKind.FREE_TEXT),
            QuestionNode("itching_or_pain", "Is it itchy, or painful?", AnswerKind.FREE_TEXT),
            QuestionNode("swelling_breathing", "Any swelling of the face or lips, or difficulty breathing?", AnswerKind.FREE_TEXT),
            QuestionNode("recent_exposure", "Did you eat, touch, or take anything new recently?", AnswerKind.FREE_TEXT),
        ),
    ),
    ComplaintCategory(
        "swelling",
        keywords=("swelling", "swollen", "sujan", "sooj gaya"),
        symptom_codes=(),
        questions=(
            QuestionNode("swelling_location", "Where is the swelling?", AnswerKind.FREE_TEXT),
            QuestionNode("swelling_onset", "When did it start?", AnswerKind.FREE_TEXT),
            QuestionNode("swelling_pain", "Is it painful?", AnswerKind.FREE_TEXT),
            QuestionNode("swelling_breathing", "Any difficulty breathing or swallowing along with the swelling?", AnswerKind.FREE_TEXT),
        ),
    ),
    ComplaintCategory(
        "eye_problem",
        keywords=("eye pain", "vision problem", "blurry vision", "cant see", "aankh mein dard", "aankhon mein dikhna band"),
        symptom_codes=(),
        questions=(
            QuestionNode("eye_which", "Which eye, or both?", AnswerKind.FREE_TEXT),
            QuestionNode("vision_change", "Has your vision changed?", AnswerKind.FREE_TEXT),
            QuestionNode("eye_injury_or_exposure", "Did anything get into the eye, or was there an injury?", AnswerKind.FREE_TEXT),
        ),
    ),
    ComplaintCategory(
        "ear_problem",
        keywords=("ear pain", "ear ache", "hearing problem", "cant hear", "kaan mein dard", "kaan dard"),
        symptom_codes=(),
        questions=(
            QuestionNode("ear_which", "Which ear, or both?", AnswerKind.FREE_TEXT),
            QuestionNode("ear_discharge", "Any discharge or fluid from the ear?", AnswerKind.FREE_TEXT),
            QuestionNode("hearing_change", "Any change in hearing?", AnswerKind.FREE_TEXT),
        ),
    ),
    ComplaintCategory(
        "dental_pain",
        keywords=("tooth pain", "toothache", "dental pain", "mouth pain", "dant dard", "mooh mein dard"),
        symptom_codes=(),
        questions=(
            QuestionNode("tooth_location", "Which tooth or area?", AnswerKind.FREE_TEXT),
            QuestionNode("face_swelling", "Any swelling in your face or jaw?", AnswerKind.FREE_TEXT),
        ),
    ),
    ComplaintCategory(
        "urinary",
        keywords=("urinary", "urine", "burning urination", "peshab mein jalan", "peshab"),
        symptom_codes=(),
        questions=(
            QuestionNode("urinary_check", "Is there any burning or pain when you urinate?", AnswerKind.FREE_TEXT),
            QuestionNode("urinary_frequency", "Are you urinating more often, or feeling urgency?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "urine_blood", "Any blood in your urine?", AnswerKind.FREE_TEXT,
                implied_by_keywords=_BLEEDING_MENTIONED,
            ),
            QuestionNode("flank_pain", "Any pain in your back or side?", AnswerKind.FREE_TEXT),
            QuestionNode(
                "associated_fever", "Any fever along with it?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.FEVER.value, implied_by_keywords=_FEVER_MENTIONED,
            ),
        ),
    ),
    # ------------------------------------------------------------------
    # Two categories added for common ED presentations the earlier list
    # did not cover. Both are FREE_TEXT throughout because the answers
    # feed the same M06 structurer as everything else, and both use
    # level-2 branching (follow_ups) so the second-page questions are
    # only asked when the first answer made them relevant.
    # ------------------------------------------------------------------
    ComplaintCategory(
        "diabetic_emergency",
        keywords=(
            "diabetic", "diabetes", "sugar", "blood sugar", "hypoglycemia", "hypo",
            "low sugar", "high sugar", "shakkar", "sugar kam", "sugar zyada",
        ),
        # Time-critical when consciousness or breathing is involved, hence
        # the reuse of the existing ObservationCodes here.
        symptom_codes=(
            ObservationCode.ALTERED_CONSCIOUSNESS.value,
            ObservationCode.WEAKNESS_GENERAL.value,
        ),
        questions=(
            QuestionNode(
                "sugar_reading", "Have you measured your sugar recently, and what was the number?", AnswerKind.FREE_TEXT,
                # Level 2: if a very low or a very high number was named,
                # the follow-ups probe the two directions separately.
                follow_up_triggers=(
                    "low", "kam", "hypo", "40", "50", "60", "70",
                    "high", "zyada", "hyper", "300", "400", "500",
                ),
                follow_ups=(
                    QuestionNode("insulin_or_meds", "Are you on insulin, or any tablets for sugar?", AnswerKind.FREE_TEXT),
                    QuestionNode("missed_or_extra_dose", "Did you miss a meal, or take an extra dose today?", AnswerKind.FREE_TEXT),
                ),
            ),
            QuestionNode(
                "symptoms_now", "How are they feeling now -- weak, sweaty, confused, or drowsy?", AnswerKind.FREE_TEXT,
                # Level 2: any of these are worth their own line item.
                follow_up_triggers=("confused", "drowsy", "sleepy", "not responding", "cant wake", "behosh", "hosh nahi"),
                follow_ups=(
                    QuestionNode(
                        "responsive_now", "Are they able to answer you normally?", AnswerKind.YES_NO,
                    ),
                ),
            ),
            QuestionNode(
                "vomiting_or_breath",
                "Any vomiting, deep breathing, or fruity smell on the breath?", AnswerKind.FREE_TEXT,
                implies_symptom=ObservationCode.VOMITING.value,
                implied_by_keywords=_VOMIT_MENTIONED,
            ),
        ),
    ),
    ComplaintCategory(
        "mental_health",
        # Kept deliberately explicit rather than folding into "generic".
        # Under Invariant 6 ("the human closes every loop") a self-harm
        # presentation must reach a clinician; the questions here collect
        # the observations that make that routing possible without asking
        # anything a distressed patient will refuse to answer to a kiosk.
        keywords=(
            "want to end my life", "kill myself", "suicide", "suicidal",
            "hurt myself", "self harm", "self-harm", "cut myself",
            "overdose intentional", "took pills to",
            "panic attack", "anxiety attack",
            "khud ko marna", "jaan dena", "khudkushi",
        ),
        symptom_codes=(),
        questions=(
            QuestionNode(
                "safety_now", "Are you safe right now, and is anyone with you?", AnswerKind.FREE_TEXT,
                # Level 2: fire only when the answer says NOT safe / alone,
                # which is the follow-up path a triage nurse would take.
                follow_up_triggers=("no", "nahi", "alone", "akela", "not safe", "unsafe"),
                follow_ups=(
                    QuestionNode(
                        "want_human", "Would you like us to bring someone to sit with you now?", AnswerKind.YES_NO,
                    ),
                ),
            ),
            QuestionNode(
                "acted_on_it", "Have you done anything to hurt yourself in the last few hours?", AnswerKind.FREE_TEXT,
                # Level 2 (yes-only, no triggers): if yes, the two things a
                # clinician needs to know before anything else.
                follow_ups=(
                    QuestionNode("what_was_taken", "What did you take or do?", AnswerKind.FREE_TEXT),
                    QuestionNode("time_since", "About how long ago was that?", AnswerKind.FREE_TEXT),
                ),
            ),
            QuestionNode(
                "current_feelings", "Can you tell me a little about how you are feeling right now?", AnswerKind.FREE_TEXT,
            ),
            QuestionNode(
                "prior_care", "Are you being seen by a doctor or counsellor for this already?", AnswerKind.FREE_TEXT,
                requires_consent=True,
            ),
        ),
    ),
]

# Derived, not hand-maintained: name -> questions / name -> keywords, for
# fast lookup (the keyword map feeds only the offline fallback classifier
# below -- it is not the primary routing mechanism).
COMPLAINT_BRANCHES = {c.name: c.questions for c in CATEGORIES}
_CATEGORY_NAMES = [c.name for c in CATEGORIES]

# Keyword coverage is extended out-of-line via intake/complaint_lexicon.py
# so growing the vocabulary of things a patient can say does not touch
# routing logic. The lexicon adds ~1000 additional bilingual phrasings
# (Hindi in Devanagari, romanized Hindi, code-mixed Hinglish, common ASR
# mistranscriptions) that a keyword-based classifier can match on.
#
# Any category name in the lexicon that has no ComplaintCategory yet
# still gets an entry so the classifier can name it -- classify_complaint
# falls back to "generic" for those, which is the correct behaviour: the
# routing "knows" a name for the problem, the tree simply does not have a
# tailored follow-up block for it yet.
from intake.complaint_lexicon import (  # noqa: E402
    merge_into as _lexicon_merge,
    score_categories as _lexicon_score,
    LEXICON_CONFIDENCE_MIN_LEN as _LEXICON_MIN_LEN,
)
_CATEGORY_KEYWORDS = _lexicon_merge({c.name: c.keywords for c in CATEGORIES})

_default_classifier_singleton: Optional[ComplaintClassifier] = None


def _get_default_classifier() -> ComplaintClassifier:
    """
    Lazily builds the classifier used when classify_complaint() isn't given
    one explicitly. Prefers Groq (robust to arbitrary phrasing); falls back
    to the deterministic keyword classifier when no credentials/package are
    available -- this is what keeps every existing offline test (and any
    environment without GROQ_API_KEY) working unchanged: the Groq attempt
    fails fast on the missing-credentials check, before any network call,
    exactly like intake/llm_structurer.py's GroqLLMStructurer.
    """
    global _default_classifier_singleton
    if _default_classifier_singleton is None:
        try:
            candidate = GroqComplaintClassifier()
            candidate._ensure_client()  # cheap: fails fast if no package/key, no network call
            _default_classifier_singleton = candidate
        except ComplaintClassifierError:
            _default_classifier_singleton = KeywordComplaintClassifier(_CATEGORY_KEYWORDS)
    return _default_classifier_singleton


def classify_complaint(narrative: StructuredNarrative, classifier: Optional[ComplaintClassifier] = None) -> str:
    """
    Routing choice for which follow-up QUESTIONS to ask next -- not a
    clinical decision, and never touches acuity or red flags.

    Three layers, in priority order:
      1. Symptom-code evidence: already vetted through the closed
         ObservationCode vocabulary by the structurer -- the most reliable
         signal when present, and phrasing-independent by construction.
      2. LLM classification (default: Groq): understands the MEANING of
         whatever the patient said, in any phrasing/language, rather than
         requiring it to match a pre-written pattern. This is what makes
         e.g. "mujhe pet ajeeb lag raha hai aur ulti bhi ho rahi hai" route
         correctly even though it matches no fixed keyword.
      3. Deterministic keyword fallback: only reached when no LLM
         classifier is available or a classification call fails (see
         ComplaintClassifierError) -- a resilient degrade-gracefully path,
         not the primary mechanism. Known limitation: catches only
         Latin-script/romanized wording it was explicitly given, same as
         intake/llm_structurer.py's code_mixed heuristic.

    `classifier` is injectable for testing (see intake/complaint_classifier.py);
    defaults to a lazily-built Groq-or-keyword classifier.
    """
    # (1) Symptom-code evidence: the structurer already vetted these
    # through the closed ObservationCode vocabulary, so this is the most
    # reliable signal when present and does not need any text matching.
    symptoms = set(narrative.symptoms or [])
    for category in CATEGORIES:
        if category.symptom_codes and any(code in symptoms for code in category.symptom_codes):
            return category.name

    text = (narrative.chief_complaint or "").strip()
    if not text:
        return "generic"

    # (2) Lexicon similarity: score every branch by its longest matching
    # keyword (see complaint_lexicon.score_categories). Longer matches are
    # more specific -- "crushing chest pain" scores stronger for chest_pain
    # than "pain" scores for any category. If the top match is at least
    # LEXICON_CONFIDENCE_MIN_LEN characters we ROUTE ON IT: the LLM is
    # skipped entirely. This is what the user asked for -- semantic
    # keyword scoring first, LLM only when it genuinely adds signal.
    #
    # Skipping the LLM here matters for latency (the local structurer
    # takes ~20-40s per free-text turn) and for determinism (a matched
    # keyword goes to the same branch every time; a small LLM can drift).
    scored = _lexicon_score(text, _CATEGORY_KEYWORDS)
    if scored and scored[0][1] >= _LEXICON_MIN_LEN:
        best_name = scored[0][0]
        return best_name if best_name in _CATEGORY_NAMES else "generic"

    # (3) Only when the lexicon has no confident hit does the LLM run --
    # for genuinely novel phrasing the keyword layer was never given.
    try:
        clf = classifier or _get_default_classifier()
        result = clf.classify(text, _CATEGORY_NAMES, fallback="generic")
        if result in _CATEGORY_NAMES:
            return result
    except ComplaintClassifierError:
        pass

    # (4) Last resort: even a weak lexicon hit (score < min length) beats
    # returning "generic" outright, so use it before giving up.
    if scored:
        best_name = scored[0][0]
        return best_name if best_name in _CATEGORY_NAMES else "generic"
    return "generic"


def build_plan(stratum: Optional[AgeStratum], consent: ConsentState) -> list:
    """
    Resolve the ordered node list for a stratum. `stratum=None` means age
    could not be resolved (see age_stratification.AgeResolution) — the
    architecture's own worked example uses the paediatric branch as the
    widest-safety fallback in that case, so we do the same here.

    Nodes marked requires_consent are dropped (not asked, not fabricated)
    when medical-information consent was declined.
    """
    if stratum in _PAEDIATRIC_STRATA or stratum is None:
        plan = list(_COMMON_OPENING) + list(_PAEDIATRIC_TAIL)
    elif stratum == AgeStratum.GERIATRIC:
        plan = list(_COMMON_OPENING) + list(_GERIATRIC_TAIL)
    else:  # ADOLESCENT, ADULT
        plan = list(_COMMON_OPENING) + list(_ADULT_ADOLESCENT_TAIL)

    if consent == ConsentState.DECLINED:
        plan = [n for n in plan if not n.requires_consent]
    return plan


@dataclass
class QuestionTreeSession:
    """Accumulates answers across a walk through the plan."""

    plan: list
    cursor: int = 0
    narrative: StructuredNarrative = dc_field(default_factory=StructuredNarrative)
    observations: list = dc_field(default_factory=list)  # list[Observation]
    reliability_signals: ReliabilitySignals = dc_field(default_factory=ReliabilitySignals)
    skipped_nodes: list = dc_field(default_factory=list)
    stopped_for_red_flag: bool = False  # set by _maybe_stop_for_confirmed_red_flag()
    _free_text_failures: dict = dc_field(default_factory=dict)

    @property
    def current_node(self) -> Optional[QuestionNode]:
        if self.cursor >= len(self.plan):
            return None
        return self.plan[self.cursor]

    def _advance(self) -> None:
        self.cursor += 1

    def record_answer(self, utterance: Utterance, structurer: LLMStructurer) -> None:
        node = self.current_node
        if node is None:
            raise InvalidAnswerError("question tree already complete")

        if utterance.asr_reliability and utterance.asr_reliability.get("unsupported_language"):
            self.reliability_signals.communication_barrier = TriState.TRUE

        if node.kind == AnswerKind.YES_NO:
            parsed = _parse_yes_no(utterance.text)
            if parsed is None:
                raise InvalidAnswerError(f"unrecognized yes/no answer for {node.node_id}: {utterance.text!r}")
            self._apply_yes_no(node, parsed, utterance)
            self._maybe_splice_follow_ups(node, "yes" if parsed else "no")
            self._advance()
            self._skip_known_nodes()
            self._maybe_stop_for_confirmed_red_flag()
            return

        if node.kind == AnswerKind.NUMERIC_0_10:
            parsed = _parse_severity(utterance.text)
            if parsed is None:
                raise InvalidAnswerError(f"unrecognized 0-10 severity answer: {utterance.text!r}")
            self.narrative.self_reported_severity = parsed
            self.observations.append(Observation("self_reported_severity", parsed, "patient", utterance.text))
            self._maybe_splice_follow_ups(node, str(parsed))
            self._advance()
            self._skip_known_nodes()
            self._maybe_stop_for_confirmed_red_flag()
            return

        # FREE_TEXT: hand off to the LLM structurer.
        try:
            partial = structurer.structure(utterance.text, context={"field_hint": node.node_id})
        except StructurerOutputError:
            self._record_free_text_failure(node)
            self._preserve_raw_answer_on_failure(node, utterance)
            self._detect_direct_symptom_answer(node, utterance.text)
            raise

        if partial.extraction_status in ("malformed", "empty_input"):
            self._record_free_text_failure(node)

        _merge_narrative(self.narrative, partial)
        self.observations.append(Observation(node.node_id, partial, "patient", utterance.text))
        self._detect_direct_symptom_answer(node, utterance.text)

        if node.node_id == "chief_complaint":
            self._insert_branch_questions()
        self._maybe_splice_follow_ups(node, utterance.text)

        self._advance()
        self._skip_known_nodes()
        self._maybe_stop_for_confirmed_red_flag()

    def _insert_branch_questions(self) -> None:
        """
        Called once, right after chief_complaint is answered. Splices the
        matching complaint branch's questions into the plan immediately
        after the current position (i.e. before onset/severity), making
        the rest of the conversation situation-specific. A no-op for the
        "generic" branch, which keeps the original onset/severity/tail flow.
        """
        branch = classify_complaint(self.narrative)
        branch_questions = COMPLAINT_BRANCHES.get(branch)
        if not branch_questions:
            return
        existing_ids = {n.node_id for n in self.plan}
        new_nodes = [n for n in branch_questions if n.node_id not in existing_ids]
        insert_at = self.cursor + 1
        self.plan[insert_at:insert_at] = new_nodes

    def _maybe_splice_follow_ups(self, node: "QuestionNode", answer_text: str) -> None:
        """
        Level-2 branching. Splice node.follow_ups into the plan after the
        current position when the answer to `node` matches its triggers.

        Never fires twice for the same parent (existing_ids guard), and
        never re-asks a follow-up already in the plan -- follow_ups is a
        menu, not an obligation.
        """
        if not node.follow_ups:
            return

        normalized = _normalize_asr_answer(answer_text or "")
        if node.follow_up_triggers:
            triggered = any(t.lower() in normalized for t in node.follow_up_triggers)
        else:
            triggered = _parse_yes_no(normalized) is True

        if not triggered:
            return

        existing_ids = {n.node_id for n in self.plan}
        new_nodes = [n for n in node.follow_ups if n.node_id not in existing_ids]
        if not new_nodes:
            return
        insert_at = self.cursor + 1
        self.plan[insert_at:insert_at] = new_nodes

    def _skip_known_nodes(self) -> None:
        """
        Fast-forwards past any upcoming question whose answer is already
        known from an earlier turn -- a good triage nurse does not re-ask
        what the patient already volunteered. Only ever looks forward from
        the current cursor; never revisits an already-answered node.
        """
        while True:
            node = self.current_node
            if node is None or not self._already_known(node):
                return
            self.skipped_nodes.append({"node_id": node.node_id, "reason": "already_known"})
            self._advance()

    def _already_known(self, node: QuestionNode) -> bool:
        if node.node_id == "onset" and self.narrative.onset_minutes is not None:
            return True
        if node.node_id == "severity" and self.narrative.self_reported_severity is not None:
            return True
        if node.implies_symptom and node.implies_symptom in self.narrative.symptoms:
            return True
        if node.implied_by_keywords:
            transcript = self.narrative.raw_transcript.lower()
            if any(kw in transcript for kw in node.implied_by_keywords):
                return True
        return False

    def skip_current(self, reason: str) -> None:
        node = self.current_node
        if node is None:
            return
        self.skipped_nodes.append({"node_id": node.node_id, "reason": reason})
        self._advance()
        self._maybe_stop_for_confirmed_red_flag()

    def _maybe_stop_for_confirmed_red_flag(self) -> None:
        """
        If the structured observations collected so far already satisfy an
        EXISTING red-flag rule (intake/red_flags.py, unmodified -- this only
        calls its public evaluate_red_flags(), the same function
        pipeline.py's finalize() uses), stop asking further intake
        questions. Once a confirmed time-critical presentation is
        established, grinding through the remaining generic follow-ups
        (onset, severity, pregnancy, medications, ...) costs time that
        should go to the patient, not the questionnaire. Invents no new
        rule and duplicates none of red_flags.py's logic -- it only decides
        WHEN to stop asking, using red_flags.py's own verdict.
        """
        if self.cursor >= len(self.plan):
            return
        if evaluate_red_flags(self.narrative).red_flag:
            self.plan = self.plan[: self.cursor]  # truncate remaining questions; already-asked ones stand
            self.stopped_for_red_flag = True

    def _detect_direct_symptom_answer(self, node: QuestionNode, text: str) -> None:
        """
        Reliability backstop for FREE_TEXT follow-ups that are explicitly
        ABOUT one existing ObservationCode (node.implies_symptom) -- e.g.
        the injury branch's "bleeding" question is about
        UNCONTROLLED_BLEEDING. Reuses node.implied_by_keywords (the same
        bilingual list already used to decide whether to skip a re-ask) as
        a positive-indicator set, combined with the existing yes/no parser,
        so an informal or code-mixed answer ("yess its bleeding heavily",
        "bahut khoon aa raha hai") still lands in narrative.symptoms even
        if the general structurer call for that turn missed it or failed
        outright (this runs in the failure path too -- see record_answer).

        Runs IN ADDITION to structurer extraction, never in place of it,
        and never overrides an explicit denial ("no", "nahi", "it stopped
        bleeding") -- a clear "no" always wins even though the negative
        phrasing may still contain the keyword itself. This invents no new
        code and no new red-flag rule; it only makes an EXISTING code more
        reliably captured for questions that are already directly about it.
        """
        if not node.implies_symptom:
            return
        normalized = (text or "").strip().lower().replace("'", "")
        if not normalized:
            return
        yn = _parse_yes_no(normalized)
        if yn is False:
            return
        matched = yn is True or (
            bool(node.implied_by_keywords) and any(kw in normalized for kw in node.implied_by_keywords)
        )
        if matched and node.implies_symptom not in self.narrative.symptoms:
            self.narrative.symptoms.append(node.implies_symptom)

    def _record_free_text_failure(self, node: QuestionNode) -> None:
        count = self._free_text_failures.get(node.node_id, 0) + 1
        self._free_text_failures[node.node_id] = count
        # Conservative, interaction-derived signal — never a demographic
        # assumption. Two garbled/unparseable free-text turns on the same
        # question is treated as evidence of a health-literacy or
        # comprehension barrier, per round2-implementation-plan.html §07.
        if count >= 2:
            self.reliability_signals.health_literacy_signal = True

    def _preserve_raw_answer_on_failure(self, node: QuestionNode, utterance: Utterance) -> None:
        """
        If the structurer call itself fails (missing credentials, network/API
        error, malformed response), the patient's own words must not simply
        vanish -- only the EXTRACTION is unavailable, not the answer. This
        preserves exactly what was said, verbatim, into raw_transcript (and
        into chief_complaint specifically, since every later turn and the
        branch selection depend on it) without fabricating anything the
        structurer could not confirm -- symptoms, onset, severity, etc. stay
        unset here, exactly as before this fix.
        """
        text = (utterance.text or "").strip()
        if not text:
            return
        if node.node_id == "chief_complaint" and not self.narrative.chief_complaint:
            self.narrative.chief_complaint = text
        self.narrative.raw_transcript = (self.narrative.raw_transcript + "\n" + text).strip()

    def _apply_yes_no(self, node: QuestionNode, value: bool, utterance: Utterance) -> None:
        if node.node_id == "pregnancy_status":
            self.narrative.pregnancy_status = value
        elif node.node_id == "analgesia_given":
            self.reliability_signals.analgesia_given = value
        elif node.node_id == "feeding_normally":
            if not value:
                self.narrative.symptoms.append("infant_not_feeding")
        elif node.node_id == "falls_or_confusion":
            pass  # recorded as a plain observation below; no clinical interpretation here
        self.observations.append(Observation(node.node_id, value, "patient", utterance.text))

    @property
    def complete(self) -> bool:
        return self.cursor >= len(self.plan)


# A real patient/attendant rarely answers a yes/no question with a bare
# "yes"/"no" -- "yeah", "not really", "I don't think so", "haan bilkul" are
# all common and all mean something unambiguous. Substring/keyword matching
# (not an exact-token set) is what makes this behave like a nurse listening
# to an answer rather than a form validator. Checked as whole words via \b
# so e.g. "known" doesn't match "no".
#
# "non" is included alongside "nahi"/"nahin": a common Whisper mis-transcription
# of a clipped/soft spoken "no" (also matches the standard Hindi spelling
# reasonably). Devanagari-script "नहीं"/"हाँ" are included too since Whisper
# renders actual Hindi speech in Devanagari, not romanized text -- a
# yes/no answer spoken in Hindi should not be limited to romanized spellings.
_NO_KEYWORDS = [
    "no", "nope", "nah", "not really", "dont think so", "never",
    "nahi", "nahin", "bilkul nahi", "non",
    "नहीं", "नही",
]
_YES_KEYWORDS = [
    "yes", "yeah", "yep", "yup", "sure", "definitely", "correct",
    "haan", "han", "ha", "bilkul",
    "हाँ", "हां",
]

# ASR output attaches sentence-level punctuation to a short spoken answer
# ("No.", "Yeah!", "Yes,") -- stripped to spaces (not deleted outright, so
# "no,thanks" doesn't accidentally fuse into "nothanks") before matching.
# Includes Devanagari danda "।"/double-danda "॥", smart quotes, dashes,
# ellipsis, and brackets, not just ASCII punctuation.
_ASR_PUNCTUATION_RE = re.compile(r"[.,!?;:()\[\]\"“”‘’…—–।॥]+")

# Emphatic elongation ("Nooo.", "yesss") collapsed to the plain word before
# matching -- 3+ repeats of the same letter is not a normal English/Hindi
# spelling, so this only ever affects ASR-style emphasis, never a real word.
_REPEATED_CHAR_RE = re.compile(r"(.)\1{2,}")


def _contains_word(text: str, phrase: str) -> bool:
    # Deliberately NOT Python's \b: \w does not include Devanagari dependent
    # vowel signs (matras, Unicode category Mc), so \b fails to find a
    # boundary at the end of most Devanagari words, which end in a matra
    # (verified: \bनही\b does not match the string "नही" at all). Text
    # reaching here has already had punctuation collapsed to single spaces
    # (see _normalize_asr_answer), so an explicit whitespace/string-edge
    # boundary is both correct and sufficient for any script.
    return re.search(r"(?:^|\s)" + re.escape(phrase) + r"(?:\s|$)", text) is not None


def _normalize_asr_answer(text: str) -> str:
    """Lowercases, strips apostrophes, strips common ASR sentence
    punctuation (including Devanagari), collapses letter-elongation, and
    collapses whitespace runs to single spaces -- shared normalization so
    yes/no matching is robust to how Whisper actually renders a short
    spoken answer, not just a clean typed one."""
    normalized = (text or "").strip().lower().replace("'", "")
    normalized = _ASR_PUNCTUATION_RE.sub(" ", normalized)
    normalized = _REPEATED_CHAR_RE.sub(r"\1", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _parse_yes_no(text: str) -> Optional[bool]:
    normalized = _normalize_asr_answer(text)
    if not normalized:
        return None
    # Negation checked first: "not really" etc. should never be read as yes.
    if any(_contains_word(normalized, kw) for kw in _NO_KEYWORDS):
        return False
    if any(_contains_word(normalized, kw) for kw in _YES_KEYWORDS):
        return True
    return None


def _parse_severity(text: str) -> Optional[int]:
    """
    Extracts a 0-10 severity from natural phrasing ("about an 8", "maybe 7
    out of 10", "I'd say 8"), not just a bare digit. Takes the first valid
    0-10 number found, so "7 out of 10" correctly reads as 7, not 10.
    """
    normalized = (text or "").strip().lower()
    if not normalized:
        return None
    for match in re.finditer(r"\b(10|[0-9])\b", normalized):
        value = int(match.group(1))
        if 0 <= value <= 10:
            return value
    return None


def _merge_narrative(target: StructuredNarrative, partial: StructuredNarrative) -> None:
    """
    Merge one turn's extraction into the running narrative.

    Content-driven, not node-id-gated: a patient may volunteer their chief
    complaint, onset, severity, or history while answering a different
    question (this is normal, especially once the tree branches into more
    specific follow-ups) -- whatever the structurer actually extracted from
    the transcript is kept, regardless of which node_id prompted it.

    Scalar fields are first-write-wins (an already-known value from a
    direct answer is never clobbered by a later incidental mention); list
    fields accumulate; nothing is ever fabricated -- only what the
    structurer actually returned is merged.
    """
    if partial.chief_complaint and not target.chief_complaint:
        target.chief_complaint = partial.chief_complaint
    if partial.onset_minutes is not None and target.onset_minutes is None:
        target.onset_minutes = partial.onset_minutes
    if partial.self_reported_severity is not None and target.self_reported_severity is None:
        target.self_reported_severity = partial.self_reported_severity
    if partial.pregnancy_status is not None and target.pregnancy_status is None:
        target.pregnancy_status = partial.pregnancy_status
    if partial.medications:
        target.medications.extend(m for m in partial.medications if m not in target.medications)
    if partial.relevant_history:
        target.relevant_history.extend(h for h in partial.relevant_history if h not in target.relevant_history)
    for code in partial.symptoms:
        if code not in target.symptoms:
            target.symptoms.append(code)
    for term in partial.unrecognized_terms:
        if term not in target.unrecognized_terms:
            target.unrecognized_terms.append(term)
    target.raw_transcript = (target.raw_transcript + "\n" + partial.raw_transcript).strip()
