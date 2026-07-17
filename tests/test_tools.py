import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import asyncio
import json
import tempfile

import pytest

import browser_mcp.tools as tools_module
from browser_mcp.browser_manager import BrowserManager
from browser_mcp.tools import app


# =============================================================================
# Fixture
# =============================================================================
@pytest.fixture
async def browser_manager():
    """Inicia o browser antes dos testes e para após."""
    # Reseta o singleton para garantir uma instância fresca a cada teste
    BrowserManager._instance = None
    BrowserManager._lock = asyncio.Lock()
    bm = BrowserManager()
    # Atualiza o browser_manager usado pelas ferramentas do módulo tools
    tools_module.browser_manager = bm
    await bm.start()
    yield bm
    await bm.stop()
    BrowserManager._instance = None


# =============================================================================
# 1. Navegação
# =============================================================================
async def test_navigate(browser_manager):
    result = await app.call_tool("browser_navigate", {"url": "https://example.com"})
    assert len(result) == 1
    assert result[0].type == "text"
    assert "Navegado para https://example.com" in result[0].text


async def test_go_back(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    await app.call_tool("browser_navigate", {"url": "data:text/html,<h1>Second Page</h1>"})
    result = await app.call_tool("browser_go_back", {})
    assert "Navegado para página anterior" in result[0].text


async def test_go_forward(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    await app.call_tool("browser_navigate", {"url": "data:text/html,<h1>Second Page</h1>"})
    await app.call_tool("browser_go_back", {})
    result = await app.call_tool("browser_go_forward", {})
    assert "Navegado para página seguinte" in result[0].text


async def test_reload(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    result = await app.call_tool("browser_reload", {})
    assert "Página recarregada" in result[0].text


# =============================================================================
# 2. Interação com elementos
# =============================================================================
async def test_click(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    result = await app.call_tool("browser_click", {"selector": "a", "by": "css"})
    assert "Elemento clicado" in result[0].text


async def test_type(browser_manager):
    # Usa data URI para garantir elementos presentes e teste determinístico
    data_uri = 'data:text/html,<input type="text" name="custname">'
    await app.call_tool("browser_navigate", {"url": data_uri})
    result = await app.call_tool(
        "browser_type",
        {"selector": 'input[name="custname"]', "text": "Test User", "clear": True},
    )
    assert "Texto digitado" in result[0].text


async def test_select_option(browser_manager):
    data_uri = (
        "data:text/html,"
        '<select name="size">'
        '<option value="small">Small</option>'
        '<option value="medium">Medium</option>'
        "</select>"
    )
    await app.call_tool("browser_navigate", {"url": data_uri})
    result = await app.call_tool(
        "browser_select_option",
        {"selector": 'select[name="size"]', "value": "medium"},
    )
    assert "Opção" in result[0].text
    assert "medium" in result[0].text


async def test_hover(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    result = await app.call_tool("browser_hover", {"selector": "a"})
    assert "Hover" in result[0].text


async def test_press_key(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    result = await app.call_tool("browser_press_key", {"key": "Tab"})
    assert "Tecla" in result[0].text


async def test_upload_file(browser_manager):
    data_uri = 'data:text/html,<input type="file" id="file">'
    await app.call_tool("browser_navigate", {"url": data_uri})
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write("test content")
        path = f.name
    try:
        result = await app.call_tool(
            "browser_upload_file",
            {"selector": "#file", "file_path": path},
        )
        assert "Arquivo" in result[0].text
        assert "enviado" in result[0].text
    finally:
        os.unlink(path)


# =============================================================================
# 3. Conteúdo e JavaScript
# =============================================================================
async def test_get_content(browser_manager):
    # Usa data URI para evitar indisponibilidade de sites externos
    data_uri = "data:text/html,<html><body><h1>Moby Dick</h1><p>Herman Melville</p></body></html>"
    await app.call_tool("browser_navigate", {"url": data_uri})
    result = await app.call_tool("browser_get_content", {})
    text = result[0].text
    assert "Herman Melville" in text or "Moby Dick" in text or "Moby" in text


async def test_get_content_html(browser_manager):
    data_uri = "data:text/html,<html><body><h1>Hello World</h1></body></html>"
    await app.call_tool("browser_navigate", {"url": data_uri})
    result = await app.call_tool("browser_get_content", {"as_html": True})
    assert "<html" in result[0].text or "<body" in result[0].text


async def test_execute_javascript(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    result = await app.call_tool(
        "browser_execute_javascript",
        {"code": "document.title"},
    )
    assert "Example Domain" in result[0].text


async def test_get_attributes(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    result = await app.call_tool(
        "browser_get_attributes",
        {"selector": "a", "attribute": "href"},
    )
    assert "iana.org" in result[0].text


# =============================================================================
# 4. Screenshot
# =============================================================================
async def test_screenshot(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        result = await app.call_tool("browser_screenshot", {"path": path})
        assert "Screenshot salvo em" in result[0].text
        assert os.path.exists(path)
    finally:
        if os.path.exists(path):
            os.unlink(path)


# =============================================================================
# 5. Rede
# =============================================================================
async def test_get_network_log(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    result = await app.call_tool("browser_get_network_log", {})
    logs = json.loads(result[0].text)
    assert isinstance(logs, list)


async def test_export_har(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    with tempfile.NamedTemporaryFile(suffix=".har", delete=False) as f:
        path = f.name
    try:
        result = await app.call_tool("browser_export_har", {"path": path})
        assert "HAR exportado" in result[0].text
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as f:
            har = json.load(f)
        assert "log" in har
    finally:
        if os.path.exists(path):
            os.unlink(path)


# =============================================================================
# 6. Gerenciamento de sessão
# =============================================================================
async def test_manage_session_get_cookies(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    result = await app.call_tool("browser_manage_session", {"action": "get_cookies"})
    cookies = json.loads(result[0].text)
    assert isinstance(cookies, list)


async def test_manage_session_resize(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    result = await app.call_tool(
        "browser_manage_session",
        {"action": "resize_viewport", "width": 800, "height": 600},
    )
    assert "Viewport redimensionado para 800x600" in result[0].text


# =============================================================================
# 7. Aguardar
# =============================================================================
async def test_wait_timeout(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    result = await app.call_tool(
        "browser_wait",
        {"condition": "timeout", "timeout": 500},
    )
    assert "Aguardado 500ms" in result[0].text


async def test_wait_network_idle(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    result = await app.call_tool("browser_wait", {"condition": "network_idle"})
    assert "Network idle atingido" in result[0].text


async def test_wait_element_visible(browser_manager):
    await app.call_tool("browser_navigate", {"url": "https://example.com"})
    result = await app.call_tool(
        "browser_wait",
        {"condition": "element_visible", "selector": "h1"},
    )
    assert "visível" in result[0].text
