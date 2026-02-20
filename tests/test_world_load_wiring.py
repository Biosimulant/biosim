def test_world_load_wiring_toml(tmp_path, biosim):
    world = biosim.BioWorld()
    path = tmp_path / "wiring.toml"
    path.write_text(
        "\n".join(
            [
                'version = "1"',
                "",
                "[modules.eye]",
                'class = "examples.wiring_builder_demo.Eye"',
                "min_dt = 0.01",
                "",
                "[modules.lgn]",
                'class = "examples.wiring_builder_demo.LGN"',
                "",
                "[[wiring]]",
                'from = "eye.visual_stream"',
                'to = ["lgn.retina"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    biosim.load_wiring(world, path)
    world.run(duration=0.1, tick_dt=0.1)
