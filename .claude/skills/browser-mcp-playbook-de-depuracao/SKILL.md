---
name: browser-mcp-playbook-de-depuracao
description: >
  Playbook sintoma → triagem para o browser-mcp-server. Use quando algo QUEBRA em runtime:
  "click não funciona" / "click não faz nada" / evento ignorado; "extensão não conecta" /
  WebSocket 401/403 / service worker dormiu; "timeout esperando elemento" / dropdown vazio /
  cascata AJAX; overlay/indicador visual não aparece; "agente em loop" / repete ação /
  estoura iterações; "ERROR: [Server] - ..." genérico; startup
  falha silenciosamente. Cada sintoma tem causa provável, experimento discriminatório
  copiável e referência file:line.
---

# Playbook de Depuração — browser-mcp-server

Runbook sintoma → causa → experimento para os modos de falha REAIS deste projeto, construído lendo o código (mensagens de erro, guards, timeouts) e os documentos históricos recuperáveis via `git show cbc8e28:<doc>.md`. Linhas verificadas em 2026-07-17 — re-confira após refactors grandes.

## Quando NÃO usar esta skill

- **Setup/instalação quebrada** (dependências, playwright install, venv) → `browser-mcp-build-e-ambiente`.
- **Como rodar/operar o servidor** (comandos de start, modos) → `browser-mcp-executar-e-operar`.
- **Significado de cada flag/env var** → `browser-mcp-config-e-flags`.
- **A crônica completa dos incidentes** → `browser-mcp-arqueologia-de-falhas` (este playbook referencia as histórias, não as reconta).
- **Catálogo das ferramentas de medição** (network log, HAR, console) → `browser-mcp-diagnosticos-e-ferramentas`.
- **Teoria por trás de isTrusted/CSP/MV3** → `browser-automacao-referencia`.
- **Escrever/alterar código** → `browser-mcp-contrato-de-arquitetura` e `browser-mcp-controle-de-mudancas`.

## Pré-triagem universal: torne o stderr visível

Todos os logs vão para **stderr** com prefixos `[SERVER]`, `[WS-SERVER]`, `[EXTENSION-BRIDGE]`, `[TOOLS]` (verificado em `server.py:68`, `websocket_server.py:118`, `extension_bridge.py:55`, `tools.py:98`). Rodando sob um cliente MCP, o stderr costuma ser engolido. Antes de qualquer triagem:

```bash
cd /caminho/do/repo/mcp_browser
.venv/bin/python -m browser_mcp.server 2> /tmp/mcp_stderr.log &   # console script browser-mcp-server está quebrado (main async)
tail -f /tmp/mcp_stderr.log
```

Duas armadilhas de "engolimento" tornam isso obrigatório — ver sintomas 7 e 8.

## Mapa rápido sintoma → seção

| Sintoma | Seção |
|---|---|
| Click não faz nada / evento ignorado | 1 |
| Extensão Chrome não conecta ao WebSocket | 2 |
| Timeout esperando elemento / dropdown vazio | 3 |
| Overlay/indicador visual não aparece | 4 |
| Agente em loop / repete ação / estoura iterações | 5 |
| `ERROR: [Server] - ...` genérico sem stack | 6 |
| Startup "funciona" mas browser não iniciou | 7 |

---

## 1. "Click não faz nada / evento ignorado"

| Hipótese | Causa provável | Como discriminar | Referência |
|---|---|---|---|
| A | Evento sintético com `isTrusted=false` — o site ignora silenciosamente | Experimento abaixo: nativo funciona, dispatchEvent não | `src/browser_mcp/agent.py:38`, `browser_manager.py:667-668` |
| B | Elemento errado/coberto — Playwright clicou, mas em outro alvo | `browser_screenshot` antes/depois; conferir seletor com `browser_get_attributes` | `browser_manager.py:699-771` |
| C | Click funcionou mas a página reage via AJAX lento | `browser_get_network_log` mostra request disparado | Sintoma 3 |

**Armadilha que custou tempo real (isTrusted).** Eventos gerados por `element.click()` dentro de `browser_execute_javascript` têm `isTrusted=false`; Google News e muitas SPAs os descartam **sem erro nenhum** — o click "funciona" e nada acontece. Custou tempo suficiente para virar regra permanente no system prompt do agente: `agent.py:38` (RULES, regra 9: "NEVER use browser_execute_javascript to click links or navigate... isTrusted=false") e na descrição da própria tool em `agent.py:64` ("⚠️ NEVER use for clicking/navigation"). O docstring de `browser_manager.click()` repete o aviso (`browser_manager.py:667-668`).

**Experimento discriminatório (causa A vs B):** no MESMO elemento, compare o caminho nativo com o sintético.

```text
# 1. Caminho nativo (eventos trusted via CDP/Playwright):
browser_click {"selector": "#alvo"}

# 2. Caminho sintético (isTrusted=false):
browser_execute_javascript {"code": "document.querySelector('#alvo').dispatchEvent(new MouseEvent('click', {bubbles:true})); 'dispatched'"}
```

- Nativo funciona, sintético não → causa A (site checa `isTrusted`). Use sempre `browser_click`.
- Nenhum funciona → causa B ou C: tire screenshot e leia o network log.

**Nota:** o próprio `_smart_click` usa `dispatchEvent` como **estratégia 4 de fallback** (`browser_manager.py:745-761`) depois de click nativo, force click e navegação via href (`browser_manager.py:709-743`). Se o resultado disser `Elemento clicado (events)`, você caiu no caminho sintético — desconfie do efeito em sites que checam `isTrusted`.

## 2. "Extensão não conecta"

Triagem em cadeia — pare no primeiro elo quebrado. Handshake: `websocket_server.py:199-304`; reconexão da extensão: `extension/background.js:38-131`.

| # | Elo | Como verificar | Referência |
|---|---|---|---|
| 1 | WS server rodando na 8765? | `lsof -iTCP:8765 -sTCP:LISTEN` — log esperado: `[WS-SERVER] WebSocket server iniciado em ws://...` | `websocket_server.py:73` (porta default 8765), `websocket_server.py:118` |
| 2 | Token confere? | Token do servidor: `cat ~/.mcp_browser_token`. Extensão lê `chrome.storage.local.mcpToken` e anexa `?token=` na URL. Mismatch → **HTTP 401** | `websocket_server.py:50,53-67,242-273`; `background.js:29-48` |
| 3 | Origin é `chrome-extension://`? | Origin presente e diferente disso → **HTTP 403**. Em modo restrito, origin vazio também é 403 | `websocket_server.py:219-239` |
| 4 | Payload > 64 MiB? | Log `[WS-SERVER] Payload muito grande (...), fechando conexão` — servidor fecha o frame | `websocket_server.py:49` (`MAX_PAYLOAD_SIZE = 64 * 1024 * 1024`), `:371-376` |
| 5 | Service worker MV3 dormiu? | Chrome mata o worker ocioso; a extensão usa `chrome.alarms` como keep-alive (`ws-keepalive` a cada 0.3 min reconecta se `!connected`; `keepalive` a cada 0.5 min). Inspecione em `chrome://extensions` → service worker → console | `background.js:134-143` e `:872-875` |
| 6 | Reconexão em andamento? | Backoff: 2000 ms inicial, +500 ms por falha, teto 5000 ms — espere ~5 s antes de concluir que morreu | `background.js:16-17,125-131` |

**Experimento discriminatório (servidor vs extensão):** simule a extensão com um cliente mínimo. Se ele conecta, o problema está do lado da extensão (token não salvo, worker dormindo); se não conecta, é servidor/porta/token.

```bash
TOKEN=$(cat ~/.mcp_browser_token)
.venv/bin/python - <<EOF
import asyncio, websockets
async def main():
    async with websockets.connect(
        f"ws://localhost:8765/?token=$TOKEN",
        origin="chrome-extension://teste",
    ) as ws:
        await ws.send('{"type":"ping"}')
        print("resposta:", await ws.recv())
asyncio.run(main())
EOF
```

- `HTTP 401` → token errado (elo 2). `HTTP 403` → origin (elo 3). Connection refused → servidor não subiu (elo 1 — ver sintoma 8).
- Cliente Python OK mas extensão não → abra o console do service worker e procure `[MCP Bridge] Token ausente — configure em Options/Popup` (`background.js:44`).

**História:** token + validação de origin entraram no commit P0 `cbc8e28` (FIX 1) — extensões antigas sem `mcpToken` em `chrome.storage.local` pararam de conectar "do nada" após o upgrade. Confira com `git show cbc8e28 --stat`.

**Timeouts relacionados:** comando para a extensão espera resposta por 10 s no WS server (`websocket_server.py:552`) e o bridge usa default 15 s (`extension_bridge.py:97`); estouro vira `Timeout ao aguardar resposta da extensão para <tool>` (`websocket_server.py:566-569`). `RuntimeError: Nenhuma extensão Chrome conectada via WebSocket.` vem de `extension_bridge.py:115`.

## 3. "Timeout esperando elemento / dropdown vazio"

| Hipótese | Causa provável | Como discriminar | Referência |
|---|---|---|---|
| A | Cascata AJAX: o dropdown só popula depois de um request disparado pelo campo anterior | Network log mostra o request dependente (ou a ausência dele) | história i-Educar abaixo |
| B | Seletor errado / elemento nunca existirá | `browser_get_content` com `as_html=true` no container pai | `tools.py:606` |
| C | Timeout curto demais para o backend lento | Repetir com `timeout` maior no `browser_wait` | `browser_manager.py:1008-1041`, default `BROWSER_TIMEOUT=30000` (`browser_manager.py:39`) |

**História (i-Educar, custou uma investigação inteira).** No diário de classe do i-Educar, os filtros Escola → Curso → Série → Turma → Etapa → Componente são dependentes: cada `change` dispara um GET para `/module/DynamicInput/*` (Curso, serie, turma, Etapa, componenteCurricular) e o JSON de resposta (`options`) popula o próximo `<select>`. Selecionar Turma antes do AJAX de Série terminar = dropdown vazio ou timeout. Pior: a base demo às vezes retornava `matriculas: []` — ou seja, o dropdown vazio era **dado real**, não bug de timing. A única forma de distinguir foi OLHAR a chamada AJAX em vez de adivinhar. Fonte completa: `git show cbc8e28:relatorio_ieducar.md` (tabela de endpoints na seção 3).

**Experimento discriminatório (timing A vs dado-vazio vs seletor B):**

```text
# 1. Ligue o monitor de rede ANTES de interagir:
browser_network_start {}

# 2. Faça a ação que deveria popular o dropdown:
browser_select_option {"selector": "#escola", "value": "481777"}

# 3. Espere a rede assentar (não use sleep cego):
browser_wait {"condition": "network_idle", "timeout": 15000}

# 4. VEJA a chamada em vez de adivinhar:
browser_get_network_log {"filter_url": "DynamicInput"}
```

- Request aparece e a resposta tem `options` preenchido → era timing (causa A): passe a usar `browser_wait` com `network_idle` ou `element_visible` entre cada filtro.
- Request aparece com `options`/`matriculas` vazio → o backend não tem dados; nenhum wait resolve.
- Request NÃO aparece → seu `select`/`click` não disparou o evento `change` (volte ao sintoma 1) ou o seletor está errado (causa B).

Condições suportadas por `browser_wait`: `element_visible`, `element_hidden`, `network_idle`, `timeout` (`browser_manager.py:1020-1041`; tool em `tools.py:952-989`). Tools de rede: `browser_network_start/stop/list/clear` (`tools.py:748-842`) e `browser_get_network_log` (`tools.py:849`).

## 4. "Overlay/indicador visual não aparece"

| Hipótese | Causa provável | Como discriminar | Referência |
|---|---|---|---|
| A | Modo extension: `inject_indicator()` retorna `""` **por design** — não há overlay nesse modo | Estava em modo extension? (`browser_connect_to_extension` foi chamado?) | `browser_manager.py:1168-1169` |
| B | CSP da página bloqueando o `page.evaluate` de injeção | Experimento abaixo; erro é ENGOLIDO (vira string de retorno, e `navigate` a descarta) | `browser_manager.py:1174-1176`, `:585-586` |
| C | `ENABLE_VISUAL_INDICATOR=0` ou `STEALTH_MODE=0` | `env \| grep -E 'VISUAL\|STEALTH'` | `browser_manager.py:41-42,156` |
| D | Página fez full reload após a injeção (overlay não persiste) | Reinjetar via nova navegação | `browser_manager.py:585-586` |

**História (motivou o CSP bypass do commit P0).** Indicadores visuais foram investigados em `git show cbc8e28:investigacao_indicadores_visuais.md` (comparativo Kimi WebBridge / Claude Desktop / Gemini CLI; decisão: overlay CSS via `Runtime.evaluate`). Na prática, páginas com CSP estrito quebravam a injeção de JS — o mesmo problema que quebrava `execute_javascript` na extensão. O commit `cbc8e28` (FIX 2) adicionou o bypass: no lado extensão, fallback `evalViaDebugger()` via `chrome.debugger` + `Runtime.evaluate` (`extension/background.js:352-357,697-717`); no lado Playwright, `context_opts["bypass_csp"] = True` — mas **só quando `STEALTH_MODE` está ativo** (`browser_manager.py:153-156`; default é `true`, `browser_manager.py:42`). Confira o escopo do commit com `git show cbc8e28 --stat`.

**Experimento discriminatório (CSP B vs flag C):**

```text
# Injeção manual — ao contrário do navigate, aqui o retorno é visível:
browser_execute_javascript {"code": "(() => { const d=document.createElement('div'); d.id='__probe'; d.style.cssText='position:fixed;top:0;left:0;z-index:2147483647;background:red;color:#fff'; d.textContent='PROBE'; document.body.appendChild(d); return 'ok'; })()"}
```

- Probe aparece mas o overlay oficial não → causa C ou A (flag desligada ou modo extension) — o CSP não é o problema.
- Probe falha/retorna erro → causa B (CSP): verifique `STEALTH_MODE=1` no Playwright, ou confirme no console do service worker que o fallback `via: 'debugger'` foi usado (`background.js:712-715`).

**Armadilha:** `inject_indicator` captura a exceção e devolve a string `"Erro ao injetar indicador: ..."` (`browser_manager.py:1175-1176`), e `navigate` chama `await self.inject_indicator()` **descartando o retorno** (`browser_manager.py:585-586`). Falha de CSP na navegação é 100% silenciosa — por isso o experimento manual acima é necessário.

## 5. "Agente em loop / repete ação / estoura iterações"

Guards do loop (`src/browser_mcp/agent.py`): `max_iterations=30` (`agent.py:87,120,216-220`), `max_consecutive_errors=3` (`agent.py:88`). `consecutive_errors` incrementa em falha de LLM (`agent.py:155`), falha de parse (`agent.py:170`) e falha de tool (`agent.py:491`).

| Hipótese | Causa provável | Como discriminar | Referência |
|---|---|---|---|
| A | `_parse_response` falhando: LLM não devolve JSON extraível | Transcript mostra `Could not parse LLM response at iteration N` | `agent.py:166-177,355-371` |
| B | Tool falhando toda iteração e o agente insistindo | `action_history[*].result` começa com `Tool '...' failed:` repetido | `agent.py:488-530` |
| C | Tarefa genuinamente grande para 30 iterações | `action_history` mostra progresso real, sem repetição | `agent.py:216-220` |

**Armadilha (o abort por erros consecutivos quase nunca dispara para tools).** `consecutive_errors` é **zerado a cada chamada de LLM bem-sucedida** (`agent.py:151`). Falha de tool incrementa em `agent.py:491`, mas na iteração seguinte o LLM responde OK e o contador volta a 0 — então erros de tool repetidos NÃO abortam em 3: o agente roda até `max_iterations=30` reexecutando a mesma ação quebrada. Se o relatório final é `Task reached max iterations (30) without completing.` (`agent.py:219`), procure a ação repetida no histórico, não espere um abort limpo.

**Triagem — leia o RECORD.** Cada iteração grava `{iteration, tool, params, thought, result}` em `action_history` (`agent.py:201-207`), devolvido no resultado final junto com `errors` (`agent.py:580-590`). Loop = mesma tripla `tool+params+result` repetida.

**Experimento discriminatório (parse A vs tool B):** os 5 testes de parsing em `tests/test_agent.py:145-197` documentam os formatos problemáticos (` ```json` fenced :145, JSON cru :160, texto sem JSON :173, resposta vazia :181, markdown aninhado :188). Reproduza com a resposta real do transcript:

```bash
.venv/bin/python -c "
from browser_mcp.agent import BrowserAgent
a = BrowserAgent.__new__(BrowserAgent)
resp = open('/tmp/resposta_llm.txt').read()  # cole a resposta crua do LLM aqui
print(a._parse_response(resp))
"
```

- `None` → causa A: o modelo está fugindo do contrato ` ```json {...} ``` ` (fallbacks do parser em `agent.py:360-366`). Ver `browser-mcp-campanha-confiabilidade-do-agente`.
- Dict válido mas loop continua → causa B: o problema é a tool/seletor, não o parse — trate como sintoma 1 ou 3.

```bash
.venv/bin/python -m pytest tests/test_agent.py -q   # os testes de parse e guards devem passar
```

## 6. "ERROR: [Server] - ..." genérico

**Armadilha:** o handler MCP engole QUALQUER exceção de tool e devolve só `f"ERROR: [Server] - {str(e)}"` — sem tipo, sem traceback (`src/browser_mcp/server.py:29-32`). Um `KeyError` de dict e um crash do Playwright chegam idênticos ao cliente. (Erros que passam pelo wrapper das tools ganham formato melhor — `ERROR: [Tipo] - mensagem - sugestão`, `tools.py:78-93` — se você vê o formato curto `[Server]`, a exceção estourou FORA desse wrapper, ex.: argumento inexistente na assinatura da tool, `tools.py:72`.)

**Triagem:** rode com stderr visível (pré-triagem no topo) e reproduza a chamada — o traceback real aparece no stderr, junto com `[TOOLS] <nome> executado em X.XXXs` (`tools.py:96-98`) das tools que chegaram a executar.

```bash
.venv/bin/python -m browser_mcp.server 2> /tmp/mcp_stderr.log &   # console script browser-mcp-server está quebrado (main async)
# reproduza a chamada da tool pelo cliente MCP, depois:
tail -50 /tmp/mcp_stderr.log
```

- `ERROR: [Server] - Ferramenta desconhecida: X` → nome de tool errado (`tools.py:70`).
- `... unexpected keyword argument ...` → parâmetro que a tool não aceita (a chamada morre em `tools.py:72` antes do wrapper).

## 7. "Startup falha silenciosamente"

**Armadilha:** `main()` trata falha de inicialização do browser/LLM/WebSocket como AVISO e segue em frente: `except Exception as e: print(f"[SERVER] Aviso: Falha na inicialização opcional: {e}")` (`src/browser_mcp/server.py:69-75`). O servidor stdio sobe normalmente (`server.py:77-78`), o cliente MCP conecta, lista tools — e a primeira chamada real falha porque o browser nunca iniciou ou a porta 8765 estava ocupada.

**Triagem:** procure a linha de sucesso no stderr; a ausência dela + presença do "Aviso" é o diagnóstico.

```bash
grep -E "Aviso: Falha na inicialização|BrowserManager, LLMClient e WebSocketServer inicializados" /tmp/mcp_stderr.log
```

- Só o "Aviso" aparece → leia a exceção na mesma linha. Causas típicas: chromium do Playwright ausente (`.venv/bin/playwright install chromium` — ver [[browser-mcp-build-e-ambiente]]), porta 8765 ocupada (`lsof -iTCP:8765`).
- Linha de sucesso aparece (`server.py:73`) → o startup está OK; o problema é outro sintoma deste playbook.

---

## Verificação de sanidade geral

```bash
.venv/bin/python -m pytest tests/ -q    # suíte completa (~1 min; requer `.venv/bin/playwright install chromium`)
```

Em 2026-07-17, a suíte é `tests/test_agent.py`, `test_smoke.py`, `test_tools.py` (43 testes coletados). Se testes falham, o problema é ambiente/regressão — vá para `browser-mcp-build-e-ambiente` ou `browser-mcp-validacao-e-qa` antes de caçar bugs de runtime.

## Proveniência e manutenção

- **Fontes primárias (todas verificadas em 2026-07-17):** `src/browser_mcp/server.py`, `tools.py`, `browser_manager.py`, `agent.py`, `extension_bridge.py`, `websocket_server.py`, `visual_indicator.py`, `extension/background.js`, `tests/test_agent.py`.
- **Docs históricos (recuperáveis do commit `cbc8e28`):** `git show cbc8e28:relatorio_ieducar.md` (cascatas AJAX), `git show cbc8e28:investigacao_indicadores_visuais.md` (overlay/CSP), `git show cbc8e28:aprendizado_webbridge.md` (@e refs, network monitoring), `git show cbc8e28:analise_extensao_necessaria.md` (por que existe a extensão). O próprio commit: `git show cbc8e28 --stat`.
- **Volatilidade:** todos os `file:line` datam de 2026-07-13; `tools.py` e `websocket_server.py` tinham modificações não commitadas nessa data — re-verifique linhas desses dois arquivos com `grep -n` antes de citar. Ao mover código, atualize esta skill junto (processo em `browser-mcp-controle-de-mudancas`).
- **Skills irmãs citadas:** `browser-mcp-perfil-restrito`, `browser-mcp-build-e-ambiente`, `browser-mcp-executar-e-operar`, `browser-mcp-config-e-flags`, `browser-mcp-arqueologia-de-falhas`, `browser-mcp-diagnosticos-e-ferramentas`, `browser-automacao-referencia`, `browser-mcp-campanha-confiabilidade-do-agente`, `browser-mcp-validacao-e-qa`, `browser-mcp-controle-de-mudancas`, `browser-mcp-contrato-de-arquitetura`.
