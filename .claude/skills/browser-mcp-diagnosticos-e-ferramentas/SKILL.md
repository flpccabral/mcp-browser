---
name: browser-mcp-diagnosticos-e-ferramentas
description: >
  Como MEDIR em vez de olhar no MCP Browser: catálogo das ferramentas de diagnóstico e
  como interpretar a saída. Use quando precisar: capturar tráfego de rede (network log,
  browser_network_start/stop/list/clear, browser_get_network_log, exportar HAR),
  achar a chamada AJAX que popula um dropdown ou cascata, ler console
  errors (browser_get_console_errors, erros GraphQL/React), despejar o accessibility tree
  e usar refs @e, listar elementos interativos, entender por que um elemento NÃO aparece,
  usar o ws_client.py manual, ler logs de stderr, listar as ferramentas registradas,
  ou conferir env vars efetivas. Gatilhos: "medir", "network log", "HAR", "console errors",
  "accessibility tree", "refs @e", "elementos interativos", "quantas tools", "dropdown vazio".
---

# Diagnósticos e Ferramentas — browser-mcp-server

Este projeto tem instrumentos para **medir** o browser em vez de adivinhar. Esta skill cataloga cada um, mostra o comando exato e — o mais importante — **como ler a saída**. Todas as referências `file:line` e contagens foram verificadas em 2026-07-17; re-confira após refactors grandes (veja "Proveniência e manutenção").

Regra de ouro: **antes de propor uma causa, produza uma medição que a discrimine.** Se a resposta for "olhei e parece que...", pare e escolha um instrumento abaixo.

## Quando NÃO usar esta skill

- **Algo QUEBROU e você quer triar o sintoma** (click não funciona, extensão não conecta, timeout) → `browser-mcp-playbook-de-depuracao` (ele *usa* estes instrumentos na triagem).
- **Teoria por trás de CDP/CSP/isTrusted/accessibility/MV3** → `browser-automacao-referencia`.
- **Significado/default de cada env var** → `browser-mcp-config-e-flags` (aqui só damos o script `check_env.py` que mostra o valor efetivo).
- **A crônica de por que o console/overlay/extensão são assim** → `browser-mcp-arqueologia-de-falhas`.
- **Como provar uma alegação com rigor** → `browser-mcp-metodologia-e-prova`.

---

## Tabela — qual instrumento para qual pergunta

| Pergunta | Ferramenta / script | Comando | Como ler |
|---|---|---|---|
| Que chamada AJAX popula este dropdown? | `browser_network_start` → interagir → `browser_network_list` | `network_start`, mudar o `<select>` pai, `network_list` com `filter_method="POST"` | procure o request disparado *depois* da sua ação; o `response_body` traz as options |
| Que endpoints a página bate? | `browser_get_network_log` | `get_network_log` com `filter_url="/api"` | JSON detalhado com headers + body (truncado em 50000 bytes) |
| Guardar a sessão de rede para análise | `browser_export_har` | `export_har` com `path="webbridge_output/x.har"` | HAR 1.2 — abra no DevTools "Import HAR" ou em har-viewer |
| A página deu erro JS? (só modo extensão) | `browser_get_console_errors` | `get_console_errors` com `filter_text="GraphQL"` | só captura `console.warn`/`console.error` — veja limitação abaixo |
| Que elementos existem e com que ref estável? | `browser_accessibility_tree` | `accessibility_tree` | lista de `{ref:@eN, role, name}`; use o `@eN` depois |
| Visão alternativa dos clicáveis | `get_interactive_elements` (interno) | via agente/CDP | tag/id/name/text/selector dos até 50 primeiros visíveis |
| Quais ferramentas existem mesmo? | `scripts/dump_tools.py` | `python .../dump_tools.py` | 39 nomes + descrição (README diz 37 — divergência aberta) |
| Minha env var tem efeito? | `scripts/check_env.py` | `python .../check_env.py` | valor efetivo + o que o `.env.example` documenta errado |
| Testar a extensão sem cliente MCP | `ws_client.py` (raiz) | `python ws_client.py navigate '{"url":"..."}'` | JSON cru da resposta da extensão |

Os `python .../` acima referem-se a `.claude/skills/browser-mcp-diagnosticos-e-ferramentas/scripts/`. Use o Python do repo: `.venv/bin/python` (3.14).

---

## 1. Network monitoring

### Dois substratos, mesma interface de tools

As tools de rede funcionam nos dois modos, mas por caminhos diferentes:

- **Playwright** (modo padrão/CDP): `NetworkInterceptor` em `network.py` — anexa listeners `page.on("request"/"response")` (`network.py:26-31`). Só captura enquanto `_recording=True` (`network.py:75`), por isso **precisa de `browser_network_start` antes**. Captura request + response body decodificado UTF-8, truncado em `max_body_length=50000` (`network.py:14,133`). O log é um ring buffer de `max_log_size=10000` entradas (`network.py:64-68`).
- **Extensão Chrome**: `browser_manager` delega para `extension_bridge.get_network_log` (`browser_manager.py:418-428`, `462-464`). Nesse modo, `browser_network_start` só limpa o log (`browser_manager.py:388-390`) — a captura é feita pelo `background.js` da extensão continuamente.

### As tools (todas em `tools.py`)

| Tool | Linha | O que faz |
|---|---|---|
| `browser_network_start` | `tools.py:753` | inicia gravação (Playwright) / limpa log (extensão) |
| `browser_network_stop` | `tools.py:774` | para gravação; retorna total capturado |
| `browser_network_list` | `tools.py:807` | lista com metadados de gravação (`recording`, `total_captured`, `filtered_count`, `requests`) |
| `browser_network_clear` | `tools.py:834` | zera o log |
| `browser_get_network_log` | `tools.py:867` | log detalhado em JSON (versão sem os metadados de gravação) |
| `browser_export_har` | `tools.py:898` | grava HAR 1.2 no `path` (cria o diretório, `network.py:240`) |

Ambos `network_list` e `get_network_log` aceitam `filter_url` (substring, `network.py:150`) e `filter_method` (igualdade, **case-insensitive via `.upper()`**, `network.py:152`). Não há filtro por status.

### Receita: achar a chamada AJAX que popula um dropdown

Caso clássico de automação: um `<select>` dependente que só carrega options após você mudar o `<select>` pai, via uma cascata AJAX. Para descobrir o endpoint:

```
1. browser_network_start
2. browser_network_clear              # começa limpo
3. (interaja) mude o <select> pai — browser_select_option no campo de cima
4. browser_wait ~1s                   # deixe o AJAX responder
5. browser_network_list  filter_method="POST"
```

**Como ler:** ordene mentalmente por `timestamp` (`network.py:90`); o request que interessa é o disparado **logo após** a sua ação. Confirme por três sinais no JSON: (a) `resource_type` costuma ser `xhr`/`fetch`; (b) o `response_body` contém as `<option>` ou o JSON com os itens que apareceram; (c) o `post_data` mostra o valor do pai que você selecionou. Anote a `url` e o `method` — é o contrato do endpoint. Se o `response_body` vier `null`, o body pode ter falhado na captura (`network.py:136-137`) ou excedido o truncamento; caia para o HAR ou re-rode.


### Ler o HAR

`browser_export_har` produz HAR 1.2 (`network.py:178-242`). Campos reais preenchidos: `request.method/url/headers`, `response.status/headers/content.text`. **Campos zerados de propósito:** todos os `timings` são `-1` e `time=0` (`network.py:194,227-235`) — este HAR **não** tem dados de latência; serve para inspecionar requests/respostas, não para medir performance. No modo extensão o HAR é mais pobre ainda (headers vazios, `browser_manager.py:492,502`).

---

## 2. Console errors (só modo extensão)

`browser_get_console_errors` (`tools.py:1189`) → `extension_bridge.get_console_errors` (`extension_bridge.py:254`). Parâmetros: `level` (`'error'`/`'warn'`/`'log'`), `filter_text` (substring na mensagem) e `limit` (default 50, mais recentes). Retorna `{total_captured, filtered_count, entries}`.

**O que é capturado EXATAMENTE — leia antes de confiar:** o `injected.js` só sobrescreve `console.warn` e `console.error` (`injected.js:99-107`). Consequências verificadas:

- **`console.log` NÃO é capturado.** O parâmetro `level='log'` existe no schema mas nunca casa nada — a lista só terá `warn`/`error`.
- **Erros não capturados (uncaught exceptions), `window.onerror` e rejeições de promise não tratadas NÃO são interceptados** — só o que passa por `console.error`/`console.warn`. Um `throw` que estoura no topo pode não aparecer aqui.
- Cada entrada é `{level, message}` onde `message = args.map(String).join(' ')` (`injected.js:100,105`) — objetos viram `[object Object]`. Para ver a estrutura, o autor da página teria que fazer `console.error(JSON.stringify(obj))`.
- Fluxo: `injected.js` → `content.js` → `background.js` → WebSocket → `extension_bridge` acumula em `_console_errors`, ring buffer (`extension_bridge.py:88-91`).

**Como ler:** para auditar erros GraphQL/React, filtre por `filter_text="GraphQL"` ou `"Cannot query"`. Se `total_captured=0` mas você viu erros no DevTools, quase sempre é um dos dois: a página lançou erro sem passar por `console.error`, ou você não está em modo extensão (a tool exige `browser_connect_to_extension`, senão levanta `RuntimeError`, `browser_manager.py:1155-1156`).

---

## 3. Accessibility tree e refs @e

`browser_accessibility_tree` (`tools.py:511`) → `browser_manager.get_accessibility_tree` (`browser_manager.py:314`). Retorna `{tree: [...], ref_map: {...}}`.

### Como é montado (dois caminhos)

- **Playwright/CDP** (`browser_manager.py:344-374`): cria uma sessão CDP e chama **`Accessibility.getFullAXTree`** (`browser_manager.py:349`). Playwright Python não expõe `page.accessibility`, por isso o CDP direto (`browser_manager.py:347`). Cada nó vira `{ref:@eN, role, name, nodeId, backendDOMNodeId}`; o `ref_map` guarda `backendDOMNodeId` para resolver o ref depois.
- **Extensão** (`browser_manager.py:316-342`): **não há AX tree** — cai para o `get_dom_snapshot` da extensão e constrói uma árvore simplificada onde `role = tag` do elemento e `name = text/name` (`browser_manager.py:327-333`). Ou seja, no modo extensão os "roles" são nomes de tags HTML, não roles ARIA.

### Como interpretar

Cada linha é `@eN  role  name`. O par **role+name** sobrevive a mudanças de classe CSS/estilo — é a âncora estável para depois clicar/digitar (é justamente por isso que os refs `@e` existem; a teoria está em `browser-automacao-referencia`). Fluxo típico: despeje a árvore → localize `role="button" name="Salvar"` → use esse `@eN`.

### Quando um elemento NÃO aparece

Checklist de causas reais:

1. **Elemento sem nome acessível.** No caminho CDP, `name` sai vazio se o elemento não tem label/aria-label/texto — ele aparece com `name=""` e fica difícil de achar. Um `<input>` sem `<label>` associado é o caso mais comum.
2. **Nós ignorados pela árvore de acessibilidade.** `getFullAXTree` já omite muita coisa `aria-hidden`/`display:none`. Se você precisa de um elemento que a AX tree esconde, use a visão alternativa (seção 4) ou um seletor CSS direto.
3. **Modo extensão:** a árvore é derivada do DOM snapshot; o que o snapshot da extensão não coletar, não estará aqui. `role` será a tag, não ARIA.
4. **Árvore vazia (`tree: []`).** Ambos os caminhos engolem exceções e retornam `{tree: [], ref_map: {}}` imprimindo o erro em **stderr** (`browser_manager.py:341,372-373`). Se veio vazio, vá ao stderr (seção 6) antes de concluir que a página não tem elementos.

---

## 4. Elementos interativos — visão alternativa

`browser_manager.get_interactive_elements` (`browser_manager.py:1090`) é a alternativa quando a AX tree não serve. No modo Playwright ele roda um `page.evaluate` que varre `a, button, input, select, textarea, [onclick], [role="button"]` (`browser_manager.py:1101-1103`), **filtra invisíveis** (rect 0×0, `display:none`, `visibility:hidden`, `browser_manager.py:1112-1114`) e retorna até **50** entradas (`browser_manager.py:1125`) com `{tag, type, id, name, text, href, selector}`.

Diferenças práticas x accessibility tree:

- Enxerga elementos **sem nome acessível** (pega por tag/onclick), então acha coisas que a AX tree esconde.
- Dá um `selector` CSS pronto (`sel + "#id"`, `browser_manager.py:1122`) — útil para tools baseadas em selector.
- Mas é limitado a 50 e à lista fixa de seletores; widgets custom sem `role="button"`/`onclick` escapam.

Não há tool MCP dedicada expondo `get_interactive_elements` diretamente na lista de 39 — ela é usada internamente (ex.: pelo agente/extensão via `get_interactive_elements`, `browser_manager.py:1092`). Se precisar do dado cru numa sessão de extensão, `browser_extension_get_dom_snapshot` (`tools.py:1165`) é o equivalente mais próximo.

---

## 5. ws_client.py — cliente WebSocket manual

Arquivo na **raiz** do repo: `ws_client.py` (37 linhas). É um utilitário para falar direto com a extensão via o WebSocket server standalone, **sem** subir o servidor MCP nem um cliente MCP.

**Uso:**
```
python ws_client.py <tool> '<params_json>'
python ws_client.py navigate '{"url":"https://example.com"}'
```
Conecta em `ws://localhost:8765`, envia `{"tool": ..., "params": ...}` e imprime a resposta JSON (`ws_client.py:13-17,32-33`).

**Limitações verificadas (leia antes de usar):**

- **Não faz handshake de token.** Ele só abre `ws://localhost:8765` e manda o comando (`ws_client.py:13`). O `WebSocketServer` real autentica por token (subprotocolo `mcp-token.<token>` ou `?token=`, `websocket_server.py:171-190`) — então este cliente **pode ser rejeitado** dependendo de como o servidor foi iniciado. É um utilitário de bancada, não um cliente de produção.
- **Requer a extensão já conectada** ao servidor standalone (`websocket_server_standalone.py`), senão não há quem responda ao comando.
- **Requer o pacote `websockets`** instalado; sem ele retorna `{"error": "websockets library not available"}` (`ws_client.py:18-20`) — o "fallback" prometido no comentário não existe.
- Timeout fixo de 10s por comando (`ws_client.py:9`).

Quando usar: reproduzir um comando isolado contra a extensão para isolar se o problema está na extensão ou na camada MCP. Para operar de verdade, use os comandos de `browser-mcp-executar-e-operar`.

---

## 6. Logs em stderr

Todo log deste projeto vai para **stderr**, com prefixos por componente:

| Prefixo | Componente | Ex. de origem |
|---|---|---|
| `[SERVER]` | servidor MCP | `server.py` |
| `[WS-SERVER]` | WebSocket server | `websocket_server.py:53` |
| `[EXTENSION-BRIDGE]` | ponte da extensão | `extension_bridge.py:55` |
| `[TOOLS]` | timing de cada tool | `tools.py` (`_log_call`, imprime `... executado em Ns`) |

Rodando sob um cliente MCP, o stderr costuma ser engolido — se estiver depurando, redirecione para arquivo (veja `browser-mcp-executar-e-operar`). O `[TOOLS] <nome> executado em <N>s` é sua medição de latência por chamada, emitido mesmo em erro (o `_log_call` roda no `except`).

**Token:** o WebSocket server lê/gera o token em `~/.mcp_browser_token` (`websocket_server.py:37`). Se `ws_client.py` ou a extensão forem rejeitados, confira esse arquivo. A validação do handshake (token via `hmac.compare_digest` + origin `chrome-extension://`) está em `websocket_server.py`; a teoria do handshake está em [[browser-automacao-referencia]].

---

## 7. Scripts desta skill

Em `scripts/`. Todos testados com `.venv/bin/python` (3.14) em 2026-07-13. Caminhos relativos à raiz do repo.

### `dump_tools.py` — lista as ferramentas registradas

```
.venv/bin/python .claude/skills/browser-mcp-diagnosticos-e-ferramentas/scripts/dump_tools.py
.venv/bin/python .../dump_tools.py --json
```

Faz **parsing estático (AST)** de `src/browser_mcp/tools.py` — **não importa** o módulo. Motivo: `tools.py` cria singletons no topo (`browser_manager = BrowserManager()`, `llm_client = LLMClient()`, `tools.py:15-16`); importar dispararia efeitos colaterais e exigiria dependências. O script extrai `name`+`description` de cada decorator `@app.tool(...)`.

**Contagem:** imprime **39** ferramentas. Cuidado com atalhos: `grep -c '^@app.tool' tools.py` também dá 39 (correto), mas um `grep 'app.tool('` ingênuo pega ocorrências extras (a definição do próprio decorator/docstrings). O **README declara 37** — divergência conhecida e ainda aberta; este script é a fonte de verdade.

### `check_env.py` — valor efetivo das env vars

```
.venv/bin/python .claude/skills/browser-mcp-diagnosticos-e-ferramentas/scripts/check_env.py
```

Imprime, para cada variável que o **código realmente lê**, o valor efetivo no ambiente atual (ou o default), com a origem `file:line`. Depois lista os nomes que o `.env.example` documenta mas o código ignora. Mascara `LLM_API_KEY`. Dois fatos que ele torna óbvios:

- **`.env.example` está ERRADO:** documenta `HEADLESS`, `DEFAULT_TIMEOUT`, `PLAYWRIGHT_BROWSER`, `USER_AGENT` — mas o código lê `BROWSER_HEADLESS` (`browser_manager.py:36`), `BROWSER_TIMEOUT` (`:39`), etc. `PLAYWRIGHT_BROWSER` e `USER_AGENT` **não são lidos em lugar nenhum**.
- **`load_dotenv()` é chamado** em `browser_mcp/__init__.py` (desde 2026-07-18), antes de qualquer submódulo ler `os.getenv`. Logo um `.env` na raiz do repo **é** carregado automaticamente. Variáveis já exportadas no ambiente vencem o `.env` (override=False).

O catálogo completo com defaults e efeitos está em `browser-mcp-config-e-flags`; aqui o script só mostra o estado *efetivo*.

---

## Proveniência e manutenção

Fatos verificados em **2026-07-17**. Re-verificações de uma linha:

- **39 tools:** `grep -c '^@app.tool' src/browser_mcp/tools.py` → 39; ou rode `dump_tools.py` (Total no stderr). README ainda diz 37 (`grep '37 ferramentas' README.md`) — divergência aberta.
- **Console só warn/error:** `grep -n 'console.warn\|console.error\|onerror' extension/injected.js` — só `warn`/`error` sobrescritos (`:99,:104`); nenhum `window.onerror`.
- **AX tree via CDP:** `grep -n 'getFullAXTree' src/browser_mcp/browser_manager.py` → `:349`.
- **`.env.example` errado / sem `load_dotenv`:** `grep -rn 'load_dotenv' src/` → vazio; `grep -rn 'os.getenv' src/browser_mcp/browser_manager.py` mostra os nomes `BROWSER_*` reais. Rode `check_env.py`.
- **Tamanhos:** `wc -l src/browser_mcp/network.py` (251), `src/browser_mcp/extension_bridge.py` (441), `ws_client.py` (37).
