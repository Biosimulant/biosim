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


def test_flatten_lab_tree_preserves_model_ref_parameters_and_child_io_override() -> None:
    child = LabTree(
        models=[
            LabTreeModel(
                alias="m",
                ref="plain-ref",
                parameters={"alpha": 1},
            )
        ],
        wiring=[LabTreeWire(from_ref="m.out", to_refs=["m.in"])],
    )
    root = LabTree(
        children=[
            LabTreeChild(
                alias="child",
                tree=child,
                io=LabTreeIO(inputs=[LabTreePort(name="external_in", maps_to="m.in")]),
            )
        ],
        wiring=[LabTreeWire(from_ref="child.external_in", to_refs=["child.m.out"])],
    )

    flat = flatten_lab_tree(root)

    assert flat.models == [
        {
            "alias": "child.m",
            "ref": "plain-ref",
            "parameters": {"alpha": 1},
        }
    ]
    assert {"from": "child.m.in", "to": ["child.m.out"]} in flat.wiring


@pytest.mark.parametrize(
    "tree, match",
    [
        (LabTree(models=[LabTreeModel(alias="", ref={})]), "non-empty alias"),
        (LabTree(children=[LabTreeChild(alias="", tree=LabTree())]), "child entries"),
        (LabTree(wiring=[LabTreeWire(from_ref="", to_refs=["a.b"])]), "from ref"),
        (LabTree(wiring=[LabTreeWire(from_ref="a.b", to_refs=[""])]), "targets"),
    ],
)
def test_flatten_lab_tree_rejects_invalid_aliases_and_wiring(tree: LabTree, match: str) -> None:
    with pytest.raises(RuntimeError, match=match):
        flatten_lab_tree(tree)


def test_lab_io_from_mapping_ignores_invalid_entries() -> None:
    from biosim.runtime.flatten import lab_io_from_mapping

    io = lab_io_from_mapping(
        {
            "inputs": [
                LabTreePort(name="as-dataclass", maps_to="m.in"),
                {"name": "as-mapping", "maps_to": "m.other"},
                {"name": 1, "maps_to": "bad"},
                "bad",
            ],
            "outputs": "bad",
        }
    )

    assert [port.name for port in io.inputs] == ["as-dataclass", "as-mapping"]
    assert io.outputs == []
