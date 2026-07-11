"""Extension Bridge — Abstração de comunicação entre MCP Server e extensão Chrome.

Padrão singleton que encapsula a lógica de enviar comandos para a extensão
via WebSocket e aguardar respostas, além de manter logs acumulados de rede
e snapshots de DOM.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from browser_mcp.websocket_server import WebSocketServer


class ExtensionBridge:
    """Singleton que abstrai a comunicação MCP Server ↔ Extensão Chrome."""

    _instance: ExtensionBridge | None = None
    _lock = asyncio.Lock()

    def __new__(cls) -> ExtensionBridge:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    async def initialize(self, ws_server: WebSocketServer | None = None) -> None:
        """Inicializa o bridge e o servidor WebSocket."""
        if self._initialized:
            return
        async with self._lock:
            if self._initialized:
                return
            if ws_server is not None:
                self._ws_server = ws_server
            else:
                from browser_mcp.websocket_server import websocket_server as _ws_singleton
                self._ws_server = _ws_singleton

            self._network_log: list[dict[str, Any]] = []
            self._dom_events: list[dict[str, Any]] = []
            self._navigation_events: list[dict[str, Any]] = []
            self._console_errors: list[dict[str, Any]] = []
            self._max_log_size = 10000
            self._recording = False

            # Registra callback para receber eventos da extensão
            self._ws_server.on_event(self._on_extension_event)
            if not self._ws_server.is_running():
                await self._ws_server.start()
            self._initialized = True
            print("[EXTENSION-BRIDGE] Inicializado.", file=sys.stderr)

    async def shutdown(self) -> None:
        """Encerra o bridge e o servidor WebSocket."""
        async with self._lock:
            if not self._initialized:
                return
            if self._ws_server:
                await self._ws_server.stop()
            self._initialized = False
            print("[EXTENSION-BRIDGE] Encerrado.", file=sys.stderr)

    def is_initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Event handlers (recebidos da extensão)
    # ------------------------------------------------------------------

    def _on_extension_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Processa eventos recebidos da extensão Chrome."""
        if event_type == "xhr":
            self._network_log.append(data)
            if len(self._network_log) > self._max_log_size:
                self._network_log = self._network_log[-self._max_log_size:]
        elif event_type == "dom":
            self._dom_events.append(data)
            if len(self._dom_events) > self._max_log_size:
                self._dom_events = self._dom_events[-self._max_log_size:]
        elif event_type == "navigation":
            self._navigation_events.append(data)
            if len(self._navigation_events) > self._max_log_size:
                self._navigation_events = self._navigation_events[-self._max_log_size:]
        elif event_type == "console":
            self._console_errors.append(data)
            if len(self._console_errors) > self._max_log_size:
                self._console_errors = self._console_errors[-self._max_log_size:]

    # ------------------------------------------------------------------
    # Comandos — enviam para a extensão e aguardam resposta
    # ------------------------------------------------------------------

    async def execute_command(self, tool: str, params: dict[str, Any], timeout: float = 15.0) -> Any:
        """Envia um comando para a extensão e aguarda a resposta.

        Args:
            tool: Nome da ferramenta (ex: 'browser_navigate')
            params: Parâmetros da ferramenta
            timeout: Timeout em segundos

        Returns:
            Resultado da execução

        Raises:
            RuntimeError: Se nenhuma extensão estiver conectada
            TimeoutError: Se a extensão não responder a tempo
        """
        if not self._initialized:
            raise RuntimeError("ExtensionBridge não inicializado. Chame initialize() primeiro.")
        if not self._ws_server.is_connected():
            raise RuntimeError("Nenhuma extensão Chrome conectada via WebSocket.")
        return await self._ws_server.execute_command(tool, params, timeout=timeout)

    async def navigate(self, url: str) -> str:
        """Navega para uma URL via extensão."""
        result = await self.execute_command("navigate", {"url": url})
        return str(result)

    async def click(self, selector: str, by: str = "css") -> str:
        """Clica em um elemento via extensão."""
        result = await self.execute_command("click", {"selector": selector, "by": by})
        return str(result)

    async def type_text(self, selector: str, text: str, clear: bool = True, by: str = "css") -> str:
        """Digita texto em um elemento via extensão."""
        result = await self.execute_command(
            "type",
            {"selector": selector, "text": text, "clear": clear, "by": by},
        )
        return str(result)

    async def get_content(self, selector: str | None = None, as_html: bool = False) -> str:
        """Obtém conteúdo da página via extensão."""
        result = await self.execute_command(
            "get_content",
            {"selector": selector, "as_html": as_html},
        )
        return str(result)

    async def screenshot(self) -> str:
        """Captura screenshot via extensão (retorna data URL base64)."""
        result = await self.execute_command("screenshot", {})
        return str(result)

    async def execute_javascript(self, code: str) -> str:
        """Executa JavaScript na página via extensão."""
        result = await self.execute_command("execute_javascript", {"code": code})
        return str(result)

    async def press_key(self, key: str, selector: str | None = None) -> str:
        """Pressiona uma tecla via extensão."""
        params = {"key": key}
        if selector:
            params["selector"] = selector
        result = await self.execute_command("press_key", params)
        return str(result)

    async def scroll(self, x: int = 0, y: int = 0) -> str:
        """Scroll na página via extensão."""
        result = await self.execute_command("scroll", {"x": x, "y": y})
        return str(result)

    async def hover(self, selector: str, by: str = "css") -> str:
        """Hover em um elemento via extensão."""
        result = await self.execute_command("hover", {"selector": selector, "by": by})
        return str(result)

    async def get_url(self) -> str:
        """Obtém URL atual via extensão."""
        result = await self.execute_command("get_url", {})
        if isinstance(result, dict):
            return result.get("url", "")
        return str(result)

    def is_connected(self) -> bool:
        """Retorna True se há pelo menos uma extensão conectada."""
        if not hasattr(self, "_ws_server") or self._ws_server is None:
            return False
        return self._ws_server.is_connected()

    async def get_title(self) -> str:
        """Obtém título da página via extensão."""
        result = await self.execute_command("get_title", {})
        if isinstance(result, dict):
            return result.get("title", "")
        return str(result)

    # ------------------------------------------------------------------
    # Queries — dados acumulados da extensão
    # ------------------------------------------------------------------

    async def get_network_log(
        self,
        filter_url: str | None = None,
        filter_method: str | None = None,
    ) -> dict[str, Any]:
        """Retorna log acumulado de requisições de rede da extensão.

        Args:
            filter_url: Filtrar por substring na URL
            filter_method: Filtrar por método HTTP

        Returns:
            Dicionário com a lista de requests e metadados
        """
        results = self._network_log[:]
        if filter_url:
            results = [e for e in results if filter_url in e.get("url", "")]
        if filter_method:
            results = [e for e in results if e.get("method", "") == filter_method.upper()]
        return {
            "recording": self._recording,
            "total_captured": len(self._network_log),
            "filtered_count": len(results),
            "requests": results,
        }

    async def get_dom_snapshot(self) -> dict[str, Any]:
        """Solicita um snapshot do DOM à extensão (executa na página atual).

        Returns:
            Snapshot do DOM com HTML, elementos interativos, etc.
        """
        if not self._ws_server.is_connected():
            raise RuntimeError("Nenhuma extensão conectada para obter DOM snapshot.")
        return await self.execute_command("get_dom_snapshot", {})

    async def get_dom_events(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Retorna eventos de DOM capturados.

        Args:
            limit: Número máximo de eventos a retornar (mais recentes)
        """
        events = self._dom_events[:]
        if limit:
            events = events[-limit:]
        return events

    async def get_navigation_events(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Retorna eventos de navegação capturados.

        Args:
            limit: Número máximo de eventos a retornar (mais recentes)
        """
        events = self._navigation_events[:]
        if limit:
            events = events[-limit:]
        return events

    async def get_console_errors(
        self,
        level: str | None = None,
        filter_text: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Retorna erros/warnings de console capturados da extensão.

        Args:
            level: Filtrar por nível ('error', 'warn', 'log')
            filter_text: Filtrar por substring na mensagem
            limit: Número máximo de entradas (mais recentes)

        Returns:
            Dict com lista de entradas e metadados
        """
        results = self._console_errors[:]
        if level:
            results = [e for e in results if e.get("level") == level]
        if filter_text:
            results = [e for e in results if filter_text in str(e.get("message", ""))]
        if limit:
            results = results[-limit:]
        return {
            "total_captured": len(self._console_errors),
            "filtered_count": len(results),
            "entries": results,
        }

    # ------------------------------------------------------------------
    # Controle de gravação
    # ------------------------------------------------------------------

    def start_recording(self) -> None:
        """Inicia acúmulo de eventos."""
        self._recording = True
        print("[EXTENSION-BRIDGE] Gravação iniciada.", file=sys.stderr)

    def stop_recording(self) -> None:
        """Para o acúmulo de eventos de rede."""
        self._recording = False
        print("[EXTENSION-BRIDGE] Gravação parada.", file=sys.stderr)

    def is_recording(self) -> bool:
        return self._recording

    def clear_logs(self) -> None:
        """Limpa todos os logs acumulados."""
        self._network_log.clear()
        self._dom_events.clear()
        self._navigation_events.clear()
        print("[EXTENSION-BRIDGE] Todos os logs limpos.", file=sys.stderr)

    def clear_network_log(self) -> None:
        """Limpa o log de rede acumulado."""
        count = len(self._network_log)
        self._network_log.clear()
        print(f"[EXTENSION-BRIDGE] Log de rede limpo. {count} entradas removidas.", file=sys.stderr)

    def clear_dom_events(self) -> None:
        """Limpa os eventos de DOM acumulados."""
        count = len(self._dom_events)
        self._dom_events.clear()
        print(f"[EXTENSION-BRIDGE] Eventos DOM limpos. {count} entradas removidas.", file=sys.stderr)

    def clear_navigation_events(self) -> None:
        """Limpa os eventos de navegação acumulados."""
        count = len(self._navigation_events)
        self._navigation_events.clear()
        print(f"[EXTENSION-BRIDGE] Eventos de navegação limpos. {count} removidos.", file=sys.stderr)

    def clear_console_log(self) -> None:
        """Limpa os erros/warnings de console acumulados."""
        count = len(self._console_errors)
        self._console_errors.clear()
        print(f"[EXTENSION-BRIDGE] Console log limpo. {count} entradas removidas.", file=sys.stderr)

    # ------------------------------------------------------------------
    # Propriedades e helpers
    # ------------------------------------------------------------------

    @property
    def network_log_count(self) -> int:
        return len(self._network_log)

    async def get_current_url(self) -> str:
        """Alias para get_url."""
        return await self.get_url()

    async def get_current_title(self) -> str:
        """Alias para get_title."""
        return await self.get_title()

    async def attach(self) -> None:
        """Inicializa o bridge se necessário."""
        if not self._initialized:
            await self.initialize()

    async def detach(self) -> None:
        """Não desliga o servidor para não afetar outras conexões."""
        print("[EXTENSION-BRIDGE] Detach: bridge continua ativo.", file=sys.stderr)

    # ------------------------------------------------------------------
    # HAR export
    # ------------------------------------------------------------------

    def export_har(self, path: str) -> None:
        """Exporta o log de rede acumulado no formato HAR 1.2.

        Args:
            path: Caminho do arquivo HAR a ser exportado
        """
        import os
        from datetime import datetime

        har = {
            "log": {
                "version": "1.2",
                "creator": {"name": "MCP Browser Bridge", "version": "1.0.0"},
                "entries": [],
            }
        }

        for e in self._network_log:
            entry = {
                "startedDateTime": datetime.fromtimestamp(
                    e.get("timestamp", 0) / 1000.0
                ).isoformat(),
                "time": e.get("duration", 0),
                "request": {
                    "method": e.get("method", "GET"),
                    "url": e.get("url", ""),
                    "httpVersion": "HTTP/1.1",
                    "headers": [
                        {"name": k, "value": v}
                        for k, v in e.get("requestHeaders", {}).items()
                    ],
                    "queryString": [],
                    "cookies": [],
                    "headersSize": -1,
                    "bodySize": len(e["requestBody"]) if e.get("requestBody") else -1,
                    "postData": (
                        {"mimeType": "application/json", "text": e["requestBody"]}
                        if e.get("requestBody")
                        else None
                    ),
                },
                "response": {
                    "status": e.get("status", 0),
                    "statusText": e.get("statusText", ""),
                    "httpVersion": "HTTP/1.1",
                    "headers": [
                        {"name": k, "value": v}
                        for k, v in e.get("responseHeaders", {}).items()
                    ],
                    "cookies": [],
                    "content": {
                        "size": len(e["responseBody"]) if e.get("responseBody") else 0,
                        "mimeType": e.get("responseHeaders", {}).get(
                            "content-type", "application/octet-stream"
                        ),
                        "text": e.get("responseBody", ""),
                    },
                    "redirectURL": "",
                    "headersSize": -1,
                    "bodySize": -1,
                },
                "cache": {},
                "timings": {
                    "blocked": -1,
                    "dns": -1,
                    "connect": -1,
                    "send": -1,
                    "wait": e.get("duration", -1),
                    "receive": -1,
                    "ssl": -1,
                },
            }
            har["log"]["entries"].append(entry)

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(har, f, indent=2, ensure_ascii=False)
        print(f"[EXTENSION-BRIDGE] HAR exportado para: {path}", file=sys.stderr)


# Singleton instance
extension_bridge = ExtensionBridge()
