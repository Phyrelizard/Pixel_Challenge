# -*- coding: utf-8 -*-
"""
Game Registry - Builds and returns the dictionary of available game modules.
"""
from games.dot_dash.dot_dash import DotDashModule


def build_game_registry():
    """
    Build and return a registry of all available game modules.
    
    Returns:
        dict mapping game_key -> GameModule instance
    """
    modules = [
        DotDashModule(),
        # Add more game modules here as they're developed:
        # PixelPopModule(),
        # SurroundModule(),
        # AscendModule(),
    ]
    return {module.META.key: module for module in modules}