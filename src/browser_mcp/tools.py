import json
import sys
import time
from collections.abc import Callable
from typing import Any, cast

from mcp import types

from browser_mcp.agent import BrowserAgent
from browser_mcp.browser_manager import BrowserManager
from browser_mcp.llm_client import LLMClient

# Singletons globais reutilizados pelas ferramentas
browser_manager = BrowserManager()
llm_client = LLMClient()


class ToolRegistry:
    """Registro de ferramentas MCP com decorator @app.tool().

    Acumula metadados (schema JSON, handler) e expõe
    ``get_tools()`` e ``call_tool()`` para integração com ``mcp.server.Server``.
    """

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}

    def tool(
        self,
        name: str | None = None,
        description: str | None = None,
        schema: dict[str, Any] | None = None,
    ) -> Callable[..., Any]:
        """Decorator equivalente a ``@app.tool()`` do FastMCP.

        Registra a função assíncora como ferramenta MCP com seu JSON Schema.
        """
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or func.__name__
            tool_desc = description or (func.__doc__ or "").strip()
            self._tools[tool_name] = {
                "func": func,
                "schema": schema or {"type": "object", "properties": {}, "required": []},
                "description": tool_desc,
            }
            return func
        return decorator

    def get_tools(self) -> list[types.Tool]:
        """Retorna lista de ``types.Tool`` para ``list_tools``."""
        return [
            types.Tool(
                name=name,
                description=meta["description"],
                inputSchema=meta["schema"],
            )
            for name, meta in self._tools.items()
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        """Roteia a chamada para a função registrada."""
        if name not in self._tools:
            raise ValueError(f"Ferramenta desconhecida: {name}")
        func = self._tools[name]["func"]
        return cast(list[types.TextContent], await func(**arguments))


app = ToolRegistry()


def _format_error(error: Exception) -> str:
    """Formata exceção no padrão: ERROR: [tipo] - mensagem - sugestão."""
    error_type = type(error).__name__
    message = str(error)
    suggestion = "Verifique os parâmetros e tente novamente."
    if "Timeout" in error_type:
        suggestion = "Aumente o timeout ou verifique se o elemento está presente."
    elif any(
        k in error_type for k in ("Locator", "Element", "Assertion", "Page")
    ):
        suggestion = "Verifique se o seletor está correto e o elemento está visível."
    elif "NotFound" in error_type or "FileNotFound" in error_type:
        suggestion = "Verifique se o caminho ou arquivo existe."
    elif "NotImplemented" in error_type:
        suggestion = "Este recurso ainda não foi implementado."
    return f"ERROR: [{error_type}] - {message} - {suggestion}"


def _log_call(name: str, start: float) -> None:
    duration = time.time() - start
    print(f"[TOOLS] {name} executado em {duration:.3f}s", file=sys.stderr)


# =============================================================================
# 1. browser_navigate
# =============================================================================
@app.tool(
    name="browser_navigate",
    description="Navega o browser para uma URL específica.",
    schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL completa para navegar (ex: https://example.com)",
            }
        },
        "required": ["url"],
    },
)
async def browser_navigate(url: str) -> list[types.TextContent]:
    """Navega para a URL fornecida."""
    start = time.time()
    try:
        await browser_manager.start()
        result = await browser_manager.navigate(url)
        _log_call("browser_navigate", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_navigate", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 2. browser_connect_to_existing
# =============================================================================
@app.tool(
    name="browser_connect_to_existing",
    description="Conecta ao Chrome do usuário via CDP em vez de iniciar um novo browser.",
    schema={
        "type": "object",
        "properties": {
            "cdp_url": {
                "type": "string",
                "default": "http://localhost:9222",
                "description": "URL do endpoint CDP do Chrome (ex: http://localhost:9222)",
            }
        },
        "required": [],
    },
)
async def browser_connect_to_existing(
    cdp_url: str = "http://localhost:9222"
) -> list[types.TextContent]:
    """Conecta ao Chrome existente via CDP."""
    start = time.time()
    try:
        result = await browser_manager.connect_to_existing(cdp_url)
        _log_call("browser_connect_to_existing", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_connect_to_existing", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 3. browser_connect_to_extension
# =============================================================================
@app.tool(
    name="browser_connect_to_extension",
    description="Conecta ao browser real do usuário via Chrome Extension + WebSocket. Usa o Chrome do usuário (sessão, cookies, extensões).",
    schema={
        "type": "object",
        "properties": {
            "ws_url": {
                "type": "string",
                "default": "ws://localhost:8765",
                "description": "URL do WebSocket server (padrão: ws://localhost:8765)",
            }
        },
        "required": [],
    },
)
async def browser_connect_to_extension(
    ws_url: str = "ws://localhost:8765"
) -> list[types.TextContent]:
    """Conecta ao Chrome real do usuário via extensão."""
    start = time.time()
    try:
        result = await browser_manager.connect_to_extension(ws_url)
        _log_call("browser_connect_to_extension", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_connect_to_extension", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 4. browser_disconnect_extension
# =============================================================================
@app.tool(
    name="browser_disconnect_extension",
    description="Desconecta do modo Chrome Extension e volta ao Playwright padrão.",
    schema={"type": "object", "properties": {}, "required": []},
)
async def browser_disconnect_extension() -> list[types.TextContent]:
    """Desconecta do modo extensão."""
    start = time.time()
    try:
        result = await browser_manager.disconnect_extension()
        _log_call("browser_disconnect_extension", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_disconnect_extension", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 5. browser_go_back
# =============================================================================
@app.tool(
    name="browser_go_back",
    description="Navega para a página anterior no histórico do browser.",
    schema={"type": "object", "properties": {}, "required": []},
)
async def browser_go_back() -> list[types.TextContent]:
    """Volta uma página no histórico."""
    start = time.time()
    try:
        result = await browser_manager.go_back()
        _log_call("browser_go_back", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_go_back", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 4. browser_go_forward
# =============================================================================
@app.tool(
    name="browser_go_forward",
    description="Navega para a página seguinte no histórico do browser.",
    schema={"type": "object", "properties": {}, "required": []},
)
async def browser_go_forward() -> list[types.TextContent]:
    """Avança uma página no histórico."""
    start = time.time()
    try:
        result = await browser_manager.go_forward()
        _log_call("browser_go_forward", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_go_forward", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 5. browser_reload
# =============================================================================
@app.tool(
    name="browser_reload",
    description="Recarrega a página atual.",
    schema={"type": "object", "properties": {}, "required": []},
)
async def browser_reload() -> list[types.TextContent]:
    """Recarrega a página atual."""
    start = time.time()
    try:
        result = await browser_manager.reload()
        _log_call("browser_reload", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_reload", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 6. browser_click
# =============================================================================
@app.tool(
    name="browser_click",
    description=(
        "Clica em um elemento na página. "
        "Pode usar seletor CSS, @e ref (ex: @e3), texto visível, ou coordenadas. "
        "Prefira @e ref quando disponível no accessibility tree — é mais estável. "
        "Se o seletor falhar, tenta fallback automático por texto visível."
    ),
    schema={
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": (
                    "Seletor do elemento: CSS, @e ref (ex: @e3), texto visível, "
                    "ou coordenadas 'x,y'. Prefira @e ref quando disponível."
                ),
            },
            "by": {
                "type": "string",
                "enum": ["css", "xpath", "text", "coordinates", "ref"],
                "default": "css",
                "description": (
                    "Método de localização do elemento. "
                    "Use 'ref' para @e refs do accessibility tree."
                ),
            },
        },
        "required": ["selector"],
    },
)
async def browser_click(selector: str, by: str = "css") -> list[types.TextContent]:
    """Clica em um elemento com suporte a @e refs e fallback."""
    start = time.time()
    try:
        result = await browser_manager.click(selector, by)
    except Exception as e:
        _log_call("browser_click", start)
        return [types.TextContent(type="text", text=_format_error(e))]
    _log_call("browser_click", start)
    return [types.TextContent(type="text", text=result)]


# =============================================================================
# 7. browser_type
# =============================================================================
@app.tool(
    name="browser_type",
    description=(
        "Digita texto em um campo de input. "
        "Use @e ref (ex: @e3) ou seletor CSS. "
        "Se usar @e ref, o campo será localizado via accessibility tree."
    ),
    schema={
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": (
                    "Seletor CSS do campo de input, ou @e ref (ex: @e3) "
                    "do accessibility tree."
                ),
            },
            "text": {
                "type": "string",
                "description": "Texto a ser digitado",
            },
            "clear": {
                "type": "boolean",
                "default": True,
                "description": "Se True, limpa o campo antes de digitar",
            },
            "by": {
                "type": "string",
                "enum": ["css", "ref"],
                "default": "css",
                "description": (
                    "Método de localização. Use 'ref' para @e refs do accessibility tree."
                ),
            },
        },
        "required": ["selector", "text"],
    },
)
async def browser_type(
    selector: str, text: str, clear: bool = True, by: str = "css"
) -> list[types.TextContent]:
    """Digita texto em um campo com suporte a @e refs."""
    start = time.time()
    try:
        result = await browser_manager.type_text(selector, text, clear, by)
    except Exception as e:
        _log_call("browser_type", start)
        return [types.TextContent(type="text", text=_format_error(e))]
    _log_call("browser_type", start)
    return [types.TextContent(type="text", text=result)]


# =============================================================================
# 8. browser_select_option
# =============================================================================
@app.tool(
    name="browser_select_option",
    description="Seleciona uma opção em um dropdown (elemento <select>).",
    schema={
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "Seletor CSS do <select>",
            },
            "value": {
                "type": "string",
                "description": "Valor da opção a ser selecionada",
            },
        },
        "required": ["selector", "value"],
    },
)
async def browser_select_option(
    selector: str, value: str
) -> list[types.TextContent]:
    """Seleciona uma opção."""
    start = time.time()
    try:
        result = await browser_manager.select_option(selector, value)
        _log_call("browser_select_option", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_select_option", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 9. browser_hover
# =============================================================================
@app.tool(
    name="browser_hover",
    description=(
        "Move o mouse sobre um elemento (hover). "
        "Use @e ref (ex: @e3) ou seletor CSS. "
        "Se usar @e ref, o elemento será localizado via accessibility tree."
    ),
    schema={
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": (
                    "Seletor CSS do elemento ou @e ref (ex: @e3) do accessibility tree."
                ),
            },
            "by": {
                "type": "string",
                "enum": ["css", "ref"],
                "default": "css",
                "description": (
                    "Método de localização. Use 'ref' para @e refs do accessibility tree."
                ),
            },
        },
        "required": ["selector"],
    },
)
async def browser_hover(selector: str, by: str = "css") -> list[types.TextContent]:
    """Hover em um elemento com suporte a @e refs."""
    start = time.time()
    try:
        result = await browser_manager.hover(selector, by)
    except Exception as e:
        _log_call("browser_hover", start)
        return [types.TextContent(type="text", text=_format_error(e))]
    _log_call("browser_hover", start)
    return [types.TextContent(type="text", text=result)]


# =============================================================================
# 10. browser_accessibility_tree
# =============================================================================
@app.tool(
    name="browser_accessibility_tree",
    description=(
        "Retorna o snapshot de acessibilidade da página atual. "
        "Inclui @e refs para elementos interativos, roles e nomes acessíveis. "
        "Ideal para descobrir refs estáveis antes de clicar/digitar."
    ),
    schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def browser_accessibility_tree() -> list[types.TextContent]:
    """Obtém o accessibility tree da página."""
    start = time.time()
    try:
        await browser_manager.start()
        if hasattr(browser_manager, "get_accessibility_tree"):
            tree = await browser_manager.get_accessibility_tree()
        else:
            page = browser_manager._page
            tree = await page.accessibility.snapshot()  # type: ignore[union-attr]
        _log_call("browser_accessibility_tree", start)
        return [
            types.TextContent(
                type="text",
                text=json.dumps(tree, ensure_ascii=False, indent=2, default=str),
            )
        ]
    except Exception as e:
        _log_call("browser_accessibility_tree", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 11. browser_press_key
# =============================================================================
@app.tool(
    name="browser_press_key",
    description="Pressiona uma tecla (Enter, Tab, Escape, etc.).",
    schema={
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "Nome da tecla (Enter, Tab, Escape, ArrowDown, etc.)",
            },
            "selector": {
                "type": "string",
                "description": "Seletor CSS opcional do elemento alvo",
            },
        },
        "required": ["key"],
    },
)
async def browser_press_key(
    key: str, selector: str | None = None
) -> list[types.TextContent]:
    """Pressiona uma tecla."""
    start = time.time()
    try:
        result = await browser_manager.press_key(key, selector)
        _log_call("browser_press_key", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_press_key", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 12. browser_upload_file
# =============================================================================
@app.tool(
    name="browser_upload_file",
    description="Faz upload de um arquivo para um input file.",
    schema={
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "Seletor CSS do input file",
            },
            "file_path": {
                "type": "string",
                "description": "Caminho absoluto do arquivo no sistema",
            },
        },
        "required": ["selector", "file_path"],
    },
)
async def browser_upload_file(
    selector: str, file_path: str
) -> list[types.TextContent]:
    """Faz upload de arquivo."""
    start = time.time()
    try:
        result = await browser_manager.upload_file(selector, file_path)
        _log_call("browser_upload_file", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_upload_file", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 13. browser_get_content
# =============================================================================
@app.tool(
    name="browser_get_content",
    description="Obtém o conteúdo de um elemento ou da página inteira.",
    schema={
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "Seletor CSS opcional. Se omitido, retorna conteúdo da página.",
            },
            "as_html": {
                "type": "boolean",
                "default": False,
                "description": "Se True, retorna HTML ao invés de texto puro",
            },
        },
        "required": [],
    },
)
async def browser_get_content(
    selector: str | None = None, as_html: bool = False
) -> list[types.TextContent]:
    """Obtém conteúdo."""
    start = time.time()
    try:
        result = await browser_manager.get_content(selector, as_html)
        _log_call("browser_get_content", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_get_content", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 14. browser_execute_javascript
# =============================================================================
@app.tool(
    name="browser_execute_javascript",
    description=(
        "Executa código JavaScript na página e retorna o resultado. "
        "⚠️ NÃO use para clicar em links/navegação — use browser_click. "
        "Eventos programáticos (element.click()) têm isTrusted=false e são "
        "bloqueados por sites como Google News. Para cliques, use browser_click "
        "que dispara eventos reais via CDP."
    ),
    schema={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Código JavaScript a ser executado",
            },
        },
        "required": ["code"],
    },
)
async def browser_execute_javascript(code: str) -> list[types.TextContent]:
    """Executa JS."""
    start = time.time()
    try:
        result = await browser_manager.execute_javascript(code)
        _log_call("browser_execute_javascript", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_execute_javascript", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 15. browser_get_attributes
# =============================================================================
@app.tool(
    name="browser_get_attributes",
    description="Obtém atributos de um elemento HTML.",
    schema={
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "Seletor CSS do elemento",
            },
            "attribute": {
                "type": "string",
                "description": "Nome do atributo específico. Se omitido, retorna todos.",
            },
        },
        "required": ["selector"],
    },
)
async def browser_get_attributes(
    selector: str, attribute: str | None = None
) -> list[types.TextContent]:
    """Obtém atributos."""
    start = time.time()
    try:
        result = await browser_manager.get_attributes(selector, attribute)
        _log_call("browser_get_attributes", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_get_attributes", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 16. browser_screenshot
# =============================================================================
@app.tool(
    name="browser_screenshot",
    description="Captura um screenshot da página.",
    schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Caminho opcional para salvar o screenshot. Se omitido, gera arquivo temporário.",
            },
            "full_page": {
                "type": "boolean",
                "default": False,
                "description": "Se True, captura a página inteira",
            },
        },
        "required": [],
    },
)
async def browser_screenshot(
    path: str | None = None, full_page: bool = False
) -> list[types.TextContent]:
    """Tira screenshot."""
    start = time.time()
    try:
        result = await browser_manager.screenshot(path, full_page)
        _log_call("browser_screenshot", start)
        return [types.TextContent(type="text", text=f"Screenshot salvo em: {result}")]
    except Exception as e:
        _log_call("browser_screenshot", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 17. browser_network_start
# =============================================================================
@app.tool(
    name="browser_network_start",
    description="Inicia a captura de tráfego de rede em tempo real.",
    schema={"type": "object", "properties": {}, "required": []},
)
async def browser_network_start() -> list[types.TextContent]:
    """Inicia network monitoring."""
    start = time.time()
    try:
        await browser_manager.start()
        result = await browser_manager.start_network_monitoring()
        _log_call("browser_network_start", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_network_start", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 18. browser_network_stop
# =============================================================================
@app.tool(
    name="browser_network_stop",
    description="Para a captura de tráfego de rede.",
    schema={"type": "object", "properties": {}, "required": []},
)
async def browser_network_stop() -> list[types.TextContent]:
    """Para network monitoring."""
    start = time.time()
    try:
        result = await browser_manager.stop_network_monitoring()
        _log_call("browser_network_stop", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_network_stop", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 19. browser_network_list
# =============================================================================
@app.tool(
    name="browser_network_list",
    description="Lista as requisições de rede capturadas.",
    schema={
        "type": "object",
        "properties": {
            "filter_url": {
                "type": "string",
                "description": "Filtrar por substring na URL",
            },
            "filter_method": {
                "type": "string",
                "description": "Filtrar por método HTTP (GET, POST, etc.)",
            },
        },
        "required": [],
    },
)
async def browser_network_list(
    filter_url: str | None = None, filter_method: str | None = None
) -> list[types.TextContent]:
    """Lista requisições capturadas."""
    start = time.time()
    try:
        result = await browser_manager.list_network_requests(filter_url, filter_method)
        _log_call("browser_network_list", start)
        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2, default=str),
            )
        ]
    except Exception as e:
        _log_call("browser_network_list", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 20. browser_network_clear
# =============================================================================
@app.tool(
    name="browser_network_clear",
    description="Limpa o log de requisições de rede.",
    schema={"type": "object", "properties": {}, "required": []},
)
async def browser_network_clear() -> list[types.TextContent]:
    """Limpa log de rede."""
    start = time.time()
    try:
        result = await browser_manager.clear_network_log()
        _log_call("browser_network_clear", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_network_clear", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 21. browser_get_network_log
# =============================================================================
@app.tool(
    name="browser_get_network_log",
    description="Obtém o log de requisições de rede capturadas (detalhado).",
    schema={
        "type": "object",
        "properties": {
            "filter_url": {
                "type": "string",
                "description": "Filtrar por substring na URL",
            },
            "filter_method": {
                "type": "string",
                "description": "Filtrar por método HTTP (GET, POST, etc.)",
            },
        },
        "required": [],
    },
)
async def browser_get_network_log(
    filter_url: str | None = None, filter_method: str | None = None
) -> list[types.TextContent]:
    """Obtém log de rede detalhado."""
    start = time.time()
    try:
        result = await browser_manager.get_network_log(filter_url, filter_method)
        _log_call("browser_get_network_log", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_get_network_log", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 22. browser_export_har
# =============================================================================
@app.tool(
    name="browser_export_har",
    description="Exporta o log de rede no formato HAR.",
    schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Caminho do arquivo HAR a ser exportado",
            },
        },
        "required": ["path"],
    },
)
async def browser_export_har(path: str) -> list[types.TextContent]:
    """Exporta HAR."""
    start = time.time()
    try:
        result = await browser_manager.export_har(path)
        _log_call("browser_export_har", start)
        return [types.TextContent(type="text", text=f"HAR exportado para: {result}")]
    except Exception as e:
        _log_call("browser_export_har", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 23. browser_manage_session
# =============================================================================
@app.tool(
    name="browser_manage_session",
    description="Gerencia a sessão do browser: cookies, abas, viewport, gravação.",
    schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "get_cookies",
                    "set_cookies",
                    "new_tab",
                    "list_tabs",
                    "close_tab",
                    "resize_viewport",
                    "start_recording",
                    "stop_recording",
                ],
                "description": "Ação a executar",
            },
        },
        "required": ["action"],
    },
)
async def browser_manage_session(
    action: str, **kwargs: Any
) -> list[types.TextContent]:
    """Gerencia sessão."""
    start = time.time()
    try:
        result = await browser_manager.manage_session(action, **kwargs)
        _log_call("browser_manage_session", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_manage_session", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 24. browser_wait
# =============================================================================
@app.tool(
    name="browser_wait",
    description="Aguarda uma condição na página.",
    schema={
        "type": "object",
        "properties": {
            "condition": {
                "type": "string",
                "enum": ["element_visible", "element_hidden", "network_idle", "timeout"],
                "description": "Condição a aguardar",
            },
            "selector": {
                "type": "string",
                "description": "Seletor CSS necessário para element_visible / element_hidden",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout em milissegundos (padrão: 30000)",
            },
        },
        "required": ["condition"],
    },
)
async def browser_wait(
    condition: str,
    selector: str | None = None,
    timeout: int | None = None,
) -> list[types.TextContent]:
    """Aguarda condição."""
    start = time.time()
    try:
        result = await browser_manager.wait(condition, selector, timeout)
        _log_call("browser_wait", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_wait", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 24b. browser_get_url
# =============================================================================
@app.tool(
    name="browser_get_url",
    description="Obtém a URL atual da página em navegação.",
    schema={"type": "object", "properties": {}, "required": []},
)
async def browser_get_url() -> list[types.TextContent]:
    """Obtém URL atual da página."""
    start = time.time()
    try:
        await browser_manager.start()
        result = await browser_manager.get_url()
        _log_call("browser_get_url", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_get_url", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 24c. browser_get_title
# =============================================================================
@app.tool(
    name="browser_get_title",
    description="Obtém o título da página atual.",
    schema={"type": "object", "properties": {}, "required": []},
)
async def browser_get_title() -> list[types.TextContent]:
    """Obtém título da página atual."""
    start = time.time()
    try:
        await browser_manager.start()
        result = await browser_manager.get_title()
        _log_call("browser_get_title", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_get_title", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 25. browser_agent_task
# =============================================================================
@app.tool(
    name="browser_agent_task",
    description="Executa uma tarefa complexa de browser usando um agente autônomo com LLM.",
    schema={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Descrição da tarefa a ser executada",
            },
            "max_iterations": {
                "type": "integer",
                "default": 50,
                "description": "Número máximo de iterações do agente",
            },
            "take_screenshots": {
                "type": "boolean",
                "default": True,
                "description": "Se True, o agente tira screenshots durante a execução",
            },
            "capture_network": {
                "type": "boolean",
                "default": True,
                "description": "Se True, captura log de rede",
            },
            "output_dir": {
                "type": "string",
                "default": "./agent_output",
                "description": "Diretório para salvar relatórios e screenshots",
            },
        },
        "required": ["task"],
    },
)
async def browser_agent_task(
    task: str,
    max_iterations: int = 50,
    take_screenshots: bool = True,
    capture_network: bool = True,
    output_dir: str = "./agent_output",
) -> list[types.TextContent]:
    """Executa tarefa via agente autônomo."""
    start = time.time()
    try:
        await browser_manager.start()
        await llm_client.initialize()  # type: ignore[no-untyped-call]
        agent = BrowserAgent(
            browser_manager,
            llm_client,
            max_iterations=max_iterations,
            screenshot_on_action=take_screenshots,
            output_dir=output_dir,
        )
        result = await agent.execute_task(task)
        from pathlib import Path

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        report_path = out / "report.md"
        report_path.write_text(result.get("report", ""), encoding="utf-8")
        _log_call("browser_agent_task", start)

        summary = f"""# Agent Task Report

**Status**: {'✅ Success' if result.get('success') else '❌ Incomplete'}
**Actions Taken**: {result.get('action_count', 0)}
**Screenshots**: {len(result.get('screenshots', []))}
**Errors**: {len(result.get('errors', []))}

{result.get('report', 'No report generated.')}
"""
        return [
            types.TextContent(
                type="text",
                text=f"Relatório salvo em: {report_path}\n\n---\n\n{summary[:3000]}...",
            )
        ]
    except Exception as e:
        _log_call("browser_agent_task", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 26. browser_extension_get_network_log
# =============================================================================
@app.tool(
    name="browser_extension_get_network_log",
    description="Obtém o log de rede capturado pela extensão Chrome (XHR/fetch). "
                "Requer modo extension ativo (browser_connect_to_extension).",
    schema={
        "type": "object",
        "properties": {
            "filter_url": {
                "type": "string",
                "description": "Filtrar por substring na URL",
            },
            "filter_method": {
                "type": "string",
                "description": "Filtrar por método HTTP (GET, POST, etc.)",
            },
        },
        "required": [],
    },
)
async def browser_extension_get_network_log(
    filter_url: str | None = None, filter_method: str | None = None
) -> list[types.TextContent]:
    """Obtém log de rede da extensão."""
    start = time.time()
    try:
        result = await browser_manager.extension_get_network_log(filter_url, filter_method)
        _log_call("browser_extension_get_network_log", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_extension_get_network_log", start)
        return [types.TextContent(type="text", text=_format_error(e))]


# =============================================================================
# 27. browser_extension_get_dom_snapshot
# =============================================================================
@app.tool(
    name="browser_extension_get_dom_snapshot",
    description="Obtém snapshot do DOM atual via extensão Chrome. "
                "Requer modo extension ativo (browser_connect_to_extension).",
    schema={"type": "object", "properties": {}, "required": []},
)
async def browser_extension_get_dom_snapshot() -> list[types.TextContent]:
    """Obtém snapshot do DOM da extensão."""
    start = time.time()
    try:
        result = await browser_manager.extension_get_dom_snapshot()
        _log_call("browser_extension_get_dom_snapshot", start)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        _log_call("browser_extension_get_dom_snapshot", start)
        return [types.TextContent(type="text", text=_format_error(e))]


@app.tool(
    name="browser_get_console_errors",
    description="Retorna erros e warnings do console JavaScript capturados pela extensao Chrome. Use para auditar erros GraphQL, React, e outros erros de runtime na pagina.",
    schema={
        "type": "object",
        "properties": {
            "level": {"type": "string", "description": "Filtrar por nivel: 'error', 'warn', ou 'log'"},
            "filter_text": {"type": "string", "description": "Filtrar por substring na mensagem (ex: 'GraphQL', 'Cannot query')"},
            "limit": {"type": "integer", "description": "Numero maximo de entradas (mais recentes)", "default": 50},
        },
    },
)
async def browser_get_console_errors(
    level: str | None = None,
    filter_text: str | None = None,
    limit: int = 50,
) -> list[types.TextContent]:
    start = time.time()
    try:
        result = await browser_manager.extension_get_console_errors(level, filter_text, limit)
        _log_call("browser_get_console_errors", start)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
    except Exception as e:
        _log_call("browser_get_console_errors", start)
        return [types.TextContent(type="text", text=_format_error(e))]


@app.tool(
    name="browser_new_tab",
    description="Abre uma nova aba no navegador e opcionalmente agrupa com um titulo de sessao",
    schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL para abrir na nova aba"},
            "group_title": {"type": "string", "description": "Titulo do grupo de abas (ex: 'Sessao MCP')", "default": "MCP Browser"},
        },
        "required": ["url"],
    },
)
async def browser_new_tab(url: str, group_title: str = "") -> list[types.TextContent]:
    start = time.time()
    try:
        result = await browser_manager.open_new_tab(url, group_title)
        _log_call("browser_new_tab", start)
        return [types.TextContent(type="text", text=result)]
    except Exception:
        _log_call("browser_new_tab", start)
        raise


# ────────────────────────────────────────────────
# Indicadores Visuais
# ────────────────────────────────────────────────

@app.tool(
    name="browser_inject_indicator",
    description="Injeta overlay visual pulsante na pagina indicando que o agente esta controlando o navegador",
)
async def browser_inject_indicator() -> list[types.TextContent]:
    start = time.time()
    try:
        result = await browser_manager.inject_indicator()
        _log_call("browser_inject_indicator", start)
        return [types.TextContent(type="text", text=result)]
    except Exception:
        _log_call("browser_inject_indicator", start)
        raise


@app.tool(
    name="browser_remove_indicator",
    description="Remove o overlay visual de automacao da pagina",
)
async def browser_remove_indicator() -> list[types.TextContent]:
    start = time.time()
    try:
        result = await browser_manager.remove_indicator()
        _log_call("browser_remove_indicator", start)
        return [types.TextContent(type="text", text=result)]
    except Exception:
        _log_call("browser_remove_indicator", start)
        raise


@app.tool(
    name="browser_highlight_element",
    description="Destaca visualmente um elemento na pagina com borda azul temporaria",
)
async def browser_highlight_element(selector: str) -> list[types.TextContent]:
    start = time.time()
    try:
        result = await browser_manager.highlight_element(selector)
        _log_call("browser_highlight_element", start)
        return [types.TextContent(type="text", text=result)]
    except Exception:
        _log_call("browser_highlight_element", start)
        raise


@app.tool(
    name="browser_set_security_level",
    description="Altera a cor do overlay visual por nivel de seguranca. Cores: blue, orange, red, green",
)
async def browser_set_security_level(level: str = "blue") -> list[types.TextContent]:
    start = time.time()
    try:
        result = await browser_manager.set_security_level(level)
        _log_call("browser_set_security_level", start)
        return [types.TextContent(type="text", text=result)]
    except Exception:
        _log_call("browser_set_security_level", start)
        raise
