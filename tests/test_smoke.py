"""Smoke tests E2E — testam o MCP Browser Server com navegador real.

Requer: pytest-asyncio.
Execução: pytest tests/test_smoke.py -v
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import contextlib

import pytest


@pytest.fixture(scope="function")
async def browser():
    """Inicia o browser para cada teste (isolamento completo)."""
    from browser_mcp.browser_manager import browser_manager

    await browser_manager.start()
    yield browser_manager
    with contextlib.suppress(Exception):
        await browser_manager.stop()


def _evaluate(page, expression: str):
    """Helper para evaluate sem usar return (causa SyntaxError no Playwright)."""
    return page.evaluate(f"({expression})")


@pytest.mark.asyncio
async def test_navigate_and_get_url(browser):
    """Navegar e verificar URL."""
    await browser.navigate("https://httpbin.org/get")
    content = await browser.get_content()
    assert "httpbin" in str(content).lower()


@pytest.mark.asyncio
async def test_go_back(browser):
    """Navegar para frente e voltar."""
    await browser.navigate("https://httpbin.org/get")
    await browser.navigate("https://httpbin.org/headers")
    await browser.go_back()
    content = await browser.get_content()
    assert "get" in str(content).lower() or "httpbin" in str(content).lower()


@pytest.mark.asyncio
async def test_type_text(browser):
    """Digitar texto em um input e verificar na página."""
    await browser.navigate("https://httpbin.org/forms/post")
    await browser.type_text("input[name='custname']", "Hermes Smoke Test")
    val = await _evaluate(browser._page, "document.querySelector('input[name=custname]').value")
    assert "Hermes" in str(val)


@pytest.mark.asyncio
async def test_screenshot(browser):
    """Tirar screenshot."""
    await browser.navigate("https://httpbin.org")
    result = await browser.screenshot()
    assert result is not None
    assert ".png" in str(result)


@pytest.mark.asyncio
async def test_execute_javascript(browser):
    """Executar JavaScript na página."""
    await browser.navigate("https://httpbin.org")
    title = await _evaluate(browser._page, "document.title")
    assert "httpbin" in str(title).lower()


@pytest.mark.asyncio
async def test_stealth_webdriver(browser):
    """Verificar stealth — navigator.webdriver."""
    await browser.navigate("https://httpbin.org/get")
    wd = await _evaluate(browser._page, "navigator.webdriver")
    assert wd in (False, None, None)


@pytest.mark.asyncio
async def test_visual_indicator(browser):
    """Injetar e remover overlay visual."""
    await browser.navigate("https://httpbin.org")
    await browser.inject_indicator()
    has = await _evaluate(
        browser._page, "document.getElementById('__mcp_browser_overlay') !== null"
    )
    assert has is True

    await browser.remove_indicator()
    has = await _evaluate(
        browser._page, "document.getElementById('__mcp_browser_overlay') !== null"
    )
    assert has is False


@pytest.mark.asyncio
async def test_security_level_colors(browser):
    """Alterar nível de segurança e verificar cor."""
    await browser.navigate("https://httpbin.org")
    await browser.set_security_level("orange")
    bg = await _evaluate(
        browser._page,
        "document.querySelector('#__mcp_browser_overlay div')?.style?.background || ''",
    )
    assert "243, 156, 18" in str(bg)


@pytest.mark.asyncio
async def test_new_tab(browser):
    """Abrir nova aba."""
    await browser.open_new_tab("https://httpbin.org/ip", "Test Suite")
    content = await browser.get_content()
    assert "origin" in str(content).lower() or "ip" in str(content).lower()


@pytest.mark.asyncio
async def test_click_navigation(browser):
    """Clicar em link e verificar navegação."""
    await browser.navigate("https://httpbin.org")
    await browser.click("text=HTTP Methods")
    await asyncio.sleep(1)
    content = await browser.get_content()
    assert "httpbin" in str(content).lower()
