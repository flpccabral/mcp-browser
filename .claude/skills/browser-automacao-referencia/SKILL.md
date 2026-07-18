---
name: browser-automacao-referencia
description: >-
  Pacote de teoria de domínio do browser MCP server, ancorado NESTE código (não
  em livro-texto). Explica os conceitos que um engenheiro pleno normalmente não
  domina e mostra onde cada um aterrissa no repo (file:line) mais a consequência
  prática. Cobre: o que é o protocolo MCP (stdio JSON-RPC, list_tools/call_tool,
  name+arguments) e como server.py o implementa; os três substratos —
  Playwright vs CDP connect_over_cdp vs extensão Chrome MV3 sobre WebSocket —
  e uma tabela capacidade×modo; o que é isTrusted e por que cliques sintéticos
  via dispatchEvent (isTrusted=false) são banidos para interação; a árvore de
  acessibilidade e as refs @e (role/name sobrevivem à troca de classes CSS); o
  que é Content-Security-Policy, bypass_csp, e se ele se aplica ao injected.js no
  modo extensão; o ciclo de vida do service worker MV3 e o keepalive via
  chrome.alarms; stealth / anti-detecção (navigator.webdriver, user-agent, launch
  args) e seus limites; o formato de export HAR; e o handshake do token da ponte
  (origin chrome-extension:// + hmac.compare_digest timing-safe). Use para
  entender POR QUE a automação é construída assim, para responder "o que é
  isTrusted / CSP / CDP vs Playwright / árvore de acessibilidade / service worker
  / MCP", ou para onboarding nos substratos de browser. Não serve para depuração
  passo a passo (ver playbook) nem para decisões de design (ver contrato).
---

# Referência de Automação de Browser — a teoria por trás deste código

Este é o **pacote de teoria do domínio** que um engenheiro pleno normalmente
não tem, explicado **como se aplica AQUI** — não como livro-texto. Cada conceito
traz: definição curta, onde aparece neste repositório (`arquivo:linha`) e a
consequência prática. Fatos voláteis estão datados de **2026-07-12**;
re-verifique com a última seção.

Esta skill é a **teoria**. As decisões de design que se apoiam nela estão em
`browser-mcp-contrato-de-arquitetura`. A aplicação prática (triagem de falhas)
está em `browser-mcp-playbook-de-depuracao` e `browser-mcp-arqueologia-de-falhas`.

**Definições usadas uma vez, valendo para o documento inteiro:**

- **Substrato** — a camada técnica que efetivamente controla o Chrome. Há três:
  Playwright gerenciado, CDP sobre Chrome existente, e extensão MV3 via WebSocket.
- **Modo** — o campo `BrowserManager._mode` (`"playwright" | "cdp" | "extension"`),
  declarado em `src/browser_mcp/browser_manager.py:113`.
- **Bridge** — o par extensão Chrome + servidor WebSocket que liga o mundo Python
  ao Chrome real do usuário (`extension/` + `src/browser_mcp/websocket_server.py`).

---

## 1. MCP (Model Context Protocol)

**O que é.** MCP é um protocolo JSON-RPC em que um *servidor* expõe *tools* a um
*client* (o modelo/host). O transporte aqui é **stdio**: o processo servidor lê
requisições e escreve respostas pelos file descriptors padrão. Um client MCP
chama uma tool enviando `name` (string) + `arguments` (objeto JSON); o servidor
devolve conteúdo (aqui, `TextContent`).

**Onde aparece.**
- Transporte stdio e loop principal: `src/browser_mcp/server.py:77` (`stdio_server()`)
  e `server.py:77` (`server.run(...)`).
- Handshake de listagem: `server.py:18-21` — `@server.list_tools()` retorna
  `app.get_tools()`.
- Despacho de execução: `server.py:24-30` — `@server.call_tool()` recebe
  `name: str, arguments: dict` e roteia para `app.call_tool(name, arguments)`.
- Registro real das tools: decorator `@app.tool(...)` em
  `src/browser_mcp/tools.py` (definição do `ToolRegistry` em `tools.py:19`;
  `get_tools()` monta `types.Tool` com `inputSchema` em `tools.py:49`;
  `call_tool()` roteia por nome em `tools.py:62`).

**Consequência prática.** A "API" do servidor é o conjunto de schemas JSON
declarados nos decorators — é isso que o modelo enxerga. Adicionar capacidade =
registrar uma tool nova com schema. Erros viram texto: `server.py:29-30` embrulha
qualquer exceção como `"ERROR: [Server] - ..."`, então o modelo nunca vê stack
trace, só a string.

---

## 2. Os três substratos: Playwright vs CDP vs extensão Chrome

O `BrowserManager` (singleton, `browser_manager.py:92`) opera em três modos
mutuamente exclusivos. Entender a diferença é o que evita expectativas erradas
("por que cookie X não aparece", "por que não consigo interceptar corpo de
resposta na extensão").

### Playwright gerenciado (`_mode = "playwright"`)
API de alto nível que **lança um Chromium próprio** e cria um contexto isolado
(sem histórico/cookies/logins do usuário). `start()` em `browser_manager.py:128`
faz `chromium.launch(...)` (`:146`) e `new_context(...)` (`:157`). É o modo
padrão (`browser_manager.py:113`). Interações usam input nativo do Playwright,
que gera eventos **trusted** via CDP.

### CDP sobre Chrome existente (`_mode = "cdp"`)
CDP = Chrome DevTools Protocol. Você inicia um Chrome real com
`--remote-debugging-port=9222` e o Playwright **anexa** a ele via
`connect_over_cdp(...)`. Reaproveita o contexto/abas já abertos.
Implementado em `connect_to_existing()` — `browser_manager.py:213`, com o
`connect_over_cdp(cdp_url)` em `:229` e a captura do contexto/página existentes
em `:230-241`. É o Chrome do usuário, mas exige a porta de debug aberta.

### Extensão MV3 via WebSocket (`_mode = "extension"`)
A **sessão REAL do usuário**, sem porta de debug. Uma extensão Manifest V3
conversa com o servidor Python por WebSocket; comandos são despachados por
`_extension_dispatch()` (`browser_manager.py:204`) que chama
`extension_bridge.execute_command(...)`. Ativado por `connect_to_extension()`
(`browser_manager.py:254`), que fecha o Playwright e seta `_mode = "extension"`
(`:282`). Como não há CDP, a extensão usa **`chrome.scripting.executeScript`** e
**`chrome.debugger`** como substitutos (ver `extension/background.js`). As
capacidades são limitadas pelas `permissions` do `extension/manifest.json:6-14`:
`activeTab, tabs, storage, scripting, alarms, debugger, downloads` + host
`<all_urls>` (`manifest.json:15-17`).

### Tabela capacidade × modo

| Capacidade | Playwright | CDP (connect_over_cdp) | Extensão MV3 |
|---|---|---|---|
| Sessão/login real do usuário | Não (contexto isolado) | Sim (Chrome existente) | **Sim** (sessão real) |
| Exige porta `--remote-debugging-port` | Não (lança próprio) | **Sim** | Não |
| Clique com evento trusted | Sim (input nativo) | Sim (input nativo) | Parcial — usa `el.click()` via `chrome.scripting` (`background.js:241`), **não** é input de mouse real |
| Corpo de resposta de rede | Sim, via `NetworkInterceptor` (`network.py:98-137`) | Sim (mesmo interceptor) | Parcial — monkey-patch de `fetch`/XHR em `content.js` (`content.js:143`, `:59`) |
| Accessibility tree (CDP `getFullAXTree`) | Sim (`browser_manager.py:348-349`) | Sim | Não — fallback DOM snapshot (`browser_manager.py:317-339`) |
| Stealth (`navigator.webdriver` etc.) | Sim (`_STEALTH_SCRIPT`, `browser_manager.py:51`) | Não aplicado (anexa a Chrome pronto) | Não aplicado (é o Chrome do usuário) |
| Upload de arquivo | Sim (`browser_manager.py:827`) | Sim | **Não** — `NotImplementedError` (`browser_manager.py:829`) |
| Cookies get/set/clear | Sim (`manage_session`, `browser_manager.py:952`) | Sim | Não — só `list_tabs`/recording (`browser_manager.py:945-947`) |

**Consequência prática.** Escolha o modo pela pergunta "preciso da sessão do
usuário?" e "posso abrir porta de debug?". Muitas tools têm um `if
self._in_extension_mode()` no topo que despacha para a extensão com
comportamento **reduzido** — ao ler um resultado estranho, confira primeiro em
qual modo você está.

---

## 3. `isTrusted`: por que cliques via JavaScript são proibidos

**O que é.** Todo evento do DOM tem a propriedade booleana `isTrusted`. Ela é
`true` só quando o evento foi gerado pelo **agente do usuário** (mouse/teclado
real ou input de nível CDP). Eventos que você cria em JS e dispara com
`element.dispatchEvent(...)` / `element.click()` têm `isTrusted=false`. Muitos
sites (Google News, SPAs com handlers defensivos) **ignoram** eventos não
confiáveis.

**Onde aparece.**
- A estratégia de clique documenta isso: `browser_manager.py:659-669`
  (docstring de `click`) diz explicitamente "Jamais use
  `page.evaluate('element.click()')` — o evento gerado tem `isTrusted=false`".
- O clique real usa input nativo do Playwright: `_smart_click`
  (`browser_manager.py:699`), estratégia 1 = `locator.click()` (`:711`), que
  emite eventos trusted via CDP. `dispatchEvent` só aparece como **último
  recurso** (estratégia 4, `:745-761`), depois de tudo confiável falhar.
- O system prompt do agente **proíbe** JS para clicar: `agent.py:64` (regra 9 da
  descrição da tool `browser_execute_javascript`: "NEVER use for
  clicking/navigation — events have isTrusted=false") e `agent.py:38` (regra 9
  das RULES: "Always use browser_click ... it dispatches real trusted events via
  CDP").

**Nuance da extensão.** No modo extensão, o clique usa `el.click()` dentro de
`chrome.scripting.executeScript` (`background.js:241`) — ou seja, `isTrusted`
tende a ser `false` ali. Por isso o modo extensão é menos robusto para sites que
filtram eventos sintéticos; prefira Playwright/CDP quando a confiabilidade do
clique importa.

**Consequência prática.** Se um clique "não faz nada" mas não dá erro, quase
sempre é isso: alguém injetou JS ou o site rejeitou o evento sintético. A regra
de ouro do repositório é usar `browser_click` (input nativo), nunca
`browser_execute_javascript` para navegar/clicar.

---

## 4. Accessibility tree e refs `@e`

**O que é.** O *accessibility tree* é a árvore **semântica** que o navegador
expõe para leitores de tela: cada nó tem `role` (ex.: `button`, `link`) e `name`
(o texto acessível). É derivada do DOM mas **não é o DOM** — ignora `<div>`
decorativas e classes CSS. Uma ref `@e<N>` é um identificador estável que este
código atribui a cada nó da árvore.

**Onde aparece.**
- Geração das refs: `get_accessibility_tree()` — `browser_manager.py:314`. No
  modo Playwright/CDP, chama o CDP `Accessibility.getFullAXTree`
  (`browser_manager.py:348-349`), itera os nós e atribui `@e1, @e2, ...`
  (`:354-356`), guardando `role`/`name`/`backendDOMNodeId` em `self._ref_map`
  (`:366-370`).
- Resolução das refs: `find_by_ref()` — `browser_manager.py:530`. Recebe `@e3`,
  busca em `_ref_map` (`:536`), e reconstrói um `Locator` do Playwright por
  `get_by_role(role, name=name)` (`:547`), com fallbacks para `get_by_text`
  (`:555`) e `get_by_role(role)` (`:563`). Se a ref estiver "stale", reconstrói a
  árvore (`:538-540`).
- O agente é instruído a **preferir** `@e` a seletores CSS: `agent.py:30`
  (regra 1: "@e refs are stable accessibility tree identifiers").

**Por que sobrevivem a mudança de classe CSS.** A ref é resolvida por `role`+`name`
(semântica), não por `.classe-xyz`. Se o time do site troca o CSS ou reordena
`<div>`s, o botão "Comprar" continua sendo `role=button name="Comprar"` — a ref
reencontra o elemento. Um seletor CSS quebraria.

**Consequência prática.** `@e` é mais estável que CSS, mas depende do CDP: no
modo extensão não há `getFullAXTree`, então `get_accessibility_tree` cai num
**fallback de DOM snapshot** (`browser_manager.py:317-339`) e a resolução por
`get_by_role` (`find_by_ref`) exige uma página Playwright — ou seja, refs `@e`
são fracas/indisponíveis em modo extensão.

---

## 5. CSP (Content-Security-Policy)

**O que é.** CSP é um header HTTP que a página envia para restringir de onde
scripts/estilos podem carregar e se `eval`/inline-script são permitidos. Um CSP
estrito **bloqueia** injeção de `<script>` inline e `eval(...)`, que é
exatamente o que ferramentas de automação querem fazer.

**Onde aparece.**
- Bypass no contexto Playwright: `browser_manager.py:156` — em `STEALTH_MODE` o
  contexto é criado com `context_opts["bypass_csp"] = True`. Isso instrui o
  Chromium a **ignorar o CSP da página** para scripts injetados pelo Playwright
  (indicadores visuais, `page.evaluate`, `_STEALTH_SCRIPT`).
- No modo extensão o bypass acima **não se aplica** (é opção do contexto
  Playwright, que nem existe nesse modo). Em vez disso, o `execute_javascript` da
  extensão tenta `eval` via `chrome.scripting` no mundo MAIN
  (`background.js:331-347`) e, **se o CSP bloquear `unsafe-eval`**, detecta o erro
  (`background.js:353-354`) e cai para `chrome.debugger` (`Runtime.evaluate`,
  `background.js:697-719`) — o CDP via debugger não é barrado pelo CSP da página.

**`injected.js` e o CSP — o ponto delicado, verificado.** No modo extensão,
`injected.js` é injetado por `content.js` criando um `<script src=...>` apontando
para `chrome.runtime.getURL('injected.js')` (`content.js:303-308`), e o recurso é
declarado em `web_accessible_resources` no `manifest.json:43-48`. **Recursos de
extensão carregados dessa forma NÃO são governados pelo CSP da página** — o
`content.js` roda em mundo isolado e o `<script>` aponta para uma URL
`chrome-extension://`, que o CSP de página não controla. Portanto `injected.js`
carrega mesmo em páginas com CSP estrito. O que o CSP da página **ainda** governa
é o `eval` de código arbitrário no mundo MAIN (o caminho `execute_javascript`
acima), daí o fallback para `chrome.debugger`.

**Consequência prática.** Em Playwright, o CSP é essencialmente um não-problema
(`bypass_csp=True`). Em extensão, seus scripts de bridge (`content.js` +
`injected.js`) rodam, mas `eval` de código do agente pode ser bloqueado pelo CSP
da página e só passa pelo caminho `chrome.debugger`. Se `browser_execute_javascript`
falhar num site com CSP rígido, é esse o mecanismo — e ele já tem fallback.

---

## 6. Ciclo de vida do service worker MV3

**O que é.** Em Manifest V3, o "background" da extensão é um **service worker**,
não uma página persistente. O Chrome pode **suspendê-lo** quando ocioso (tipicamente
~30s sem eventos). Se ele dorme, o WebSocket cai e comandos param de chegar.

**Onde aparece.**
- Keepalive via `chrome.alarms`: `background.js:135-144` cria o alarme
  `'ws-keepalive'` com `periodInMinutes: 0.3` (~18s) e, a cada disparo, se
  desconectado, chama `connectWebSocket()`. Há um segundo alarme `'keepalive'` a
  `0.5` min em `background.js:873-879`.
- Reconexão com backoff: `scheduleReconnect()` (`background.js:115-132`) reagenda
  a conexão com atraso crescente (2000ms → +500ms até 5000ms, `:131`) — o
  comentário `:130` diz explicitamente "Backoff mais curto para MV3 (service
  worker pode suspender)".
- Do lado do servidor, cada cliente builtin tem timeout de leitura de frame de
  60s (`websocket_server.py:264`); ping→pong mantém vivo (`background.js:177-180`,
  `websocket_server.py:271-276`).

**Consequência prática.** A conexão da extensão é **intrinsecamente instável**:
espere reconexões. Não assuma sessão WebSocket contínua; o `execute_command` do
servidor tem timeout de 10s por padrão (`websocket_server.py:467`) e lança
`TimeoutError` se a extensão estiver dormindo/reconectando
(`websocket_server.py:484`). Ao depurar "comando não respondeu", cheque se o
service worker suspendeu (o alarme deveria trazê-lo de volta em ~18s).

---

## 7. Stealth / anti-detecção

**O que é.** Sites detectam automação por sinais: `navigator.webdriver === true`,
user-agent de headless, ausência de plugins, flags do Chrome. Stealth = apagar/
falsificar esses sinais. Vale só no modo Playwright (é o único que lança o
Chromium).

**Onde aparece.** `browser_manager.py:40-151`:
- `_STEALTH_SCRIPT` (`browser_manager.py:51-89`) injetado via CDP
  `Page.addScriptToEvaluateOnNewDocument` (`:164-165`), rodando **antes** de
  qualquer script da página:
  - `navigator.webdriver → undefined` (`:53-54`) — remove o sinal #1.
  - `navigator.plugins` como `PluginArray` realista (`:56-69`) — headless não tem
    plugins.
  - `navigator.languages`, `window.chrome`, `permissions.query`,
    `hardwareConcurrency`/`deviceMemory`/`maxTouchPoints` (`:71-88`) — coerência
    de fingerprint.
- User-agent rotativo de um pool de Chrome/macOS reais (`_USER_AGENTS`,
  `browser_manager.py:44-49`; escolha aleatória em `:154-155`).
- Launch args: `browser_manager.py:137-145` —
  `--disable-blink-features=AutomationControlled` (esconde webdriver no nível do
  Blink), `--disable-features=IsolateOrigins,site-per-process`, `--disable-infobars`,
  `--use-gl=angle`/`--use-angle=swiftshader` (render coerente headless).

**Limites (honestos).** Isto derrota checagens simples (`navigator.webdriver`,
plugins vazios), **não** fingerprinting avançado (canvas/WebGL profundo, timing,
sinais de rede TLS). Nada disso se aplica nos modos CDP/extensão — lá é o Chrome
real do usuário, já "não-webdriver", mas também sem essas defesas injetadas.
Stealth é ligado por `STEALTH_MODE` (default on, `browser_manager.py:42`).

---

## 8. HAR (HTTP Archive)

**O que é.** HAR é um JSON padronizado (`log.version` 1.2) que descreve uma
sessão HTTP: lista de `entries`, cada uma com `request` (método, url, headers,
postData) e `response` (status, headers, `content.text`). É o formato que
DevTools exporta e que ferramentas de análise (Charles, HAR viewers) leem.

**Onde aparece.**
- Export no modo Playwright/CDP: `NetworkInterceptor.export_har()` —
  `network.py:178`. Monta `log` 1.2 (`:180-189`) e converte cada entry capturado
  (`_entries`) em request+response HAR (`:191-237`). O corpo da resposta vem de
  `network.py:98-137` (`_on_response`), truncado em `max_body_length` (50000,
  `network.py:14`/`:133-135`).
- Chamado por `browser_manager.export_har()` (`browser_manager.py:472`); no modo
  extensão há um caminho paralelo que constrói HAR a partir do log da extensão
  (`browser_manager.py:473-521`) e a própria extensão tem `buildHAR()` em
  `content.js:386-435`.

**O que dá para analisar.** Como o interceptor captura `response_body`
(`network.py:131-136`), o HAR do modo Playwright inclui **corpos de resposta**
(truncados) — dá para inspecionar respostas de API/XHR, não só metadados.
Limites: `timings` são zerados/-1 (`network.py:227-235`) — não confie no HAR
para latência real; e headers de request no modo extensão vêm vazios
(`browser_manager.py:493-496`).

---

## 9. Token / handshake do bridge

**O que é.** O servidor WebSocket é uma porta local (`ws://localhost:8765`) por
onde a extensão executa comandos no browser do usuário. Sem autenticação,
**qualquer página ou processo local** poderia se conectar e dirigir o Chrome.
Duas defesas: verificar a **origin** (`chrome-extension://...`) e um **token**
compartilhado comparado de forma *timing-safe*.

**Onde aparece.** `src/browser_mcp/websocket_server.py`:
- Origin: no handshake, lê o header `Origin` (`:163`). Origin vazio é aceito; se
  origin não-vazia e `chrome-extension://` (`:221-233`); fora do restrito,
  rejeita qualquer origin presente que não seja `chrome-extension://`
  (`:234-239`). Isso bloqueia páginas web comuns (que enviariam
  `https://...`).
- Token: gerado/persistido com permissão `0o600` em `~/.mcp_browser_token`
  (`_load_or_create_token`, `:40-53`), via `secrets.token_urlsafe(32)` (`:50`).
  Aceito por header `Authorization: Bearer`, subprotocolo `mcp-token.` ou query
  `?token=` (`:241-257`). A comparação usa **`hmac.compare_digest(provided,
  self._token)`** (`:259`).
- A extensão manda o token na query da URL do WebSocket
  (`background.js:41-52`, token vindo de `chrome.storage.local`).

**Por que `hmac.compare_digest` (timing-safe).** Uma comparação normal (`==`)
retorna assim que encontra o primeiro byte diferente; medindo o tempo, um
atacante consegue adivinhar o token byte a byte (*timing attack*).
`compare_digest` gasta tempo **constante** independentemente de onde diverge,
fechando esse canal lateral.

**Consequência prática.** Payload máximo de 64 MiB evita exaustão de memória
(`websocket_server.py:36`, `:290-292`). O bind usa o host do construtor
loopback `127.0.0.1` (`:75-82`) e o token é obrigatório com mensagem explícita
(`:261-267`). Ao depurar "extensão não conecta (401/403)": 403 = origin errada;
401 = token ausente/errado.

---

## Quando NÃO usar esta skill

- **Vai depurar uma falha concreta / triar um erro** → `browser-mcp-playbook-de-depuracao`
  (esta skill explica o *porquê*, não o passo-a-passo de triagem).
- **Vai reconstruir a cronologia de um bug histórico** →
  `browser-mcp-arqueologia-de-falhas`.
- **Vai justificar/rever uma decisão de design** →
  `browser-mcp-contrato-de-arquitetura` (esta skill é a teoria por trás dela).
- **Vai buildar, instalar deps ou configurar ambiente** →
  `browser-mcp-build-e-ambiente`.
- **Vai rodar/operar o servidor ou setar flags** →
  `browser-mcp-executar-e-operar`, `browser-mcp-config-e-flags`.
- **Vai adicionar/mergear uma tool ou seguir estilo de docs** →
  `browser-mcp-controle-de-mudancas`.
- **Quer a lista de ferramentas de diagnóstico** →
  `browser-mcp-diagnosticos-e-ferramentas`, `browser-mcp-validacao-e-qa`.

---

## Glossário (1 linha por termo)

- **MCP** — protocolo JSON-RPC sobre stdio onde o servidor expõe *tools* ao modelo.
- **Tool** — função registrada com `@app.tool(...)` em `tools.py`, com schema JSON.
- **stdio server** — transporte por file descriptors padrão (`server.py:77`).
- **Playwright (modo)** — Chromium próprio, contexto isolado, input nativo trusted.
- **CDP** — Chrome DevTools Protocol; `connect_over_cdp` anexa a Chrome com porta de debug.
- **Extensão (modo)** — sessão real do usuário via extensão MV3 + WebSocket, sem porta de debug.
- **`isTrusted`** — flag do evento DOM; `false` para eventos sintéticos, que sites podem ignorar.
- **`dispatchEvent` / `el.click()`** — clique sintético (isTrusted=false), último recurso apenas.
- **Accessibility tree** — árvore semântica role/name derivada do DOM (via CDP `getFullAXTree`).
- **Ref `@e`** — identificador estável de nó da árvore de acessibilidade (`role`+`name`).
- **CSP** — header que restringe scripts/`eval`; contornado por `bypass_csp` no Playwright.
- **`bypass_csp`** — opção do contexto Playwright que ignora o CSP da página (`browser_manager.py:156`).
- **`web_accessible_resources`** — declara `injected.js` como carregável pela página (fora do CSP dela).
- **Service worker MV3** — background efêmero que o Chrome pode suspender.
- **`chrome.alarms`** — timer que acorda o service worker para manter o WebSocket (keepalive).
- **Stealth** — apagar sinais de automação (`navigator.webdriver`, plugins, UA) no modo Playwright.
- **`navigator.webdriver`** — sinal #1 de automação; zerado pelo `_STEALTH_SCRIPT`.
- **HAR** — JSON HTTP Archive 1.2 com requests/responses (inclui corpos truncados aqui).
- **`NetworkInterceptor`** — captura request/response no Playwright (`network.py:11`).
- **Handshake do bridge** — validação de origin `chrome-extension://` + token no WebSocket.
- **`hmac.compare_digest`** — comparação de token em tempo constante (anti timing attack).
- **`chrome.debugger`** — fallback de `eval` quando o CSP da página bloqueia `unsafe-eval`.

---

## Proveniência e manutenção

- Fatos datados de **2026-07-12**. Verificado contra o código nesta data; commit
  de contexto: os modos `@e` refs e extensão vêm do benchmark Kimi WebBridge
  (`git show cbc8e28:aprendizado_webbridge.md`).
- **Re-verifique** as citações `arquivo:linha` (números mudam com edições):
  - `rg -n "bypass_csp|_STEALTH_SCRIPT|_mode =|find_by_ref|get_accessibility_tree" src/browser_mcp/browser_manager.py`
  - `rg -n "compare_digest|chrome-extension://|MAX_PAYLOAD_SIZE|token" src/browser_mcp/websocket_server.py`
  - `rg -n "ws-keepalive|scheduleReconnect|evalViaDebugger|web_accessible|isContentEditable" extension/background.js`
  - `rg -n "getURL\('injected.js'\)|web_accessible" extension/manifest.json extension/content.js`
  - `rg -n "export_har|response_body|max_body_length" src/browser_mcp/network.py`
  - `rg -n "isTrusted|list_tools|call_tool" src/browser_mcp/agent.py src/browser_mcp/server.py`
- Confirme as `permissions` da extensão em `extension/manifest.json:6-14` e o host
  `<all_urls>` em `:15-17`.
