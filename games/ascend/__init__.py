# -*- coding: utf-8 -*-
"""
Ascend Game Module
Version 1.0.0

A vertical-climbing, lane-switching, color-reaction game.
The player's marker starts near the bottom of a vertical pixel string,
and the world scrolls downward past them.

Phase 1: Auto-scroll gauntlet with accelerating speed
Phase 2: Manual ascent through a static obstacle field to the Portal
"""

from .ascend import AscendSession, AscendModule

__all__ = ['AscendSession', 'AscendModule']
__version__ = '1.0.0'