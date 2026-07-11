"""Teste do agente autônomo usando navegador real do Chrome via extensão.

Este script:
1. Inicia o WebSocket server
2. Conecta a extensão Chrome
3. Cria um agente com browser_manager em modo extension
4. Executa uma tarefa simples de navegação e extração
"""
import asyncio
import os
import sys

# Carrega .env antes de importar os módulos
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, "/Users/felipecc/Documents/Kimi/Workspaces/mcp_browser/src")

from browser_mcp.websocket_server import websocket_server
from browser_mcp.extension_bridge import extension_bridge
from browser_mcp.browser_manager import BrowserManager
from browser_mcp.llm_client import LLMClient
from browser_mcp.agent import BrowserAgent


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
    print("TESTE: Agente Autônomo via Extensão Chrome")
    print("=" * 60)
    print("\n⚠️  IMPORTANTE:")
    print("   1. Certifique-se de que a extensão MCP Browser no Chrome está")
    print("      recarregada (chrome://extensions/ → clique ↻)")
    print("   2. Abra uma aba normal no Chrome (não chrome://)")
    print("   3. O agente vai navegar para example.com e extrair informações")
    print("=" * 60)

    # 1. Inicia WebSocket server
    print("\n[1/4] Iniciando WebSocket server...")
    await websocket_server.start()
    print(f"   ✅ WebSocket server em ws://localhost:8765")
    await asyncio.sleep(2)

    # 2. Inicia Extension Bridge
    print("\n[2/4] Iniciando Extension Bridge...")
    await extension_bridge.initialize(websocket_server)
    print(f"   ✅ Bridge inicializado")

    # 3. Aguarda extensão conectar
    print("\n[3/4] Aguardando extensão Chrome...")
    connected = await wait_for_extension(timeout=30)
    if not connected:
        print("\n❌ Teste abortado: extensão não conectou.")
        await websocket_server.stop()
        return

    await asyncio.sleep(2)

    # 4. Conecta browser_manager ao modo extension
    print("\n[4/4] Configurando browser_manager para modo extension...")
    bm = BrowserManager()
    result = await bm.connect_to_extension()
    print(f"   {result}")

    # 5. Inicializa LLM client
    print("\n[5/5] Inicializando LLM client...")
    llm = LLMClient()
    await llm.initialize()
    print(f"   ✅ LLM client pronto")

    # 6. Cria agente e executa tarefa
    print("\n" + "=" * 60)
    print("🤖 EXECUTANDO TAREFA DO AGENTE")
    print("=" * 60)
    
    output_dir = "/Users/felipecc/Documents/Kimi/Workspaces/mcp_browser/agent_output_extension"
    os.makedirs(output_dir, exist_ok=True)

    agent = BrowserAgent(
        browser_manager=bm,
        llm_client=llm,
        max_iterations=10,
        max_consecutive_errors=2,
        screenshot_on_action=False,  # Screenshot não funciona no modo extension
        output_dir=output_dir,
    )

    task = """Navigate to https://comunidade.ieducar.com.br and explore the website.

Extract and summarize:
1. What is i-Educar? (main purpose, target audience)
2. What features or modules are mentioned on the site?
3. Any pricing or plan information
4. How to contact or get support
5. Any testimonials or case studies mentioned

Return a comprehensive summary in Portuguese."""

    print(f"\n📋 Tarefa: {task}")
    print("\n⏳ Executando (pode levar 1-2 minutos)...")

    try:
        result = await agent.execute_task(task)
        
        print("\n" + "=" * 60)
        print("📊 RESULTADO DO AGENTE")
        print("=" * 60)
        print(f"\n✅ Sucesso: {result.get('success', False)}")
        print(f"📝 Ações executadas: {result.get('action_count', 0)}")
        print(f"🖼️ Screenshots: {len(result.get('screenshots', []))}")
        print(f"❌ Erros: {len(result.get('errors', []))}")
        
        if result.get('errors'):
            print(f"\n⚠️ Erros encontrados:")
            for err in result['errors']:
                print(f"   - {err}")
        
        print(f"\n📄 Relatório:")
        report = result.get('report', 'Nenhum relatório gerado.')
        print(report[:2000] if len(report) > 2000 else report)
        
        # Salva relatório
        report_path = os.path.join(output_dir, "report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n💾 Relatório salvo em: {report_path}")
        
    except Exception as e:
        print(f"\n❌ Erro durante execução do agente: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # Cleanup
    print("\n[Cleanup] Encerrando...")
    await bm.disconnect_extension()
    await websocket_server.stop()
    print("✅ Teste concluído!")


if __name__ == "__main__":
    asyncio.run(main())
