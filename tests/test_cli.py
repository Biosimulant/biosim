"""Tests for biosim.__main__ (CLI) – achieve 100% coverage."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from biosim.__main__ import load_config, create_world, run_headless, main


class TestLoadConfig:
    def test_yaml(self, tmp_path):
        p = tmp_path / "cfg.yaml"
        p.write_text("runtime:\n  communication_step: 0.1\nmodules:\n  eye:\n    class: examples.wiring_builder_demo.Eye\n")
        result = load_config(p)
        assert "modules" in result

    def test_yml(self, tmp_path):
        p = tmp_path / "cfg.yml"
        p.write_text("version: '1'\n")
        result = load_config(p)
        assert result["version"] == "1"

    def test_yaml_empty(self, tmp_path):
        p = tmp_path / "cfg.yaml"
        p.write_text("")
        result = load_config(p)
        assert result == {}

    def test_toml(self, tmp_path):
        p = tmp_path / "cfg.toml"
        p.write_text('[meta]\ntitle = "test"\n')
        result = load_config(p)
        assert result["meta"]["title"] == "test"

    def test_tml(self, tmp_path):
        p = tmp_path / "cfg.tml"
        p.write_text('[meta]\ntitle = "test"\n')
        result = load_config(p)
        assert result["meta"]["title"] == "test"

    def test_unsupported_format(self, tmp_path):
        p = tmp_path / "cfg.json"
        p.write_text("{}")
        with pytest.raises(SystemExit):
            load_config(p)

    def test_yaml_import_error(self, tmp_path):
        """yaml ImportError should print error and sys.exit(1)."""
        p = tmp_path / "cfg.yaml"
        p.write_text("x: 1\n")
        import builtins
        real_import = builtins.__import__
        def fake_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("No module named 'yaml'")
            return real_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=fake_import):
            with pytest.raises(SystemExit) as exc_info:
                load_config(p)
            assert exc_info.value.code == 1

    def test_toml_all_imports_fail(self, tmp_path):
        """toml ImportError should print error and sys.exit(1)."""
        p = tmp_path / "cfg.toml"
        p.write_text('[meta]\ntitle = "test"\n')
        import builtins
        real_import = builtins.__import__
        def fake_import(name, *args, **kwargs):
            if name in ("tomllib", "tomli"):
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=fake_import):
            with pytest.raises(SystemExit) as exc_info:
                load_config(p)
            assert exc_info.value.code == 1

    def test_toml_tomli_fallback(self, tmp_path):
        """When tomllib fails but tomli succeeds."""
        p = tmp_path / "cfg.toml"
        p.write_text('[meta]\ntitle = "test"\n')
        import builtins
        real_import = builtins.__import__
        def fake_import(name, *args, **kwargs):
            if name == "tomllib":
                raise ImportError("No module named 'tomllib'")
            return real_import(name, *args, **kwargs)
        # Only test if tomli is available
        try:
            import tomli
        except ImportError:
            pytest.skip("tomli not available")
        with patch("builtins.__import__", side_effect=fake_import):
            result = load_config(p)
        assert result["meta"]["title"] == "test"


class TestCreateWorld:
    def test_creates_bioworld(self):
        world = create_world({"runtime": {"communication_step": 0.1}})
        from biosim.world import BioWorld
        assert isinstance(world, BioWorld)


class TestRunHeadless:
    def test_basic_run(self, biosim, capsys):
        world = biosim.BioWorld(communication_step=0.1)

        class M(biosim.BioModule):
            def __init__(self):
                pass

            def advance_window(self, _start, t):
                pass

            def get_outputs(self):
                return {}

        world.add_biomodule("m", M())
        run_headless(world, duration=0.2, tick_dt=0.1)
        captured = capsys.readouterr()
        assert "Running simulation" in captured.out
        assert "Simulation complete" in captured.out
        assert "No visuals collected" in captured.out

    def test_with_visuals(self, biosim, capsys):
        world = biosim.BioWorld(communication_step=0.1)

        class VisModule(biosim.BioModule):
            def __init__(self):
                pass

            def advance_window(self, _start, t):
                pass

            def get_outputs(self):
                return {}

            def visualize(self):
                return {"render": "bar", "data": {"items": [{"label": "a", "value": 1}]}}

        world.add_biomodule("vis", VisModule())
        run_headless(world, duration=0.1, tick_dt=0.1)
        captured = capsys.readouterr()
        assert "Collected visuals" in captured.out
        assert "vis" in captured.out
        assert "bar" in captured.out


class TestRunSimui:
    def test_simui_import_error(self, biosim, capsys):
        from biosim.__main__ import run_simui

        with patch.dict(sys.modules, {"biosim.simui": None}):
            with pytest.raises(SystemExit):
                run_simui(
                    biosim.BioWorld(communication_step=0.1),
                    {},
                    config_path=Path("/tmp/test.yaml"),
                    duration=1.0,
                    tick_dt=0.1,
                    port=8765,
                    host="127.0.0.1",
                    open_browser=False,
                )

    def test_simui_success(self, biosim, capsys):
        """run_simui should create Interface and call launch."""
        from biosim.__main__ import run_simui
        from biosim.simui.interface import Interface
        mock_interface = MagicMock()
        with patch.object(Interface, "launch") as mock_launch:
            with patch.object(Interface, "mount"):
                run_simui(
                    biosim.BioWorld(communication_step=0.1),
                    {"meta": {"title": "Test Sim", "description": "Desc"}},
                    config_path=Path("/tmp/test.yaml"),
                    duration=5.0,
                    tick_dt=0.1,
                    port=9999,
                    host="0.0.0.0",
                    open_browser=True,
                )
        mock_launch.assert_called_once_with(host="0.0.0.0", port=9999, open_browser=True)
        captured = capsys.readouterr()
        assert "Starting SimUI" in captured.out


class TestMain:
    def test_missing_config(self, tmp_path):
        with patch("sys.argv", ["biosim", str(tmp_path / "nonexistent.yaml")]):
            with pytest.raises(SystemExit):
                main()

    def test_headless_run(self, tmp_path):
        from examples.wiring_builder_demo import Eye, LGN

        cfg = tmp_path / "wiring.yaml"
        cfg.write_text(f"""
modules:
  eye:
    class: "{Eye.__module__}.{Eye.__name__}"
  lgn:
    class: "{LGN.__module__}.{LGN.__name__}"
runtime:
  communication_step: 0.1
wiring:
  - from: "eye.visual_stream"
    to: ["lgn.retina"]
""")
        with patch("sys.argv", ["biosim", str(cfg), "--duration", "0.2", "--tick", "0.1"]):
            main()

    def test_tick_zero(self, tmp_path):
        """--tick 0 should result in tick_dt=None."""
        from examples.wiring_builder_demo import Eye

        cfg = tmp_path / "wiring.yaml"
        cfg.write_text(f"""
modules:
  eye:
    class: "{Eye.__module__}.{Eye.__name__}"
runtime:
  communication_step: 0.1
""")
        with patch("sys.argv", ["biosim", str(cfg), "--duration", "0.1", "--tick", "0"]):
            # tick <= 0 -> tick_dt = None
            main()

    def test_simui_mode(self, tmp_path):
        """--simui flag should call run_simui."""
        from examples.wiring_builder_demo import Eye

        cfg = tmp_path / "wiring.yaml"
        cfg.write_text(f"""
modules:
  eye:
    class: "{Eye.__module__}.{Eye.__name__}"
runtime:
  communication_step: 0.1
""")
        with patch("sys.argv", ["biosim", str(cfg), "--simui"]):
            with patch("biosim.__main__.run_simui") as mock_simui:
                main()
                mock_simui.assert_called_once()

    def test_module_count_exception(self, tmp_path):
        """If module_names raises, module_count should default to 0."""
        from examples.wiring_builder_demo import Eye

        cfg = tmp_path / "wiring.yaml"
        cfg.write_text(f"""
modules:
  eye:
    class: "{Eye.__module__}.{Eye.__name__}"
runtime:
  communication_step: 0.1
""")
        with patch("sys.argv", ["biosim", str(cfg), "--duration", "0.1"]):
            with patch("biosim.world.BioWorld.module_names", new_callable=lambda: property(lambda self: (_ for _ in ()).throw(RuntimeError("test")))):
                main()

    def test_pack_validate_success_human_output(self, tmp_path, capsys):
        from biosim.pack import build_package

        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "model.yaml").write_text(
            """
schema_version: "2.0"
title: "Counter"
description: "Counter model"
standard: other
tags: [test]
authors: ["Tests"]
biosim:
  entrypoint: "src.counter:Counter"
  communication_step: 0.1
""".strip()
            + "\n",
            encoding="utf-8",
        )
        src_dir = pkg_dir / "src"
        src_dir.mkdir()
        (src_dir / "counter.py").write_text(
            """
from biosim import BioModule


class Counter(BioModule):
    def advance_window(self, _start, t): return
    def get_outputs(self): return {}
""".strip()
            + "\n",
            encoding="utf-8",
        )
        package_path = build_package(pkg_dir, package_name="local/counter", version="1.0.0")

        with patch("sys.argv", ["biosim", "pack", "validate", str(package_path)]):
            main()

        captured = capsys.readouterr()
        assert "BioSim package validation passed." in captured.out
        assert "local/counter@1.0.0" in captured.out

    def test_pack_validate_failure_human_output(self, tmp_path, capsys):
        package_path = tmp_path / "bad.bsimpkg"
        package_path.write_bytes(b"not a zip")

        with patch("sys.argv", ["biosim", "pack", "validate", str(package_path)]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "BioSim package validation failed." in captured.err
        assert "not a zip" in captured.err.lower() or "file is not a zip file" in captured.err.lower()

    def test_pack_build_human_output(self, tmp_path, capsys):
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "model.yaml").write_text(
            """
schema_version: "2.0"
title: "Counter"
description: "Counter model"
standard: other
tags: [test]
authors: ["Tests"]
package: declared/counter
version: 9.9.9
biosim:
  entrypoint: "src.counter:Counter"
  communication_step: 0.1
""".strip()
            + "\n",
            encoding="utf-8",
        )
        src_dir = pkg_dir / "src"
        src_dir.mkdir()
        (src_dir / "counter.py").write_text(
            """
from biosim import BioModule


class Counter(BioModule):
    def advance_window(self, _start, t): return
    def get_outputs(self): return {}
""".strip()
            + "\n",
            encoding="utf-8",
        )

        with patch("sys.argv", ["biosim", "pack", "build", str(pkg_dir)]):
            main()

        captured = capsys.readouterr()
        assert "BioSim package build succeeded." in captured.out
        assert "declared/counter@9.9.9" in captured.out

    def test_pack_command_error_output(self, capsys):
        with patch("sys.argv", ["biosim", "pack", "fetch", "badref"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "BioSim package command failed." in captured.err
        assert "package@version" in captured.err
