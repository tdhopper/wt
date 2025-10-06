"""Pytest configuration."""

from pathlib import Path
import sys


# Add parent directory to path so we can import wt
sys.path.insert(0, str(Path(__file__).parent.parent))
