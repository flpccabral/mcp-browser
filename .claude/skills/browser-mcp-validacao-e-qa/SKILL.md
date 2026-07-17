---
name: browser-mcp-validacao-e-qa
description: >-
  Disciplina de validação e QA do MCP Browser Server: o que conta como
  evidência AQUI, como rodar a suíte de testes, como adicionar teste de cada
  tipo e como o lint/CI portam-se de verdade. Use quando o assunto for "rodar
  os testes", "adicionar teste", "pytest", "a suíte", "test_smoke",
  "test_tools", "test_agent", "test_restricted_profile", "MockLLM", "fixture
  browser_manager", "CI", "lint", "ruff", "ruff format", "mypy", "cobertura",
  "evidência", "provar que funciona", "teste adversarial", "asyncio_mode",
  "playwright install", "por que o CI não roda na minha branch", ou quando
  alguém afirmar que algo "funciona" / "é seguro" sem teste verde nomeado.
---

# Validação e QA — MCP Browser Server

Esta skill define **a disciplina de aceitação deste repositório**: o que conta
como prova, qual é a suíte real, como rodá-la, como estendê-la e como o
lint/CI se comportam de verdade (não como o README imagina). Público:
engenheiro pleno sem contexto prévio. Voz imperativa. Comandos copiáveis.

Antes de dizer que algo "funciona", releia a seção **Disciplina de evidência**.

## Regra-mãe

> Uma afirmação de comportamento só é aceita com **(1) um teste verde nomeado**
> mais **(2) o comando exato que o roda**. Uma afirmação de segurança exige,
> além disso, **um teste adversarial** que tenta quebrar o controle e falha.

Sem esses dois (ou três) itens, a afirmação é hipótese — trate-a como
[[browser-mcp-metodologia-e-prova]] manda.

---

## Anatomia da suíte REAL

A suíte vive em `tests/`. Config em `pyproject.toml` (`[tool.pytest.ini_options]`
com `asyncio_mode = "auto"` — por isso testes `async def` rodam sem decorador
`@pytest.mark.asyncio` em `test_tools.py`/`test_agent.py`). São **4 arquivos**,
**85 testes coletados** (medido 2026-07-17: `85 tests collected`).

| Arquivo | Testes | Precisa de browser real? | Precisa de rede? | O que prova |
|---|---|---|---|---|
| `tests/test_smoke.py` | E2E | **Sim** (Chromium via Playwright) | **Sim** (httpbin.org) | Navegação, type, click, screenshot, stealth, overlay, nova aba — fim a fim |
| `tests/test_tools.py` | camada MCP | **Sim** | Parcial (usa `data:` URIs + example.com) | Cada tool via `app.call_tool(...)` retorna o texto esperado |
| `tests/test_agent.py` | agente | Parcial (fixture sobe browser; parsing/prune não) | Não (MockLLM) | Loop do agente SEM LLM real: parsing, prune, max_iterations, erros consecutivos |
| `tests/test_restricted_profile.py` | segurança | **Não** (funções puras) | Não | Allowlists de domínio/tool/JS, look-alike domains, token 0600, loopback, sanitização |

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

### `test_restricted_profile.py` — adversarial de segurança

- Importa funções puras de `browser_mcp.restricted_profile` e as ataca
  diretamente. **Não sobe browser.** É a camada de prova de segurança do repo.
- Casos adversariais que você deve preservar e citar como precedente:
  - **Typosquatting / look-alike:** `test_similar_domain_rejected` rejeita
    `https://portal.ifood.com.br.hacker.net` e `...ifood.com.br.evil.com`.
  - **Subdomínio não autorizado:** `test_unauthorized_subdomain_rejected`
    rejeita `api.portal.ifood.com.br` (match é **exato**, não sufixo).
  - **Downgrade de esquema:** `test_http_rejected` rejeita `http://` em host permitido.
  - **`chrome://`:** `test_chrome_url_rejected`.
  - **JS secure-by-default:** `test_script_rejected_when_allowlist_empty`
    (allowlist vazia ⇒ tudo rejeitado).
  - **Permissão de token:** 0600/0400 passam, 0644 falha, ausente falha.
- Semântica dos 6 controles: [[browser-mcp-perfil-restrito]].

---

## RODE a suíte — comando canônico e números reais

Use o Python do venv (`.venv/bin/python` local roda 3.14; o CI roda 3.11/3.12/3.13).

```bash
# suíte completa (browser + rede — demora minutos)
./.venv/bin/pytest tests/ -q

# por camada
./.venv/bin/pytest tests/test_restricted_profile.py -v   # rápido, sem browser
./.venv/bin/pytest tests/test_agent.py -v                # parcial, sem LLM
./.venv/bin/pytest tests/test_tools.py -v                # browser
./.venv/bin/pytest tests/test_smoke.py -v                # browser + rede

# só coletar (sanidade, <1s)
./.venv/bin/pytest tests/ --collect-only -q              # => 85 tests collected
```

### Resultado medido HOJE (2026-07-17, branch `etapa-1-ifood-restricted-profile`, Python 3.14.6)

```
8 failed, 77 passed, 2 warnings in 229.01s (0:03:49)
85 tests collected
```

**Isto é uma regressão em relação ao baseline de 2026-07-13** (85 passando em
55.71s). As 8 falhas se dividem em dois grupos — reporte-os fielmente, não os
esconda:

#### Grupo A — 2 falhas causadas pelo WIP não commitado (a suíte precisa acompanhar)

| Teste que falha | Por quê |
|---|---|
| `test_restricted_profile.py::TestToolAllowlist::test_unauthorized_tool_rejected` | Afirma que `browser_click` e `browser_type` são **rejeitados**. O WIP em `restricted_profile.py` **adicionou** ambos a `ALLOWED_TOOLS`. |
| `test_restricted_profile.py::TestValidateToolCall::test_disallowed_tool_rejected_in_restricted_mode` | Afirma `browser_click` rejeitado em modo restrito — o WIP o tornou permitido. |

O dono do repo adicionou **2 hosts** (`partners-auth.ifood.com.br`,
`developer.ifood.com.br`) e **2 tools** (`browser_type`, `browser_click`) às
allowlists (confirmado com `git diff HEAD -- src/browser_mcp/restricted_profile.py`).
**Diagnóstico:** o código de segurança mudou mas os testes adversariais ainda
codificam a política antiga. Isto é exatamente a falha "a suíte não acompanhou
o WIP" — **não é bug de teste, é dívida de sincronização**. Quem commitar o WIP
deve atualizar esses 2 testes na mesma mudança (regra de [[browser-mcp-controle-de-mudancas]]:
mudança de segurança e seu teste andam juntos).

#### Grupo B — 6 falhas de flakiness de rede (NÃO relacionadas ao WIP)

`test_smoke.py::{test_navigate_and_get_url, test_go_back, test_type_text,
test_execute_javascript, test_new_tab, test_click_navigation}` — todas com
`Page.goto: Timeout 30000ms ... waiting until "networkidle"` ou click timeout
contra `httpbin.org`. `curl https://httpbin.org/get` responde `200` em ~1s, mas
o `networkidle` do Playwright estoura sob httpbin lento. **Causa: rede/latência,
não código.** Reexecute isoladamente para confirmar não-determinismo antes de
tratar como regressão de produto.

> **Regra de reporte:** ao rodar a suíte, sempre classifique cada falha em
> "WIP", "flaky/rede" ou "regressão real de código". Nunca reporte só o número
> agregado — `8 failed` sozinho engana.

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

### 2. Regra de segurança nova → em `tests/test_restricted_profile.py`

Escreva **o caso feliz E o adversarial**. Uma regra sem teste que tenta
burlá-la não está provada.

```python
def test_meu_host_permitido_passa(self):
    assert is_domain_allowed("https://novo-host.ifood.com.br/x") is True

def test_lookalike_do_meu_host_rejeitado(self):
    # Adversarial: quem tenta se passar pelo host tem de falhar.
    assert is_domain_allowed("https://novo-host.ifood.com.br.attacker.io") is False
    assert is_domain_allowed("https://sub.novo-host.ifood.com.br") is False   # subdomínio != exato
    assert is_domain_allowed("http://novo-host.ifood.com.br") is False        # downgrade de esquema
```

Para validar pela pipeline completa, use `RestrictedProfile.validate_tool_call`
com `monkeypatch.setenv("IFOOD_RESTRICTED_MODE", "1")` e afirme `"REJECTED" in reason`.

### 3. Comportamento do agente → em `tests/test_agent.py`

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
| `test_restricted_profile.py` | Que as allowlists e a sanitização rejeitam o que devem, incluindo ataques nomeados | Que o modo restrito está **plugado** em runtime na tool call real (isso é integração; ver estado WIP em [[browser-mcp-perfil-restrito]]) |
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

### Números medidos HOJE (2026-07-17, com o WIP presente)

| Comando | Resultado | Exit |
|---|---|---|
| `ruff check src/browser_mcp tests` | **17 errors** (14 auto-fixáveis com `--fix`) | 1 (falha) |
| `ruff format --check src/browser_mcp tests` | **14 arquivos seriam reformatados, 3 já formatados** | 1 (falha) |

> Baseline anterior em HEAD limpo era ~19 erros / 17 arquivos a reformatar; o
> WIP mudou a contagem. **Ambos os gates falham hoje** — ver a dívida histórica
> de lint em [[browser-mcp-arqueologia-de-falhas]].

**Disciplina inegociável:** **não misture correção de lint com mudança
funcional no mesmo commit.** Um commit "corrige lint" não deve alterar
comportamento; um commit funcional não deve varrer 14 arquivos com
`ruff format`. Misturar torna o diff irrevisável e esconde regressão dentro de
ruído de formatação. Política completa: [[browser-mcp-controle-de-mudancas]]
(não duplicar aqui).

---

## CI real — o que dispara, onde, e o que NÃO roda

Fonte: `.github/workflows/ci.yml` (lido 2026-07-17).

- **Gatilho:** só `push`/`pull_request` para `main` **ou** `master`. Nenhuma
  outra branch aciona CI. **A branch atual (`etapa-1-ifood-restricted-profile`)
  NUNCA passou por CI** — não confie em "verde" que não existe.
- **Matriz:** Python `3.11`, `3.12`, `3.13` (o local roda 3.14 — divergência de
  versão; ver [[browser-mcp-build-e-ambiente]]).
- **Jobs:**
  1. `lint` — `ruff check` + `ruff format --check`. Os demais jobs têm
     `needs: lint`, então **se o lint falhar, nada mais roda**. Como o lint
     falha hoje (17 erros), a suíte nunca chegaria a executar no CI.
  2. `test` — `pytest tests/test_smoke.py tests/test_tools.py tests/test_agent.py -v`
     (o "core"). **Não inclui `test_restricted_profile.py`.**
  3. `restricted-profile` — `pytest tests/test_restricted_profile.py -v`, job dedicado.
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
| "esse domínio/tool é bloqueado" | teste adversarial em `test_restricted_profile.py` (caso happy + caso de burla que falha) — cite `test_similar_domain_rejected` como padrão |
| "está seguro" | controle + teste que **tenta violá-lo** e é rejeitado. Sem adversarial, não é segurança |
| "passou no CI" | a branch tem de ter ido a `main`/`master`; caso contrário CI nunca rodou |
| "não quebra lint" | `ruff check` e `ruff format --check` exit 0 — hoje ambos falham |

Fundamento metodológico (barra de evidência, refutação designada, prever
números antes de rodar): [[browser-mcp-metodologia-e-prova]].

---

## Quando NÃO usar esta skill

- **Setup de ambiente / venv / `playwright install` / DeprecationWarnings** →
  [[browser-mcp-build-e-ambiente]].
- **Política de merge, gates obrigatórios, convenções de commit/branch,
  publicação** → [[browser-mcp-controle-de-mudancas]] (esta skill não define
  política; só operacionaliza a evidência).
- **Semântica dos 6 controles do modo restrito, aprovar script, adicionar host** →
  [[browser-mcp-perfil-restrito]].
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

- **Verificado em 2026-07-17** rodando os comandos nesta skill no venv local
  (`.venv/bin`, Python 3.14.6), branch `etapa-1-ifood-restricted-profile` **com
  WIP não commitado** em `src/browser_mcp/restricted_profile.py`,
  `tools.py`, `websocket_server.py`.
- **Números datados (podem mudar):**
  - Suíte: **85 testes coletados**; execução completa **8 failed, 77 passed em
    229s** (2 falhas WIP em `test_restricted_profile.py` + 6 flaky de rede em
    `test_smoke.py`). Baseline 2026-07-13: 85 passando em 55.71s.
  - `ruff check`: **17 erros** (exit 1). `ruff format --check`: **14 a
    reformatar / 3 ok** (exit 1). Baseline HEAD anterior: ~19 erros / 17 a reformatar.
  - **2 `DeprecationWarning`** de `websockets`.
  - Contagem de tools: `grep -c "^@app.tool" src/browser_mcp/tools.py` → **39**;
    README diz **37 ferramentas**. **Divergência aberta** (uma skill irmã citava
    41 numa medição anterior — a contagem é volátil e o README está defasado).
- **`mypy` NÃO está no CI** (confirmado: `grep mypy .github/workflows/ci.yml` = 0),
  apesar de estar nas dev deps.
- **Fatos NÃO confirmados / a revalidar:**
  - Se o WIP for commitado, os 2 testes do Grupo A devem ser atualizados; até
    lá a suíte "falha por design divergente".
  - Se o CI passa de fato no "core" depende de o runner ter Chromium do
    Playwright — o `ci.yml` não roda `playwright install`, então isso é dúvida
    aberta até alguém observar um run em `main`/`master`.
- **Como manter:** re-rode `pytest tests/`, `ruff check` e `ruff format --check`
  e reescreva a seção de números. Reconfirme `ci.yml` (gatilho, matriz, jobs,
  ausência de mypy) e a contagem de tools por grep.
