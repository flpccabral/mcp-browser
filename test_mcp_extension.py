"""Teste do modo extension via cliente MCP stdio.

Este script conecta ao servidor MCP via stdio e executa ferramentas
para testar a cadeia completa:
  Cliente MCP → Servidor stdio → WebSocket → Extensão Chrome → Página web
"""
import asyncio
import json
import sys

sys.path.insert(0, "/Users/felipecc/Documents/Kimi/Workspaces/mcp_browser/src")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def wait_for_extension(session, timeout=30):
    """Aguarda a extensão Chrome conectar ao servidor WebSocket.
    
    Tenta browser_get_url que realmente requer comunicação com a extensão.
    """
    print(f"   Aguardando extensão conectar (até {timeout}s)...")
    for i in range(timeout):
        await asyncio.sleep(1)
        try:
            result = await session.call_tool("browser_get_url", {})
            text = result.content[0].text
            if "ERROR" not in text and "RuntimeError" not in text and "Nenhuma extensão" not in text:
                print(f"   ✅ Extensão conectada após {i+1}s! URL atual: {text}")
                return True
        except Exception as e:
            print(f"   Tentativa {i+1}: {type(e).__name__}: {e}")
    print(f"   ⚠️ Extensão não conectou após {timeout}s")
    return False


async def main():
    print("=" * 60)
    print("TESTE 2: Modo Extension via Cliente MCP stdio")
    print("=" * 60)
    print("\n⚠️  IMPORTANTE: Certifique-se de que a extensão MCP Browser")
    print("   no Chrome mostra 'Conectado' antes de continuar.")
    print("   Se mostrar 'Desconectado', clique em 'Reconectar Servidor'.")
    print("=" * 60)

    server_params = StdioServerParameters(
        command="/Users/felipecc/Documents/Kimi/Workspaces/mcp_browser/.venv/bin/python",
        args=["-m", "browser_mcp.server"],
        env={"BROWSER_HEADLESS": "false"},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("\n✅ Conectado ao servidor MCP via stdio")

            # 1. Listar ferramentas
            tools_result = await session.list_tools()
            print(f"\n[1/6] Ferramentas disponíveis: {len(tools_result.tools)}")

            # 2. Conectar ao modo extension
            print("\n[2/6] Ativando modo extension...")
            result = await session.call_tool(
                "browser_connect_to_extension",
                {"ws_url": "ws://localhost:8765"},
            )
            print(f"   {result.content[0].text}")

            # Aguarda extensão conectar
            connected = await wait_for_extension(session, timeout=30)
            if not connected:
                print("\n❌ Teste abortado: extensão não conectou.")
                print("   Dica: Clique no ícone da extensão no Chrome e em 'Reconectar Servidor'")
                return

            # Aguarda mais 2s para estabilizar
            await asyncio.sleep(2)

            # 3. Navegar para example.com
            print("\n[3/6] Navegando para https://example.com...")
            try:
                result = await session.call_tool(
                    "browser_navigate",
                    {"url": "https://example.com"},
                )
                print(f"   {result.content[0].text}")
            except Exception as e:
                print(f"   ❌ Erro: {type(e).__name__}: {e}")

            # Aguarda carregamento
            await asyncio.sleep(3)

            # 4. Obter URL e título
            print("\n[4/6] Obtendo URL e título...")
            try:
                result = await session.call_tool("browser_get_url", {})
                print(f"   URL: {result.content[0].text}")
            except Exception as e:
                print(f"   ❌ Erro URL: {type(e).__name__}: {e}")

            try:
                result = await session.call_tool("browser_get_title", {})
                print(f"   Título: {result.content[0].text}")
            except Exception as e:
                print(f"   ❌ Erro título: {type(e).__name__}: {e}")

            # 5. Tirar screenshot
            print("\n[5/6] Capturando screenshot...")
            try:
                result = await session.call_tool(
                    "browser_screenshot",
                    {"path": "/Users/felipecc/Documents/Kimi/Workspaces/mcp_browser/screenshot_mcp.png", "full_page": False},
                )
                text = result.content[0].text
                if len(text) > 200:
                    print(f"   {text[:150]}...")
                else:
                    print(f"   {text}")
            except Exception as e:
                print(f"   ❌ Erro screenshot: {type(e).__name__}: {e}")

            # 6. Obter DOM snapshot
            print("\n[6/6] Obtendo DOM snapshot...")
            try:
                result = await session.call_tool("browser_extension_get_dom_snapshot", {})
                text = result.content[0].text
                if len(text) > 500:
                    print(f"   {text[:400]}...")
                else:
                    print(f"   {text}")
            except Exception as e:
                print(f"   ❌ Erro DOM snapshot: {type(e).__name__}: {e}")

            # Desconectar
            print("\n[Cleanup] Desconectando...")
            try:
                result = await session.call_tool("browser_disconnect_extension", {})
                print(f"   {result.content[0].text}")
            except Exception as e:
                print(f"   ⚠️ Erro: {type(e).__name__}: {e}")

            print("\n" + "=" * 60)
            print("✅ Teste concluído!")
            print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
