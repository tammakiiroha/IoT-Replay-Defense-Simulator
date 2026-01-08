"""
GUI Package for Replay Attack Simulation
模块化 GUI 界面 - Web-style version
"""

from .gui.app import SimulationGUI, main
from .widgets import AcademicButton, SectionCard, ModernButton, ModernCard
from .theme import COLORS, FONTS, MODE_META
from .translations import TRANSLATIONS

__all__ = [
    "SimulationGUI",
    "main",
    "AcademicButton",
    "SectionCard",
    "ModernButton",
    "ModernCard",
    "COLORS",
    "FONTS",
    "MODE_META",
    "TRANSLATIONS",
]
