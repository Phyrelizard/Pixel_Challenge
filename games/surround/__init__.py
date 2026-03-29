# -*- coding: utf-8 -*-
"""
Surround Game Module
Version 1.0.2

A center-defense, two-lane, dual-direction pressure game with eggs,
hatch events, and special hunter threats.

Supports two modes:
- Mode 1: Arcade Timing Game
- Mode 2: Objective Game
"""

from .surround import SurroundSession, SurroundModule

__all__ = ['SurroundSession', 'SurroundModule']
__version__ = '1.0.2'