#!/usr/bin/env python3
"""Teste direto — Login no i-Educar Demo (versão simples).

Usa get_content e get_dom_snapshot em vez de execute_javascript
para evitar problemas de CSP.
"""
import asyncio
import json
import sys

sys.path.insert(0, "/Users/felipecc/Documents/Kimi/Workspaces/mcp_browser/src")

from browser_mcp.websocket_server import websocket_server
from browser_mcp.extension_bridge import extension_bridge
from browser_mcp.browser_manager import BrowserManager


async def main():
    print("=" * 60)
    print("TESTE DIRETO: Login i-Educar Demo")
    print("=" * 60)

    # Inicia servidor
    await websocket_server.start()
    await asyncio.sleep(2)
    await extension_bridge.initialize(websocket_server)

    # Aguarda extensão
    print("Aguardando extensão...")
    for i in range(60):
        await asyncio.sleep(1)
        if websocket_server.is_connected():
            print(f"✅ Extensão conectada!")
            break
        print(f"{i+1}s...", end="\r")
    else:
        print("\n❌ Extensão não conectou")
        return

    await asyncio.sleep(2)

    bm = BrowserManager()
    await bm.connect_to_extension()
    await asyncio.sleep(1)

    # Navega para demo
    print("\n🌐 Navegando para https://ieducar.org/demo.html...")
    try:
        result = await bm.navigate("https://ieducar.org/demo.html")
        print(f"✅ {result}")
    except Exception as e:
        print(f"❌ {e}")

    await asyncio.sleep(5)

    # Obtém URL e título
    print("\n📄 URL e Título:")
    try:
        url = await bm.get_url()
        title = await bm.get_title()
        print(f"   URL: {url}")
        print(f"   Título: {title}")
    except Exception as e:
        print(f"   ❌ {e}")

    # Obtém conteúdo da página
    print("\n📝 Conteúdo da página (texto):")
    try:
        result = await bm.get_content()
        print(f"   {result[:1500]}...")
    except Exception as e:
        print(f"   ❌ {e}")

    # Obtém DOM snapshot
    print("\n🔍 DOM Snapshot:")
    try:
        result = await bm.extension_get_dom_snapshot()
        try:
            data = json.loads(result)
            print(f"   URL: {data.get('url', 'N/A')}")
            print(f"   Título: {data.get('title', 'N/A')}")
            elements = data.get('elements', [])
            print(f"   Elementos: {len(elements)}")
            for el in elements[:10]:
                print(f"     {el}")
        except:
            print(f"   {result[:500]}")
    except Exception as e:
        print(f"   ❌ {e}")

    print("\n✅ Teste concluído!")
    await bm.disconnect_extension()
    await websocket_server.stop()


if __name__ == "__main__":
    asyncio.run(main())
