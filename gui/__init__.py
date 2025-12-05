"""
GUI Package for Replay Attack Simulation
模块化 GUI 界面
"""

from .app import SimulationGUI, main
from .widgets import AcademicButton, SectionCard
from .theme import COLORS, FONTS
from .translations import TRANSLATIONS

__all__ = [
    "SimulationGUI",
    "main",
    "AcademicButton",
    "SectionCard",
    "COLORS",
    "FONTS",
    "TRANSLATIONS",
]
