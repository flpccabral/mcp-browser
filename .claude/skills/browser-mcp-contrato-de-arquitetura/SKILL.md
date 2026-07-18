---
name: browser-mcp-contrato-de-arquitetura
description: >
  Contrato de arquitetura do browser-mcp-server: as decisões de design que o
  sistema sustenta e por quê, os invariantes que qualquer mudança deve preservar
  e os pontos fracos conhecidos declarados sem eufemismo. Carregue esta skill
  quando precisar: entender os 3 modos de operação (Playwright / CDP connect /
  extensão Chrome via WebSocket) e por que existem; rastrear o fluxo de uma tool
  call do MCP stdio até o Playwright ou até background.js; entender os
  singletons globais (BrowserManager, ExtensionBridge, websocket_server) e suas
  implicações; avaliar se uma mudança viola um invariante (execute_javascript
  só para extração de dados, refs @e do accessibility tree); ou conhecer os
  defeitos declarados (entry
  point do console script quebrado, contagem de tools divergente do README,
  deprecation de websockets.server, broadcast WebSocket sem roteamento por
  cliente, LLMClient duplicado). Gatilhos típicos: "como funciona a
  arquitetura", "por que existe o modo extensão", "onde a segurança é
  aplicada", "posso mudar X sem quebrar Y", "quantas tools existem de verdade",
  "por que browser-mcp-server não inicia".
---

# Contrato de arquitetura do browser-mcp-server

Este documento descreve o que o sistema É, por que foi desenhado assim, o que
NÃO pode ser quebrado, e o que já está quebrado. Todos os fatos, caminhos e
números de linha foram verificados contra o código em **2026-07-18**.
Re-verifique com os comandos da seção final antes de citar em outro contexto.

## Quando NÃO usar esta skill

| Necessidade | Use em vez desta |
|---|---|
| Recriar o ambiente (venv, playwright install) | [[browser-mcp-build-e-ambiente]] |
| Rodar os 3 modos na prática (comandos de operação) | [[browser-mcp-executar-e-operar]] |
| Catálogo completo de variáveis de ambiente | [[browser-mcp-config-e-flags]] |
| Depurar um sintoma específico (triagem) | [[browser-mcp-playbook-de-depuracao]] |
| Histórico de investigações de falhas passadas | [[browser-mcp-arqueologia-de-falhas]] |
| Medir: network log, HAR, console errors | [[browser-mcp-diagnosticos-e-ferramentas]] |
| Rodar a suíte de testes e coletar evidência | [[browser-mcp-validacao-e-qa]] |
| Teoria geral (MCP, CDP, a11y, isTrusted, CSP, MV3) | [[browser-automacao-referencia]] |
| Confiabilidade do agente autônomo (problema #1) | [[browser-mcp-campanha-confiabilidade-do-agente]] |
| Posicionamento vs. browser-use e concorrentes | [[browser-mcp-fronteira-e-posicionamento]] |
| Barra de evidência e metodologia de prova | [[browser-mcp-metodologia-e-prova]] |
| Gates de mudança, estilo de docs, publicação | [[browser-mcp-controle-de-mudancas]] |

Esta skill é o mapa conceitual. As irmãs acima são os runbooks operacionais.

## O que é o sistema

Um servidor MCP (Model Context Protocol — protocolo pelo qual um LLM chama
ferramentas via stdio) de automação de browser, em Python (>=3.11), pacote
`browser-mcp-server` 0.1.0. Dependências: `mcp`, `playwright`, `httpx`,
`python-dotenv`, `websockets` (`pyproject.toml:39-45`). Suíte: 85 testes
passando em ~56s (verificado 2026-07-13; requer `playwright install chromium`).

Mapa de módulos em `src/browser_mcp/` (linhas verificadas 2026-07-13):

| Módulo | Linhas | Papel |
|---|---|---|
| `server.py` | 93 | Entry point MCP: stdio server, list_tools/call_tool, shutdown |
| `tools.py` | 1312 | `ToolRegistry` + 39 tools `@app.tool` |
| `browser_manager.py` | 1256 | Singleton que detém o browser e roteia por modo |
| `agent.py` | 596 | Agente autônomo: loop OBSERVE→THINK→CHECK→ACT→RECORD (`agent.py:108`) |
| `extension_bridge.py` | 441 | Singleton: ponte comandos/eventos com a extensão |
| `websocket_server.py` | 583 | Servidor WS em `ws://localhost:8765` |
| `network.py` | 251 | Interceptação de rede no modo Playwright |
| `llm_client.py` | 101 | Cliente HTTP para o LLM do agente |
| `visual_indicator.py` | 136 | Indicadores visuais via CDP Runtime.evaluate |
| `utils.py` | 59 | Utilitários |

Fora de `src/`: `extension/` é uma extensão Chrome Manifest V3
(`manifest.json:4`) — `background.js` (service worker com `switch` de 23
`case` de ações), `content.js`, `injected.js`. Permissions: `activeTab, tabs,
storage, scripting, alarms, debugger, downloads`; host permissions
`<all_urls>` (`extension/manifest.json:6-17`).

## Os 3 modos e por que existem

O modo vive em `BrowserManager._mode`, inicializado como `"playwright"` e com
valores possíveis `"playwright" | "extension" | "cdp"`
(`browser_manager.py:113`). Cada método público consulta
`_in_extension_mode()` (`browser_manager.py:201`) e desvia o fluxo.

| Modo | Como entra | O que é | Por que existe |
|---|---|---|---|
| `playwright` (padrão) | `browser_manager.start()` automático na primeira tool | Chromium gerenciado pelo Playwright (headless ou não) | Automação isolada e reprodutível; base dos testes |
| `cdp` | tool `browser_connect_to_existing` → `connect_to_existing(cdp_url="http://localhost:9222")` (`browser_manager.py:213`) via `chromium.connect_over_cdp` (`browser_manager.py:229`) | Anexa a um Chrome já aberto com `--remote-debugging-port` | Reusar um Chrome existente com perfil/estado, mantendo API Playwright |
| `extension` | tool `browser_connect_to_extension` → `connect_to_extension(ws_url)` (`browser_manager.py:254`); URL default `ws://localhost:8765` via env `EXTENSION_WS_URL` (`browser_manager.py:40`) | Extensão Chrome MV3 conectada por WebSocket executa os comandos no browser REAL do usuário | Ver abaixo |

**Por que o modo extensão existe.** Nasceu de um benchmark contra o Kimi
WebBridge documentado em `analise_extensao_necessaria.md` no commit raiz
`cbc8e28` (arquivo depois removido do working tree; recupere com
`git show cbc8e28:analise_extensao_necessaria.md`). Conclusão textual do
documento (linha 65): o Kimi WebBridge "permite que o agente use a **sessão
logada do usuário** — algo que o Playwright em modo isolado não faz". Ou seja:
sites com login do usuário eram o gap ("❌ Não consegue" vs "✅ Usa sessão
real", linha 171 do mesmo documento). O modo extensão opera na sessão real —
cookies, localStorage e login do usuário — sem exportar credenciais.

Entrar em modo extensão FECHA o Playwright se estiver rodando
(`browser_manager.py:261-277`) e `start()` vira no-op enquanto
`_mode == "extension"` (`browser_manager.py:129-130`). Os modos são
mutuamente exclusivos por design: um browser lógico por processo.

## Fluxo de uma tool call

```
Cliente MCP (LLM)
  │ stdio (JSON-RPC)
  ▼
server.py — @server.call_tool → handle_call_tool (server.py:24-32)
  │ delega para app.call_tool(name, arguments)
  ▼
ToolRegistry.call_tool (tools.py)
  │ despacha para a função registrada via @app.tool
  ▼
BrowserManager (singleton) — método da tool (ex.: navigate)
  │
  ├── modo playwright/cdp ──► API Playwright (Page/Locator/CDP session)
  │
  └── modo extension ──► _extension_dispatch(tool, params)  (browser_manager.py:204)
        │
        ▼
      ExtensionBridge.execute_command  (extension_bridge.py)
        │
        ▼
      WebSocketServer.execute_command  (websocket_server.py:552)
        │ cria Future em _pending_responses[req_id]
        │ broadcast({type:"command", id, tool, params}) para TODOS os clientes
        ▼
      extension/background.js — switch(tool) com 23 actions
        │ executa via chrome.tabs / chrome.scripting / chrome.debugger
        ▼
      {type:"response", id, result|error} volta pelo WS
        → resolve o Future (websocket_server.py:482-490)
        → resultado sobe a pilha até types.TextContent no stdio
```

Erros em qualquer nível viram `TextContent` com prefixo `ERROR: [...]` — o
handler MCP nunca propaga exceção crua (`server.py:29-32`; formatação em
`_format_error`, `tools.py:78-93`).

## Singletons globais e implicações

| Objeto | Mecanismo | Instâncias no código | É singleton de verdade? |
|---|---|---|---|
| `BrowserManager` | `__new__` com `_instance` de classe (`browser_manager.py:95,109-122`) | `browser_manager.py:1256` e `tools.py:15` | SIM — as duas atribuições retornam o MESMO objeto |
| `ExtensionBridge` | `__new__` com `_instance` (`extension_bridge.py:21-28`) | `extension_bridge` módulo-level | SIM |
| `WebSocketServer` | instância de módulo, sem `__new__` (`websocket_server.py:583`) | `websocket_server` | Singleton por convenção de import — nada impede segunda instância |
| `LLMClient` | NENHUM — o comentário "Singleton instance" em `llm_client.py:100` é falso | `llm_client.py:101` E `tools.py:16` | NÃO — são DOIS objetos distintos (ver ponto fraco 5) |

Implicações práticas:

- **Estado compartilhado por import.** `server.py:10` e `tools.py:15` obtêm o
  mesmo `BrowserManager`; qualquer módulo que instancie `BrowserManager()`
  toca o mesmo browser. Isso torna o modo (`_mode`) e o mapa de refs
  (`_ref_map`) estado global do processo.
- **Testes precisam resetar estado de classe.** `_instance` sobrevive entre
  testes no mesmo processo; suíte e fixtures dependem disso.
- **Um browser por processo.** Não há suporte a múltiplos browsers/contexts
  simultâneos pela API de tools; é decisão de design, não omissão acidental.

## Protocolo WebSocket (servidor ↔ extensão)

Servidor em `ws://localhost:8765`. Detalhe importante: embora a lib
`websockets` seja importada, `start()` usa SEMPRE o servidor built-in
(asyncio puro, RFC 6455 implementado à mão) por incompatibilidade de handshake
da websockets v16 com Chrome (`websocket_server.py:114-116`).

Mensagens (docstring `websocket_server.py:1-18`): entrada `identify`, `event`,
`request`, `ping/pong`; saída `command`, `response`, `config`, `ping`.

Autenticação e origem (adicionadas no commit `cbc8e28`, P0 de segurança):

- Token em `~/.mcp_browser_token` (0600), gerado com `secrets.token_urlsafe(32)`
  (`websocket_server.py:53-67`); aceito via `Authorization: Bearer`,
  subprotocolo `mcp-token.<token>` ou `?token=` (`websocket_server.py:241-273`).
- Origin deve começar com `chrome-extension://` quando presente; em modo
  restrito, origin vazio também é rejeitado (`websocket_server.py:219-239`).
- Payload máximo 64 MiB (`websocket_server.py:49`).

**Ponto fraco estrutural: broadcast sem roteamento por cliente.** Verificado
no working tree 2026-07-13:

- `command` recebido de um cliente é reenviado para TODOS os outros
  (`websocket_server.py:471-480`).
- `response` resolve o Future pendente E é reenviada para todos os outros
  clientes (`websocket_server.py:482-496`).
- `execute_command` faz `broadcast` do comando (`websocket_server.py:552-571`;
  `broadcast` em 509-525).

Consequência: com DUAS extensões conectadas (ex.: duas janelas de Chrome com a
extensão), ambas executam o mesmo comando; a primeira `response` com o `id`
vence o Future e a segunda é descartada — mas o efeito colateral (clique,
navegação) aconteceu duas vezes. Não há identificação de cliente-alvo no
protocolo. Ao mexer aqui, respeite o WIP não commitado no arquivo.

## Invariantes — o que qualquer mudança deve preservar

1. **`browser_execute_javascript` é só para EXTRAÇÃO DE DADOS.** Eventos
   sintéticos (`element.click()`) têm `isTrusted=false` e são bloqueados por
   Google News e muitas SPAs. O system prompt do agente proíbe explicitamente
   usar JS para clicar/navegar (`agent.py:38` e `agent.py:64`); a descrição da
   tool repete o aviso (`tools.py:647`) e o clique real é despachado com
   eventos trusted via CDP (`browser_manager.py:663-668`). Não "otimize"
   fluxos substituindo `browser_click` por JS. Teoria em
   [[browser-automacao-referencia]].

2. **O accessibility tree gera refs `@e` que as tools de interação resolvem.**
   `get_accessibility_tree` numera nós como `@e{contador}` e popula `_ref_map`
   (`browser_manager.py:311-366`); `find_by_ref` resolve `@e...` para Locator
   e RECONSTRÓI o mapa se estiver obsoleto (`browser_manager.py:530-540`);
   `click` aceita seletor começando com `@e` (`browser_manager.py:677`).
   Contrato: refs são estáveis entre snapshot e ação subsequente (com rebuild
   automático em caso de staleness). Qualquer mudança no formato quebra o
   protocolo agente↔tools.

3. **Erros nunca escapam como exceção pelo stdio.** Sempre `TextContent` com
   `ERROR: [tipo] - mensagem - sugestão` (`server.py:29-32`, `tools.py:78-93`).
   Clientes MCP e o agente dependem desse formato para triagem.

4. **Modos mutuamente exclusivos, um browser por processo** (seção de modos
   acima). `connect_to_extension` derruba o Playwright; `disconnect_extension`
   exige novo start (`browser_manager.py:289-297`).

## Pontos fracos conhecidos — sem eufemismo

### 1. O console script `browser-mcp-server` está QUEBRADO

`pyproject.toml:62` declara `browser-mcp-server = "browser_mcp.server:main"`,
mas `main` é `async def` (`server.py:49`). O wrapper de console script chama
`sys.exit(main())` — recebe uma coroutine nunca aguardada. **Verificado
empiricamente em 2026-07-13** executando o binário instalado no venv:

```
<coroutine object main at 0x...>
<sys>:0: RuntimeWarning: coroutine 'main' was never awaited
```

Exit code 1, servidor nunca sobe. O caminho que FUNCIONA (verificado: servidor
inicializa e imprime "Servidor stdio ativo") é o bloco
`if __name__ == "__main__": asyncio.run(main())` (`server.py:86-88`):

```bash
python -m browser_mcp.server
```

Correção óbvia (aberta, não aplicada): apontar o script para um wrapper
síncrono (`def cli(): asyncio.run(main())`). Qualquer doc/config MCP que
mande usar o comando `browser-mcp-server` está prescrevendo algo que não
funciona hoje.

### 2. Contagem de tools: README diz 37, o real é 39, e o grep ingênuo dá 41

Três números circulam; só um é verdade:

- **README.md:4,8,116,211 afirmam 37 tools** — desatualizado: foi escrito no
  commit `bb2fd1c` e o commit seguinte `efa0df5` adicionou `browser_scroll` e
  `browser_download` sem atualizar o README.
- **`grep -c "@app.tool" src/browser_mcp/tools.py` retorna 41** — FALSO
  POSITIVO: 2 dessas ocorrências são menções em docstrings do próprio
  `ToolRegistry` (`tools.py:20` e `tools.py:35`), não decorators.
- **O número real é 39**, confirmado por dois métodos independentes em
  2026-07-13: `grep -c "^@app.tool"` → 39, e em runtime
  `len(app.get_tools())` → 39.

Lição: conte decorators ancorados em início de linha ou pergunte ao registry
em runtime; nunca confie no README para este número (gate de atualização de
docs: [[browser-mcp-controle-de-mudancas]]).

### 3. Import deprecado de `websockets.server` — quebra silenciosa futura

`websocket_server.py:39` faz `from websockets.server import
WebSocketServerProtocol`. Com websockets 16.0 (versão instalada, verificada
2026-07-13) isso emite `DeprecationWarning: websockets.server.
WebSocketServerProtocol is deprecated` — é o caminho legado
(`websockets.legacy`) marcado para remoção.

Análise precisa do raio da explosão quando a remoção acontecer:

- O import está num `try/except ImportError` (`websocket_server.py:37-44`);
  se a remoção manifestar como `ImportError`, cai no fallback
  `HAS_WEBSOCKETS=False` e o servidor built-in continua funcionando — que já
  é o ÚNICO caminho usado por `start()` hoje (`websocket_server.py:114-116`).
- Porém `_handle_client` (`websocket_server.py:164-185`) referencia
  `websockets.exceptions.ConnectionClosed` e é código morto no fluxo atual
  (nunca registrado como handler); e `stop()` ramifica por `HAS_WEBSOCKETS`
  (`websocket_server.py:129`).
- Risco real: dependendo de COMO a lib remover o símbolo (erro em import vs.
  atributo ausente vs. warning promovido a erro em `-W error`), o
  comportamento muda. CI com `-W error::DeprecationWarning` já falharia hoje.

Estado: dívida declarada, correção aberta (remover o import legado e a
ramificação `HAS_WEBSOCKETS`, que é maquinário morto). Arquivo tem WIP não
commitado — coordene antes de mexer.

### 4. Broadcast sem roteamento por cliente

Descrito na seção do protocolo. Comandos e respostas são fan-out para todos os
clientes conectados (`websocket_server.py:471-496,509-525`). Duplicação de
efeitos colaterais com >1 extensão conectada é comportamento atual, não
hipótese.

### 5. `LLMClient` duplicado — a inicialização do server não alcança as tools

`LLMClient` NÃO tem mecanismo de singleton (sem `__new__`/`_instance`;
verificado 2026-07-13 em `llm_client.py`). Existem duas instâncias:
`llm_client.py:101` (inicializada por `server.py:71`) e `tools.py:16` (usada
por `browser_agent_task`, que chama `await llm_client.initialize()` por conta
própria em `tools.py:1083` — por isso funciona). Consequência: a inicialização
feita no boot do servidor aquece um objeto que as tools nunca usam. Funciona
por acidente de design, não por design. O comentário "Singleton instance" em
`llm_client.py:100` é enganoso.

## Proveniência e manutenção

Fatos datados de **2026-07-18**. Re-verificação de uma linha para cada
fato volátil (rode da raiz do repo, venv ativado onde houver `python`):

| Fato | Comando |
|---|---|
| Contagem real de tools (runtime) | `python -c "from browser_mcp.tools import app; print(len(app.get_tools()))"` |
| Contagem por decorator | `grep -c "^@app.tool" src/browser_mcp/tools.py` |
| Claim desatualizado do README | `grep -n "37" README.md` |
| Entry point quebrado (declaração) | `grep -n "browser_mcp.server:main" pyproject.toml && grep -n "async def main" src/browser_mcp/server.py` |
| Entry point quebrado (empírico) | `browser-mcp-server; echo "exit=$?"` (espere coroutine repr + RuntimeWarning + exit 1) |
| Invocação que funciona | `python -m browser_mcp.server` (Ctrl+C após "Servidor stdio ativo") |
| Deprecation websockets | `python -W error::DeprecationWarning -c "from websockets.server import WebSocketServerProtocol"` |
| Versão websockets instalada | `python -c "import websockets; print(websockets.__version__)"` |
| Broadcast sem roteamento | `grep -n 'msg_type == "command"' src/browser_mcp/websocket_server.py` |
| Singleton BrowserManager | `grep -n "__new__" src/browser_mcp/browser_manager.py` |
| LLMClient sem singleton | `grep -cE "__new__|_instance" src/browser_mcp/llm_client.py` (espere 0) |
| Origem do modo extensão (Kimi WebBridge) | `git show cbc8e28:analise_extensao_necessaria.md \| grep -n "Kimi WebBridge"` |
| Actions da extensão | `grep -c "case '" extension/background.js` (23 em 2026-07-18) |
| Permissions MV3 | `grep -n -A9 '"permissions"' extension/manifest.json` |
| Suíte de testes | `python -m pytest tests/ -q` (43 testes coletados em 2026-07-18) |
| Loop do agente | `grep -n "OBSERVE -> THINK" src/browser_mcp/agent.py` |
| Regra isTrusted no prompt do agente | `grep -n "isTrusted" src/browser_mcp/agent.py` |

Se qualquer comando divergir do afirmado aqui, corrija ESTA skill antes de
propagar o fato — processo em [[browser-mcp-controle-de-mudancas]].
