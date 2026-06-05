"""Compatibility wrapper for the canonical GUI implementation."""

from .gui.app import SimulationGUI, main

__all__ = ["SimulationGUI", "main"]


if __name__ == "__main__":
    main()
