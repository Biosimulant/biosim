from __future__ import annotations

import pytest

from biosim.runtime import (
    LabTree,
    LabTreeChild,
    LabTreeIO,
    LabTreeModel,
    LabTreePort,
    LabTreeWire,
    flatten_lab_tree,
)


def test_flatten_lab_tree_scopes_child_aliases_and_remaps_external_ports() -> None:
    child = LabTree(
        models=[LabTreeModel(alias="counter", ref={"path": "child/models/counter"})],
        wiring=[],
        io=LabTreeIO(outputs=[LabTreePort(name="count", maps_to="counter.count")]),
    )
    root = LabTree(
        models=[LabTreeModel(alias="acc", ref={"path": "models/acc"})],
        children=[LabTreeChild(alias="nested", tree=child)],
        wiring=[LabTreeWire(from_ref="nested.count", to_refs=["acc.value"])],
    )

    flat = flatten_lab_tree(root)

    assert flat.models == [
        {"alias": "acc", "path": "models/acc"},
        {"alias": "nested.counter", "path": "child/models/counter"},
    ]
    assert flat.wiring == [{"from": "nested.counter.count", "to": ["acc.value"]}]


def test_flatten_lab_tree_rejects_unresolved_child() -> None:
    root = LabTree(children=[LabTreeChild(alias="missing", tree=None)])

    with pytest.raises(RuntimeError, match="unresolved"):
        flatten_lab_tree(root)


def test_flatten_lab_tree_rejects_cycles() -> None:
    root = LabTree()
    root.children.append(LabTreeChild(alias="self", tree=root))

    with pytest.raises(RuntimeError, match="Circular"):
        flatten_lab_tree(root)


def test_flatten_lab_tree_rejects_excessive_depth() -> None:
    current = LabTree()
    root = current
    for idx in range(6):
        child = LabTree()
        current.children.append(LabTreeChild(alias=f"c{idx}", tree=child))
        current = child

    with pytest.raises(RuntimeError, match="maximum depth"):
        flatten_lab_tree(root, max_depth=5)
