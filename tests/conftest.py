"""Pytest configuration and shared fixtures."""

import asyncio
import sys
from pathlib import Path

import pytest

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
