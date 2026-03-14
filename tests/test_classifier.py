import pytest
from unittest.mock import patch, MagicMock
from task_queue.task import Priority
from ai.classifier import AIClassifier


@pytest.fixture
def classifier():
    return AIClassifier()


# --- Fallback logic (no API key needed) ---

def test_fallback_payment():
    c = AIClassifier()
    c.enabled = False
    priority, ai = c.classify("Payment confirmation", "payment")
    assert priority == Priority.CRITICAL
    assert ai is False


def test_fallback_digest():
    c = AIClassifier()
    c.enabled = False
    priority, ai = c.classify("Weekly digest", "digest")
    assert priority == Priority.LOW
    assert ai is False


def test_fallback_unknown_type_defaults_to_medium():
    c = AIClassifier()
    c.enabled = False
    priority, ai = c.classify("Some random task", "unknown_type")
    assert priority == Priority.MEDIUM
    assert ai is False


# --- AI path (mocked OpenAI) ---

def make_mock_response(priority: str, reason: str = "test reason"):
    mock_msg = MagicMock()
    mock_msg.content = f'{{"priority": "{priority}", "reason": "{reason}"}}'
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


def test_ai_classifies_critical(classifier):
    classifier.enabled = True
    classifier.client = MagicMock()
    classifier.client.chat.completions.create.return_value = make_mock_response("CRITICAL")
    priority, ai = classifier.classify("Payment confirmation", "payment")
    assert priority == Priority.CRITICAL
    assert ai is True


def test_ai_classifies_low(classifier):
    classifier.enabled = True
    classifier.client = MagicMock()
    classifier.client.chat.completions.create.return_value = make_mock_response("LOW")
    priority, ai = classifier.classify("Weekly digest email", "digest")
    assert priority == Priority.LOW
    assert ai is True


def test_ai_falls_back_on_api_error(classifier):
    classifier.enabled = True
    classifier.client = MagicMock()
    classifier.client.chat.completions.create.side_effect = Exception("API timeout")
    priority, ai = classifier.classify("Payment confirmation", "payment")
    assert priority == Priority.CRITICAL  # fallback kicks in
    assert ai is False


def test_ai_falls_back_on_invalid_json(classifier):
    classifier.enabled = True
    classifier.client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.content = "not valid json at all"
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    classifier.client.chat.completions.create.return_value = mock_response
    priority, ai = classifier.classify("Payment confirmation", "payment")
    assert ai is False  # fell back gracefully


def test_ai_falls_back_on_invalid_priority_value(classifier):
    classifier.enabled = True
    classifier.client = MagicMock()
    classifier.client.chat.completions.create.return_value = make_mock_response("SUPER_URGENT")
    priority, ai = classifier.classify("Some task", "payment")