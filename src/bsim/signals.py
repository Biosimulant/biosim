"""
BioSignal - Neutral interchange format for cross-module communication.

BioSignals carry values, timing, and metadata so modules can exchange data
with consistent semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import numpy as np


@dataclass
class SignalMetadata:
    """Metadata describing a BioSignal's semantics and units."""

    units: Optional[str] = None
    """Physical units (e.g., 'mM', 'mV', 'Hz'). None if dimensionless."""

    shape: Optional[tuple[int, ...]] = None
    """Expected shape for array values. None for scalars."""

    description: Optional[str] = None
    """Human-readable description of what this signal represents."""

    min_value: Optional[float] = None
    """Expected minimum value (for validation/visualization)."""

    max_value: Optional[float] = None
    """Expected maximum value (for validation/visualization)."""

    dtype: Optional[str] = None
    """Data type hint (e.g., 'float64', 'int32', 'bool')."""

    kind: Optional[str] = "state"
    """Signal kind: 'state' (default) or 'event'."""

    def __post_init__(self):
        # Convert shape to tuple if it's a list
        if isinstance(self.shape, list):
            self.shape = tuple(self.shape)


@dataclass
class BioSignal:
    """
    A signal passed between modules in a biosim simulation.

    BioSignals are the standard interchange format for cross-module communication.
    They carry values along with metadata about their source, timing, and semantics.
    """

    source: str
    """Identifier of the producing module."""

    name: str
    """Name of this signal."""

    value: Any
    """The signal value - scalar, array, or structured data."""

    time: float
    """Simulation time when this signal was produced."""

    metadata: SignalMetadata = field(default_factory=SignalMetadata)
    """Optional metadata about the signal."""

    def __post_init__(self):
        # Ensure metadata is a SignalMetadata instance
        if isinstance(self.metadata, dict):
            self.metadata = SignalMetadata(**self.metadata)

    @property
    def is_scalar(self) -> bool:
        """Check if the value is a scalar (not an array)."""
        return not isinstance(self.value, (np.ndarray, list, tuple))

    @property
    def is_array(self) -> bool:
        """Check if the value is an array."""
        return isinstance(self.value, (np.ndarray, list, tuple))

    def as_float(self) -> float:
        """Get the value as a float. Raises if not scalar."""
        if self.is_array:
            raise ValueError(f"Signal {self.name} is an array, not a scalar")
        return float(self.value)

    def as_array(self) -> np.ndarray:
        """Get the value as a numpy array."""
        if isinstance(self.value, np.ndarray):
            return self.value
        return np.asarray(self.value)

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""
        value = self.value
        if isinstance(value, np.ndarray):
            value = value.tolist()

        return {
            "source": self.source,
            "name": self.name,
            "value": value,
            "time": self.time,
            "metadata": {
                "units": self.metadata.units,
                "shape": self.metadata.shape,
                "description": self.metadata.description,
                "min_value": self.metadata.min_value,
                "max_value": self.metadata.max_value,
                "dtype": self.metadata.dtype,
                "kind": self.metadata.kind,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> BioSignal:
        """Create a BioSignal from a dictionary."""
        metadata = SignalMetadata(**data.get("metadata", {}))
        return cls(
            source=data["source"],
            name=data["name"],
            value=data["value"],
            time=data["time"],
            metadata=metadata,
        )
