"""
M07 — Immediate red-flag pass.

Deterministic table lookup over structured observations (M06 output). No
LLM call happens in this module, and it never asks the LLM "is this a red
flag" — the LLM extracts observations; this fixed table maps observations
to Red. See round2-implementation-plan.html §10.

The question tree (M04) and the LLM structurer (M06) never assign
Red/Yellow/Green; this is the one place in Stage 2 that produces a red-flag
verdict, and it does so purely from a closed set of ObservationCodes, with
no model inference involved.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field

from intake.models import ObservationCode as OC
from intake.models import RedFlagResult, StructuredNarrative


@dataclass(frozen=True)
class RedFlagRule:
    rule_id: str
    description: str
    requires_all: frozenset = dc_field(default_factory=frozenset)  # every code must be present
    requires_any: frozenset = dc_field(default_factory=frozenset)  # at least one must be present


# Illustrative table for the prototype, matching round2-implementation-plan.html
# §10 and intake_architecture_part3.svg (RF-01 .. RF-08) exactly. In a real
# deployment this table is clinician-signed-off and version-controlled with
# the model, per the plan document.
RED_FLAG_RULES = [
    RedFlagRule(
        "RF-01", "Altered consciousness / not responding",
        requires_any=frozenset({OC.ALTERED_CONSCIOUSNESS.value, OC.NOT_RESPONDING.value}),
    ),
    RedFlagRule(
        "RF-02", "Active labour, or bleeding in pregnancy",
        requires_any=frozenset({OC.ACTIVE_LABOUR.value, OC.BLEEDING_IN_PREGNANCY.value}),
    ),
    RedFlagRule(
        "RF-03", "Chest pain with sweating, radiation or breathlessness",
        requires_all=frozenset({OC.CHEST_PAIN.value}),
        requires_any=frozenset({OC.SWEATING.value, OC.RADIATING_PAIN.value, OC.BREATHLESSNESS.value}),
    ),
    RedFlagRule(
        "RF-04", "Difficulty speaking in full sentences",
        requires_any=frozenset({OC.DIFFICULTY_SPEAKING_FULL_SENTENCES.value}),
    ),
    RedFlagRule(
        "RF-05", "Sudden one-sided weakness, facial droop, speech change",
        requires_any=frozenset({
            OC.SUDDEN_ONE_SIDED_WEAKNESS.value, OC.FACIAL_DROOP.value, OC.SUDDEN_SPEECH_CHANGE.value,
        }),
    ),
    RedFlagRule(
        "RF-06", "Uncontrolled bleeding, or a penetrating injury",
        requires_any=frozenset({OC.UNCONTROLLED_BLEEDING.value, OC.PENETRATING_INJURY.value}),
    ),
    RedFlagRule(
        "RF-07", "Poisoning, overdose, or a snakebite",
        requires_any=frozenset({OC.POISONING_OR_OVERDOSE.value, OC.SNAKEBITE.value}),
    ),
    RedFlagRule(
        "RF-08", "Infant not feeding, floppy, or inconsolable",
        requires_any=frozenset({
            OC.INFANT_NOT_FEEDING.value, OC.INFANT_FLOPPY.value, OC.INFANT_INCONSOLABLE.value,
        }),
    ),
]


def _matches(rule: RedFlagRule, symptoms: set) -> bool:
    if rule.requires_all and not rule.requires_all.issubset(symptoms):
        return False
    if rule.requires_any and not (rule.requires_any & symptoms):
        return False
    return bool(rule.requires_all or rule.requires_any)


def evaluate_red_flags(narrative: StructuredNarrative) -> RedFlagResult:
    """
    First-match-wins deterministic sweep over RED_FLAG_RULES, operating only
    on narrative.symptoms (the closed ObservationCode vocabulary). A patient
    could in principle match more than one rule; the table order decides
    which is reported as the leading factor, matching the plan's "displays
    as the leading factor on the card" framing.
    """
    symptoms = set(narrative.symptoms) if narrative else set()
    for rule in RED_FLAG_RULES:
        if _matches(rule, symptoms):
            matched = sorted((rule.requires_all | rule.requires_any) & symptoms)
            return RedFlagResult(
                red_flag=True,
                rule_id=rule.rule_id,
                matched_observations=matched,
                description=rule.description,
            )
    return RedFlagResult(red_flag=False, rule_id=None, matched_observations=[], description=None)
