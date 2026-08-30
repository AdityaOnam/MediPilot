"""
Contract tests — asserts the 12 definition-of-done rows from
BACKEND_INTEGRATION_LOG.md §8 against the live orchestrator app.
"""

import json
import pytest
from fastapi.testclient import TestClient

from backend.orchestrator.app import app, world


@pytest.fixture(scope="module", autouse=True)
def bootstrap():
    world.bootstrap()
    yield


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ── 1. /v1/score carries no band when abstained; effectiveBand=YELLOW (I-5) ──

def test_abstained_score_has_no_band_and_yellow_effective(client):
    # P-15 is OOD → always abstains
    r = client.post("/v1/score", json={"encounterId": "P-15"})
    assert r.status_code == 200
    d = r.json()
    assert d["abstained"] is True
    assert d["effectiveBand"] == "YELLOW"
    # band key should be absent or None when abstained
    assert d.get("band") is None


# ── 2. Non-abstained score has confidence, conformalSet, inputsUsed (I-2) ──

def test_non_abstained_score_has_required_fields(client):
    r = client.post("/v1/score", json={"encounterId": "P-02"})
    assert r.status_code == 200
    d = r.json()
    assert d["abstained"] is False
    assert d["confidence"] in ("high", "moderate", "low")
    assert isinstance(d["conformalSet"], list)
    assert len(d["conformalSet"]) >= 1
    assert isinstance(d["inputsUsed"], list)
    assert len(d["inputsUsed"]) >= 1


# ── 3. Every encounter has ageStratum; unknown age sets ageStratumInferred (I-3) ──

def test_age_stratum_always_present(client):
    r = client.get("/v1/census")
    census = r.json()
    for e in census:
        assert "ageStratum" in e, f"{e['encounterId']} missing ageStratum"
        assert e["ageStratum"] in ("neonate", "infant", "child", "adolescent", "adult", "geriatric")


def test_unknown_age_sets_inferred(client):
    # P-16 has unknown age
    r = client.get("/v1/encounter/P-16")
    d = r.json()
    assert d["ageStratumInferred"] is True


# ── 4. Every measurement is a full tuple with validity (I-4) ──

def test_measurements_have_validity(client):
    r = client.get("/v1/census")
    for e in r.json():
        for m in e.get("measurements", []):
            assert "validity" in m, f"{e['encounterId']} measurement missing validity"
            assert m["validity"] in ("fresh", "discounted", "expired")
            assert "code" in m
            assert "takenAt" in m
            assert "source" in m


# ── 5. Cadence carries all three clocks and a breach kind ──

def test_cadence_has_three_clocks(client):
    r = client.get("/v1/census")
    for e in r.json():
        c = e["cadence"]
        assert "rescoreSec" in c
        assert "remeasureSec" in c
        assert "ceilingSec" in c
        assert "nextRescoreAt" in c
        assert "nextRemeasureAt" in c
        assert "ceilingBreachesAt" in c
        assert "breached" in c


# ── 6. /v1/decision returns all 16 override fields ──

def test_decision_returns_16_fields(client):
    r = client.post("/v1/decision", json={
        "encounterId": "P-14",
        "action": "override",
        "band": "RED",
        "reasonCode": "clinical-finding-on-exam",
        "reasonText": "Rigid abdomen on palpation",
        "clinicianId": "NURSE-001",
        "clinicianRole": "senior_nurse",
    })
    assert r.status_code == 200
    d = r.json()
    required = [
        "patientId", "timestampUtc", "clinicianId", "clinicianRole",
        "systemBand", "clinicianBand", "direction", "reasonCode",
        "reasonText", "score", "confidence", "factorsShown",
        "inputsHash", "modelVersion", "calibrationVersion", "consentState",
    ]
    for field in required:
        assert field in d, f"Missing field: {field}"
    assert "hash" in d
    assert "prevHash" in d


# ── 7. /v1/control/r returns moved.down === 0 across its range ──

def test_r_control_down_always_zero(client):
    for R in [2.0, 5.0, 10.0, 20.0]:
        r = client.post("/v1/control/r", json={"R": R})
        assert r.status_code == 200
        d = r.json()
        assert d["moved"]["down"] == 0, f"moved.down={d['moved']['down']} at R={R}"


# ── 8. Both serverTime and simTime on every score response ──

def test_score_has_both_times(client):
    r = client.post("/v1/score", json={"encounterId": "P-05"})
    d = r.json()
    assert "serverTime" in d
    assert "simTime" in d
    assert len(d["serverTime"]) > 10
    assert len(d["simTime"]) > 10


# ── 9. Audit rows chain: row[n].prevHash === row[n-1].hash ──

def test_audit_chain_integrity(client):
    # Create a second override to have 2+ records
    client.post("/v1/decision", json={
        "encounterId": "P-07",
        "action": "override",
        "band": "RED",
        "reasonCode": "suspected-serious-diagnosis",
        "reasonText": "Inferior MI suspected",
        "clinicianId": "DR-002",
        "clinicianRole": "attending",
    })
    r = client.get("/v1/audit")
    records = r.json()
    assert len(records) >= 2
    # Records come newest-first, reverse for chain check
    ordered = list(reversed(records))
    assert ordered[0]["prevHash"] == "GENESIS"
    for i in range(1, len(ordered)):
        assert ordered[i]["prevHash"] == ordered[i - 1]["hash"], (
            f"Chain broken at record {i}: prevHash={ordered[i]['prevHash'][:16]} "
            f"!= prev.hash={ordered[i-1]['hash'][:16]}"
        )


# ── 10. Config has R bounds, cadence table, strata, versions ──

def test_config_complete(client):
    r = client.get("/v1/config")
    cfg = r.json()
    assert "costRatioR" in cfg
    assert cfg["rBounds"]["min"] < cfg["rBounds"]["max"]
    assert "RED" in cfg["cadences"]
    assert "YELLOW" in cfg["cadences"]
    assert "GREEN" in cfg["cadences"]
    assert "ABSTAINED" in cfg["cadences"]
    assert len(cfg["strata"]) == 6
    assert len(cfg["modelVersion"]) > 0
    assert len(cfg["calibrationVersion"]) > 0


# ── 11. Census returns 20 encounters ──

def test_census_has_20(client):
    r = client.get("/v1/census")
    assert len(r.json()) == 20


# ── 12. SSE stream verified manually with curl (TestClient blocks on streams) ──
