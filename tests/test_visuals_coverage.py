"""Tests for biosim.visuals – cover remaining lines."""
from biosim.visuals import validate_visual_spec, normalize_visuals


def test_validate_not_dict():
    ok, msg = validate_visual_spec("not_a_dict")
    assert ok is False
    assert "dict" in msg


def test_validate_missing_render():
    ok, msg = validate_visual_spec({"data": {}})
    assert ok is False
    assert "render" in msg


def test_validate_missing_data():
    ok, msg = validate_visual_spec({"render": "bar"})
    assert ok is False
    assert "data" in msg


def test_validate_render_not_string():
    ok, msg = validate_visual_spec({"render": 123, "data": {}})
    assert ok is False
    assert "non-empty string" in msg


def test_validate_render_empty_string():
    ok, msg = validate_visual_spec({"render": "", "data": {}})
    assert ok is False
    assert "non-empty string" in msg


def test_validate_data_not_dict():
    ok, msg = validate_visual_spec({"render": "bar", "data": "not_dict"})
    assert ok is False
    assert "'data' must be a dict" in msg


def test_validate_description_not_string():
    ok, msg = validate_visual_spec({"render": "bar", "data": {}, "description": 123})
    assert ok is False
    assert "description" in msg


def test_validate_not_json_serializable():
    ok, msg = validate_visual_spec({"render": "bar", "data": {"x": set([1])}})
    assert ok is False
    assert "JSON-serializable" in msg


def test_validate_valid():
    ok, msg = validate_visual_spec({"render": "bar", "data": {"x": 1}})
    assert ok is True
    assert msg is None


def test_validate_with_description():
    ok, msg = validate_visual_spec({"render": "bar", "data": {}, "description": "hello"})
    assert ok is True


def test_normalize_single_valid():
    result = normalize_visuals({"render": "bar", "data": {"x": 1}})
    assert len(result) == 1
    assert result[0]["render"] == "bar"


def test_normalize_list_filters_invalid():
    items = [
        {"render": "bar", "data": {"x": 1}},
        {"bad": True},
        {"render": "line", "data": {"y": 2}, "description": "desc"},
    ]
    result = normalize_visuals(items)
    assert len(result) == 2
    assert result[0]["render"] == "bar"
    assert result[1]["description"] == "desc"


def test_normalize_empty_list():
    result = normalize_visuals([])
    assert result == []


def test_normalize_all_invalid():
    result = normalize_visuals([{"bad": True}])
    assert result == []
