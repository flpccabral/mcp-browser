#!/usr/bin/env python3
"""Cliente WebSocket para controlar a extensão Chrome via servidor standalone."""

import asyncio
import json
import sys


async def send_command(tool: str, params: dict | None = None, timeout: float = 10) -> dict:
    """Envia comando para a extensão Chrome via WebSocket."""
    try:
        import websockets
        async with websockets.connect("ws://localhost:8765") as ws:
            cmd = json.dumps({"tool": tool, "params": params or {}})
            await ws.send(cmd)
            resp = await asyncio.wait_for(ws.recv(), timeout=timeout)
            return json.loads(resp)
    except ImportError:
        # Fallback: usar subprocess para curl via websocat ou python puro
        return {"error": "websockets library not available"}


async def main():
    if len(sys.argv) < 2:
        print("Uso: python ws_client.py <tool> [params_json]")
        print("Ex:   python ws_client.py navigate '{\"url\":\"https://example.com\"}'")
        sys.exit(1)

    tool = sys.argv[1]
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    result = await send_command(tool, params)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
