"""Servidor WebSocket para comunicação com a extensão Chrome MCP Browser Bridge.

Escuta em ws://localhost:8765 e troca mensagens JSON bidirecionais com a extensão.
Mensagens de ENTRADA (extensão → servidor):
  - {type: 'identify', client: 'chrome-extension', version: '...'}
  - {type: 'event', eventType: 'xhr'|'dom'|'navigation', data: {...}, tabId, tabUrl}
  - {type: 'request', tool: 'browser_navigate', params: {...}}
  - {type: 'ping'}
  - {type: 'pong'}

Mensagens de SAÍDA (servidor → extensão):
  - {type: 'command', id: '...', tool: 'browser_navigate', params: {...}}
  - {type: 'response', id: '...', result: '...', error: '...'}
  - {type: 'config', wsUrl: '...'}
  - {type: 'ping'}

Integra-se com browser_manager para executar comandos no browser da extensão.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import os
import secrets
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

# websockets é um dependência opcional; tentamos importar
# Se não estiver instalado, usamos asyncio puro com implementação mínima
try:
    import websockets
    from websockets.server import WebSocketServerProtocol

    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    WebSocketServerProtocol = Any

from browser_mcp.restricted_profile import RestrictedProfile

# Tamanho máximo de payload para evitar ataques de exaustão de memória (64 MiB)
MAX_PAYLOAD_SIZE = 64 * 1024 * 1024
TOKEN_PATH = Path.home() / ".mcp_browser_token"


def _load_or_create_token() -> str:
    try:
        if TOKEN_PATH.exists():
            existing = TOKEN_PATH.read_text(encoding="utf-8").strip()
            if existing:
                with contextlib.suppress(Exception):
                    os.chmod(TOKEN_PATH, 0o600)
                return existing
    except Exception as e:
        print(f"[WS-SERVER] Falha ao ler token existente: {e}", file=sys.stderr)
    token = secrets.token_urlsafe(32)
    TOKEN_PATH.write_text(token, encoding="utf-8")
    os.chmod(TOKEN_PATH, 0o600)
    print(f"[WS-SERVER] Token gerado em {TOKEN_PATH}", file=sys.stderr)
    return token


class WebSocketServer:
    """Servidor WebSocket que faz ponte entre MCP Server e extensão Chrome."""

    def __init__(self, host: str = "localhost", port: int = 8765):
        # In restricted mode, force loopback binding
        if RestrictedProfile.is_active():
            self.host = "127.0.0.1"
            if host != "localhost" and host != "127.0.0.1":
                print(
                    f"[WS-SERVER] WARNING: host='{host}' ignored in restricted mode. "
                    f"Forcing 127.0.0.1 (loopback only).",
                    file=sys.stderr,
                )
            # Run startup security checks
            ok, msg = RestrictedProfile.check_startup_conditions()
            if not ok:
                print(f"[WS-SERVER] FATAL: {msg}", file=sys.stderr)
                sys.exit(1)
        else:
            self.host = host
        self.port = port
        self._clients: set[WebSocketServerProtocol] = set()
        self._server: Any | None = None
        self._task: asyncio.Task | None = None
        self._running = False
        self._event_callbacks: list[Callable[[str, dict[str, Any]], None]] = []
        self._command_callbacks: dict[str, Callable[[dict[str, Any]], None]] = {}
        self._pending_responses: dict[str, asyncio.Future] = {}
        self._token = _load_or_create_token()

    def is_running(self) -> bool:
        """Retorna True se o servidor estiver ativo."""
        return self._running

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Inicia o servidor WebSocket."""
        if self._running:
            return
        self._running = True

        # Usar sempre o servidor built-in para máxima compatibilidade
        # (a biblioteca websockets v16 tem bugs de handshake com Chrome)
        self._task = asyncio.create_task(self._start_builtin_server())
        print(
            f"[WS-SERVER] WebSocket server iniciado em ws://{self.host}:{self.port}",
            file=sys.stderr,
        )

    async def stop(self) -> None:
        """Para o servidor WebSocket e fecha todas as conexões."""
        self._running = False

        # Fecha conexões pendentes
        for client in list(self._clients):
            try:
                if HAS_WEBSOCKETS:
                    await client.close()
                else:
                    client.writer.close()
                    await client.writer.wait_closed()
            except Exception as e:
                print(f"[WS-SERVER] Erro ao fechar cliente: {e}", file=sys.stderr)
        self._clients.clear()

        # Cancela futures pendentes
        for fut in self._pending_responses.values():
            if not fut.done():
                fut.cancel()
        self._pending_responses.clear()

        if self._server:
            try:
                self._server.close()
                await self._server.wait_closed()
            except Exception as e:
                print(f"[WS-SERVER] Erro ao fechar servidor: {e}", file=sys.stderr)
            self._server = None

        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        print("[WS-SERVER] Servidor WebSocket parado.", file=sys.stderr)

    # ------------------------------------------------------------------
    # Handlers de conexão (websockets library)
    # ------------------------------------------------------------------

    async def _handle_client(self, ws: Any) -> None:
        """Handler para cada conexão WebSocket (websockets lib)."""
        self._clients.add(ws)
        client_addr = getattr(ws, "remote_address", ("unknown", 0))
        client_addr_str = f"{client_addr[0]}:{client_addr[1]}"
        print(f"[WS-SERVER] Cliente conectado: {client_addr_str}", file=sys.stderr)

        try:
            async for message in ws:
                try:
                    msg = json.loads(message)
                except json.JSONDecodeError:
                    print(f"[WS-SERVER] JSON inválido: {message[:200]}", file=sys.stderr)
                    continue
                await self._handle_message(msg, ws)
        except websockets.exceptions.ConnectionClosed as e:
            print(
                f"[WS-SERVER] Conexão fechada: {client_addr_str} (code={e.code})", file=sys.stderr
            )
        except Exception as e:
            print(f"[WS-SERVER] Erro no handler: {e}", file=sys.stderr)
        finally:
            self._clients.discard(ws)
            print(f"[WS-SERVER] Cliente desconectado: {client_addr_str}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Servidor built-in (asyncio puro) — fallback se websockets não estiver instalado
    # ------------------------------------------------------------------

    async def _start_builtin_server(self) -> None:
        """Servidor WebSocket mínimo usando asyncio puro (RFC 6455)."""
        import base64
        import hashlib
        import struct

        guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

        async def _handle_builtin_client(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            addr = writer.get_extra_info("peername")
            print(f"[WS-SERVER] Cliente builtin conectado: {addr}", file=sys.stderr)

            # Handshake HTTP
            try:
                header_lines = []
                while True:
                    line = await asyncio.wait_for(reader.readline(), timeout=5)
                    if line == b"\r\n":
                        break
                    header_lines.append(line.decode().strip())

                request_line = header_lines[0] if header_lines else ""
                headers = {}
                for line in header_lines[1:]:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        headers[k.strip().lower()] = v.strip()

                origin = headers.get("origin", "")
                # In restricted mode, require chrome-extension origin (no empty origins)
                if RestrictedProfile.is_active():
                    if not origin:
                        writer.write(
                            b"HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\n\r\nOrigin required in restricted mode.\r\n"
                        )
                        await writer.drain()
                        writer.close()
                        await writer.wait_closed()
                        return
                    if not origin.startswith("chrome-extension://"):
                        writer.write(
                            b"HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\n\r\nOnly chrome-extension origins allowed in restricted mode.\r\n"
                        )
                        await writer.drain()
                        writer.close()
                        await writer.wait_closed()
                        return
                elif origin and not origin.startswith("chrome-extension://"):
                    writer.write(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                    return

                provided = None
                auth = headers.get("authorization", "")
                if auth.lower().startswith("bearer "):
                    provided = auth[7:].strip()
                if provided is None:
                    proto = headers.get("sec-websocket-protocol", "")
                    for p in proto.split(","):
                        p = p.strip()
                        if p.startswith("mcp-token."):
                            provided = p[len("mcp-token.") :]
                            break
                if provided is None:
                    with contextlib.suppress(Exception):
                        path = request_line.split(" ")[1]
                        if "?" in path:
                            qs = parse_qs(path.split("?", 1)[1])
                            provided = (qs.get("token") or [None])[0]

                if not provided or not hmac.compare_digest(provided, self._token):
                    # In restricted mode, token is mandatory with explicit message
                    if RestrictedProfile.is_active() and not provided:
                        writer.write(
                            b"HTTP/1.1 401 Unauthorized\r\n"
                            b"Content-Type: text/plain\r\n\r\n"
                            b"Token required in restricted mode. "
                            b"Provide via Authorization: Bearer <token> or ?token=<token> query param.\r\n"
                        )
                    else:
                        writer.write(b"HTTP/1.1 401 Unauthorized\r\n\r\n")
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                    return

                key = None
                for line in header_lines:
                    if line.lower().startswith("sec-websocket-key:"):
                        key = line.split(":", 1)[1].strip()
                        break

                if not key:
                    writer.close()
                    await writer.wait_closed()
                    return

                accept = base64.b64encode(hashlib.sha1((key + guid).encode()).digest()).decode()

                response = (
                    "HTTP/1.1 101 Switching Protocols\r\n"
                    "Upgrade: websocket\r\n"
                    "Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Accept: {accept}\r\n"
                    "\r\n"
                )
                writer.write(response.encode())
                await writer.drain()

            except Exception as e:
                print(f"[WS-SERVER] Handshake falhou: {e}", file=sys.stderr)
                writer.close()
                await writer.wait_closed()
                return

            # Wrapper para compatibilidade
            class _BuiltinWS:
                def __init__(self, r, w):
                    self.reader = r
                    self.writer = w
                    self.closed = False

                async def send(self, text: str) -> None:
                    if self.closed:
                        return
                    data = text.encode("utf-8")
                    length = len(data)
                    if length < 126:
                        header = struct.pack("!BB", 0x81, length)
                    elif length < 65536:
                        header = struct.pack("!BBH", 0x81, 126, length)
                    else:
                        header = struct.pack("!BBQ", 0x81, 127, length)
                    self.writer.write(header + data)
                    await self.writer.drain()

                async def close(self) -> None:
                    if not self.closed:
                        self.closed = True
                        try:
                            self.writer.write(struct.pack("!BB", 0x88, 0))
                            await self.writer.drain()
                        except Exception:
                            pass
                        self.writer.close()
                        await self.writer.wait_closed()

            ws_wrapper = _BuiltinWS(reader, writer)
            self._clients.add(ws_wrapper)

            try:
                while self._running and not ws_wrapper.closed:
                    try:
                        # Read frame header
                        first = await asyncio.wait_for(reader.read(1), timeout=60)
                        if not first:
                            break
                        opcode = first[0] & 0x0F

                        if opcode == 0x8:  # close
                            break
                        if opcode == 0x9:  # ping
                            # Send pong
                            ws_wrapper.writer.write(struct.pack("!BB", 0x8A, 0))
                            await ws_wrapper.writer.drain()
                            continue
                        if opcode == 0xA:  # pong
                            continue
                        if opcode not in (0x1, 0x2):  # text or binary
                            continue

                        second = await asyncio.wait_for(reader.read(1), timeout=5)
                        masked = bool(second[0] & 0x80)
                        length = second[0] & 0x7F

                        if length == 126:
                            length = struct.unpack("!H", await reader.readexactly(2))[0]
                        elif length == 127:
                            length = struct.unpack("!Q", await reader.readexactly(8))[0]

                        if length > MAX_PAYLOAD_SIZE:
                            print(
                                f"[WS-SERVER] Payload muito grande ({length} bytes), fechando conexão",
                                file=sys.stderr,
                            )
                            break

                        if masked:
                            mask = await reader.readexactly(4)
                            payload = bytearray(await reader.readexactly(length))
                            for i in range(len(payload)):
                                payload[i] ^= mask[i % 4]
                            payload = bytes(payload)
                        else:
                            payload = await reader.readexactly(length)

                        if opcode == 0x1:
                            try:
                                msg = json.loads(payload.decode("utf-8"))
                                await self._handle_message(msg, ws_wrapper)
                            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                                print(f"[WS-SERVER] JSON inválido: {e}", file=sys.stderr)
                    except TimeoutError:
                        continue
                    except Exception as e:
                        print(f"[WS-SERVER] Erro no frame: {e}", file=sys.stderr)
                        break
            finally:
                self._clients.discard(ws_wrapper)
                with contextlib.suppress(Exception):
                    await ws_wrapper.close()
                print(f"[WS-SERVER] Cliente builtin desconectado: {addr}", file=sys.stderr)

        srv = await asyncio.start_server(_handle_builtin_client, self.host, self.port)
        self._server = srv
        try:
            await srv.serve_forever()
        except asyncio.CancelledError:
            pass
        finally:
            srv.close()
            await srv.wait_closed()

    # ------------------------------------------------------------------
    # Processamento de mensagens
    # ------------------------------------------------------------------

    async def _handle_message(self, msg: dict[str, Any], ws: Any) -> None:
        """Processa uma mensagem recebida de um cliente WebSocket."""
        msg_type = msg.get("type")

        # In restricted mode, sanitize log output (no full code, no token, no DOM)
        if RestrictedProfile.is_active():
            msg = RestrictedProfile.sanitize_log_dict(msg)

        print(f"[WS-SERVER] Recebido: {msg_type}", file=sys.stderr)

        if msg_type == "hello":
            print(
                f"[WS-SERVER] Cliente hello: {msg.get('source')} v{msg.get('version')}",
                file=sys.stderr,
            )
            # Responde com welcome para manter a conexão viva
            await self.send_to_client(ws, {"type": "welcome", "server": "browser-mcp-server"})

        elif msg_type == "identify":
            print(
                f"[WS-SERVER] Cliente identificado: {msg.get('client')} v{msg.get('version')}",
                file=sys.stderr,
            )
            # Envia config de volta
            await self.send_to_client(
                ws, {"type": "config", "wsUrl": f"ws://{self.host}:{self.port}"}
            )

        elif msg_type == "event":
            event_type = msg.get("eventType")
            data = msg.get("data", {})
            for callback in self._event_callbacks:
                try:
                    callback(event_type, data)
                except Exception as e:
                    print(f"[WS-SERVER] Erro no callback de evento: {e}", file=sys.stderr)
            # Also forward event to all other clients (Python clients want to see events)
            for client in list(self._clients):
                if client is not ws:
                    await self.send_to_client(client, msg)

        elif msg_type == "request":
            # Extensão pedindo ação ao servidor — processa via callback registrado
            tool = msg.get("tool")
            params = msg.get("params", {})
            req_id = msg.get("id", str(uuid.uuid4()))
            for callback in self._command_callbacks.values():
                try:
                    result = await callback(tool, params)
                    await self.send_to_client(
                        ws, {"type": "response", "id": req_id, "result": result}
                    )
                except Exception as e:
                    await self.send_to_client(
                        ws, {"type": "response", "id": req_id, "error": str(e)}
                    )

        elif msg_type == "command":
            # Cliente (ex: Python) envia comando para a extensão executar
            # Reenviar para todos os outros clientes (extensão Chrome)
            sent = 0
            for client in list(self._clients):
                if client is not ws and await self.send_to_client(client, msg):
                    sent += 1
            if sent == 0:
                print("[WS-SERVER] Nenhum cliente destino para o comando", file=sys.stderr)

        elif msg_type == "response":
            # Resposta a um comando — encaminhar para todos os outros clientes
            req_id = msg.get("id")
            fut = self._pending_responses.pop(req_id, None)
            if fut and not fut.done():
                if msg.get("error"):
                    fut.set_exception(RuntimeError(msg["error"]))
                else:
                    fut.set_result(msg.get("result"))

            # Reenviar a resposta para TODOS os clientes (menos o remetente)
            for client in list(self._clients):
                if client is not ws:
                    ok = await self.send_to_client(client, msg)
                    print(
                        f"[WS-SERVER] Resposta {req_id} para cliente: {'OK' if ok else 'FALHA'}",
                        file=sys.stderr,
                    )

        elif msg_type == "pong":
            # Keep-alive response
            pass

        elif msg_type == "ping":
            await self.send_to_client(ws, {"type": "pong"})

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    async def broadcast(self, message: dict[str, Any]) -> int:
        """Envia mensagem para todos os clientes conectados. Retorna número de envios."""
        if not self._clients:
            return 0
        sent = 0
        text = json.dumps(message, ensure_ascii=False, default=str)
        for client in list(self._clients):
            try:
                if HAS_WEBSOCKETS and hasattr(client, "send"):
                    await client.send(text)
                else:
                    await client.send(text)
                sent += 1
            except Exception as e:
                print(f"[WS-SERVER] Erro ao broadcast: {e}", file=sys.stderr)
                self._clients.discard(client)
        return sent

    async def send_to_client(self, ws: Any, message: dict[str, Any]) -> bool:
        """Envia mensagem para um cliente específico."""
        try:
            text = json.dumps(message, ensure_ascii=False, default=str)
            if HAS_WEBSOCKETS and hasattr(ws, "send"):
                await ws.send(text)
            else:
                await ws.send(text)
            return True
        except Exception as e:
            print(f"[WS-SERVER] Erro ao enviar para cliente: {e}", file=sys.stderr)
            return False

    def on_event(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """Registra um callback para eventos recebidos da extensão."""
        self._event_callbacks.append(callback)

    def on_command(self, name: str, callback: Callable[[str, dict[str, Any]], Any]) -> None:
        """Registra um callback para requests da extensão."""
        self._command_callbacks[name] = callback

    def remove_command_callback(self, name: str) -> None:
        """Remove um callback de comando."""
        self._command_callbacks.pop(name, None)

    async def execute_command(
        self, tool: str, params: dict[str, Any], timeout: float = 10.0
    ) -> Any:
        """Envia um comando para a extensão e aguarda a resposta."""
        if not self._clients:
            raise RuntimeError("Nenhuma extensão conectada")

        req_id = str(uuid.uuid4())
        fut = asyncio.get_running_loop().create_future()
        self._pending_responses[req_id] = fut

        message = {"type": "command", "id": req_id, "tool": tool, "params": params}

        try:
            await self.broadcast(message)
            return await asyncio.wait_for(fut, timeout=timeout)
        except TimeoutError as e:
            raise TimeoutError(f"Timeout ao aguardar resposta da extensão para {tool}") from e
        finally:
            self._pending_responses.pop(req_id, None)

    def is_connected(self) -> bool:
        """Retorna True se há pelo menos uma extensão conectada."""
        return len(self._clients) > 0

    def get_client_count(self) -> int:
        """Retorna o número de clientes conectados."""
        return len(self._clients)


# Singleton global
websocket_server = WebSocketServer()
