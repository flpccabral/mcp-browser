#!/usr/bin/env python3
"""Servidor WebSocket standalone para a extensão Chrome MCP Browser Bridge.

Este script inicia APENAS o WebSocket server (sem stdio_server MCP)
para manter a porta 8765 aberta enquanto a extensão se conecta.

Uso:
    python websocket_server_standalone.py

O servidor permanece ativo até receber Ctrl+C.
"""
import asyncio
import sys

sys.path.insert(0, "/Users/felipecc/Documents/kimi/workspaces/mcp_browser/src")

from browser_mcp.websocket_server import websocket_server


async def main():
    print("=" * 60)
    print("WebSocket Server Standalone — MCP Browser Bridge")
    print("=" * 60)
    print("Iniciando servidor em ws://localhost:8765...")
    print("Pressione Ctrl+C para encerrar.\n")

    await websocket_server.start()

    # Mantém o servidor vivo indefinidamente
    last_count = -1
    try:
        while True:
            await asyncio.sleep(1)
            count = websocket_server.get_client_count()
            if count != last_count:
                print(f"[WS] Clientes: {count}", file=sys.stderr)
                last_count = count
    except KeyboardInterrupt:
        print("\nEncerrando servidor...")
        await websocket_server.stop()
        print("Servidor encerrado.")


if __name__ == "__main__":
    asyncio.run(main())
