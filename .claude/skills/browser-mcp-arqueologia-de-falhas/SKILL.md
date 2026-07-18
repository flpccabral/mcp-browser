---
name: browser-mcp-arqueologia-de-falhas
description: A crônica do mcp_browser — por que o projeto é como é. Consulte antes de investigar qualquer comportamento estranho, propor mudança de design ou reabrir uma discussão. Cobre histórico de investigações (benchmark Kimi WebBridge, indicadores visuais), becos sem saída (isTrusted em eventos sintéticos), incidentes (chave privada extension.pem vazada e purgada com filter-repo), decisões de design (modo extensão, @e refs, overlay CSS), dívidas conhecidas (lint) e o que cada fix P0 corrigiu. Gatilhos: "por que isso existe?", "já foi tentado?", "qual o histórico disso?", "houve algum incidente?", "de onde veio essa decisão?", "por que os hashes mudaram?", "por que JS não pode clicar?".
---

# Arqueologia de Falhas — mcp_browser

Este documento é a **crônica** do repositório: cada investigação maior, beco sem saída, decisão e incidente, no formato **Sintoma/Pergunta → Causa raiz/Decisão → Evidência → Status**. Objetivo: **ninguém reabre batalha já vencida**.

Regras de leitura:

- Toda evidência é um comando copiável. **Rode-o antes de confiar** — o histórico já foi reescrito uma vez (filter-repo em 2026-07-12) e pode ser reescrito de novo.
- Os docs históricos de investigação foram **removidos do working tree** no commit `ddf9bc1`, mas continuam recuperáveis via `git show cbc8e28:<arquivo>`. Isso é intencional: o commit raiz `cbc8e28` é o arquivo morto do projeto.
- Status possíveis: **resolvido** (implementado e verificável no código), **cercado** (o problema não tem solução — há uma regra ativa impedindo reincidência), **aberto** (dívida ou pendência conhecida).

## Índice rápido

| # | Entrada | Data | Status |
|---|---------|------|--------|
| 1 | Benchmark Kimi WebBridge → decisões de arquitetura | ~2026-06/07 | resolvido |
| 2 | Investigação de indicadores visuais | 2026-07-01 | resolvido |
| 3 | Descoberta isTrusted (eventos sintéticos) | ≤2026-07-10 | **cercado** |
| 4 | Commit P0 `cbc8e28` — os 4 fixes | 2026-07-10 | resolvido |
| 5 | Incidente da chave privada `extension.pem` | 2026-07-12 | **aberto** (regenerar chave) |
| 6 | Estado do lint | 2026-07-12 | resolvido (dívida quitada; escopo do CI limpo) |

---

## 1. Benchmark Kimi WebBridge → decisões de arquitetura (~junho/julho 2026)

**Sintoma/Pergunta:** Por que o WebBridge da Moonshot resolvia sites legados (com sessão real do usuário e dropdowns em cascata AJAX) melhor que nosso agente Playwright puro? O que copiar?

**Causa raiz/Decisões geradas:**

1. **`@e` refs de accessibility tree** — o WebBridge referencia elementos por refs semânticas (`@e3`) da árvore de acessibilidade, não por seletores CSS. Sobrevive a mudanças de classe/hash. Decisão: suportar `@e` refs em `browser_click`/`browser_type` e expor a árvore.
2. **Modo extensão (sessão real do usuário)** — o WebBridge opera no perfil Chrome real do usuário (cookies, logins, extensões). Playwright isolado não faz isso. Decisão: **arquitetura híbrida** — Playwright como padrão + extensão Chrome para sessão real.
3. **Network monitoring nativo** — comandos `network start/list/detail` de primeira classe, em vez de interceptors manuais.

**Evidência:**

```bash
git show cbc8e28:aprendizado_webbridge.md
```

**Status: resolvido — implementado.** Verificável no código atual:

```bash
grep -n "def get_accessibility_tree" src/browser_mcp/browser_manager.py   # linha ~314
ls src/browser_mcp/extension_bridge.py                                     # modo extensão
grep -n '"ref"' src/browser_mcp/agent.py                                   # @e refs nas tools
```

Não proponha "migrar tudo para Playwright puro" nem "abandonar a extensão" sem antes entender isto: a extensão existe **por causa** da sessão real do usuário, não por acidente.

---

## 2. Investigação de indicadores visuais (2026-07-01)

**Sintoma/Pergunta:** Como mostrar ao usuário que o agente está controlando o browser dele? Como os concorrentes fazem?

**Causa raiz/Decisão:** Foram analisados **5 agentes**:

| Agente | Tecnologia de indicador |
|--------|------------------------|
| Kimi WebBridge | Chrome Tab Groups coloridos (`group_title`) — sem overlay no DOM |
| Claude Desktop | Content script `agent-visual-indicator.js` em `<all_urls>` |
| Gemini CLI | CDP `Runtime.evaluate` + CSS injection (borda pulsante) |
| cdpilot | CDP + overlay nativo (green glow, cursor ripples, red toast) |
| OpenClaw Browser Relay | Badge ON/OFF no ícone da extensão (`chrome.action`) |

Decisão: **overlay CSS via injeção** (`Runtime.evaluate`/`page.evaluate`) — não exige extensão, funciona em qualquer Chromium, liga/desliga fácil.

**Evidência:**

```bash
git show cbc8e28:investigacao_indicadores_visuais.md   # relatório completo, datado 2026-07-01
```

**Status: resolvido — implementado** em `src/browser_mcp/visual_indicator.py` (função `get_overlay_js`, div `__mcp_browser_overlay` com `z-index: 2147483647`, 4 cores de estado). Confirme:

```bash
grep -n "__mcp_browser_overlay" src/browser_mcp/visual_indicator.py
```

---

## 3. Descoberta isTrusted — beco sem saída CERCADO (≤ 2026-07-10)

**Sintoma:** Cliques feitos via `browser_execute_javascript` (`element.click()`) "funcionam" localmente mas são **ignorados silenciosamente** por Google News e muitas SPAs. O agente entra em loop tentando clicar via JS.

**Causa raiz:** Eventos sintéticos disparados por JavaScript têm `isTrusted=false`. Sites que checam essa flag descartam o evento. **Não há workaround via JS** — só eventos gerados pelo browser (CDP input) são trusted.

**Decisão/Cerca:** Regra gravada no system prompt do agente, em dois pontos de `src/browser_mcp/agent.py`:

- Regra 9 (linha ~38): "NEVER use browser_execute_javascript to click links or navigate. JS click events (element.click()) have isTrusted=false and are blocked by Google News and many SPAs. Always use browser_click…"
- Descrição da tool (linha ~64, com ⚠️): "Execute JavaScript on the page for DATA EXTRACTION only. ⚠️ NEVER use for clicking/navigation — events have isTrusted=false. Use browser_click instead."

**Evidência:**

```bash
grep -n "isTrusted" src/browser_mcp/agent.py
```

**Status: CERCADO — regra ativa.** Não tente "consertar" clicks JS (dispatchEvent, MouseEvent com bubbles, simulação de coordenadas via JS — tudo isso continua `isTrusted=false`). Use `browser_click`, que dispara eventos reais via CDP. Se um site ignora até `browser_click`, o problema é outro (elemento coberto, iframe, shadow DOM) — vá para a skill `browser-mcp-playbook-de-depuracao`.

---

## 4. Commit P0 `cbc8e28` — "4 P0 fixes" (2026-07-10)

**Sintoma/Pergunta:** O que exatamente os "4 P0 fixes — security, CSP bypass, navigate, future leak" corrigiram? Onde está cada um?

**Nota arqueológica importante:** após o filter-repo de 2026-07-12, `cbc8e28` é o **commit raiz** — não existe estado "antes dos fixes" no histórico, então `git show cbc8e28` mostra o repositório inteiro sendo adicionado (94 arquivos, ~32.800 inserções), não um diff incremental. A evidência de cada fix é a **mensagem de commit + o código presente no snapshot**, verificados abaixo.

| Fix | O que era | Onde está (verificado no snapshot `cbc8e28`) |
|-----|-----------|---------------------------------------------|
| 1 — Security (WS auth) | WebSocket server sem autenticação | `websocket_server.py`: token `secrets.token_urlsafe(32)` gerado no boot → `~/.mcp_browser_token` (linhas ~48/61); validação de Origin `chrome-extension://` no handshake (linha ~203); token via header `Authorization` (Python) ou `?token=` (extensão); extensão lê de `chrome.storage.local` (`getAuthToken` em `background.js` linha ~28) |
| 2 — CSP bypass | `execute_javascript` falhava em sites com CSP sem `unsafe-eval` | `extension/background.js`: fallback `eval` → se erro CSP → `evalViaDebugger()` usando `chrome.debugger` + `Runtime.evaluate` (CDP), detach imediato (linha ~635); permissão `debugger` no `manifest.json`. Obs.: existe também `bypass_csp = True` no contexto Playwright (`browser_manager.py` linha ~154) — é mecanismo do modo Playwright, distinto deste fix da extensão |
| 3 — Navigate | `navigate` criava aba nova sempre (perdia a aba ativa) | `background.js` linha ~206: sem `params.newTab` → `chrome.tabs.update` (reusa aba ativa); com `newTab: true` → `chrome.tabs.create` |
| 4 — Future leak | Futures pendurados após timeout em `execute_command` | `websocket_server.py` `execute_command` (~linha 507): `try/finally` com `self._pending_responses.pop(req_id, None)`; `get_running_loop()` no lugar do deprecado `get_event_loop()`; branch de resposta com erro agora faz `fut.set_exception(RuntimeError(...))` (linha ~443) em vez de resolver com `None` silencioso |

**Evidência:**

```bash
git show cbc8e28 --stat | head -40                       # mensagem completa descrevendo os 4 fixes
git show cbc8e28:src/browser_mcp/websocket_server.py | grep -n "token_urlsafe\|chrome-extension\|get_running_loop\|pop(req_id"
git show cbc8e28:extension/background.js | grep -n "evalViaDebugger\|tabs.update\|getAuthToken"
```

**Status: resolvido.** Mensagem do commit registra "43/43 pytest passing. Tested: Perplexity, GitHub, example.com". **Não confirmado por diff**: o estado pré-fix (o bug em si) não é observável — foi eliminado pela reescrita de histórico. Confie na mensagem + snapshot, nada além disso.

---

## 5. Incidente da chave privada `extension.pem` (2026-07-12)

**Sintoma:** A chave privada de assinatura da extensão Chrome (`extension.pem`) estava **commitada no repositório** e, segundo o registro do incidente, esteve presente em **2 remotes**.

**Causa raiz:** Artefato de build versionado por descuido; `.gitignore` inicial não cobria `*.pem`/`*.crx`.

**Resposta (2026-07-12):**

1. Removida do working tree junto com `extension.crx` e demais artefatos (commit `ddf9bc1`).
2. **Purgada do histórico com `git filter-repo`** — todos os hashes de commit foram reescritos. Por isso qualquer referência a hashes antigos (em issues, notas, chats) está morta; os hashes válidos são os desta crônica.
3. `.gitignore` atualizado: `extension.pem`, `*.pem`, `extension.crx`, `*.crx`.

**Evidência:**

```bash
git show ddf9bc1 --stat | head -20                 # mensagem cita a remoção da chave; extension.crx aparece no diff
git log --all --full-history --oneline -- extension.pem   # VAZIO = purga bem-sucedida (o .pem não existe em NENHUM commit)
grep -n "pem\|crx" .gitignore                      # linhas 40-43
```

Note a assimetria proposital: `extension.crx` aparece no diff de `ddf9bc1` (foi só deletado), mas `extension.pem` **não aparece em lugar nenhum do histórico** — o filter-repo o apagou de todos os commits, inclusive do raiz.

**Status: ABERTO.** A chave é considerada **COMPROMETIDA** (esteve exposta em remotes). Pendência: **regenerar a chave de assinatura** — atenção: **o ID da extensão Chrome mudará**, o que afeta a validação de Origin `chrome-extension://<id>` e qualquer configuração que fixe o ID. Lição gravada: nunca versionar `*.pem`/`*.crx`; o `.gitignore` agora cerca isso. A afirmação "2 remotes" vem do registro do incidente e não é verificável pelo repo atual (`git remote -v` hoje lista 1 remote).

---

## 6. Estado do lint — dívida quitada (2026-07-18)

**Sintoma histórico:** por um período, `ruff check` e `ruff format --check` falhavam **em código já commitado** — dívida acumulada porque o CI só dispara em push/PR para `main`/`master` (`.github/workflows/ci.yml`, gatilhos nas linhas 4-7) e branches de feature não têm gate.

**Resolução:** a dívida foi quitada num commit dedicado (`ruff check --fix` + `ruff format`, sem mudança funcional). Hoje `ruff check src/browser_mcp tests` e `ruff format --check src/browser_mcp tests` (o escopo do CI) passam limpos. `ruff check .` na raiz ainda acusa erros em scripts fora do escopo do CI (`manage_mcp_browser.py`, scripts de skills) — não bloqueiam o CI.

**Evidência (re-meça sempre):**

```bash
.venv/bin/ruff check src/browser_mcp tests
.venv/bin/ruff format --check src/browser_mcp tests
grep -n -A4 "^on:" .github/workflows/ci.yml
```

**Status: RESOLVIDO** no escopo do CI. **Lar canônico do estado de lint/CI:** [[browser-mcp-controle-de-mudancas]] §3.

---

## Quando NÃO usar esta skill

- **Depuração ativa de um problema acontecendo agora** → `browser-mcp-playbook-de-depuracao` (a arqueologia é consulta histórica, não triagem).
- **Entender o design atual do sistema** → `browser-mcp-contrato-de-arquitetura` (aqui está o *porquê* histórico; lá, o *o quê* resultante).
- **Regras do que pode/não pode mudar** → `browser-mcp-controle-de-mudancas` (os inegociáveis derivados destes incidentes moram lá).
- **Setup, build, dependências** → `browser-mcp-build-e-ambiente`. **Rodar/operar** → `browser-mcp-executar-e-operar`. **Flags e configuração** → `browser-mcp-config-e-flags`.
- **Ferramentas de diagnóstico** → `browser-mcp-diagnosticos-e-ferramentas`. **QA/validação** → `browser-mcp-validacao-e-qa`.
- **Referência de automação de browser em geral** → `browser-automacao-referencia`.
- **Confiabilidade do agente LLM** → `browser-mcp-campanha-confiabilidade-do-agente`. **Posicionamento vs concorrentes** → `browser-mcp-fronteira-e-posicionamento`. **Método de prova/verificação** → `browser-mcp-metodologia-e-prova`.

---

## Proveniência e manutenção

**Fontes desta crônica** (verificadas pós filter-repo de 2026-07-12):

- Histórico git: o commit raiz é `cbc8e28` (os 4 P0 fixes); o incidente da
  chave `.pem` foi tratado em `ddf9bc1`. Para o histórico completo e atual, rode
  `git log --oneline` — a lista cresce a cada mudança.
- Docs históricos recuperáveis apenas via `git show cbc8e28:<arquivo>`: `aprendizado_webbridge.md` (benchmark WebBridge), `investigacao_indicadores_visuais.md` (indicadores visuais).
- Código vivo: `src/browser_mcp/agent.py`, `websocket_server.py`, `browser_manager.py`, `visual_indicator.py`, `extension_bridge.py`, `extension/background.js`, `.github/workflows/ci.yml`, `.gitignore`.

**Para listar o que aconteceu desde a última entrada desta crônica:**

```bash
git log --oneline ddf9bc1..HEAD          # commits novos desde a última entrada registrada
git log --all --oneline | head -20       # visão geral (o repo é raso; cabe na tela)
```

**Como adicionar uma nova entrada:**

1. Formato obrigatório: **Sintoma/Pergunta → Causa raiz/Decisão → Evidência (comando copiável) → Status (resolvido/cercado/aberto)**. Date a entrada.
2. A evidência deve ser reproduzível por quem chega frio: `git show <hash>:<arquivo>`, `grep -n` em arquivo vivo, ou saída de comando. Rode o comando antes de escrever. Se algo não for confirmável, rotule explicitamente como "não confirmado".
3. Nunca use caminhos privados de máquina de usuário como fonte essencial.
4. Atualize o índice rápido e, se a entrada gerar um inegociável, propague-o para `browser-mcp-controle-de-mudancas`.
5. **Se o histórico for reescrito de novo** (outro filter-repo), todos os hashes desta crônica quebram: rode `git log --all --oneline`, remapeie pelos títulos de commit (que sobrevivem à reescrita) e atualize os hashes aqui.
