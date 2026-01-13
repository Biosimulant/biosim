"""
BioSignal - Neutral interchange format for cross-adapter communication.

BioSignals are the standard way for adapters to exchange data. They carry:
- The value (scalar, array, or structured data)
- Metadata about units, shape, and semantics
- Source and timing information for debugging
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

    def __post_init__(self):
        # Convert shape to tuple if it's a list
        if isinstance(self.shape, list):
            self.shape = tuple(self.shape)


@dataclass
class BioSignal:
    """
    A signal passed between adapters/modules in a bsim simulation.

    BioSignals are the standard interchange format for cross-adapter communication.
    They carry values along with metadata about their source, timing, and semantics.

    Attributes:
        source: Identifier of the adapter/module that produced this signal.
        name: Name of the signal (e.g., 'glucose', 'spike_times', 'prediction').
        value: The actual data - can be scalar, numpy array, or structured data.
        time: Simulation time when this signal was produced.
        metadata: Optional metadata about units, shape, and semantics.

    Example:
        >>> signal = BioSignal(
        ...     source="metabolism_model",
        ...     name="glucose",
        ...     value=5.2,
        ...     time=10.0,
        ...     metadata=SignalMetadata(units="mM", min_value=0, max_value=20)
        ... )
    """

    source: str
    """Identifier of the producing adapter/module."""

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
