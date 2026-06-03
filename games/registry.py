# -*- coding: utf-8 -*-
"""
Game Registry - Central registration of all game modules.
"""
from __future__ import annotations


def build_game_registry() -> dict:
    """
    Build and return the registry of all available game modules.
    
    Returns:
        Dictionary mapping game_key -> GameModule instance
    """
    registry = {}
    
    # Import and register Dot Dash
    try:
        from games.dot_dash import DotDashModule
        registry["dot_dash"] = DotDashModule()
    except ImportError as e:
        print(f"[REGISTRY] Failed to load dot_dash: {e}")
    
    # Import and register Pixel Pop
    try:
        from games.pixel_pop import PixelPopModule
        registry["pixel_pop"] = PixelPopModule()
    except ImportError as e:
        print(f"[REGISTRY] Failed to load pixel_pop: {e}")
    
    # Import and register Surround
    try:
        from games.surround import SurroundModule
        registry["surround"] = SurroundModule()
    except ImportError as e:
        print(f"[REGISTRY] Failed to load surround: {e}")
    
    try:
        from games.ascend import AscendModule
        registry["ascend"] = AscendModule()
    except ImportError as e:
        print(f"[REGISTRY] Failed to load ascend: {e}")

    try:
        from games.chomp_chase import ChompChaseModule
        registry["chomp_chase"] = ChompChaseModule()
    except ImportError as e:
        print(f"[REGISTRY] Failed to load chomp_chase: {e}")
    
    return registry
