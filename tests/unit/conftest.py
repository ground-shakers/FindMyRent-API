"""Conftest for unit tests.

This module provides fixtures for unit testing repositories.
Uses standard mocking approaches compatible with Python unittest.mock.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
