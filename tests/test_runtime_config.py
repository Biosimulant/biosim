from __future__ import annotations

import pytest

from biosim.runtime import extract_communication_step, extract_settle_steps


def test_extract_communication_step_precedence() -> None:
    assert (
        extract_communication_step(
            {"runtime": {"communication_step": 0.01}, "communication_step": 0.02},
            {"communication_step": 0.03},
            fallback=0.04,
        )
        == 0.01
    )
    assert (
        extract_communication_step(
            {"communication_step": 0.02},
            {"communication_step": 0.03},
            fallback=0.04,
        )
        == 0.02
    )
    assert (
        extract_communication_step({}, {"communication_step": 0.03}, fallback=0.04)
        == 0.03
    )
    assert extract_communication_step({}, {}, fallback=0.04) == 0.04
    assert extract_communication_step(None, None, fallback="0.05") == 0.05


def test_extract_communication_step_requires_value() -> None:
    with pytest.raises(RuntimeError, match="required"):
        extract_communication_step({}, {}, fallback=None)


@pytest.mark.parametrize("value", [0, -1, "bad"])
def test_extract_communication_step_rejects_invalid(value: object) -> None:
    with pytest.raises(RuntimeError):
        extract_communication_step({}, {"communication_step": value})


def test_extract_settle_steps_precedence_and_default() -> None:
    assert (
        extract_settle_steps(
            {"runtime": {"settle_steps": 3}, "settle_steps": 2},
            {"settle_steps": 1},
            fallback=4,
        )
        == 3
    )
    assert extract_settle_steps({"settle_steps": 2}, {"settle_steps": 1}) == 2
    assert extract_settle_steps({}, {"settle_steps": 1}) == 1
    assert extract_settle_steps({}, {}) == 0
    assert extract_settle_steps(None, None, fallback=None) == 0
    assert extract_settle_steps({}, {}, fallback=" 5 ") == 5


@pytest.mark.parametrize("value", [-1, 1.5, "bad", True])
def test_extract_settle_steps_rejects_invalid(value: object) -> None:
    with pytest.raises(RuntimeError):
        extract_settle_steps({}, {"settle_steps": value})
