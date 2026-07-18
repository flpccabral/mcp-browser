---
name: browser-mcp-validacao-e-qa
description: >-
  Disciplina de validação e QA do MCP Browser Server: o que conta como
  evidência AQUI, como rodar a suíte de testes, como adicionar teste de cada
  tipo e como o lint/CI portam-se de verdade. Use quando o assunto for "rodar
  os testes", "adicionar teste", "pytest", "a suíte", "test_smoke",
  "test_tools", "test_agent", "MockLLM", "fixture
  browser_manager", "CI", "lint", "ruff", "ruff format", "mypy", "cobertura",
  "evidência", "provar que funciona", "teste adversarial", "asyncio_mode",
  "playwright install", "por que o CI não roda na minha branch", ou quando
  alguém afirmar que algo "funciona" sem teste verde nomeado.
---

# Validação e QA — MCP Browser Server

Esta skill define **a disciplina de aceitação deste repositório**: o que conta
como prova, qual é a suíte real, como rodá-la, como estendê-la e como o
lint/CI se comportam de verdade (não como o README imagina). Público:
engenheiro pleno sem contexto prévio. Voz imperativa. Comandos copiáveis.

Antes de dizer que algo "funciona", releia a seção **Disciplina de evidência**.

## Regra-mãe

> Uma afirmação de comportamento só é aceita com **(1) um teste verde nomeado**
> mais **(2) o comando exato que o roda**.

Sem esses dois itens, a afirmação é hipótese — trate-a como
[[browser-mcp-metodologia-e-prova]] manda.

---

## Anatomia da suíte REAL

A suíte vive em `tests/`. Config em `pyproject.toml` (`[tool.pytest.ini_options]`
com `asyncio_mode = "auto"` — por isso testes `async def` rodam sem decorador
`@pytest.mark.asyncio` em `test_tools.py`/`test_agent.py`). São **3 arquivos**,
**43 testes coletados** (medido 2026-07-18: `43 tests collected`).

| Arquivo | Testes | Precisa de browser real? | Precisa de rede? | O que prova |
|---|---|---|---|---|
| `tests/test_smoke.py` | 10 (E2E) | **Sim** (Chromium via Playwright) | **Sim** (httpbin.org) | Navegação, type, click, screenshot, stealth, overlay, nova aba — fim a fim |
| `tests/test_tools.py` | 22 (camada MCP) | **Sim** | Parcial (usa `data:` URIs + example.com) | Cada tool via `app.call_tool(...)` retorna o texto esperado |
| `tests/test_agent.py` | 11 (agente) | Parcial (fixture sobe browser; parsing/prune não) | Não (MockLLM) | Loop do agente SEM LLM real: parsing, prune, max_iterations, erros consecutivos |

### `test_smoke.py` — E2E contra browser + páginas reais

- Fixture `browser` (scope `function`, isolamento por teste): importa o
  **singleton** `browser_manager` de `browser_mcp.browser_manager`, chama
  `await browser_manager.start()`, entrega, e para com `stop()` em `try/except`.
- **Browser:** Chromium headless do Playwright (o mesmo que
  `playwright install chromium` baixa). Contexto em
  [[browser-mcp-build-e-ambiente]].
- **Páginas-alvo:** `https://httpbin.org/*` (get, headers, forms/post, ip) e
  navegação real. Isso torna os smokes **dependentes de rede e sensíveis a
  latência** — o `navigate` espera `networkidle`, então httpbin lento faz
  `Page.goto: Timeout 30000ms` mesmo com a rede "no ar".
- Helper `_evaluate(page, expr)` embrulha `page.evaluate(f"({expr})")` porque
  `return` cru dá `SyntaxError` no Playwright.

### `test_tools.py` — fixture `browser_manager`

- Fixture `browser_manager` **reseta o singleton** antes de cada teste
  (`BrowserManager._instance = None`, novo `_lock`), instancia um `BrowserManager`
  fresco e **reatribui** `tools_module.browser_manager = bm` — as tools em
  `tools.py` usam essa referência de módulo. Sem essa reatribuição as tools
  falariam contra um manager velho.
- Cada teste chama `app.call_tool("browser_xxx", {...})` e valida `result[0].text`
  (mensagens em PT-BR: `"Navegado para ..."`, `"Texto digitado"`, `"REJECTED"`, etc.).
- Usa `data:text/html,...` URIs para inputs/selects determinísticos e evitar
  depender de sites externos onde possível.

### `test_agent.py` — MockLLM (agente testado SEM LLM real)

- Classe `MockLLM` substitui `LLMClient`: `chat(messages)` devolve respostas
  pré-programadas (`responses[call_count]`) ou `default_response`; `fail_count`
  faz `chat` **lançar `RuntimeError`** N vezes para simular falha de LLM.
- Cobre: `execute_task` feliz (`test_execute_task_simple`), teto de iterações
  (`test_max_iterations`), erros consecutivos (`test_consecutive_errors` — sobe
  `fail_count=3` porque o agente **zera** `consecutive_errors` após um `chat`
  bem-sucedido, então só falhas do LLM acumulam), parsing (`_parse_response`
  com markdown ```json, JSON cru, texto inválido, vazio, ``` genérico) e prune
  (`_prune_messages` sob/ sobre limite, sem system).
- Testes de `_parse_response`/`_prune_messages` instanciam `BrowserAgent(None, None)`
  — **não sobem browser nem LLM**, são unitários puros.

---

## RODE a suíte — comando canônico e números reais

Use o Python do venv (`.venv/bin/python` local roda 3.14; o CI roda 3.11/3.12/3.13).

```bash
# suíte completa (browser + rede — demora minutos)
./.venv/bin/pytest tests/ -q

# por camada
./.venv/bin/pytest tests/test_agent.py -v                # parcial, sem LLM
./.venv/bin/pytest tests/test_tools.py -v                # browser
./.venv/bin/pytest tests/test_smoke.py -v                # browser + rede

# testes rápidos sem browser (parsing/prune do agente)
./.venv/bin/pytest tests/test_agent.py -k "parse or prune"

# só coletar (sanidade, <1s)
./.venv/bin/pytest tests/ --collect-only -q              # => 43 tests collected
```

### Resultado medido (2026-07-18, Python 3.14.6)

`43 tests collected`. Os testes que não sobem browser passam de imediato; os de
browser (`test_tools.py`, `test_smoke.py`) exigem Chromium e rede.

**Flakiness conhecida de rede.** Alguns smokes de `test_smoke.py`
(`test_navigate_and_get_url`, `test_go_back`, `test_type_text`,
`test_execute_javascript`, `test_new_tab`, `test_click_navigation`) podem falhar
com `Page.goto: Timeout 30000ms ... waiting until "networkidle"` contra
`httpbin.org`. `curl https://httpbin.org/get` responde `200` em ~1s, mas o
`networkidle` do Playwright estoura sob httpbin lento. **Causa: rede/latência,
não código.** Reexecute isoladamente para confirmar não-determinismo antes de
tratar como regressão de produto.

> **Regra de reporte:** ao rodar a suíte, sempre classifique cada falha em
> "flaky/rede" ou "regressão real de código". Nunca reporte só o número
> agregado — um `N failed` sozinho engana.

**2 `DeprecationWarning`** persistem (`websockets.server.WebSocketServerProtocol`
e `websockets.legacy`); esperados e rastreados em [[browser-mcp-build-e-ambiente]].

---

## Requisitos de ambiente

| Requisito | Como garantir | Sintoma se faltar |
|---|---|---|
| Chromium do Playwright | `playwright install chromium` (ou `./.venv/bin/playwright install chromium`) | Todos os smokes/tools falham em massa no `start()` |
| `pytest-asyncio` com `asyncio_mode=auto` | Já em `pyproject.toml` (`[tool.pytest.ini_options]`) e nas dev deps | `async def` tests coletados mas não rodados / skipped |
| Rede aberta a `httpbin.org` e `example.com` | Conexão externa | Grupo B de falhas (timeouts) |

Setup completo do zero: [[browser-mcp-build-e-ambiente]].

---

## Como adicionar teste — por tipo, com exemplo copiável

Siga o estilo do arquivo-alvo. Não invente framework novo.

### 1. Tool nova → em `tests/test_tools.py`

Use a fixture `browser_manager` e valide `result[0].text`. Prefira `data:` URI
para determinismo.

```python
async def test_minha_tool(browser_manager):
    await app.call_tool("browser_navigate", {"url": "data:text/html,<h1>Oi</h1>"})
    result = await app.call_tool("browser_minha_tool", {"arg": "valor"})
    assert len(result) == 1
    assert result[0].type == "text"
    assert "Mensagem esperada em PT-BR" in result[0].text
```

### 2. Comportamento do agente → em `tests/test_agent.py`

Programe respostas no `MockLLM`. **Não chame LLM real.** Para lógica pura
(parsing/prune), instancie `BrowserAgent(None, None)`.

```python
async def test_agente_para_em_erro(mock_llm, browser_manager):
    mock_llm.responses = [
        '{"thought": "passo 1", "tool": "browser_navigate", '
        '"params": {"url": "https://example.com"}, "is_complete": false}',
        '{"thought": "fim", "is_complete": true, "report": "ok"}',
    ]
    agent = BrowserAgent(browser_manager, mock_llm, max_iterations=5, screenshot_on_action=False)
    result = await agent.execute_task("tarefa")
    assert result["success"] is True

def test_parse_de_algo_novo():
    agent = BrowserAgent(None, None)                 # unitário puro, sem browser/LLM
    assert agent._parse_response("lixo sem json") is None
```

---

## O que cada camada prova — e o que NÃO prova

| Camada | Prova | NÃO prova |
|---|---|---|
| `test_tools.py` | Que cada tool retorna a mensagem correta contra um browser real | Confiabilidade sob páginas hostis/AJAX pesado; concorrência de múltiplos clientes |
| `test_smoke.py` | Que o fluxo E2E funciona contra sites reais | Estabilidade — é flaky por rede; não é gate de regressão fino |
| `test_agent.py` (MockLLM) | Parsing, prune, tetos e tratamento de erro do **loop** | **A qualidade de decisão de um LLM real.** MockLLM devolve respostas roteirizadas; não há benchmark de taxa de sucesso do agente |

> **Lacuna DECLARADA:** não existe, hoje, benchmark de taxa de sucesso do agente
> com LLM real. MockLLM valida a mecânica do loop, não se o agente *acerta a
> tarefa*. Quem ataca isso é a campanha [[browser-mcp-campanha-confiabilidade-do-agente]]
> (Fase 0 = construir o harness de benchmark, porque hoje não medimos nada).
> Não afirme "o agente é confiável" com base em `test_agent.py`.

---

## Lint como gate — RODE e reporte

O CI **bloqueia** em dois passos de lint. Rode-os localmente antes de qualquer push:

```bash
./.venv/bin/ruff check src/browser_mcp tests
./.venv/bin/ruff format --check src/browser_mcp tests
```

### Números medidos (2026-07-18)

| Comando | Resultado | Exit |
|---|---|---|
| `ruff check src/browser_mcp tests` | **limpo** | 0 |
| `ruff format --check src/browser_mcp tests` | **tudo formatado** | 0 |

> A dívida histórica de lint foi quitada num commit dedicado. `ruff check .` na
> raiz ainda acusa erros em scripts fora do escopo do CI (`manage_mcp_browser.py`,
> scripts de skills) — não bloqueiam o gate. Contexto histórico em
> [[browser-mcp-arqueologia-de-falhas]].

**Disciplina inegociável:** **não misture correção de lint com mudança
funcional no mesmo commit.** Um commit "corrige lint" não deve alterar
comportamento; um commit funcional não deve varrer 14 arquivos com
`ruff format`. Misturar torna o diff irrevisável e esconde regressão dentro de
ruído de formatação. Política completa: [[browser-mcp-controle-de-mudancas]]
(não duplicar aqui).

---

## CI real — o que dispara, onde, e o que NÃO roda

Fonte: `.github/workflows/ci.yml` (lido 2026-07-18).

- **Gatilho:** só `push`/`pull_request` para `main` **ou** `master`. Nenhuma
  outra branch aciona CI — não confie em "verde" numa branch de trabalho, ele
  não existe.
- **Matriz:** Python `3.11`, `3.12`, `3.13` (o local roda 3.14 — divergência de
  versão; ver [[browser-mcp-build-e-ambiente]]).
- **Jobs:**
  1. `lint` — `ruff check` + `ruff format --check`. O job `test` tem
     `needs: lint`, então **se o lint falhar, o test não roda**. O lint hoje
     passa limpo no escopo do CI.
  2. `test` — `pytest tests/test_smoke.py tests/test_tools.py tests/test_agent.py -v`
     (o "core") — a suíte inteira, já que hoje há só esses 3 arquivos.
- **`mypy` NÃO roda no CI.** Está nas dev deps do `pyproject.toml`
  (`mypy>=1.8`) e há `[tool.mypy]` configurado, mas `grep mypy .github/workflows/ci.yml`
  retorna **0** ocorrências. Não trate type-check como gate — ele não é.
- **Atenção:** o job `test` do CI **não roda `playwright install`** antes do
  pytest. Os smokes/tools dependem de Chromium; se o runner não tiver o browser
  do Playwright, essas camadas quebram no CI. Verifique isso antes de prometer
  que o "core" passa no CI.

---

## Disciplina de evidência (aplicação prática)

| Alguém afirma... | Você exige... |
|---|---|
| "essa tool funciona" | teste em `test_tools.py` nomeado + `./.venv/bin/pytest tests/test_tools.py::test_x -q` verde |
| "o agente completa a tarefa" | teste em `test_agent.py` com MockLLM roteirizado + comando. E lembre: não prova qualidade de LLM real |
| "passou no CI" | a branch tem de ter ido a `main`/`master`; caso contrário CI nunca rodou |
| "não quebra lint" | `ruff check src/browser_mcp tests` e `ruff format --check src/browser_mcp tests` exit 0 |

Fundamento metodológico (barra de evidência, refutação designada, prever
números antes de rodar): [[browser-mcp-metodologia-e-prova]].

---

## Quando NÃO usar esta skill

- **Setup de ambiente / venv / `playwright install` / DeprecationWarnings** →
  [[browser-mcp-build-e-ambiente]].
- **Política de merge, gates obrigatórios, convenções de commit/branch,
  publicação** → [[browser-mcp-controle-de-mudancas]] (esta skill não define
  política; só operacionaliza a evidência).
- **Melhorar de fato a confiabilidade do agente / construir benchmark de sucesso** →
  [[browser-mcp-campanha-confiabilidade-do-agente]].
- **Algo QUEBRA em runtime (click não faz nada, extensão não conecta, agente em loop)** →
  [[browser-mcp-playbook-de-depuracao]].
- **"Por que isso é assim / já foi tentado / houve incidente"** →
  [[browser-mcp-arqueologia-de-falhas]].
- **Metodologia de prova de uma hipótese antes de shipar** →
  [[browser-mcp-metodologia-e-prova]].
- **Como rodar o servidor / conectar extensão / modo CDP** →
  [[browser-mcp-executar-e-operar]].

---

## Proveniência e manutenção

- **Verificado em 2026-07-18** rodando os comandos nesta skill no venv local
  (`.venv/bin`, Python 3.14.6).
- **Números datados (podem mudar):**
  - Suíte: **43 testes coletados** (`test_smoke.py` 10, `test_tools.py` 22,
    `test_agent.py` 11). Alguns smokes são flaky por rede (httpbin/networkidle).
  - `ruff check src/browser_mcp tests` e `ruff format --check src/browser_mcp tests`:
    **limpos** (exit 0).
  - **2 `DeprecationWarning`** de `websockets`.
  - Contagem de tools: `grep -c "^@app.tool" src/browser_mcp/tools.py` → **39**;
    README diz **37 ferramentas**. **Divergência aberta** (sem a âncora `^` o
    grep dá 41, contando 2 docstrings — o README está defasado).
- **`mypy` NÃO está no CI** (confirmado: `grep mypy .github/workflows/ci.yml` = 0),
  apesar de estar nas dev deps.
- **Fatos NÃO confirmados / a revalidar:**
  - Se o CI passa de fato no "core" depende de o runner ter Chromium do
    Playwright — o `ci.yml` não roda `playwright install`, então isso é dúvida
    aberta até alguém observar um run em `main`/`master`.
- **Como manter:** re-rode `pytest tests/`, `ruff check` e `ruff format --check`
  e reescreva a seção de números. Reconfirme `ci.yml` (gatilho, matriz, jobs,
  ausência de mypy) e a contagem de tools por grep.
