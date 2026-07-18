import asyncio
import contextlib
import signal
import sys

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from browser_mcp.browser_manager import browser_manager
from browser_mcp.llm_client import llm_client
from browser_mcp.tools import app
from browser_mcp.websocket_server import websocket_server

server = Server("browser-mcp-server")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Handler MCP: lista todas as ferramentas disponíveis."""
    return app.get_tools()


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handler MCP: executa uma ferramenta pelo nome."""
    try:
        return await app.call_tool(name, arguments)
    except Exception as e:
        return [types.TextContent(type="text", text=f"ERROR: [Server] - {str(e)}")]


async def _shutdown(signal_name: str):
    """Graceful shutdown: encerra browser, websocket server e finaliza processo."""
    print(f"[SERVER] Recebido {signal_name}. Encerrando...", file=sys.stderr)
    try:
        await browser_manager.stop()
    except Exception as e:
        print(f"[SERVER] Erro ao parar browser: {e}", file=sys.stderr)
    try:
        await websocket_server.stop()
    except Exception as e:
        print(f"[SERVER] Erro ao parar WebSocket server: {e}", file=sys.stderr)
    sys.exit(0)


async def _run_server():
    """Corrotina principal do servidor MCP.

    - Inicializa BrowserManager e LLMClient
    - Configura handlers de sinal (SIGINT / SIGTERM)
    - Inicia o stdio_server e aguarda conexões
    """
    loop = asyncio.get_running_loop()

    # Configurar handlers de sinal para graceful shutdown
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, ValueError):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(_shutdown(signal.Signals(s).name)),
            )

    print("[SERVER] Iniciando browser-mcp-server...", file=sys.stderr)
    try:
        await browser_manager.start()
        await llm_client.initialize()
        await websocket_server.start()
        print(
            "[SERVER] BrowserManager, LLMClient e WebSocketServer inicializados.", file=sys.stderr
        )
    except Exception as e:
        print(f"[SERVER] Aviso: Falha na inicialização opcional: {e}", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        print("[SERVER] Servidor stdio ativo. Aguardando conexões...", file=sys.stderr)
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Entry point síncrono (console script `browser-mcp-server`).

    Roda a corrotina do servidor com asyncio.run — o console script do
    pyproject aponta para cá, então precisa ser síncrono.
    """
    try:
        asyncio.run(_run_server())
    except KeyboardInterrupt:
        print("[SERVER] Interrompido pelo usuário.", file=sys.stderr)
    except Exception as e:
        print(f"[SERVER] Erro fatal: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
