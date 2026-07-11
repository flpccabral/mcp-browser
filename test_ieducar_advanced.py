#!/usr/bin/env python3
"""Teste avançado: Login i-Educar + navegação até Faltas e Notas + captura AJAX.

Este script roda com BROWSER_HEADLESS=false para que o usuário possa ver
o navegador em tempo real.
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from browser_mcp.browser_manager import browser_manager
from browser_mcp.llm_client import LLMClient
from browser_mcp.agent import BrowserAgent


async def main():
    print("=" * 70)
    print("🧪 TESTE AVANÇADO: i-Educar + Lançamentos + Captura AJAX")
    print("=" * 70)
    print("\n💡 O navegador será aberto em MODO VISÍVEL.")
    print("   Você poderá acompanhar todas as ações em tempo real!")
    print("   Iniciando em 3 segundos...")
    await asyncio.sleep(3)

    provider = os.getenv("LLM_PROVIDER", "deepseek")
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")

    if not api_key or len(api_key) < 10:
        print("\n❌ ERRO: LLM_API_KEY não configurada no .env")
        sys.exit(1)

    print("\n🚀 Iniciando browser em modo VISÍVEL...")
    await browser_manager.start()
    print("✅ Browser aberto!\n")

    # Limpa log de rede antes de começar
    if browser_manager._network_interceptor:
        browser_manager._network_interceptor.clear()

    llm_client = LLMClient(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        max_tokens=4096,
        temperature=0.1,
    )

    agent = BrowserAgent(
        browser_manager=browser_manager,
        llm_client=llm_client,
        max_iterations=25,
        max_consecutive_errors=3,
        screenshot_on_action=True,
        output_dir="./agent_output_advanced",
    )

    task = """
Execute as seguintes etapas no site i-Educar:

1. Navegue para https://comunidade.ieducar.com.br/login
2. Preencha o formulário de login:
   - Matrícula: comunidade
   - Senha: Comunidade@1
3. Clique em "Entrar" e aguarde o carregamento completo da página
4. Após login, navegue para o menu "Escola" no menu lateral esquerdo
5. Dentro de Escola, procure e clique em "Lançamentos"
6. Em Lançamentos, clique em "Faltas e notas"
7. Na tela de lançamento, preencha os filtros disponíveis (ano, escola, curso, série, turma) se houver
8. Capture TODO o tráfego de rede AJAX feito durante o carregamento dessa tela
9. Documente o formato das requisições e respostas (URLs, métodos, headers, bodies)
10. Tire screenshots de cada tela visitada
11. Gere um relatório completo com todas as descobertas

IMPORTANTE:
- Use browser_wait com condition="network_idle" após cada navegação para aguardar o carregamento
- Use browser_screenshot após cada tela carregada para documentar
- Use browser_get_network_log para capturar o tráfego
- Use browser_execute_javascript para extrair dados da página quando necessário
"""

    print("📋 Tarefa do agente:")
    print(task)
    print("\n" + "=" * 70)
    print("🤖 Agente iniciando... Acompanhe no navegador!")
    print("=" * 70 + "\n")

    try:
        result = await agent.execute_task(task)

        print("\n" + "=" * 70)
        print("📊 RESULTADO FINAL")
        print("=" * 70)
        print(f"\n✅ Sucesso: {result['success']}")
        print(f"📸 Ações executadas: {result['action_count']}")
        print(f"🖼️ Screenshots: {len(result['screenshots'])}")
        print(f"⚠️ Erros: {len(result['errors'])}")

        print(f"\n📝 Relatório:\n{result['report']}")

        # Capturar network log final
        print("\n" + "-" * 70)
        print("🌐 CAPTURA DE REDE (AJAX)")
        print("-" * 70)
        try:
            network_log = await browser_manager.get_network_log()
            logs = json.loads(network_log) if isinstance(network_log, str) else network_log
            
            # Filtrar apenas chamadas AJAX/API relevantes
            ajax_calls = [e for e in logs if any(
                kw in e.get("url", "").lower() for kw in ["api", "ajax", "diario", "json", "module"]
            )]
            
            print(f"\nTotal de requisições capturadas: {len(logs)}")
            print(f"Requisições AJAX/API relevantes: {len(ajax_calls)}")
            
            if ajax_calls:
                print("\n--- Chamadas AJAX/API ---")
                for entry in ajax_calls:
                    print(f"\n🔹 {entry.get('method', '?')} {entry.get('url', '?')[:120]}")
                    print(f"   Status: {entry.get('status', '?')}")
                    if entry.get('post_data'):
                        print(f"   Body: {str(entry['post_data'])[:300]}")
                    if entry.get('response_body'):
                        print(f"   Response: {str(entry['response_body'])[:300]}")
            else:
                print("\n⚠️ Nenhuma chamada AJAX/API encontrada nos filtros.")
                print("   Mostrando as 10 últimas requisições gerais:")
                for entry in logs[-10:]:
                    print(f"  - {entry.get('method', '?')} {entry.get('url', '?')[:100]}")

            # Exportar HAR
            har_path = "./agent_output_advanced/network_capture.har"
            await browser_manager.export_har(har_path)
            print(f"\n💾 HAR exportado para: {har_path}")

        except Exception as e:
            print(f"\n⚠️ Erro ao capturar network log: {e}")

        if result['screenshots']:
            print(f"\n📸 Screenshots capturados:")
            for ss in result['screenshots']:
                print(f"   - {ss}")

        if result['errors']:
            print(f"\n❌ Erros encontrados:")
            for err in result['errors']:
                print(f"   - {err}")

    except Exception as e:
        print(f"\n❌ Erro durante execução: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\n" + "-" * 70)
        print("🔒 Aguardando 5 segundos antes de fechar o browser...")
        print("   (Você pode inspecionar a página neste intervalo)")
        await asyncio.sleep(5)
        await browser_manager.stop()
        print("✅ Browser encerrado")

    print("\n" + "=" * 70)
    print("🏁 Teste avançado finalizado")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
