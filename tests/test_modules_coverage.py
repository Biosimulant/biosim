"""Tests for biosim.modules – cover all default method implementations."""


def test_setup_default_noop(biosim):
    """BioModule.setup() default is a no-op."""

    class Minimal(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    m = Minimal()
    result = m.setup()
    assert result is None


def test_reset_default_noop(biosim):
    class Minimal(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    m = Minimal()
    result = m.reset()
    assert result is None


def test_set_inputs_default_noop(biosim):
    class Minimal(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    m = Minimal()
    result = m.set_inputs({"x": biosim.BioSignal("src", "x", 1.0, 0.0)})
    assert result is None


def test_get_state_default_empty(biosim):
    class Minimal(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    m = Minimal()
    assert m.get_state() == {}


def test_next_due_time_default(biosim):
    class Minimal(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.5

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    m = Minimal()
    assert m.next_due_time(1.0) == 1.5


def test_inputs_default_empty(biosim):
    class Minimal(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    m = Minimal()
    assert m.inputs() == set()


def test_outputs_default_empty(biosim):
    class Minimal(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    m = Minimal()
    assert m.outputs() == set()


def test_input_schemas_default_empty(biosim):
    class Minimal(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    m = Minimal()
    assert m.input_schemas() == {}


def test_output_schemas_default_empty(biosim):
    class Minimal(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    m = Minimal()
    assert m.output_schemas() == {}


def test_visualize_default_none(biosim):
    class Minimal(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    m = Minimal()
    assert m.visualize() is None
