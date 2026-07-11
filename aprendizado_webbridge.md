# Relatório de Aprendizado: Kimi WebBridge vs MCP Browser Server

## Objetivo
Aprender os comportamentos e capacidades do Kimi WebBridge para identificar o que pode ser agregado ao nosso MCP Browser Server com Playwright.

---

## 1. O que o Kimi WebBridge faz diferente (e melhor)

### 1.1 Accessibility Tree (Snapshot) nativo
- O WebBridge retorna uma **árvore de acessibilidade** com `@e` refs para elementos interativos
- Não depende de seletores CSS — usa `role`, `name`, e refs semânticas
- Isso é **mais robusto** que seletores CSS porque sobrevive a mudanças de classe/hash
- O Playwright tem `page.accessibility.snapshot()` mas não é tão integrado

### 1.2 Sessão do Browser REAL do usuário
- O WebBridge opera no **perfil do Chrome do usuário** (não um contexto isolado)
- Reutiliza cookies, localStorage, logins, extensões do usuário
- Isso é um **diferencial ENORME** para automação de sites que exigem login manual
- O Playwright sempre roda em contexto isolado (mesmo persistente)

### 1.3 Network Monitoring nativo
- Comandos `network start`, `network list`, `network detail` são **nativos** no WebBridge
- Captura requests/responses automaticamente em tempo real
- Fácil de usar: não precisa de interceptors manuais no código
- No nosso projeto, o NetworkInterceptor é uma classe separada que requer setup

### 1.4 Operador `@e` refs
- Cada elemento interativo recebe um `@e123` ref no snapshot
- O `@e` ref é mais **estável** que seletores CSS porque usa a árvore de acessibilidade
- Permite interação direta sem precisar conhecer o DOM
- Isso reduz erros de `Locator.click: Timeout` por elementos invisíveis

### 1.5 Content Scripts nativos
- O WebBridge já tem content scripts injetados na página
- Pode capturar eventos de forma mais granular que o Playwright
- Pode acessar elementos dentro de shadow DOM e iframes mais facilmente

---

## 2. O que podemos agregar ao MCP Browser Server

### 2.1 Usar `@e` refs como alternativa a seletores CSS
```python
# Hoje nosso agente usa:
agent_response = {"tool": "browser_click", "params": {"selector": "#botao_busca"}}

# Melhoria: suportar @e refs:
agent_response = {"tool": "browser_click", "params": {"selector": "@e3"}}
```

Implementação:
- Adicionar um método `get_accessibility_tree()` no BrowserManager
- Mapear `@e` refs para elementos do Playwright usando `page.get_by_role()` ou `page.locator()`
- O agente pode "ver" a página como o WebBridge vê (accessibility tree)

### 2.2 Snapshot + Interação em um só passo
```python
# Hoje o agente faz:
# 1. _observe() -> extrai texto e elementos interativos via JS
# 2. LLM decide qual seletor usar
# 3. _execute_tool() -> clica no seletor

# Melhoria: usar accessibility.snapshot() do Playwright
async def _observe(self) -> dict:
    page = await self.browser_manager.get_page()
    snapshot = await page.accessibility.snapshot()
    # extrair elementos interativos do snapshot nativo
```

Isso seria mais **preciso** e **rápido** que o TreeWalker JavaScript que usamos hoje.

### 2.3 Network Monitoring nativo simplificado
```python
# Hoje usamos NetworkInterceptor com listeners manuais
# Melhoria: integrar com o Playwright de forma mais transparente

class NetworkInterceptor:
    # Adicionar métodos start(), stop(), list() como o WebBridge
    # Expor via ferramenta MCP: browser_network_start, browser_network_list
```

### 2.4 Modo "Browser do Usuário" (não isolado)
```python
# Hoje o BrowserManager inicia um novo browser em contexto isolado
# Melhoria: opção de conectar ao Chrome instalado do usuário

async def start(self, connect_to_existing: bool = False):
    if connect_to_existing:
        # Conectar via CDP ao Chrome do usuário
        self._browser = await self._playwright.chromium.connect_over_cdp(
            "http://localhost:9222"
        )
    else:
        # Modo padrão (isolated)
        self._browser = await self._playwright.chromium.launch(...)
```

Isso permite:
- Reutilizar sessões logadas do usuário
- Usar extensões do usuário
- Acessar sites que bloqueiam browsers automatizados

### 2.5 Ferramenta `browser_find_tab` (como o WebBridge)
```python
@app.tool()
async def browser_find_tab(url_pattern: str) -> str:
    """Find and activate an existing tab by URL pattern."""
    # Implementar usando browser.tabs() do Playwright
```

Isso permite o agente trabalhar com abas já abertas (como o WebBridge faz).

---

## 3. Melhorias específicas no Agente Autônomo

### 3.1 Usar Accessibility Tree para observação
```python
# Hoje: extrai texto via TreeWalker JS + elementos interativos via querySelectorAll
# Problema: texto truncado, elementos invisíveis incluídos, seletores quebram

# Melhoria: usar page.accessibility.snapshot()
async def _observe(self) -> dict:
    page = await self.browser_manager.get_page()
    snapshot = await page.accessibility.snapshot()
    
    # Extrair elementos interativos do snapshot
    interactive = []
    def extract(node):
        if node.get('role') in ['button', 'link', 'textbox', 'combobox', 'checkbox']:
            interactive.append({
                'ref': node.get('keyshortcuts'),  # ou gerar @e ref
                'role': node.get('role'),
                'name': node.get('name'),
                'value': node.get('value'),
            })
        for child in node.get('children', []):
            extract(child)
    extract(snapshot)
    
    return {
        'url': page.url,
        'title': await page.title(),
        'interactive_elements': interactive,
    }
```

### 3.2 Reduzir erros de seletor com fallback
```python
async def _execute_tool(self, tool_name: str, params: dict) -> str:
    selector = params.get('selector', '')
    
    # Se o seletor é @e ref, usar accessibility tree
    if selector.startswith('@e'):
        element = await self._find_by_ref(selector)
        if element:
            # executar ação no elemento
    
    # Fallback: tentar seletor CSS
    try:
        return await self._execute_with_css(tool_name, params)
    except Exception:
        # Segundo fallback: tentar por texto/role
        return await self._execute_with_text(tool_name, params)
```

### 3.3 Melhorar o System Prompt do Agente
```python
AGENT_SYSTEM_PROMPT = """
# COMO INTERAGIR COM A PÁGINA

## Métodos de Localização (em ordem de preferência)
1. **@e ref** (MAIS ESTÁVEL): Use refs do accessibility tree
   Ex: `browser_click({"selector": "@e3"})`
   
2. **ID CSS**: `#id_do_elemento`
   Ex: `browser_click({"selector": "#botao_busca"})`
   
3. **Texto**: Use `by="text"` para clicar por texto visível
   Ex: `browser_click({"selector": "Entrar", "by": "text"})`

## Regras de Ouro
1. SEMPRE use @e refs quando disponíveis no snapshot
2. Para dropdowns, use o ID do select (ex: `#ref_cod_escola`)
3. Para botões, use o texto visível ou ID
4. NUNCA use classes CSS com hash (ex: `.btn-green-abc123`)
5. Se um seletor falhar, tente o fallback por texto
"""
```

---

## 4. Integração WebBridge + MCP Server (visão de futuro)

### 4.1 Arquitetura ideal
```
┌──────────────────┐
│  Cliente MCP     │
│  (IDE/Chat/CLI)  │
└────────┬─────────┘
         │
    ┌────┴────┐
    │  MCP    │
    │ Server  │
    └────┬────┘
         │
    ┌────┴────┐
    │ Routing │
    │ Engine  │
    └────┬────┘
         │
    ┌────┴────┐
    │Playwright│   OR    ┌─────────────┐
    │(padrão) │◄────────►│ WebBridge   │
    │         │          │ (browser    │
    │         │          │  real)      │
    └─────────┘          └─────────────┘
```

### 4.2 Modo de seleção
```python
# Variável de ambiente ou parâmetro da ferramenta
BROWSER_MODE=playwright  # padrão: rápido, isolado, headless
BROWSER_MODE=webbridge   # avançado: browser real, sessão do usuário

# Ou ferramenta específica:
browser_agent_task(task="...", mode="webbridge")
```

---

## 5. Conclusão: O que implementar AGORA

### Prioridade 1 (rápido, alto impacto)
1. **Adicionar suporte a @e refs** no BrowserManager
2. **Usar accessibility.snapshot()** no `_observe()` do agente
3. **Adicionar fallback por texto** quando seletor CSS falha

### Prioridade 2 (médio prazo)
4. **Modo connect_to_existing** para usar Chrome do usuário via CDP
5. **Ferramentas `browser_network_start` / `browser_network_list`** nativas
6. **Melhorar o System Prompt** com instruções de @e refs

### Prioridade 3 (futuro)
7. **Integração nativa com WebBridge** como motor alternativo
8. **Content scripts** para interceptar XHR/fetch no contexto da página
9. **Extension helper** para sites com shadow DOM complexo

---

## 6. Teste Realizado com WebBridge

Durante o teste no i-Educar, o WebBridge demonstrou:
- ✅ Snapshot de acessibilidade funciona bem (encontrou @e refs para todos os elementos)
- ✅ Sessão do browser real reutiliza login automaticamente
- ✅ Network monitoring nativo captura AJAX sem setup manual
- ✅ `@e` refs são mais estáveis que seletores CSS
- ⚠️ Network `list` mostra apenas requests recentes, precisa de `start` antes de cada ação
- ⚠️ Não tem captura de response body (apenas URL, método, status)
- ⚠️ Não tem exportação nativa de HAR

---

> **Próximo passo recomendado**: Implementar Prioridade 1 (suporte a @e refs + accessibility snapshot) no nosso agente para reduzir erros de seletor e melhorar a observação da página.
