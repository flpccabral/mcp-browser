#!/usr/bin/env python3
"""Teste do agente autônomo no site i-Educar."""

import asyncio
import os
import sys

# Adicionar src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv

# Carregar variáveis de ambiente do .env
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from browser_mcp.browser_manager import browser_manager
from browser_mcp.llm_client import LLMClient
from browser_mcp.agent import BrowserAgent


async def main():
    print("=" * 60)
    print("🧪 TESTE: Agente Autônomo - i-Educar Login")
    print("=" * 60)
    
    # Verificar configuração LLM
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    
    print(f"\n📡 Provider: {provider}")
    print(f"🤖 Model: {model}")
    print(f"🔗 Base URL: {base_url}")
    print(f"🔑 API Key: {'✅ configurada' if api_key and len(api_key) > 10 else '❌ NÃO configurada'}")
    
    if not api_key or len(api_key) < 10:
        print("\n❌ ERRO: LLM_API_KEY não está configurada corretamente no .env")
        print("   Por favor, adicione sua API key no arquivo .env")
        sys.exit(1)
    
    # Inicializar browser
    print("\n🚀 Iniciando browser...")
    await browser_manager.start()
    print("✅ Browser iniciado")
    
    # Criar LLM client
    llm_client = LLMClient(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        max_tokens=4096,
        temperature=0.1,
    )
    
    # Criar agente
    agent = BrowserAgent(
        browser_manager=browser_manager,
        llm_client=llm_client,
        max_iterations=20,
        max_consecutive_errors=3,
        screenshot_on_action=True,
        output_dir="./agent_output",
    )
    
    # Tarefa do agente
    task = """
Navegue para https://comunidade.ieducar.com.br/login

Na tela de login:
1. Localize o campo de matrícula e digite: comunidade
2. Localize o campo de senha e digite: Comunidade@1
3. Clique no botão de login
4. Aguarde o carregamento da página após o login
5. Capture o título da página e a URL atual
6. Tire um screenshot do estado final da página

Retorne um relatório com:
- URL final após login
- Título da página
- Se o login foi bem-sucedido ou não
- Screenshots capturados
"""
    
    print("\n📋 Tarefa:")
    print(task)
    print("\n" + "=" * 60)
    print("🤖 Iniciando execução do agente...")
    print("=" * 60 + "\n")
    
    try:
        result = await agent.execute_task(task)
        
        print("\n" + "=" * 60)
        print("📊 RESULTADO")
        print("=" * 60)
        print(f"\n✅ Sucesso: {result['success']}")
        print(f"📸 Ações executadas: {result['action_count']}")
        print(f"🖼️ Screenshots: {len(result['screenshots'])}")
        print(f"⚠️ Erros: {len(result['errors'])}")
        
        print(f"\n📝 Relatório:\n{result['report']}")
        
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
        print("\n🔒 Encerrando browser...")
        await browser_manager.stop()
        print("✅ Browser encerrado")
    
    print("\n" + "=" * 60)
    print("🏁 Teste finalizado")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
