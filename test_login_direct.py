"""Teste direto — Login no i-Educar Demo.

Inicia o WebSocket server internamente e executa o teste em um único processo.
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
    print("   1. Recarregue a extensão MCP Browser no Chrome")
    print("   2. Confirme que o popup mostra 'Conectado'")
    print("   3. Este servidor vai iniciar em ws://localhost:8765")
    print("=" * 60)

    # Inicia servidor
    print("\n[1] Iniciando WebSocket server...")
    await websocket_server.start()
    await asyncio.sleep(2)
    print("   ✅ Servidor em ws://localhost:8765")

    # Inicia bridge
    await extension_bridge.initialize(websocket_server)
    print("   ✅ Extension bridge inicializado")

    # Aguarda extensão conectar
    print("\n[2] Aguardando extensão Chrome conectar...")
    print("   (Certifique-se de que a extensão mostra 'Conectado')")
    for i in range(60):
        await asyncio.sleep(1)
        if websocket_server.is_connected():
            print(f"   ✅ Extensão conectada! ({websocket_server.get_client_count()} cliente)")
            break
        print(f"   {i+1}s...", end="\r")
    else:
        print("\n   ❌ Extensão não conectou em 60s")
        await websocket_server.stop()
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

    # Extrai conteúdo da página
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
            print(f"   Texto: {data.get('text', 'N/A')[:500]}...")
        except:
            print(f"   {result[:500]}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")

    # Procura campos de login
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
        print(f"   Elementos encontrados:")
        try:
            elements = json.loads(result)
            for el in elements[:20]:
                print(f"     {el}")
        except:
            print(f"   {result[:500]}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")

    # Cleanup
    print("\n[Cleanup] Encerrando...")
    await bm.disconnect_extension()
    await websocket_server.stop()
    print("✅ Teste concluído!")


if __name__ == "__main__":
    asyncio.run(main())
