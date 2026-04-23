def test_world_load_wiring_yaml(tmp_path, biosim):
    world = biosim.BioWorld(communication_step=0.1)
    path = tmp_path / "wiring.yaml"
    path.write_text(
        "\n".join(
            [
                'version: "1"',
                "modules:",
                '  eye: { class: "examples.wiring_builder_demo.Eye" }',
                '  lgn: { class: "examples.wiring_builder_demo.LGN" }',
                "wiring:",
                '  - { from: "eye.visual_stream", to: ["lgn.retina"] }',
                "",
            ]
        ),
        encoding="utf-8",
    )
    biosim.load_wiring(world, path)
    world.run(duration=0.1, tick_dt=0.1)
