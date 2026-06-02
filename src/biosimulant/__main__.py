# SPDX-FileCopyrightText: 2026-present Biosimulant Team
#
# SPDX-License-Identifier: MIT
# PYTHON_ARGCOMPLETE_OK
"""Primary `biosimulant` CLI entrypoint.

This delegates to the compatibility `biosim` CLI implementation so Phase 1 adds
the new command surface without creating a second CLI implementation.
"""
from __future__ import annotations

from biosim.__main__ import main as _biosim_main


def main(argv: list[str] | None = None) -> None:
    _biosim_main(argv, prog="biosimulant")


if __name__ == "__main__":
    main()
