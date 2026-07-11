"""Teste do modo extension — conecta via extensão Chrome e executa ações."""
import asyncio
import json
import sys

sys.path.insert(0, "/Users/felipecc/Documents/Kimi/Workspaces/mcp_browser/src")

from browser_mcp.browser_manager import BrowserManager


async def main():
    bm = BrowserManager()

    print("=" * 60)
    print("TESTE 2: Modo Extension via Chrome Extension")
    print("=" * 60)

    # 1. Conectar ao modo extension
    print("\n[1/5] Conectando ao modo extension...")
    try:
        result = await bm.connect_to_extension()
        print(f"✅ {result}")
    except Exception as e:
        print(f"❌ Erro ao conectar: {type(e).__name__}: {e}")
        return

    # 2. Navegar para exemplo
    print("\n[2/5] Navegando para https://example.com...")
    try:
        result = await bm.navigate("https://example.com")
        print(f"✅ {result}")
    except Exception as e:
        print(f"❌ Erro ao navegar: {type(e).__name__}: {e}")
        # Continua para tentar outras ações

    # Aguarda carregamento
    await asyncio.sleep(2)

    # 3. Obter URL e título
    print("\n[3/5] Obtendo URL e título...")
    try:
        url = await bm.get_current_url()
        title = await bm.get_current_title()
        print(f"✅ URL: {url}")
        print(f"✅ Título: {title}")
    except Exception as e:
        print(f"❌ Erro: {type(e).__name__}: {e}")

    # 4. Tirar screenshot
    print("\n[4/5] Capturando screenshot...")
    try:
        screenshot_result = await bm.screenshot()
        # screenshot_result pode ser um dict com dataUrl ou outro formato
        print(f"✅ Screenshot capturado (tipo: {type(screenshot_result).__name__})")
        if isinstance(screenshot_result, dict) and "dataUrl" in screenshot_result:
            data_url = screenshot_result["dataUrl"]
            if len(data_url) > 100:
                print(f"   Data URL: {data_url[:80]}...")
            # Salva o screenshot
            import base64
            header, b64 = data_url.split(",", 1)
            img_data = base64.b64decode(b64)
            path = "/Users/felipecc/Documents/Kimi/Workspaces/mcp_browser/screenshot_test.png"
            with open(path, "wb") as f:
                f.write(img_data)
            print(f"   💾 Salvo em: {path}")
        elif isinstance(screenshot_result, str) and screenshot_result.startswith("data:"):
            import base64
            header, b64 = screenshot_result.split(",", 1)
            img_data = base64.b64decode(b64)
            path = "/Users/felipecc/Documents/Kimi/Workspaces/mcp_browser/screenshot_test.png"
            with open(path, "wb") as f:
                f.write(img_data)
            print(f"   💾 Salvo em: {path}")
        else:
            print(f"   Resultado: {str(screenshot_result)[:200]}")
    except Exception as e:
        print(f"❌ Erro no screenshot: {type(e).__name__}: {e}")
        traceback.print_exc()

    # 5. Obter DOM snapshot
    print("\n[5/5] Obtendo DOM snapshot...")
    try:
        snapshot = await bm.extension_get_dom_snapshot()
        if isinstance(snapshot, dict):
            print(f"✅ Snapshot obtido:")
            print(f"   URL: {snapshot.get('url', 'N/A')}")
            print(f"   Título: {snapshot.get('title', 'N/A')}")
            elements = snapshot.get('elements', [])
            print(f"   Elementos: {len(elements)}")
            if elements:
                for i, el in enumerate(elements[:3]):
                    print(f"     [{i}] {el.get('tag', '?')} — {el.get('text', '')[:40]}")
        else:
            print(f"✅ Resultado: {str(snapshot)[:200]}")
    except Exception as e:
        print(f"❌ Erro no DOM snapshot: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # Desconectar
    print("\n[Cleanup] Desconectando...")
    await bm.disconnect_extension()
    print("✅ Teste concluído!")


if __name__ == "__main__":
    import traceback
    asyncio.run(main())
