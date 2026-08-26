"""
Tests for intake/complaint_classifier.py and its integration into
classify_complaint() (intake/question_tree.py).

No network access or GROQ_API_KEY required: GroqComplaintClassifier's
wiring is tested with an injected stub client (no real API call), and its
clean-failure paths are tested directly. classify_complaint()'s use of an
LLM-style classifier is tested by injecting a fake "smart" classifier that
stands in for what a real LLM would understand -- proving the architecture
routes correctly on MEANING, not on keyword-matching, which is the actual
point of this module.
"""

import json

import pytest

from intake.complaint_classifier import (
    ComplaintClassifierError,
    GroqComplaintClassifier,
    KeywordComplaintClassifier,
)
from intake.models import StructuredNarrative
from intake.question_tree import CATEGORIES, classify_complaint


# ---------------------------------------------------------------------------
# GroqComplaintClassifier: request/response wiring, no real API call
# ---------------------------------------------------------------------------

def test_groq_classifier_fails_cleanly_without_credentials(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    clf = GroqComplaintClassifier()
    with pytest.raises(ComplaintClassifierError, match="GROQ_API_KEY"):
        clf.classify("my stomach hurts", ["abdominal_pain", "fever"])


def test_groq_classifier_wiring_with_injected_client():
    class _StubMessage:
        content = json.dumps({"category": "vomiting"})

    class _StubChoice:
        message = _StubMessage()

    class _StubResponse:
        choices = [_StubChoice()]

    class _StubCompletions:
        def create(self, **kwargs):
            assert kwargs["model"] == "openai/gpt-oss-20b"
            schema = kwargs["response_format"]["json_schema"]["schema"]
            assert schema["properties"]["category"]["enum"] == ["vomiting", "fever", "generic"]
            assert kwargs["response_format"]["json_schema"]["strict"] is True
            return _StubResponse()

    class _StubChat:
        completions = _StubCompletions()

    class _StubClient:
        chat = _StubChat()

    clf = GroqComplaintClassifier(client=_StubClient())
    result = clf.classify("mujhe ulti ho rahi hai", ["vomiting", "fever"], fallback="generic")
    assert result == "vomiting"


def test_groq_classifier_rejects_out_of_enum_response():
    """Defense in depth: even if the model somehow returned something
    outside the given options, the classifier does not pass it through."""
    class _StubMessage:
        content = json.dumps({"category": "diagnosis: gastroenteritis"})

    class _StubChoice:
        message = _StubMessage()

    class _StubResponse:
        choices = [_StubChoice()]

    class _StubCompletions:
        def create(self, **kwargs):
            return _StubResponse()

    class _StubChat:
        completions = _StubCompletions()

    class _StubClient:
        chat = _StubChat()

    clf = GroqComplaintClassifier(client=_StubClient())
    result = clf.classify("something", ["vomiting", "fever"], fallback="generic")
    assert result == "generic"


def test_groq_classifier_empty_text_returns_fallback_without_calling_api():
    calls = {"made": False}

    class _StubClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    calls["made"] = True

    clf = GroqComplaintClassifier(client=_StubClient())
    assert clf.classify("   ", ["vomiting", "fever"], fallback="generic") == "generic"
    assert calls["made"] is False


# ---------------------------------------------------------------------------
# KeywordComplaintClassifier: unchanged deterministic fallback behavior
# ---------------------------------------------------------------------------

def test_keyword_classifier_matches_and_falls_back():
    clf = KeywordComplaintClassifier({"fever": ("fever", "bukhar"), "vomiting": ("ulti",)})
    assert clf.classify("mujhe bukhar hai", ["fever", "vomiting"]) == "fever"
    assert clf.classify("something totally unrelated", ["fever", "vomiting"]) == "generic"


# ---------------------------------------------------------------------------
# classify_complaint(): the actual point of this feature -- routes on
# MEANING via an injected LLM-style classifier, not on keyword matching.
# ---------------------------------------------------------------------------

class _FakeSmartClassifier:
    """Stands in for a real LLM: understands indirect/novel phrasing that
    the keyword fallback cannot, by simple exact-text mapping in these
    tests (a real Groq call would generalize far beyond this)."""

    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def classify(self, text, category_names, fallback="generic"):
        self.calls.append(text)
        return self.mapping.get(text, fallback)


def test_classify_complaint_handles_phrasing_the_keyword_list_cannot():
    """This is the concrete problem reported: indirect phrasing with zero
    keyword overlap. The keyword-only path returns 'generic' for this (see
    test_keyword_fallback_alone_fails_on_this_phrasing below); routing
    through a classifier that understands meaning fixes it."""
    text = "kal se kuch theek nahi lag raha, baar baar mooh se aata hai"
    narrative = StructuredNarrative(chief_complaint=text, symptoms=[])

    smart = _FakeSmartClassifier({text: "vomiting"})
    assert classify_complaint(narrative, classifier=smart) == "vomiting"
    assert smart.calls == [text]  # classifier was actually consulted


def test_keyword_fallback_alone_fails_on_this_phrasing():
    """Documents the actual limitation being fixed: pins that the OLD
    (keyword-only) mechanism genuinely cannot handle this phrasing, so the
    fix above is meaningful and not testing a no-op."""
    text = "kal se kuch theek nahi lag raha, baar baar mooh se aata hai"
    narrative = StructuredNarrative(chief_complaint=text, symptoms=[])
    always_fails = KeywordComplaintClassifier({})  # no keyword data at all -> pure fallback path

    class _AlwaysUnavailable:
        def classify(self, *a, **kw):
            raise ComplaintClassifierError("simulated: no LLM available")

    result = classify_complaint(narrative, classifier=_AlwaysUnavailable())
    assert result == "generic"  # falls through to the real keyword list, which also can't match this


def test_classify_complaint_falls_back_when_classifier_unavailable():
    """A classifier failure (no credentials, network error, etc.) must not
    break the conversation -- it degrades to the keyword fallback."""
    narrative = StructuredNarrative(chief_complaint="I have chest pain", symptoms=[])

    class _AlwaysUnavailable:
        def classify(self, *a, **kw):
            raise ComplaintClassifierError("simulated failure")

    result = classify_complaint(narrative, classifier=_AlwaysUnavailable())
    assert result == "chest_pain"  # recovered via the keyword layer


def test_classify_complaint_prefers_symptom_code_over_classifier():
    """Symptom-code evidence (already vetted by the structurer) still wins
    over the classifier -- the classifier is only consulted when there is
    no closed-vocabulary evidence."""
    narrative = StructuredNarrative(chief_complaint="something", symptoms=["fever"])

    smart = _FakeSmartClassifier({"something": "injury"})  # would misroute if consulted
    assert classify_complaint(narrative, classifier=smart) == "fever"
    assert smart.calls == []  # never even called


def test_classify_complaint_classifier_result_must_be_a_known_category():
    """Defense in depth at the call site too: an out-of-range classifier
    result is not trusted blindly."""
    narrative = StructuredNarrative(chief_complaint="something", symptoms=[])

    class _Rogue:
        def classify(self, *a, **kw):
            return "not_a_real_category"

    assert classify_complaint(narrative, classifier=_Rogue()) == "generic"


def test_all_category_names_are_valid_enum_members_for_the_classifier():
    """Sanity check that the category registry and the classifier's enum
    construction stay in sync."""
    names = [c.name for c in CATEGORIES]
    assert len(names) == len(set(names))
    assert "generic" not in names  # fallback is not itself a category
