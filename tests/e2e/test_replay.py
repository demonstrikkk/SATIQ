"""Deterministic RunLedger-style replay cassette — no Ollama, no GPU, no docker.

Validates input_validator_node fast-fail invariants that must hold on friend's
first run. Reads tests/e2e/replay.jsonl; each line is {input_state, expected_passed, expected_error_code}.
"""
from __future__ import annotations
import json
import pathlib
import pytest
from orchestrator.agents.input_validator import input_validator_node

CASSETTE = pathlib.Path(__file__).with_name("replay.jsonl")

def _load_cassette():
    samples = []
    for line in CASSETTE.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line:
            continue
        samples.append(json.loads(line))
    return samples

@pytest.mark.parametrize("sample", _load_cassette(), ids=lambda s: s["name"])
def test_input_validator_rejection_cassette(sample):
    state = dict(sample["input_state"])
    # required GraphState defaults
    state.setdefault("execution_trace", [])
    state.setdefault("error_log", [])
    state.setdefault("node_latencies", {})
    out = input_validator_node(state)  # type: ignore[arg-type]
    assert out.get("validation_passed") is sample["expected_passed"] or out.get("validation_passed") == sample["expected_passed"]
    if not sample["expected_passed"]:
        assert out.get("error_code") == sample["expected_error_code"], f"got {out.get('error_code')} err={out.get('error')}"
    else:
        assert out.get("validation_passed") is True
        assert out.get("error_code") is None

def test_cassette_has_minimum_coverage():
    samples = _load_cassette()
    names = {s["name"] for s in samples}
    assert {"empty_query","greeting","crs_mismatch","image_too_large","prompt_injection","valid_single_image"} <= names
