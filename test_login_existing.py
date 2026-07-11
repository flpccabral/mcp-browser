#!/usr/bin/env python3
"""Teste direto — Login no i-Educar Demo.

Conecta ao servidor WebSocket existente (standalone) e executa o teste.
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
    print("\n⚠️  IMPORTANTE:")
    print("   Certifique-se de que a extensão MCP Browser no Chrome")
    print("   mostra 'Conectado'. Se não, clique em 'Reconectar Servidor'")
    print("=" * 60)

    # Conecta ao servidor WebSocket existente (standalone)
    print("\n[1] Conectando ao servidor WebSocket existente...")
    await websocket_server.start()
    await asyncio.sleep(2)
    print(f"   ✅ Servidor: {websocket_server.is_running()}")
    print(f"   👥 Clientes: {websocket_server.get_client_count()}")

    # Inicia bridge
    await extension_bridge.initialize(websocket_server)
    print("   ✅ Bridge inicializado")

    # Aguarda extensão
    print("\n[2] Aguardando extensão Chrome...")
    for i in range(60):
        await asyncio.sleep(1)
        if websocket_server.is_connected():
            print(f"   ✅ Extensão conectada! ({websocket_server.get_client_count()} cliente)")
            break
        print(f"   {i+1}s...", end="\r")
    else:
        print("\n   ❌ Extensão não conectou")
        return

    await asyncio.sleep(2)

    # Conecta browser_manager
    print("\n[3] Configurando browser_manager...")
    bm = BrowserManager()
    result = await bm.connect_to_extension()
    print(f"   {result}")
    await asyncio.sleep(2)

    # Navega para demo
    print("\n[4] Navegando para https://ieducar.org/demo.html...")
    try:
        result = await bm.navigate("https://ieducar.org/demo.html")
        print(f"   ✅ {result}")
    except Exception as e:
        print(f"   ❌ {e}")

    await asyncio.sleep(5)

    # Extrai conteúdo
    print("\n[5] Extraindo conteúdo da página...")
    try:
        result = await bm.execute_javascript("""
        () => {
            const text = document.body.innerText;
            return {
                url: window.location.href,
                title: document.title,
                text: text.substring(0, 3000)
            };
        }
        """)
        print(f"   Resultado:")
        try:
            data = json.loads(result)
            print(f"   URL: {data.get('url', 'N/A')}")
            print(f"   Título: {data.get('title', 'N/A')}")
            print(f"   Texto:\n{data.get('text', 'N/A')[:1000]}")
        except:
            print(f"   {result[:500]}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")

    # Procura elementos de login
    print("\n[6] Procurando campos de login...")
    try:
        result = await bm.execute_javascript("""
        () => {
            const inputs = Array.from(document.querySelectorAll('input, button, a'));
            return inputs.map(el => ({
                tag: el.tagName.toLowerCase(),
                type: el.type,
                name: el.name,
                id: el.id,
                text: el.innerText?.trim() || el.value || '',
                href: el.href || null
            })).filter(el => el.text || el.name || el.id);
        }
        """)
        try:
            elements = json.loads(result)
            print(f"   Elementos encontrados:")
            for el in elements[:20]:
                print(f"     {el}")
        except:
            print(f"   {result[:500]}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")

    print("\n✅ Teste concluído!")


if __name__ == "__main__":
    asyncio.run(main())
