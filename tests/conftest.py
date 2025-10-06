"""Pytest configuration."""

import sys
from pathlib import Path

# Add parent directory to path so we can import wt
sys.path.insert(0, str(Path(__file__).parent.parent))
