from __future__ import annotations

from pathlib import Path

import pytest

from scripts.snapshot_biomodule_outputs import snapshot_model_dir


def _write_model(path: Path, source: str, *, initial_inputs: str = "") -> Path:
    path.mkdir()
    runtime = f"\nruntime:\n{initial_inputs}" if initial_inputs else ""
    (path / "model.yaml").write_text(
        (
            'schema_version: "2.0"\n'
            'title: "Snapshot Model"\n'
            "standard: other\n"
            "biosim:\n"
            '  entrypoint: "src.model:SnapshotModel"\n'
            "  communication_step: 0.1\n"
            f"{runtime}\n"
        ),
        encoding="utf-8",
    )
    src_dir = path / "src"
    src_dir.mkdir()
    (src_dir / "model.py").write_text(source, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("policy", "duration", "expected_calls"),
    [
        ("ONCE_BEFORE_RUN", 0.3, 1),
        ("EACH_WINDOW", 0.3, 3),
        ("ONCE_AFTER_RUN", 0.3, 1),
    ],
)
def test_snapshot_model_dir_runs_canonical_modules_through_bioworld(
    tmp_path: Path,
    policy: str,
    duration: float,
    expected_calls: int,
) -> None:
    model_dir = _write_model(
        tmp_path / policy.lower(),
        f'''from biosimulant import BioModule, ExecutionPolicy, SignalSpec


class SnapshotModel(BioModule):
    execution_policy = ExecutionPolicy.{policy}

    def __init__(self):
        self.calls = 0

    def outputs(self):
        return {{"value": SignalSpec.scalar(dtype="int64")}}

    def execute(self, inputs, *, context):
        self.calls += 1
        return {{"value": self.calls}}

    def snapshot(self):
        return {{"calls": self.calls}}
''',
    )

    result = snapshot_model_dir(
        model_dir,
        duration=duration,
        install_deps=False,
        source_root=tmp_path,
    )

    assert result["state"] == {"calls": expected_calls}
    assert result["signals"]["value"]["value"] == expected_calls


def test_snapshot_model_dir_preserves_temporal_compatibility(tmp_path: Path) -> None:
    model_dir = _write_model(
        tmp_path / "legacy",
        '''from biosimulant import BioModule, ScalarSignal, SignalSpec


class SnapshotModel(BioModule):
    def __init__(self):
        self.calls = 0
        self.time = 0.0

    def outputs(self):
        return {"value": SignalSpec.scalar(dtype="int64")}

    def advance_window(self, start, end):
        self.calls += 1
        self.time = end

    def get_outputs(self):
        return {
            "value": ScalarSignal(
                source="legacy",
                name="value",
                value=self.calls,
                emitted_at=self.time,
                spec=self.outputs()["value"],
            )
        }

    def snapshot(self):
        return {"calls": self.calls}
''',
    )

    result = snapshot_model_dir(
        model_dir,
        duration=0.3,
        install_deps=False,
        source_root=tmp_path,
    )

    assert result["state"] == {"calls": 3}
    assert result["signals"]["value"]["value"] == 3
