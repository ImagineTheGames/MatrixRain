#!/usr/bin/env pythonw
"""
Launcher for Matrix Rain - runs with no console window (tray only).
Double-click this file or run: pythonw run_matrix_rain.pyw
"""
import os
import sys

# Run from this script's directory so config and imports work
_root = os.path.dirname(os.path.abspath(__file__))
os.chdir(_root)
if _root not in sys.path:
    sys.path.insert(0, _root)

import matrix_rain
matrix_rain.main()
