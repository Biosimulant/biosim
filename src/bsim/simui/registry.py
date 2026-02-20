# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Module registry for config editor - introspects available BioModules."""
from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, Dict, List, Optional, Set, Type, get_type_hints

from ..modules import BioModule

logger = logging.getLogger(__name__)


@dataclass
class ArgSpec:
    """Specification for a module constructor argument."""
    name: str
    type: str
    default: Any = None
    required: bool = False
    description: Optional[str] = None
    options: Optional[List[Any]] = None  # For enum-like args


@dataclass
class ModuleSpec:
    """Specification for a BioModule class."""
    class_path: str
    name: str
    category: str
    description: Optional[str] = None
    inputs: Set[str] = field(default_factory=set)
    outputs: Set[str] = field(default_factory=set)
    args: List[ArgSpec] = field(default_factory=list)


def _get_arg_type_str(annotation: Any) -> str:
    """Convert a type annotation to a string representation."""
    if annotation is inspect.Parameter.empty:
        return "any"

    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        # Handle Optional, List, etc.
        args = getattr(annotation, "__args__", ())
        if origin.__name__ == "Union" and type(None) in args:
            # Optional type
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return _get_arg_type_str(non_none[0])
        return origin.__name__

    if hasattr(annotation, "__name__"):
        return annotation.__name__

    return str(annotation)


def introspect_module(cls: Type[BioModule], class_path: str, category: str = "unknown") -> ModuleSpec:
    """Introspect a BioModule class to extract its specification."""
    # Get docstring
    description = inspect.getdoc(cls)

    # Get inputs/outputs by instantiating with minimal args if possible
    inputs: Set[str] = set()
    outputs: Set[str] = set()

    try:
        # Try to get inputs/outputs from a temporary instance
        sig = inspect.signature(cls.__init__)
        minimal_kwargs: Dict[str, Any] = {}
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            if param.default is inspect.Parameter.empty and param.kind not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                # Required param - try to provide a sensible default
                if "name" in param_name.lower():
                    minimal_kwargs[param_name] = "test"
                elif "n" == param_name or "count" in param_name.lower():
                    minimal_kwargs[param_name] = 1
                elif "rate" in param_name.lower():
                    minimal_kwargs[param_name] = 0.1
                else:
                    minimal_kwargs[param_name] = None

        instance = cls(**minimal_kwargs)
        inputs = set(instance.inputs())
        outputs = set(instance.outputs())
    except Exception as e:
        logger.debug(f"Could not instantiate {class_path} for port introspection: {e}")
        # Try to extract from class methods directly
        try:
            if hasattr(cls, "inputs"):
                src = inspect.getsource(cls.inputs)
                # Simple heuristic: look for return {"port1", "port2"}
                if "return" in src and "{" in src:
                    # Extract set literals
                    import re
                    match = re.search(r'return\s*\{([^}]+)\}', src)
                    if match:
                        ports = match.group(1)
                        inputs = {p.strip().strip('"\'') for p in ports.split(",")}
            if hasattr(cls, "outputs"):
                src = inspect.getsource(cls.outputs)
                if "return" in src and "{" in src:
                    import re
                    match = re.search(r'return\s*\{([^}]+)\}', src)
                    if match:
                        ports = match.group(1)
                        outputs = {p.strip().strip('"\'') for p in ports.split(",")}
        except Exception:
            pass

    # Get constructor arguments
    args: List[ArgSpec] = []
    try:
        sig = inspect.signature(cls.__init__)
        hints = {}
        try:
            hints = get_type_hints(cls.__init__)
        except Exception:
            pass

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue

            arg_type = _get_arg_type_str(hints.get(param_name, param.annotation))
            has_default = param.default is not inspect.Parameter.empty
            default = param.default if has_default else None

            args.append(ArgSpec(
                name=param_name,
                type=arg_type,
                default=default,
                required=not has_default,
            ))
    except Exception as e:
        logger.debug(f"Could not introspect args for {class_path}: {e}")

    return ModuleSpec(
        class_path=class_path,
        name=cls.__name__,
        category=category,
        description=description,
        inputs=inputs,
        outputs=outputs,
        args=args,
    )


def discover_pack_modules(pack_path: str, category: str) -> Dict[str, ModuleSpec]:
    """Discover all BioModule classes in a pack.

    Args:
        pack_path: Dotted path to the pack module (e.g., "biosim.packs.neuro")
        category: Category name for these modules (e.g., "neuro")

    Returns:
        Dict mapping class paths to ModuleSpec objects
    """
    registry: Dict[str, ModuleSpec] = {}

    try:
        pack = import_module(pack_path)
    except ImportError as e:
        logger.warning(f"Could not import pack {pack_path}: {e}")
        return registry

    # Get all exported names from __all__ or dir
    names = getattr(pack, "__all__", None) or dir(pack)

    for name in names:
        if name.startswith("_"):
            continue

        try:
            obj = getattr(pack, name)
            if isinstance(obj, type) and issubclass(obj, BioModule) and obj is not BioModule:
                class_path = f"{pack_path}.{name}"
                spec = introspect_module(obj, class_path, category)
                registry[class_path] = spec
        except Exception as e:
            logger.debug(f"Could not process {name} from {pack_path}: {e}")

    return registry


class ModuleRegistry:
    """Central registry of available BioModule classes."""

    def __init__(self) -> None:
        self._registry: Dict[str, ModuleSpec] = {}
        self._categories: Dict[str, List[str]] = {}  # category -> [class_paths]

    def register_pack(self, pack_path: str, category: str) -> None:
        """Register all modules from a pack."""
        modules = discover_pack_modules(pack_path, category)
        self._registry.update(modules)

        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].extend(modules.keys())

    def register_module(self, cls: Type[BioModule], class_path: str, category: str = "custom") -> None:
        """Register a single module class."""
        spec = introspect_module(cls, class_path, category)
        self._registry[class_path] = spec

        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(class_path)

    def get(self, class_path: str) -> Optional[ModuleSpec]:
        """Get a module spec by class path."""
        return self._registry.get(class_path)

    def all_modules(self) -> Dict[str, ModuleSpec]:
        """Get all registered modules."""
        return dict(self._registry)

    def by_category(self) -> Dict[str, List[ModuleSpec]]:
        """Get modules grouped by category."""
        result: Dict[str, List[ModuleSpec]] = {}
        for category, paths in self._categories.items():
            result[category] = [self._registry[p] for p in paths if p in self._registry]
        return result

    def to_json(self) -> Dict[str, Any]:
        """Convert registry to JSON-serializable format."""
        modules: Dict[str, Any] = {}
        for path, spec in self._registry.items():
            modules[path] = {
                "name": spec.name,
                "category": spec.category,
                "description": spec.description,
                "inputs": list(spec.inputs),
                "outputs": list(spec.outputs),
                "args": [
                    {
                        "name": arg.name,
                        "type": arg.type,
                        "default": arg.default,
                        "required": arg.required,
                        "description": arg.description,
                        "options": arg.options,
                    }
                    for arg in spec.args
                ],
            }

        categories = {cat: list(paths) for cat, paths in self._categories.items()}

        return {"modules": modules, "categories": categories}


# Global registry instance
_default_registry: Optional[ModuleRegistry] = None


def get_default_registry() -> ModuleRegistry:
    """Get the default module registry, creating it if needed."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ModuleRegistry()
        # Models are self-contained in their own directories (models/models/)
    return _default_registry
