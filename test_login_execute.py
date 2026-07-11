#!/usr/bin/env python3
"""Teste de Login no i-Educar Demo.

1. Clica em "Acessar" do i-Educar
2. Preenche Matrícula e Senha
3. Clica no botão de login
4. Verifica resultado
"""
import asyncio
import sys

sys.path.insert(0, "/Users/felipecc/Documents/Kimi/Workspaces/mcp_browser/src")

from browser_mcp.websocket_server import websocket_server
from browser_mcp.extension_bridge import extension_bridge
from browser_mcp.browser_manager import BrowserManager


async def main():
    print("=" * 60)
    print("TESTE: Login no i-Educar Demo")
    print("=" * 60)
    print("\n⚠️  IMPORTANTE:")
    print("   Certifique-se de que a extensão MCP Browser está 'Conectado'")
    print("=" * 60)

    # Inicia servidor
    await websocket_server.start()
    await asyncio.sleep(2)
    await extension_bridge.initialize(websocket_server)

    # Aguarda extensão
    print("\n[1] Aguardando extensão...")
    for i in range(60):
        await asyncio.sleep(1)
        if websocket_server.is_connected():
            print(f"   ✅ Extensão conectada!")
            break
    else:
        print("   ❌ Extensão não conectou")
        return

    await asyncio.sleep(2)

    bm = BrowserManager()
    await bm.connect_to_extension()
    await asyncio.sleep(1)

    # 1. Navega para a página de demo
    print("\n[2] Navegando para https://ieducar.org/demo.html...")
    try:
        result = await bm.navigate("https://ieducar.org/demo.html")
        print(f"   ✅ {result}")
    except Exception as e:
        print(f"   ❌ {e}")

    await asyncio.sleep(3)

    # 2. Navega diretamente para a página de login do i-Educar
    print("\n[3] Navegando para a página de login...")
    try:
        result = await bm.navigate("https://comunidade.ieducar.com.br/")
        print(f"   ✅ {result}")
    except Exception as e:
        print(f"   ❌ {e}")

    await asyncio.sleep(5)

    # 3. Verifica URL atual
    print("\n[4] URL atual:")
    try:
        url = await bm.get_url()
        print(f"   {url}")
    except Exception as e:
        print(f"   ❌ {e}")

    # 4. Obtém conteúdo para encontrar campos de login
    print("\n[5] Analisando página de login...")
    try:
        result = await bm.get_content()
        print(f"   Texto encontrado:\n{result[:1000]}")
    except Exception as e:
        print(f"   ❌ {e}")

    # 5. Obtém DOM snapshot para encontrar os campos
    print("\n[5.1] Obtendo DOM snapshot para encontrar campos...")
    try:
        result = await bm.extension_get_dom_snapshot()
        try:
            import json
            data = json.loads(result)
            elements = data.get('elements', [])
            print(f"   Elementos encontrados: {len(elements)}")
            for el in elements:
                if el.get('tag') in ('input', 'button'):
                    print(f"     {el}")
        except Exception as e:
            print(f"   Erro ao parse: {e}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")

    # 6. Tenta preencher o campo de matrícula/usuário
    print("\n[6] Preenchendo credenciais...")
    
    # O campo de matrícula tem id="login" e name="login"
    try:
        result = await bm.type_text("input[name='login']", "comunidade", clear=True, by="css")
        print(f"   ✅ Matrícula preenchida (name='login'): {result}")
    except Exception as e:
        print(f"   ⚠️ Erro matrícula por name: {e}")
        # Tenta por id
        try:
            result = await bm.type_text("input[id='login']", "comunidade", clear=True, by="css")
            print(f"   ✅ Matrícula preenchida (id='login'): {result}")
        except Exception as e2:
            print(f"   ❌ Erro matrícula: {e2}")

    await asyncio.sleep(1)

    # Preenche senha
    try:
        result = await bm.type_text("input[type='password']", "Comunidade@1", clear=True, by="css")
        print(f"   ✅ Senha preenchida: {result}")
    except Exception as e:
        print(f"   ❌ Erro senha: {e}")

    await asyncio.sleep(1)

    # 6. Clica no botão de login
    print("\n[7] Clicando no botão de login...")
    try:
        result = await bm.click("button[type='submit']", by="css")
        print(f"   ✅ {result}")
    except Exception as e:
        print(f"   ⚠️ Erro submit: {e}")
        # Tenta qualquer botão
        try:
            result = await bm.click("button", by="css")
            print(f"   ✅ Botão clicado (fallback): {result}")
        except Exception as e2:
            print(f"   ❌ Erro botão: {e2}")

    await asyncio.sleep(5)

    # 7. Verifica resultado
    print("\n[8] Verificando resultado...")
    try:
        url = await bm.get_url()
        title = await bm.get_title()
        print(f"   URL: {url}")
        print(f"   Título: {title}")
        
        if "login" in url.lower() or "login" in title.lower():
            print("   ⚠️ Ainda na página de login — login pode ter falhado")
        else:
            print("   ✅ Login bem-sucedido! Página pós-login carregada.")
    except Exception as e:
        print(f"   ❌ {e}")

    # 8. Conteúdo final
    print("\n[9] Conteúdo da página atual:")
    try:
        result = await bm.get_content()
        print(f"   {result[:1500]}...")
    except Exception as e:
        print(f"   ❌ {e}")

    print("\n✅ Teste concluído!")
    await bm.disconnect_extension()
    await websocket_server.stop()


if __name__ == "__main__":
    asyncio.run(main())
