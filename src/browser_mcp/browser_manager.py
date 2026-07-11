"""Gerenciador de browser Playwright para MCP — singleton async consolidado."""

import asyncio
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional, cast
from urllib.parse import unquote, urlparse

from playwright.async_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    async_playwright,
)

from browser_mcp.extension_bridge import extension_bridge
from browser_mcp.network import NetworkInterceptor
from browser_mcp.visual_indicator import (
    ACTIVE_TAB_GROUP_TITLE,
    get_click_ripple_js,
    get_highlight_element_js,
    get_overlay_js,
    get_remove_overlay_js,
    get_status_overlay_js,
)

# ────────────────────────────────────────────────
# Configuração via env vars
# ────────────────────────────────────────────────
_HEADLESS = os.getenv("BROWSER_HEADLESS", "true").lower() in ("1", "true", "yes", "on")
_VIEWPORT_W = int(os.getenv("BROWSER_VIEWPORT_WIDTH", "1280"))
_VIEWPORT_H = int(os.getenv("BROWSER_VIEWPORT_HEIGHT", "720"))
_TIMEOUT = int(os.getenv("BROWSER_TIMEOUT", "30000"))
_EXTENSION_WS_URL = os.getenv("EXTENSION_WS_URL", "ws://localhost:8765")
_ENABLE_VISUAL_INDICATOR = os.getenv("ENABLE_VISUAL_INDICATOR", "true").lower() in ("1", "true", "yes", "on")
_STEALTH_MODE = os.getenv("STEALTH_MODE", "true").lower() in ("1", "true", "yes", "on")

# Pool de User Agents reais (Chrome macOS)
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]

_STEALTH_SCRIPT = """
// Remove webdriver — múltiplas camadas de proteção
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => undefined });

// PluginArray realista (não array comum)
const makePluginArray = () => {
    const plugins = [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format', length: 1 },
        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '', length: 1 },
        { name: 'Native Client', filename: 'internal-nacl-plugin', description: '', length: 2 },
    ];
    plugins.item = (i) => plugins[i] || null;
    plugins.namedItem = (name) => plugins.find(p => p.name === name) || null;
    plugins.refresh = () => {};
    Object.setPrototypeOf(plugins, PluginArray.prototype);
    return plugins;
};
Object.defineProperty(navigator, 'plugins', { get: () => makePluginArray() });

// Languages
Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });

// Chrome runtime
window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {} };

// Permissions
const origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (params) => (
    params.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        origQuery(params)
);

// Hardware (M4 MacBook Pro)
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 });
"""


class BrowserManager:
    """Singleton async que gerencia uma instância do Playwright."""

    _instance: Optional["BrowserManager"] = None
    _lock: Any = asyncio.Lock()

    # ── Instance attributes (declared for mypy strict) ──
    _initialized: bool
    _mode: str
    _ref_counter: int
    _ref_map: dict[str, dict[str, Any]]
    _playwright: Optional[Playwright]
    _browser: Optional[Browser]
    _context: Optional[BrowserContext]
    _page: Optional[Page]
    _network_interceptor: Optional[NetworkInterceptor]

    def __new__(cls) -> "BrowserManager":
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._initialized = False
            instance._mode = "playwright"  # "playwright" | "extension" | "cdp"
            instance._ref_counter = 0
            instance._ref_map = {}
            instance._playwright = None
            instance._browser = None
            instance._context = None
            instance._page = None
            instance._network_interceptor = None
            cls._instance = instance
        return cls._instance

    # ═══════════════════════════════════════════════════════════
    # Ciclo de vida
    # ═══════════════════════════════════════════════════════════

    async def start(self) -> None:
        if self._mode == "extension":
            return
        if self._initialized:
            return
        async with self._lock:
            if self._initialized or self._mode == "extension":
                return
            self._playwright = await async_playwright().start()
            launch_args = ["--no-sandbox", "--disable-dev-shm-usage"]
            if _STEALTH_MODE:
                launch_args += [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-infobars",
                    "--use-gl=angle",
                    "--use-angle=swiftshader",
                ]
            self._browser = await self._playwright.chromium.launch(
                headless=_HEADLESS,
                args=launch_args,
            )
            context_opts: dict[str, Any] = {
                "viewport": {"width": _VIEWPORT_W, "height": _VIEWPORT_H},
            }
            if _STEALTH_MODE:
                import random
                context_opts["user_agent"] = random.choice(_USER_AGENTS)
                context_opts["bypass_csp"] = True
            self._context = await self._browser.new_context(**context_opts)
            
            # Criar página primeiro
            self._page = await self._context.new_page()
            
            # Stealth via CDP (executa antes de qualquer script da página nas próximas navegações)
            if _STEALTH_MODE:
                cdp = await self._context.new_cdp_session(self._page)
                await cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": _STEALTH_SCRIPT})

            # NetworkInterceptor
            self._network_interceptor = NetworkInterceptor()
            self._network_interceptor.attach(self._page)

            self._initialized = True

    async def stop(self) -> None:
        async with self._lock:
            if not self._initialized:
                return
            try:
                if self._context:
                    await self._context.close()
                if self._browser:
                    await self._browser.close()
                if self._playwright:
                    await self._playwright.stop()
            except Exception as e:
                print(f"Erro ao parar browser: {e}", file=sys.stderr)
            finally:
                self._initialized = False
                self._page = None
                self._context = None
                self._browser = None
                self._playwright = None
                self._network_interceptor = None
                self._mode = "playwright"

    def _ensure_started(self) -> None:
        if self._mode == "extension":
            return
        if not self._initialized or self._page is None:
            raise RuntimeError("Browser não iniciado. Chame start() primeiro.")

    def _in_extension_mode(self) -> bool:
        return self._mode == "extension"

    async def _extension_dispatch(self, tool: str, params: dict[str, Any]) -> str:
        """Delega comando para a extensão quando em modo extension."""
        result = await extension_bridge.execute_command(tool, params)
        return json.dumps(result, ensure_ascii=False, default=str)

    # ═══════════════════════════════════════════════════════════
    # Modos de conexão
    # ═══════════════════════════════════════════════════════════

    async def connect_to_existing(self, cdp_url: str = "http://localhost:9222") -> str:
        """Conecta a uma instância do Chrome existente via CDP."""
        async with self._lock:
            if self._initialized:
                try:
                    if self._context:
                        await self._context.close()
                    if self._browser:
                        await self._browser.close()
                except Exception as e:
                    print(f"Erro ao fechar browser anterior: {e}", file=sys.stderr)
                finally:
                    self._initialized = False

            try:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
                contexts = self._browser.contexts
                if contexts:
                    self._context = contexts[0]
                else:
                    self._context = await self._browser.new_context(
                        viewport={"width": _VIEWPORT_W, "height": _VIEWPORT_H},
                    )
                pages = self._context.pages
                if pages:
                    self._page = pages[0]
                else:
                    self._page = await self._context.new_page()

                # NetworkInterceptor
                self._network_interceptor = NetworkInterceptor()
                self._network_interceptor.attach(self._page)

                self._mode = "cdp"
                self._initialized = True
                return f"Conectado ao Chrome em {cdp_url}"
            except Exception as e:
                print(f"Erro ao conectar via CDP: {e}", file=sys.stderr)
                raise RuntimeError(f"Falha ao conectar via CDP: {e}") from e

    async def connect_to_extension(self, ws_url: str = _EXTENSION_WS_URL) -> str:
        """Conecta ao browser real do usuário via Chrome Extension + WebSocket."""
        async with self._lock:
            if self._mode == "extension":
                return f"Já em modo extension ({ws_url})"

            # Fechar Playwright se estiver rodando
            if self._initialized:
                try:
                    if self._context:
                        await self._context.close()
                    if self._browser:
                        await self._browser.close()
                    if self._playwright:
                        await self._playwright.stop()
                except Exception as e:
                    print(f"Erro ao fechar browser anterior: {e}", file=sys.stderr)
                finally:
                    self._initialized = False
                    self._page = None
                    self._context = None
                    self._browser = None
                    self._playwright = None
                    self._network_interceptor = None

            # Inicializa o bridge (que inicia o WebSocket server singleton se necessário)
            await extension_bridge.attach()

            self._mode = "extension"
            self._initialized = True
            return (
                f"Modo extension ativado. WebSocket em {ws_url}. "
                f"Extensão conectada: {extension_bridge.is_connected()}"
            )

    async def disconnect_extension(self) -> str:
        """Desconecta do modo extension e retorna ao modo Playwright padrão."""
        async with self._lock:
            if self._mode != "extension":
                return "Não está em modo extension"
            self._mode = "playwright"
            self._initialized = False
            await extension_bridge.detach()
            return "Modo extension desativado. Use browser_start para iniciar Playwright."

    async def get_by_text(self, text: str) -> str:
        """Usa page.get_by_text(text).first e retorna resultado descritivo."""
        self._ensure_started()
        assert self._page is not None
        locator = self._page.get_by_text(text).first
        count = await locator.count()
        if count == 0:
            return f"Nenhum elemento encontrado com texto: {text}"
        tag = await locator.evaluate("el => el.tagName.toLowerCase()")
        return f"Elemento encontrado: <{tag}> com texto '{text}'"

    # ═══════════════════════════════════════════════════════════
    # Accessibility tree e @e refs
    # ═══════════════════════════════════════════════════════════

    async def get_accessibility_tree(self) -> dict[str, Any]:
        """Retorna o accessibility tree da página com @e refs."""
        if self._in_extension_mode():
            # Fallback: usa DOM snapshot da extensão para construir árvore simples
            try:
                snapshot = await extension_bridge.get_dom_snapshot()
                elements = snapshot.get("elements", [])
                self._ref_counter = 0
                self._ref_map = {}
                enriched = []
                for el in elements:
                    self._ref_counter += 1
                    ref = f"@e{self._ref_counter}"
                    role = el.get("tag", "")
                    name = el.get("text", "") or el.get("name", "")
                    enriched.append({
                        "ref": ref,
                        "role": role,
                        "name": name,
                    })
                    self._ref_map[ref] = {
                        "role": role,
                        "name": name,
                        "selector": el.get("selector", ""),
                    }
                return {"tree": enriched, "ref_map": self._ref_map}
            except Exception as e:
                print(f"Erro ao obter accessibility tree (modo extension): {e}", file=sys.stderr)
                return {"tree": [], "ref_map": {}}

        self._ensure_started()
        assert self._page is not None
        try:
            # Playwright Python não tem page.accessibility — usar CDP
            cdp = await self._page.context.new_cdp_session(self._page)
            result = await cdp.send("Accessibility.getFullAXTree")
            nodes = result.get("nodes", [])
            self._ref_counter = 0
            self._ref_map = {}
            enriched = []
            for node in nodes:
                self._ref_counter += 1
                ref = f"@e{self._ref_counter}"
                role = node.get("role", {}).get("value", "") if isinstance(node.get("role"), dict) else node.get("role", "")
                name = node.get("name", {}).get("value", "") if isinstance(node.get("name"), dict) else node.get("name", "")
                enriched.append({
                    "ref": ref,
                    "role": role,
                    "name": name,
                    "nodeId": node.get("nodeId"),
                    "backendDOMNodeId": node.get("backendDOMNodeId"),
                })
                self._ref_map[ref] = {
                    "role": role,
                    "name": name,
                    "backendDOMNodeId": node.get("backendDOMNodeId"),
                }
            return {"tree": enriched, "ref_map": self._ref_map}
        except Exception as e:
            print(f"Erro ao obter accessibility tree: {e}", file=sys.stderr)
            return {"tree": [], "ref_map": {}}

    async def get_page(self) -> Page:
        """Retorna a página atual do Playwright."""
        self._ensure_started()
        assert self._page is not None
        return self._page

    # ═══════════════════════════════════════════════════════════
    # Network monitoring
    # ═══════════════════════════════════════════════════════════

    async def start_network_monitoring(self) -> str:
        """Ativa o NetworkInterceptor para capturar todos os requests em tempo real."""
        if self._in_extension_mode():
            extension_bridge.clear_network_log()
            return "Network monitoring iniciado (modo extension)"
        self._ensure_started()
        assert self._page is not None
        if self._network_interceptor is None:
            return "ERROR: NetworkInterceptor não está disponível."
        self._network_interceptor.start_recording()
        info = self._network_interceptor.get_recording_info()
        return f"Network monitoring iniciado em {info.get('started_at')}"

    async def stop_network_monitoring(self) -> str:
        """Desativa a captura de requests de rede."""
        if self._in_extension_mode():
            events = await extension_bridge.get_network_log()
            return f"Network monitoring parado (modo extension). Total: {len(events)}"
        self._ensure_started()
        assert self._page is not None
        if self._network_interceptor is None:
            return "ERROR: NetworkInterceptor não está disponível."
        self._network_interceptor.stop_recording()
        info = self._network_interceptor.get_recording_info()
        return f"Network monitoring parado. Total capturado: {info.get('total_captured', 0)}"

    async def list_network_requests(
        self,
        filter_url: str | None = None,
        filter_method: str | None = None,
    ) -> dict[str, Any]:
        """Retorna lista de requests capturados, com filtros opcionais."""
        if self._in_extension_mode():
            log_data = await extension_bridge.get_network_log(filter_url, filter_method)
            events = log_data.get("requests", [])
            return {
                "recording": True,
                "recording_start": None,
                "recording_end": None,
                "total_captured": log_data.get("total_captured", 0),
                "filtered_count": log_data.get("filtered_count", 0),
                "requests": events,
            }
        self._ensure_started()
        assert self._page is not None
        if self._network_interceptor is None:
            return {
                "recording": False,
                "recording_start": None,
                "recording_end": None,
                "total_captured": 0,
                "filtered_count": 0,
                "requests": [],
            }
        return self._network_interceptor.list_requests(
            filter_url=filter_url, filter_method=filter_method
        )

    async def clear_network_log(self) -> str:
        """Limpa o log de requisições de rede."""
        if self._in_extension_mode():
            extension_bridge.clear_network_log()
            return "Log de rede limpo (modo extension)"
        self._ensure_started()
        assert self._page is not None
        if self._network_interceptor is None:
            return "ERROR: NetworkInterceptor não está disponível."
        count = len(self._network_interceptor.get_log())
        self._network_interceptor.clear()
        return f"Log de rede limpo. {count} entradas removidas."

    async def get_network_log(
        self,
        filter_url: str | None = None,
        filter_method: str | None = None,
    ) -> str:
        if self._in_extension_mode():
            ext_logs = await extension_bridge.get_network_log(filter_url, filter_method)
            return json.dumps(ext_logs, ensure_ascii=False, indent=2, default=str)
        self._ensure_started()
        assert self._page is not None
        if self._network_interceptor is None:
            return json.dumps([], ensure_ascii=False)
        logs = self._network_interceptor.get_log(filter_url=filter_url, filter_method=filter_method)
        return json.dumps(logs, ensure_ascii=False, indent=2, default=str)

    async def export_har(self, path: str) -> str:
        if self._in_extension_mode():
            log_data = await extension_bridge.get_network_log()
            events = log_data.get("requests", [])
            har: dict[str, Any] = {
                "log": {
                    "version": "1.2",
                    "creator": {"name": "mcp-browser-extension", "version": "1.0.0"},
                    "entries": [],
                }
            }
            for e in events:
                data = e.get("data", e)
                entry = {
                    "startedDateTime": data.get("timestamp", ""),
                    "time": 0,
                    "request": {
                        "method": data.get("method", "GET"),
                        "url": data.get("url", ""),
                        "httpVersion": "HTTP/1.1",
                        "headers": [],
                        "queryString": [],
                        "cookies": [],
                        "headersSize": -1,
                        "bodySize": -1,
                    },
                    "response": {
                        "status": data.get("status", 0),
                        "statusText": "",
                        "httpVersion": "HTTP/1.1",
                        "headers": [],
                        "cookies": [],
                        "content": {
                            "size": len(data.get("responseBody", "")) if data.get("responseBody") else 0,
                            "mimeType": "application/octet-stream",
                            "text": data.get("responseBody", ""),
                        },
                        "redirectURL": "",
                        "headersSize": -1,
                        "bodySize": -1,
                    },
                    "cache": {},
                    "timings": {},
                }
                har["log"]["entries"].append(entry)
            output = Path(path)
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(har, f, indent=2, ensure_ascii=False)
            return str(output.absolute())
        self._ensure_started()
        assert self._page is not None
        assert self._network_interceptor is not None
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        self._network_interceptor.export_har(str(output))
        return str(output.absolute())

    async def find_by_ref(self, ref: str) -> Locator | None:
        """Mapeia @e3 para um locator do Playwright com base no accessibility tree."""
        self._ensure_started()
        assert self._page is not None
        if not ref.startswith("@e"):
            return None
        info = self._ref_map.get(ref)
        if not info:
            # Rebuild ref map if stale
            await self.get_accessibility_tree()
            info = self._ref_map.get(ref)
        if not info:
            return None
        role = info.get("role")
        name = info.get("name")
        if role and name:
            try:
                locator = self._page.get_by_role(role, name=name)
                count = await locator.count()
                if count > 0:
                    return locator
            except Exception:
                pass
        if name:
            try:
                locator = self._page.get_by_text(name, exact=False)
                count = await locator.count()
                if count > 0:
                    return locator.first
            except Exception:
                pass
        if role:
            try:
                locator = self._page.get_by_role(role)
                count = await locator.count()
                if count > 0:
                    return locator
            except Exception:
                pass
        return None

    # ═══════════════════════════════════════════════════════════
    # Ferramentas MCP (retornam string)
    # ═══════════════════════════════════════════════════════════

    async def navigate(self, url: str, new_tab: bool = False, group_title: str = "") -> str:
        if self._in_extension_mode():
            return await self._extension_dispatch("navigate", {"url": url, "newTab": new_tab, "groupTitle": group_title})
        self._ensure_started()
        assert self._page is not None
        assert self._context is not None
        if new_tab:
            self._page = await self._context.new_page()
        response = await self._page.goto(url, wait_until="networkidle", timeout=_TIMEOUT)
        status = response.status if response else "unknown"
        if _ENABLE_VISUAL_INDICATOR:
            await self.inject_indicator()
        info = f"Navegado para {url} (status: {status})"
        if group_title:
            info += f" [grupo: {group_title}]"
        return info

    async def open_new_tab(self, url: str, group_title: str = ACTIVE_TAB_GROUP_TITLE) -> str:
        """Abre uma nova aba e opcionalmente agrupa (Fase 4)."""
        return await self.navigate(url, new_tab=True, group_title=group_title)

    async def go_back(self) -> str:
        if self._in_extension_mode():
            return await self._extension_dispatch("go_back", {})
        self._ensure_started()
        assert self._page is not None
        await self._page.go_back(wait_until="networkidle", timeout=_TIMEOUT)
        return "Navegado para página anterior"

    async def go_forward(self) -> str:
        if self._in_extension_mode():
            return await self._extension_dispatch("go_forward", {})
        self._ensure_started()
        assert self._page is not None
        await self._page.go_forward(wait_until="networkidle", timeout=_TIMEOUT)
        return "Navegado para página seguinte"

    async def reload(self) -> str:
        if self._in_extension_mode():
            return await self._extension_dispatch("reload", {})
        self._ensure_started()
        assert self._page is not None
        await self._page.reload(wait_until="networkidle", timeout=_TIMEOUT)
        return "Página recarregada"

    async def scroll(self, direction: str, amount: int = 300, selector: str | None = None) -> str:
        if self._in_extension_mode():
            return await self._extension_dispatch("scroll", {
                "direction": direction,
                "amount": amount,
                "selector": selector,
            })
        if not self._page:
            raise RuntimeError("Nenhuma página ativa")

        deltas = {
            "up": (0, -amount),
            "down": (0, amount),
            "left": (-amount, 0),
            "right": (amount, 0),
        }
        if direction not in deltas:
            raise ValueError(f"Direção inválida: {direction!r}. Use up, down, left ou right.")
        dx, dy = deltas[direction]

        result = await self._page.evaluate(
            """([selector, dx, dy]) => {
                const target = selector ? document.querySelector(selector) : null;
                if (selector && !target) {
                    return { error: 'Elemento não encontrado: ' + selector };
                }
                const el = target || document.scrollingElement || document.documentElement;
                el.scrollBy({ left: dx, top: dy, behavior: 'instant' });
                return {
                    scrollX: target ? el.scrollLeft : window.scrollX,
                    scrollY: target ? el.scrollTop : window.scrollY,
                };
            }""",
            [selector, dx, dy],
        )
        if result.get("error"):
            raise RuntimeError(result["error"])
        return json.dumps({"direction": direction, "amount": amount, "selector": selector, **result})

    async def click(self, selector: str, by: str = "css") -> str:
        """Clica em um elemento com fallback inteligente.

        Estratégia de clique em 3 níveis:
        1. Playwright native click (eventos trusted, nível CDP)
        2. Force click (ignora checks de visibilidade para SPAs complexas)
        3. Se for link (<a href>), navegação direta via page.goto()

        Nota: Jamais use page.evaluate('element.click()') — o evento gerado
        tem isTrusted=false e é bloqueado por sites como Google News.
        """
        if self._in_extension_mode():
            return await self._extension_dispatch("click", {"selector": selector, "by": by})
        self._ensure_started()
        assert self._page is not None

        # Resolve o locator
        locator: Locator
        if by == "ref" or selector.startswith("@e"):
            locator = await self.find_by_ref(selector)
            if locator is None:
                raise ValueError(f"Ref não encontrado: {selector}")
        elif by == "css":
            locator = self._page.locator(selector).first
        elif by == "xpath":
            locator = self._page.locator(f"xpath={selector}").first
        elif by == "text":
            locator = self._page.get_by_text(selector).first
        elif by == "coordinates":
            parts = selector.split(",")
            if len(parts) != 2:
                raise ValueError("Para coordinates, use formato 'x,y'")
            x, y = int(parts[0].strip()), int(parts[1].strip())
            await self._page.mouse.click(x, y)
            return f"Elemento clicado: {selector} (by=coordinates)"
        else:
            raise ValueError(f"Tipo de seletor desconhecido: {by}")

        return await self._smart_click(locator, selector, by)

    async def _smart_click(self, locator: Locator, selector: str, by: str) -> str:
        """Clique inteligente com fallback para sites como Google News.

        Tenta 3 estratégias em ordem:
        1. Playwright native click (eventos trusted)
        2. Force click com force=True (ignora visibility/actionability checks)
        3. Para links: extrai href e navega diretamente via page.goto()
        """
        assert self._page is not None

        # ── Estratégia 1: Playwright native click ──
        try:
            await locator.click(timeout=_TIMEOUT)
            await self._page.wait_for_load_state("networkidle", timeout=5000)
            return f"Elemento clicado: {selector} (by={by})"
        except Exception as e1:
            pass  # Tenta próximo fallback

        # ── Estratégia 2: Force click (ignora actionability checks) ──
        try:
            await locator.click(timeout=_TIMEOUT, force=True)
            await self._page.wait_for_load_state("networkidle", timeout=5000)
            return f"Elemento clicado (force): {selector} (by={by})"
        except Exception as e2:
            pass  # Tenta próximo fallback

        # ── Estratégia 3: Link navigation via href ──
        try:
            tag = await locator.evaluate("el => el.tagName.toLowerCase()")
            if tag == "a":
                href = await locator.get_attribute("href", timeout=3000)
                if href and not href.startswith("#") and not href.startswith("javascript:"):
                    # Resolve URL relativa para absoluta
                    resolved = await self._page.evaluate(
                        """([base, href]) => {
                            try { return new URL(href, base).href; }
                            catch(e) { return null; }
                        }""",
                        [self._page.url, href],
                    )
                    if resolved:
                        await self._page.goto(resolved, wait_until="networkidle", timeout=_TIMEOUT)
                        return f"Navegado para link: {selector} -> {resolved} (by={by}, via-href)"
        except Exception:
            pass

        # ── Estratégia 4: dispatchEvent com MouseEvent completo ──
        try:
            result = await locator.evaluate("""el => {
                const rect = el.getBoundingClientRect();
                const cx = rect.left + rect.width / 2;
                const cy = rect.top + rect.height / 2;
                const opts = {
                    bubbles: true, cancelable: true, view: window,
                    clientX: cx, clientY: cy, button: 0, buttons: 1
                };
                el.dispatchEvent(new PointerEvent('pointerdown', opts));
                el.dispatchEvent(new MouseEvent('mousedown', opts));
                el.dispatchEvent(new PointerEvent('pointerup', opts));
                el.dispatchEvent(new MouseEvent('mouseup', opts));
                el.dispatchEvent(new MouseEvent('click', opts));
                return 'dispatched';
            }""")
            if result == "dispatched":
                await self._page.wait_for_load_state("networkidle", timeout=5000)
                return f"Elemento clicado (events): {selector} (by={by})"
        except Exception as e4:
            pass

        # Último recurso: tenta um click normal de novo (pode ter sido
        # problema de timing na primeira tentativa)
        await locator.click(timeout=_TIMEOUT, force=True, no_wait_after=True)
        return f"Elemento clicado (force+no_wait): {selector} (by={by})"

    async def type_text(self, selector: str, text: str, clear: bool = True, by: str = "css") -> str:
        if self._in_extension_mode():
            return await self._extension_dispatch("type", {"selector": selector, "text": text, "clear": clear, "by": by})
        self._ensure_started()
        assert self._page is not None
        if by == "ref" or selector.startswith("@e"):
            locator = await self.find_by_ref(selector)
            if locator is None:
                raise ValueError(f"Ref não encontrado: {selector}")
            if clear:
                await locator.fill(text, timeout=_TIMEOUT)
            else:
                await locator.type(text, timeout=_TIMEOUT)
            return f"Texto digitado em {selector} (by=ref)"
        locator = self._page.locator(selector)
        if clear:
            await locator.fill(text, timeout=_TIMEOUT)
        else:
            await locator.type(text, timeout=_TIMEOUT)
        return f"Texto digitado em {selector}"

    async def select_option(self, selector: str, value: str) -> str:
        if self._in_extension_mode():
            return await self._extension_dispatch("select_option", {"selector": selector, "value": value})
        self._ensure_started()
        assert self._page is not None
        await self._page.locator(selector).select_option(value, timeout=_TIMEOUT)
        return f"Opção '{value}' selecionada em {selector}"

    async def hover(self, selector: str, by: str = "css") -> str:
        if self._in_extension_mode():
            return await self._extension_dispatch("hover", {"selector": selector, "by": by})
        self._ensure_started()
        assert self._page is not None
        if by == "ref" or selector.startswith("@e"):
            locator = await self.find_by_ref(selector)
            if locator is None:
                raise ValueError(f"Ref não encontrado: {selector}")
            await locator.hover(timeout=_TIMEOUT)
            return f"Hover em {selector} (by=ref)"
        await self._page.locator(selector).hover(timeout=_TIMEOUT)
        return f"Hover em {selector}"

    async def press_key(self, key: str, selector: str | None = None) -> str:
        if self._in_extension_mode():
            return await self._extension_dispatch("press_key", {"key": key, "selector": selector})
        self._ensure_started()
        assert self._page is not None
        if selector:
            await self._page.press(selector, key, timeout=_TIMEOUT)
        else:
            await self._page.keyboard.press(key)
        return f"Tecla '{key}' pressionada"

    async def upload_file(self, selector: str, file_path: str) -> str:
        if self._in_extension_mode():
            raise NotImplementedError("upload_file não suportado no modo extension")
        self._ensure_started()
        assert self._page is not None
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        await self._page.locator(selector).set_input_files(str(path), timeout=_TIMEOUT)
        return f"Arquivo '{file_path}' enviado para {selector}"

    async def get_content(self, selector: str | None = None, as_html: bool = False) -> str:
        if self._in_extension_mode():
            return await self._extension_dispatch("get_content", {"selector": selector, "as_html": as_html})
        self._ensure_started()
        assert self._page is not None
        if selector:
            locator = self._page.locator(selector)
            if as_html:
                return await locator.inner_html(timeout=_TIMEOUT)
            return await locator.inner_text(timeout=_TIMEOUT)
        if as_html:
            return await self._page.content()
        return cast(str, await self._page.evaluate("document.body.innerText || ''"))

    async def execute_javascript(self, code: str) -> str:
        if self._in_extension_mode():
            return await self._extension_dispatch("execute_javascript", {"code": code})
        self._ensure_started()
        assert self._page is not None
        result = await self._page.evaluate(code)
        return json.dumps(result, ensure_ascii=False, default=str)

    async def get_attributes(self, selector: str, attribute: str | None = None) -> str:
        if self._in_extension_mode():
            return await self._extension_dispatch("get_attributes", {"selector": selector, "attribute": attribute})
        self._ensure_started()
        assert self._page is not None
        locator = self._page.locator(selector)
        if attribute:
            value = await locator.get_attribute(attribute, timeout=_TIMEOUT)
            return json.dumps({attribute: value}, ensure_ascii=False)
        else:
            attrs = await self._page.evaluate(
                """(sel) => {
                    const el = document.querySelector(sel);
                    if (!el) return null;
                    const res = {};
                    for (const attr of el.attributes) {
                        res[attr.name] = attr.value;
                    }
                    return res;
                }""",
                selector,
            )
            return json.dumps(attrs, ensure_ascii=False, default=str)

    async def screenshot(self, path: str | None = None, full_page: bool = False) -> str:
        if self._in_extension_mode():
            result = await self._extension_dispatch("screenshot", {"path": path, "full_page": full_page})
            if path:
                return result
            return result
        self._ensure_started()
        assert self._page is not None
        if path:
            output = Path(path)
            output.parent.mkdir(parents=True, exist_ok=True)
            await self._page.screenshot(path=str(output), full_page=full_page)
            return str(output.absolute())
        else:
            fd, tmp_path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            await self._page.screenshot(path=tmp_path, full_page=full_page)
            return str(Path(tmp_path).absolute())

    async def download(self, url: str, filename: str | None = None) -> str:
        if self._in_extension_mode():
            return await self._extension_dispatch("download", {"url": url, "filename": filename})
        if not self._page:
            raise RuntimeError("Nenhuma página ativa")

        download_dir = Path(
            os.environ.get(
                "BROWSER_MCP_DOWNLOAD_DIR",
                str(Path(tempfile.gettempdir()) / "browser_mcp_downloads"),
            )
        )
        download_dir.mkdir(parents=True, exist_ok=True)

        # APIRequestContext compartilha cookies com o contexto do navegador
        response = await self._page.context.request.get(url)
        if not response.ok:
            raise RuntimeError(f"Download falhou: HTTP {response.status} para {url}")

        if not filename:
            cd = response.headers.get("content-disposition", "")
            match = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)\"?", cd, re.IGNORECASE)
            if match:
                filename = unquote(match.group(1))
            else:
                filename = os.path.basename(urlparse(url).path) or "download.bin"
        # evita path traversal via filename vindo do agente ou do servidor
        filename = os.path.basename(filename)

        base = Path(filename)
        dest = download_dir / filename
        counter = 1
        while dest.exists():
            dest = download_dir / f"{base.stem}_{counter}{base.suffix}"
            counter += 1

        body = await response.body()
        dest.write_bytes(body)
        return json.dumps({"path": str(dest.resolve()), "size": len(body), "url": url})

    async def manage_session(self, action: str, **kwargs: Any) -> str:
        if self._in_extension_mode():
            if action in ("start_recording", "stop_recording", "list_tabs"):
                return await self._extension_dispatch("manage_session", {"action": action, **kwargs})
            raise NotImplementedError(f"manage_session '{action}' não suportado no modo extension")
        self._ensure_started()
        assert self._page is not None
        assert self._context is not None

        if action == "get_cookies":
            cookies = await self._context.cookies()
            return json.dumps(cookies, ensure_ascii=False, indent=2)

        elif action == "set_cookies":
            cookies = kwargs.get("cookies", [])
            await self._context.add_cookies(cookies)
            return f"{len(cookies)} cookies definidos"

        elif action == "clear_cookies":
            await self._context.clear_cookies()
            return "Cookies limpos"

        elif action == "new_tab":
            await self._context.new_page()
            return "Nova aba aberta"

        elif action == "list_tabs":
            tabs = self._context.pages
            tabs_info = []
            for i, tab in enumerate(tabs):
                try:
                    url = tab.url
                except Exception:
                    url = "about:blank"
                tabs_info.append({"index": i, "url": url})
            return json.dumps(tabs_info, ensure_ascii=False, indent=2, default=str)

        elif action == "close_tab":
            index = kwargs.get("index", -1)
            tabs = self._context.pages
            if 0 <= index < len(tabs):
                tab = tabs[index]
                await tab.close()
                if self._page == tab and self._context.pages:
                    self._page = self._context.pages[-1]
                return f"Aba {index} fechada"
            raise ValueError(f"Índice de aba inválido: {index}")

        elif action == "resize_viewport":
            width = kwargs.get("width", 1280)
            height = kwargs.get("height", 720)
            await self._page.set_viewport_size({"width": width, "height": height})
            return f"Viewport redimensionado para {width}x{height}"

        elif action == "start_recording":
            path = kwargs.get("path", "./recording")
            return f"Gravação iniciada (stub) em {path}"

        elif action == "stop_recording":
            return "Gravação finalizada (stub)"

        else:
            raise ValueError(f"Ação desconhecida: {action}")
            raise ValueError(f"Ação desconhecida: {action}")

    async def wait(self, condition: str, selector: str | None = None, timeout: int | None = None) -> str:
        if self._in_extension_mode():
            t = timeout or _TIMEOUT
            return await self._extension_dispatch("wait", {
                "condition": condition,
                "selector": selector,
                "timeout": t,
            })
        self._ensure_started()
        assert self._page is not None
        t = timeout or _TIMEOUT

        if condition == "element_visible":
            if not selector:
                raise ValueError("selector é obrigatório para element_visible")
            await self._page.wait_for_selector(selector, state="visible", timeout=t)
            return f"Elemento {selector} está visível"

        elif condition == "element_hidden":
            if not selector:
                raise ValueError("selector é obrigatório para element_hidden")
            await self._page.wait_for_selector(selector, state="hidden", timeout=t)
            return f"Elemento {selector} está oculto"

        elif condition == "network_idle":
            await self._page.wait_for_load_state("networkidle", timeout=t)
            return "Network idle atingido"

        elif condition == "timeout":
            await asyncio.sleep(t / 1000)
            return f"Aguardado {t}ms"

        else:
            raise ValueError(f"Condição desconhecida: {condition}")

    # ═══════════════════════════════════════════════════════════
    # Auxiliares para o agente (retornam valores diretos)
    # ═══════════════════════════════════════════════════════════

    async def get_url(self) -> str:
        if self._in_extension_mode():
            return await extension_bridge.get_current_url()
        self._ensure_started()
        assert self._page is not None
        return self._page.url

    async def get_title(self) -> str:
        if self._in_extension_mode():
            return await extension_bridge.get_current_title()
        self._ensure_started()
        assert self._page is not None
        return await self._page.title()

    async def get_visible_text(self) -> str:
        if self._in_extension_mode():
            result = await self._extension_dispatch("get_visible_text", {})
            try:
                return cast(str, json.loads(result))
            except json.JSONDecodeError:
                return result
        self._ensure_started()
        assert self._page is not None
        text = cast(str, await self._page.evaluate(
            """() => {
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );
                let node;
                let text = "";
                while (node = walker.nextNode()) {
                    if (node.parentElement && getComputedStyle(node.parentElement).display !== "none") {
                        text += node.textContent + " ";
                    }
                }
                return text.trim().replace(/\\s+/g, " ");
            }"""
        ))
        return text[:5000]

    async def get_interactive_elements(self) -> list[dict[str, Any]]:
        if self._in_extension_mode():
            result = await self._extension_dispatch("get_interactive_elements", {})
            try:
                return cast(list[dict[str, Any]], json.loads(result))
            except json.JSONDecodeError:
                return []
        self._ensure_started()
        assert self._page is not None
        elements = cast(list[dict[str, Any]], await self._page.evaluate(
            """() => {
                const selectors = [
                    "a", "button", "input", "select", "textarea",
                    "[onclick]", "[role=\\"button\\"]"
                ];
                const found = new Set();
                const result = [];
                for (const sel of selectors) {
                    for (const el of document.querySelectorAll(sel)) {
                        if (found.has(el)) continue;
                        found.add(el);
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 && rect.height === 0) continue;
                        const style = window.getComputedStyle(el);
                        if (style.display === "none" || style.visibility === "hidden") continue;
                        const entry = {
                            tag: el.tagName.toLowerCase(),
                            type: el.type || null,
                            id: el.id || null,
                            name: el.name || null,
                            text: el.innerText?.trim().substring(0, 100) || null,
                            href: el.href || null,
                            selector: sel + (el.id ? "#" + el.id : ""),
                        };
                        result.push(entry);
                        if (result.length >= 50) break;
                    }
                    if (result.length >= 50) break;
                }
                return result;
            }"""
        ))
        return elements

    async def extension_get_network_log(self, filter_url: str | None = None, filter_method: str | None = None) -> str:
        """Obtém log de rede da extensão (modo extension)."""
        if not self._in_extension_mode():
            raise RuntimeError("Disponível apenas no modo extension. Use browser_connect_to_extension primeiro.")
        logs = await extension_bridge.get_network_log(filter_url, filter_method)
        return json.dumps(logs, ensure_ascii=False, indent=2, default=str)

    async def extension_get_dom_snapshot(self) -> str:
        """Obtém snapshot do DOM da extensão (modo extension)."""
        if not self._in_extension_mode():
            raise RuntimeError("Disponível apenas no modo extension. Use browser_connect_to_extension primeiro.")
        snapshot = await extension_bridge.get_dom_snapshot()
        return str(snapshot)

    async def extension_get_console_errors(
        self,
        level: str | None = None,
        filter_text: str | None = None,
        limit: int = 50,
    ) -> str:
        """Retorna erros/warnings de console capturados pela extensão."""
        if not self._in_extension_mode():
            raise RuntimeError("Disponível apenas no modo extension. Use browser_connect_to_extension primeiro.")
        result = await extension_bridge.get_console_errors(level, filter_text, limit)
        return json.dumps(result, indent=2, ensure_ascii=False)

    # ────────────────────────────────────────────────
    # Indicadores visuais (CDP Runtime.evaluate)
    # ────────────────────────────────────────────────

    async def inject_indicator(self, color: str = "blue") -> str:
        """Injeta overlay visual de automação na página.
        Cores: blue (padrão), orange (atenção), red (perigo), green (concluído).
        """
        if self._in_extension_mode():
            return ""
        self._ensure_started()
        assert self._page is not None
        try:
            await self._page.evaluate(get_overlay_js(color))
            return f"Indicador visual injetado (cor: {color})"
        except Exception as e:
            return f"Erro ao injetar indicador: {e}"

    async def set_security_level(self, level: str) -> str:
        """Altera a cor do overlay por nível de segurança (Fase 5)."""
        if self._in_extension_mode():
            return ""
        self._ensure_started()
        assert self._page is not None
        try:
            # Remove old + inject new in single call
            get_remove_overlay_js().strip()
            inject_js = get_overlay_js(level).strip()
            combined = f"""
                (() => {{
                    const el = document.getElementById('__mcp_browser_overlay');
                    if (el) el.remove();
                }})();
                {inject_js}
            """
            await self._page.evaluate(combined)
            return f"Nível de segurança: {level}"
        except Exception as e:
            return f"Erro ao alterar nível: {e}"

    async def remove_indicator(self) -> str:
        """Remove o overlay visual."""
        if self._in_extension_mode():
            return ""
        self._ensure_started()
        assert self._page is not None
        try:
            await self._page.evaluate(get_remove_overlay_js())
            return "Indicador visual removido"
        except Exception as e:
            return f"Erro ao remover indicador: {e}"

    async def highlight_element(self, selector: str) -> str:
        """Destaca um elemento na página (Fase 2)."""
        if self._in_extension_mode():
            return ""
        self._ensure_started()
        assert self._page is not None
        try:
            await self._page.evaluate(get_highlight_element_js(), selector)
            return f"Elemento '{selector}' destacado"
        except Exception as e:
            return f"Erro ao destacar: {e}"

    async def click_ripple(self, x: int, y: int) -> str:
        """Cria ripple de clique na posição (x, y)."""
        if self._in_extension_mode():
            return ""
        self._ensure_started()
        try:
            await self._page.evaluate(get_click_ripple_js(), {"x": x, "y": y})
            return f"Ripple em ({x}, {y})"
        except Exception as e:
            return f"Erro no ripple: {e}"

    async def update_status(self, status: str) -> str:
        """Atualiza o badge de status do overlay (Fase 3)."""
        if self._in_extension_mode():
            return ""
        self._ensure_started()
        assert self._page is not None
        try:
            await self._page.evaluate(get_status_overlay_js(), status)
            return f"Status: {status}"
        except Exception as e:
            return f"Erro no status: {e}"

    async def get_pending_network_count(self) -> int:
        if self._in_extension_mode():
            return extension_bridge.network_log_count
        if not self._initialized or self._network_interceptor is None:
            return 0
        return len(self._network_interceptor.get_log())


# Singleton instance
browser_manager = BrowserManager()
