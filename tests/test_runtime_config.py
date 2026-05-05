from __future__ import annotations

import pytest

from biosim.runtime import extract_communication_step


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


@pytest.mark.parametrize("value", [0, -1, "bad"])
def test_extract_communication_step_rejects_invalid(value: object) -> None:
    with pytest.raises(RuntimeError):
        extract_communication_step({}, {"communication_step": value})
