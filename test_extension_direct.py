"""Teste do modo extension via WebSocket direto (sem stdio server).

Este script inicia apenas o WebSocket server e o ExtensionBridge,
e testa a comunicação com a extensão Chrome.
"""
import asyncio
import json
import sys

sys.path.insert(0, "/Users/felipecc/Documents/Kimi/Workspaces/mcp_browser/src")

from browser_mcp.websocket_server import websocket_server
from browser_mcp.extension_bridge import extension_bridge
from browser_mcp.browser_manager import BrowserManager


async def wait_for_extension(timeout=30):
    """Aguarda a extensão Chrome conectar ao WebSocket."""
    print(f"   Aguardando extensão conectar (até {timeout}s)...")
    for i in range(timeout):
        await asyncio.sleep(1)
        if websocket_server.is_connected():
            print(f"   ✅ Extensão conectada! ({websocket_server.get_client_count()} cliente(s))")
            return True
        print(f"   Tentativa {i+1}/{timeout}...", end="\r")
    print(f"\n   ⚠️ Extensão não conectou após {timeout}s")
    return False


async def main():
    print("=" * 60)
    print("TESTE 2: Modo Extension via WebSocket Direto")
    print("=" * 60)
    print("\n⚠️  IMPORTANTE: Certifique-se de que a extensão MCP Browser")
    print("   no Chrome mostra 'Conectado' antes de continuar.")
    print("=" * 60)

    # 1. Inicia apenas o WebSocket server
    print("\n[1/6] Iniciando WebSocket server...")
    await websocket_server.start()
    print(f"   ✅ WebSocket server em ws://localhost:8765")
    
    # Aguarda servidor estabilizar
    await asyncio.sleep(2)

    # 2. Inicia o extension bridge
    print("\n[2/6] Iniciando Extension Bridge...")
    await extension_bridge.initialize(websocket_server)
    print(f"   ✅ Bridge inicializado")

    # 3. Aguarda extensão conectar
    print("\n[3/6] Aguardando extensão Chrome...")
    connected = await wait_for_extension(timeout=30)
    if not connected:
        print("\n❌ Teste abortado: extensão não conectou.")
        print("   Dica: Recarregue a extensão no Chrome (chrome://extensions/)")
        await websocket_server.stop()
        return

    # Aguarda mais 2s para estabilizar
    await asyncio.sleep(2)

    # 4. Testa navegação
    print("\n[4/6] Navegando para https://example.com via extensão...")
    try:
        result = await extension_bridge.navigate("https://example.com")
        print(f"   ✅ Resultado: {result}")
    except Exception as e:
        print(f"   ❌ Erro: {type(e).__name__}: {e}")

    await asyncio.sleep(3)

    # 5. Obtém URL e título
    print("\n[5/6] Obtendo URL e título...")
    try:
        url = await extension_bridge.get_url()
        print(f"   ✅ URL: {url}")
    except Exception as e:
        print(f"   ❌ Erro URL: {type(e).__name__}: {e}")

    try:
        title = await extension_bridge.get_title()
        print(f"   ✅ Título: {title}")
    except Exception as e:
        print(f"   ❌ Erro título: {type(e).__name__}: {e}")

    # 6. Screenshot
    print("\n[6/6] Capturando screenshot...")
    try:
        result = await extension_bridge.screenshot()
        if isinstance(result, dict) and "dataUrl" in result:
            import base64
            data_url = result["dataUrl"]
            header, b64 = data_url.split(",", 1)
            img_data = base64.b64decode(b64)
            path = "/Users/felipecc/Documents/Kimi/Workspaces/mcp_browser/screenshot_extension.png"
            with open(path, "wb") as f:
                f.write(img_data)
            print(f"   ✅ Screenshot salvo em: {path}")
        else:
            print(f"   ✅ Resultado: {str(result)[:100]}...")
    except Exception as e:
        print(f"   ❌ Erro screenshot: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # Cleanup
    print("\n[Cleanup] Encerrando...")
    await websocket_server.stop()
    print("✅ Teste concluído!")


if __name__ == "__main__":
    asyncio.run(main())
