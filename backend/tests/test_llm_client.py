"""Tests for the LLM Client boundary layer."""

from collections.abc import Generator
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Profile, Task
from app.services.llm_client import (
    LLMClient,
    LLMResult,
    LLMUsage,
    get_llm_client,
    llm_is_available,
)
from app.workflow_constants import WORKFLOW_STATUS_CREATED, WORKFLOW_TYPE_FORM_FILL


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory session for tests."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def task(session):
    """Create a task for testing."""

    profile = Profile(profile_name="Test")
    session.add(profile)
    session.flush()

    task = Task(
        url="https://example.com/form",
        profile_id=profile.id,
        workflow_type=WORKFLOW_TYPE_FORM_FILL,
        workflow_status=WORKFLOW_STATUS_CREATED,
    )
    session.add(task)
    session.flush()
    return task


def test_llm_client_complete_json_returns_fallback_when_unavailable():
    """Verify complete_json returns fallback when LLM provider is unavailable."""

    with patch("app.services.llm_provider_config.is_provider_configured", return_value=False):
        client = LLMClient()
        result = client.complete_json(
            prompt="Test prompt",
            schema={"type": "object", "required": ["result"]},
        )

        assert not result.success
        assert result.fallback_used is True
        assert result.error_type == "LLM_UNAVAILABLE"
        assert "not configured" in result.reason


def test_llm_client_summarize_returns_fallback_when_unavailable():
    """Verify summarize returns fallback when LLM provider is unavailable."""

    with patch("app.services.llm_provider_config.is_provider_configured", return_value=False):
        client = LLMClient()
        result = client.summarize(text="This is a test text to summarize.")

        assert not result.success
        assert result.fallback_used is True
        assert result.error_type == "LLM_UNAVAILABLE"
        assert result.content == ""


def test_llm_client_classify_returns_fallback_when_unavailable():
    """Verify classify returns fallback when LLM provider is unavailable."""

    with patch("app.services.llm_provider_config.is_provider_configured", return_value=False):
        client = LLMClient()
        result = client.classify(
            text="This is a test text",
            categories=["positive", "negative", "neutral"],
        )

        assert not result.success
        assert result.fallback_used is True
        assert result.error_type == "LLM_UNAVAILABLE"
        assert result.content == "UNKNOWN"


def test_llm_client_suggest_mapping_returns_fallback_when_unavailable():
    """Verify suggest_mapping returns fallback when LLM provider is unavailable."""

    with patch("app.services.llm_provider_config.is_provider_configured", return_value=False):
        client = LLMClient()
        result = client.suggest_mapping(
            prompt="Test mapping prompt",
            schema={"type": "object", "required": ["mappings"]},
        )

        assert not result.success
        assert result.fallback_used is True
        assert result.error_type == "LLM_UNAVAILABLE"


def test_llm_is_available_returns_false_when_no_api_key():
    """Verify llm_is_available returns False when API key is not configured."""

    with patch("app.services.llm_provider_config.is_provider_configured", return_value=False):
        # Create a fresh client to avoid singleton state issues
        client = LLMClient()
        assert client._is_available() is False


def test_llm_result_is_immutable():
    """Verify LLMResult is immutable."""

    result = LLMResult(
        success=True,
        content={"test": "data"},
        raw_response='{"test": "data"}',
        usage=LLMUsage(provider="test", model="test-model"),
        reason="Test success",
    )

    with pytest.raises(AttributeError):
        result.success = False

    with pytest.raises(AttributeError):
        result.content = {}


def test_llm_usage_defaults():
    """Verify LLMUsage has correct defaults."""

    usage = LLMUsage(provider="test", model="test-model")

    assert usage.prompt_tokens == 0
    assert usage.completion_tokens == 0
    assert usage.total_tokens == 0
    assert usage.cache_hit_tokens == 0
    assert usage.cache_miss_tokens == 0
    assert usage.latency_ms == 0
    assert usage.estimated_cost == 0.0


def test_get_llm_client_returns_singleton():
    """Verify get_llm_client returns a singleton instance."""

    client1 = get_llm_client()
    client2 = get_llm_client()

    assert client1 is client2


def test_get_llm_client_creates_new_with_provider():
    """Verify get_llm_client creates new instance when provider is specified."""

    client1 = get_llm_client(provider="openai")
    client2 = get_llm_client(provider="gemini")

    assert client1 is not client2


def test_llm_client_complete_json_validates_schema():
    """Verify complete_json validates JSON schema."""

    client = LLMClient()

    # Test basic schema validation
    schema = {"type": "object", "required": ["result"], "properties": {"result": {"type": "string"}}}

    # Mock successful provider call
    with patch.object(client, '_call_provider', return_value='{"result": "test"}'):
        with patch.object(client, '_is_available', return_value=True):
            with patch.object(client, '_resolve_provider', return_value='openai'):
                with patch('app.services.llm_provider_config.get_provider_model', return_value='test-model'):
                    result = client.complete_json(
                        prompt="Test",
                        schema=schema,
                    )

                    assert result.success
                    assert result.content == {"result": "test"}


def test_llm_client_complete_json_fails_on_invalid_json():
    """Verify complete_json fails when response is not valid JSON."""

    client = LLMClient()

    schema = {"type": "object", "required": ["result"]}

    # Mock provider returning invalid JSON
    with patch.object(client, '_call_provider', return_value='not valid json'):
        with patch.object(client, '_is_available', return_value=True):
            with patch.object(client, '_resolve_provider', return_value='openai'):
                with patch('app.services.llm_provider_config.get_provider_model', return_value='test-model'):
                    result = client.complete_json(
                        prompt="Test",
                        schema=schema,
                    )

                    assert not result.success
                    assert result.fallback_used is True
                    assert result.error_type == "ValueError"


def test_llm_client_complete_json_fails_on_missing_required_field():
    """Verify complete_json fails when required field is missing."""

    client = LLMClient()

    schema = {"type": "object", "required": ["result", "status"]}

    # Mock provider returning JSON without required field
    with patch.object(client, '_call_provider', return_value='{"result": "test"}'):
        with patch.object(client, '_is_available', return_value=True):
            with patch.object(client, '_resolve_provider', return_value='openai'):
                with patch('app.services.llm_provider_config.get_provider_model', return_value='test-model'):
                    result = client.complete_json(
                        prompt="Test",
                        schema=schema,
                    )

                    assert not result.success
                    assert result.fallback_used is True
                    assert "Missing required field" in result.reason


def test_llm_client_summarize_success():
    """Verify summarize returns success when LLM is available."""

    client = LLMClient()

    with patch.object(client, '_call_provider', return_value='This is a summary.'):
        with patch.object(client, '_is_available', return_value=True):
            with patch.object(client, '_resolve_provider', return_value='openai'):
                with patch('app.services.llm_provider_config.get_provider_model', return_value='test-model'):
                    result = client.summarize(text="This is a long text to summarize.")

                    assert result.success
                    assert result.content == "This is a summary."


def test_llm_client_classify_success():
    """Verify classify returns correct category when LLM is available."""

    client = LLMClient()

    categories = ["positive", "negative", "neutral"]

    with patch.object(client, '_call_provider', return_value='positive'):
        with patch.object(client, '_is_available', return_value=True):
            with patch.object(client, '_resolve_provider', return_value='openai'):
                with patch('app.services.llm_provider_config.get_provider_model', return_value='test-model'):
                    result = client.classify(
                        text="This is great!",
                        categories=categories,
                    )

                    assert result.success
                    assert result.content == "positive"


def test_llm_client_classify_returns_unknown_for_invalid_category():
    """Verify classify returns UNKNOWN when category is not in list."""

    client = LLMClient()

    categories = ["positive", "negative", "neutral"]

    with patch.object(client, '_call_provider', return_value='invalid_category'):
        with patch.object(client, '_is_available', return_value=True):
            with patch.object(client, '_resolve_provider', return_value='openai'):
                with patch('app.services.llm_provider_config.get_provider_model', return_value='test-model'):
                    result = client.classify(
                        text="This is a test.",
                        categories=categories,
                    )

                    assert result.success
                    assert result.content == "UNKNOWN"


def test_llm_client_usage_recording(session, task):
    """Verify usage logging works correctly."""

    client = LLMClient()

    with patch.object(client, '_call_provider', return_value='{"result": "test"}'):
        with patch.object(client, '_is_available', return_value=True):
            with patch.object(client, '_resolve_provider', return_value='openai'):
                with patch('app.services.llm_provider_config.get_provider_model', return_value='test-model'):
                    result = client.complete_json(
                        prompt="Test",
                        schema={"type": "object", "required": ["result"]},
                        task_id=task.id,
                        db=session,
                    )

                    assert result.success
                    assert result.usage is not None
                    assert result.usage.provider == "openai"
                    # Model comes from get_provider_model, which returns configured value
                    assert result.usage.model is not None