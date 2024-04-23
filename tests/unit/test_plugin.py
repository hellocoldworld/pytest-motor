"""Test pytest_motor.plugin."""
from asyncio import AbstractEventLoop
from pathlib import Path
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from _pytest.config import Config as PytestConfig

from pytest_motor.plugin import database_path as _database_path
from pytest_motor.plugin import event_loop as _event_loop
from pytest_motor.plugin import root_directory as _root_directory

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
@pytest.mark.skip("Deprecated pytest code")
async def test_root_directory() -> None:
    """Test the pytest root directory fixture."""
    mock_root_directory = MagicMock()
    mock_pytestconfig = MagicMock(PytestConfig)
    type(mock_pytestconfig).rootpath = PropertyMock(return_value=mock_root_directory)

    assert await _root_directory(mock_pytestconfig) == mock_root_directory


@pytest.mark.skip("Deprecated pytest code")
def test_event_loop() -> None:
    """Test pytest_motor.plugin._event_loop."""
    mock_close = Mock(AbstractEventLoop.close)
    mock_event_loop = Mock(AbstractEventLoop, close=mock_close)
    with patch('asyncio.get_event_loop', return_value=mock_event_loop):
        loop_iterator = _event_loop()

        loop = next(loop_iterator)

    assert loop is mock_event_loop

    with pytest.raises(StopIteration):
        next(loop_iterator)

    mock_close.assert_called_once()
