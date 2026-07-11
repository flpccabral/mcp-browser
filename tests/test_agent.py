import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import asyncio

import pytest

import browser_mcp.tools as tools_module
from browser_mcp.agent import BrowserAgent
from browser_mcp.browser_manager import BrowserManager


# =============================================================================
# MockLLM
# =============================================================================
class MockLLM:
    """Mock do LLMClient para testes do agente."""

    def __init__(self, responses=None, default_response=None, fail_count=0):
        self.responses = responses or []
        self.default_response = default_response or (
            '{"thought": "default", "tool": "browser_navigate", '
            '"params": {"url": "https://example.com"}, "is_complete": false}'
        )
        self.fail_count = fail_count
        self.call_count = 0

    async def initialize(self):
        """No-op para compatibilidade."""
        pass

    async def chat(self, messages):
        """Retorna a próxima resposta mockada ou lança exceção se fail_count > 0."""
        if self.fail_count > 0:
            self.fail_count -= 1
            self.call_count += 1
            raise RuntimeError("Simulated LLM failure")

        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
        else:
            response = self.default_response
        self.call_count += 1
        return response


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def mock_llm():
    return MockLLM()


@pytest.fixture
async def browser_manager():
    """Inicia o browser antes dos testes e para após."""
    BrowserManager._instance = None
    BrowserManager._lock = asyncio.Lock()
    bm = BrowserManager()
    tools_module.browser_manager = bm
    await bm.start()
    yield bm
    await bm.stop()
    BrowserManager._instance = None


# =============================================================================
# execute_task
# =============================================================================
async def test_execute_task_simple(mock_llm, browser_manager):
    """Cenário simples: navegar para example.com, tirar screenshot, completar."""
    mock_llm.responses = [
        (
            '{"thought": "Navigate to example.com", '
            '"tool": "browser_navigate", '
            '"params": {"url": "https://example.com"}, '
            '"is_complete": false}'
        ),
        (
            '{"thought": "Take a screenshot", '
            '"tool": "browser_screenshot", '
            '"params": {}, '
            '"is_complete": false}'
        ),
        (
            '{"thought": "Task is done", '
            '"is_complete": true, '
            '"report": "Successfully visited example.com and took a screenshot"}'
        ),
    ]
    agent = BrowserAgent(
        browser_manager,
        mock_llm,
        max_iterations=10,
        screenshot_on_action=False,
    )
    result = await agent.execute_task("Go to example.com and take a screenshot")
    assert result["success"] is True
    assert "Successfully visited example.com" in result["report"]
    assert result["action_count"] == 2


async def test_max_iterations(mock_llm, browser_manager):
    """Agente deve parar após max_iterations sem completar."""
    mock_llm.default_response = (
        '{"thought": "Keep going", '
        '"tool": "browser_navigate", '
        '"params": {"url": "https://example.com"}, '
        '"is_complete": false}'
    )
    agent = BrowserAgent(
        browser_manager,
        mock_llm,
        max_iterations=3,
        screenshot_on_action=False,
    )
    result = await agent.execute_task("Infinite task")
    assert result["success"] is False
    assert "max iterations" in result["report"].lower()


async def test_consecutive_errors(mock_llm, browser_manager):
    """Agente deve falhar após max_consecutive_errors erros consecutivos."""
    # O código do agente reseta consecutive_errors=0 após LLM call bem-sucedida.
    # Para acumular erros consecutivos, precisamos simular falhas na chamada ao LLM.
    mock_llm.fail_count = 3
    agent = BrowserAgent(
        browser_manager,
        mock_llm,
        max_iterations=10,
        max_consecutive_errors=3,
        screenshot_on_action=False,
    )
    result = await agent.execute_task("Task with failing LLM")
    assert result["success"] is False
    assert "consecutive" in result["report"].lower()


# =============================================================================
# _parse_response
# =============================================================================
def test_parse_response_markdown_json():
    """JSON dentro de bloco markdown ```json ... ```."""
    agent = BrowserAgent(None, None)
    text = (
        '```json\n'
        '{"thought": "test", "tool": "browser_navigate", '
        '"params": {}, "is_complete": true}\n'
        '```'
    )
    result = agent._parse_response(text)
    assert result is not None
    assert result["thought"] == "test"
    assert result["is_complete"] is True


def test_parse_response_raw_json():
    """JSON cru sem markdown."""
    agent = BrowserAgent(None, None)
    text = (
        '{"thought": "raw", "tool": "browser_click", '
        '"params": {"selector": "a"}, "is_complete": false}'
    )
    result = agent._parse_response(text)
    assert result is not None
    assert result["thought"] == "raw"
    assert result["is_complete"] is False


def test_parse_response_invalid_text():
    """Texto que não é JSON válido."""
    agent = BrowserAgent(None, None)
    text = "This is just plain text without any JSON structure"
    result = agent._parse_response(text)
    assert result is None


def test_parse_response_empty():
    """Resposta vazia."""
    agent = BrowserAgent(None, None)
    result = agent._parse_response("")
    assert result is None


def test_parse_response_nested_markdown():
    """JSON dentro de bloco markdown genérico ``` ... ```."""
    agent = BrowserAgent(None, None)
    text = '```\n{"thought": "nested", "is_complete": true}\n```'
    result = agent._parse_response(text)
    assert result is not None
    assert result["thought"] == "nested"


# =============================================================================
# _prune_messages
# =============================================================================
def test_prune_messages_under_limit():
    """Não deve remover mensagens se estiver abaixo do limite."""
    agent = BrowserAgent(None, None)
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": "response"},
    ]
    pruned = agent._prune_messages(messages, max_messages=10)
    assert len(pruned) == 3
    assert pruned[0]["role"] == "system"


def test_prune_messages_over_limit():
    """Deve manter system + primeira user + mensagens mais recentes."""
    agent = BrowserAgent(None, None)
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "original task"},
    ]
    for i in range(50):
        messages.append({"role": "user", "content": f"observation {i}"})
        messages.append({"role": "assistant", "content": f"action {i}"})

    pruned = agent._prune_messages(messages, max_messages=10)
    assert len(pruned) <= 10
    # System deve estar presente
    assert any(m["role"] == "system" for m in pruned)
    # Primeira mensagem do usuário (task) deve estar presente
    assert any(m.get("content") == "original task" for m in pruned)
    # Mensagens recentes devem estar presentes
    assert any("observation 49" in m.get("content", "") for m in pruned)


def test_prune_messages_no_system():
    """Funciona mesmo sem mensagens de sistema."""
    agent = BrowserAgent(None, None)
    messages = [{"role": "user", "content": "task"}]
    for i in range(50):
        messages.append({"role": "assistant", "content": f"reply {i}"})

    pruned = agent._prune_messages(messages, max_messages=10)
    assert len(pruned) <= 10
    assert pruned[0]["content"] == "task"
