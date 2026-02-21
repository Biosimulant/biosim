"""Tests for biosim.simui.graph – 100% coverage."""
import pytest
from biosim.simui.graph import (
    Position, GraphNode, GraphEdge, ConfigMeta, ConfigGraph,
    _parse_ref, yaml_to_graph, graph_to_yaml, load_config_file,
    save_config_file, graph_to_json, json_to_graph, auto_layout,
)


class TestParseRef:
    def test_valid(self):
        name, port = _parse_ref("eye.visual_stream")
        assert name == "eye"
        assert port == "visual_stream"

    def test_invalid(self):
        with pytest.raises(ValueError, match="Invalid reference"):
            _parse_ref("nodot")


class TestYamlToGraph:
    def test_simple(self):
        yaml_content = """
modules:
  eye:
    class: my.Eye
    args:
      rate: 0.5
  lgn:
    class: my.LGN
wiring:
  - from: eye.visual
    to: [lgn.retina]
"""
        graph = yaml_to_graph(yaml_content)
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
        assert graph.edges[0].source == "eye"
        assert graph.edges[0].target == "lgn"
        # Args should be preserved
        eye = next(n for n in graph.nodes if n.id == "eye")
        assert eye.args == {"rate": 0.5}

    def test_string_module_entry(self):
        yaml_content = """
modules:
  eye: my.module.Eye
"""
        graph = yaml_to_graph(yaml_content)
        assert len(graph.nodes) == 1
        assert graph.nodes[0].type == "my.module.Eye"

    def test_meta_section(self):
        yaml_content = """
meta:
  title: My Sim
  description: A test simulation
modules: {}
"""
        graph = yaml_to_graph(yaml_content)
        assert graph.meta.title == "My Sim"
        assert graph.meta.description == "A test simulation"

    def test_invalid_yaml_type(self):
        with pytest.raises(ValueError, match="dictionary"):
            yaml_to_graph("- item1\n- item2\n")

    def test_invalid_module_entry(self):
        yaml_content = """
modules:
  bad: 42
"""
        graph = yaml_to_graph(yaml_content)
        assert len(graph.nodes) == 0

    def test_wiring_string_target(self):
        yaml_content = """
modules:
  a:
    class: my.A
  b:
    class: my.B
wiring:
  - from: a.out
    to: b.in
"""
        graph = yaml_to_graph(yaml_content)
        assert len(graph.edges) == 1

    def test_wiring_invalid_entries(self):
        yaml_content = """
modules:
  a:
    class: my.A
wiring:
  - "not_a_dict"
  - from: 123
    to: [b.in]
  - from: a.out
    to: 42
  - from: "nodot"
    to: [b.in]
"""
        graph = yaml_to_graph(yaml_content)
        assert len(graph.edges) == 0

    def test_wiring_invalid_target_ref(self):
        yaml_content = """
modules:
  a:
    class: my.A
wiring:
  - from: a.out
    to: ["nodot", 42]
"""
        graph = yaml_to_graph(yaml_content)
        assert len(graph.edges) == 0

    def test_ports_inferred_from_wiring(self):
        yaml_content = """
modules:
  src:
    class: my.Src
  dst:
    class: my.Dst
wiring:
  - from: src.signal_out
    to: [dst.signal_in]
"""
        graph = yaml_to_graph(yaml_content)
        src = next(n for n in graph.nodes if n.id == "src")
        dst = next(n for n in graph.nodes if n.id == "dst")
        assert "signal_out" in src.outputs
        assert "signal_in" in dst.inputs

    def test_empty_modules_and_wiring(self):
        yaml_content = "version: '1'\n"
        graph = yaml_to_graph(yaml_content)
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0


class TestGraphToYaml:
    def test_simple(self):
        graph = ConfigGraph(
            nodes=[
                GraphNode(id="a", type="my.A", args={"x": 1}),
                GraphNode(id="b", type="my.B"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", source_handle="out", target="b", target_handle="in"),
            ],
            meta=ConfigMeta(title="Test"),
        )
        yaml_str = graph_to_yaml(graph)
        assert "my.A" in yaml_str
        assert "my.B" in yaml_str
        assert "Test" in yaml_str

    def test_no_meta(self):
        graph = ConfigGraph(
            nodes=[GraphNode(id="a", type="my.A")],
        )
        yaml_str = graph_to_yaml(graph)
        assert "meta" not in yaml_str

    def test_with_description(self):
        graph = ConfigGraph(
            meta=ConfigMeta(title="T", description="Long\nmultiline\ndescription"),
        )
        yaml_str = graph_to_yaml(graph)
        assert "T" in yaml_str

    def test_empty_graph(self):
        graph = ConfigGraph()
        yaml_str = graph_to_yaml(graph)
        assert yaml_str.strip() == "{}"

    def test_no_args(self):
        graph = ConfigGraph(
            nodes=[GraphNode(id="a", type="my.A")],
        )
        yaml_str = graph_to_yaml(graph)
        assert "args" not in yaml_str


class TestLoadSaveConfigFile:
    def test_load(self, tmp_path):
        p = tmp_path / "test.yaml"
        p.write_text("modules:\n  a:\n    class: my.A\n")
        graph = load_config_file(p)
        assert len(graph.nodes) == 1

    def test_load_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config_file(tmp_path / "missing.yaml")

    def test_save(self, tmp_path):
        graph = ConfigGraph(
            nodes=[GraphNode(id="a", type="my.A")],
        )
        p = tmp_path / "out.yaml"
        save_config_file(graph, p)
        assert p.exists()
        loaded = load_config_file(p)
        assert len(loaded.nodes) == 1

    def test_save_creates_dirs(self, tmp_path):
        graph = ConfigGraph()
        p = tmp_path / "nested" / "dir" / "out.yaml"
        save_config_file(graph, p)
        assert p.exists()


class TestGraphToJson:
    def test_roundtrip(self):
        graph = ConfigGraph(
            nodes=[
                GraphNode(id="a", type="my.A", position=Position(10, 20),
                          args={"x": 1}, inputs=["in"], outputs=["out"]),
            ],
            edges=[
                GraphEdge(id="e1", source="a", source_handle="out", target="a", target_handle="in"),
            ],
            meta=ConfigMeta(title="T", description="D"),
        )
        j = graph_to_json(graph)
        assert j["nodes"][0]["id"] == "a"
        assert j["nodes"][0]["position"]["x"] == 10
        assert j["edges"][0]["sourceHandle"] == "out"
        assert j["meta"]["title"] == "T"


class TestJsonToGraph:
    def test_full(self):
        data = {
            "nodes": [
                {"id": "a", "type": "my.A", "position": {"x": 10, "y": 20},
                 "data": {"args": {"x": 1}, "inputs": ["in"], "outputs": ["out"]}},
            ],
            "edges": [
                {"id": "e1", "source": "a", "sourceHandle": "out", "target": "a", "targetHandle": "in"},
            ],
            "meta": {"title": "T"},
        }
        graph = json_to_graph(data)
        assert len(graph.nodes) == 1
        assert graph.nodes[0].position.x == 10
        assert len(graph.edges) == 1
        assert graph.meta.title == "T"

    def test_empty(self):
        graph = json_to_graph({})
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_invalid_node_and_edge_skipped(self):
        data = {
            "nodes": ["not_a_dict", {"id": "a", "type": "my.A"}],
            "edges": ["not_a_dict", {"id": "e1", "source": "a", "sourceHandle": "out",
                                     "target": "a", "targetHandle": "in"}],
        }
        graph = json_to_graph(data)
        assert len(graph.nodes) == 1
        assert len(graph.edges) == 1


class TestAutoLayout:
    def test_empty_graph(self):
        graph = ConfigGraph()
        result = auto_layout(graph)
        assert len(result.nodes) == 0

    def test_simple_chain(self):
        graph = ConfigGraph(
            nodes=[
                GraphNode(id="a", type="x"),
                GraphNode(id="b", type="x"),
                GraphNode(id="c", type="x"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", source_handle="o", target="b", target_handle="i"),
                GraphEdge(id="e2", source="b", source_handle="o", target="c", target_handle="i"),
            ],
        )
        result = auto_layout(graph)
        # a should be leftmost, then b, then c
        pos_map = {n.id: n.position for n in result.nodes}
        assert pos_map["a"].x < pos_map["b"].x < pos_map["c"].x

    def test_cycle_handling(self):
        graph = ConfigGraph(
            nodes=[
                GraphNode(id="a", type="x"),
                GraphNode(id="b", type="x"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", source_handle="o", target="b", target_handle="i"),
                GraphEdge(id="e2", source="b", source_handle="o", target="a", target_handle="i"),
            ],
        )
        # Should not raise even with cycle
        result = auto_layout(graph)
        assert len(result.nodes) == 2

    def test_disconnected_nodes(self):
        graph = ConfigGraph(
            nodes=[
                GraphNode(id="a", type="x"),
                GraphNode(id="b", type="x"),
            ],
        )
        result = auto_layout(graph)
        # Both should get positions
        for n in result.nodes:
            assert n.position.x >= 0
