"""Tests for prompt activation/deactivation endpoints."""

import os

# Configure logging before importing simpa modules
os.environ["JSON_LOGGING"] = "false"
os.environ["LOG_LEVEL"] = "INFO"

import uuid

import pytest

from simpa.mcp_server import (
    ActivatePromptRequest,
    DeactivatePromptRequest,
)


class TestActivatePromptRequest:
    """Test activate prompt request validation."""

    def test_valid_prompt_key(self):
        """Test valid UUID prompt key is accepted."""
        valid_uuid = str(uuid.uuid4())
        request = ActivatePromptRequest(prompt_key=valid_uuid)
        assert request.prompt_key == valid_uuid

    def test_invalid_prompt_key(self):
        """Test invalid prompt key raises validation error."""
        with pytest.raises(ValueError) as exc_info:
            ActivatePromptRequest(prompt_key="not-a-valid-uuid")
        assert "prompt_key must be a valid UUID" in str(exc_info.value)

    def test_empty_prompt_key(self):
        """Test empty prompt key raises validation error."""
        with pytest.raises(ValueError):
            ActivatePromptRequest(prompt_key="")


class TestDeactivatePromptRequest:
    """Test deactivate prompt request validation."""

    def test_valid_prompt_key(self):
        """Test valid UUID prompt key is accepted."""
        valid_uuid = str(uuid.uuid4())
        request = DeactivatePromptRequest(prompt_key=valid_uuid)
        assert request.prompt_key == valid_uuid

    def test_invalid_prompt_key(self):
        """Test invalid prompt key raises validation error."""
        with pytest.raises(ValueError) as exc_info:
            DeactivatePromptRequest(prompt_key="not-a-valid-uuid")
        assert "prompt_key must be a valid UUID" in str(exc_info.value)

    def test_empty_prompt_key(self):
        """Test empty prompt key raises validation error."""
        with pytest.raises(ValueError):
            DeactivatePromptRequest(prompt_key="")