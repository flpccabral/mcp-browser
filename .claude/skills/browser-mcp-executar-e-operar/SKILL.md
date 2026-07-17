---
name: browser-mcp-executar-e-operar
description: >
  Runbook operacional do browser-mcp-server: como rodar o servidor (python -m
  browser_mcp.server), conectar a extensão Chrome, usar modo CDP com Chrome
  existente, iniciar o WebSocket server standalone, subcomandos de
  manage_mcp_browser.py, token em ~/.mcp_browser_token, modo restrito iFood
  (IFOOD_RESTRICTED_MODE), config de mcpServers em clients MCP, hermes-mcp.sh,
  e onde artefatos aterrissam (screenshots, HAR, downloads, agent_output).
  Use quando a pergunta for "como rodar o servidor", "como conectar a
  extensão", "como usar modo CDP", "onde ficam os screenshots/downloads",
  "qual comando inicia o quê", "o que o startup faz".
---

# Executar e operar o browser-mcp-server

Runbook para subir e operar o sistema nos seus 3 modos, com a anatomia de cada
comando e as convenções de saída. Tudo abaixo foi verificado contra o código
em 2026-07-12 (branch `etapa-1-ifood-restricted-profile`).

## Quando NÃO usar esta skill

| Situação | Skill correta |
|---|---|
| Setup do zero (venv, dependências, Playwright install) | `browser-mcp-build-e-ambiente` |
| Catálogo completo de env vars e flags | `browser-mcp-config-e-flags` |
| Algo não conecta / falha em runtime | `browser-mcp-playbook-de-depuracao` |
| Por que existem 3 modos, trade-offs de arquitetura | `browser-mcp-contrato-de-arquitetura` |
| Detalhes de segurança do modo restrito iFood | `browser-mcp-perfil-restrito` |
| Medir tráfego de rede / console da página | `browser-mcp-diagnosticos-e-ferramentas` |
| Teoria dos substratos e semântica das tools | `browser-automacao-referencia` |
| Catálogo/medição das 39 tools (dump_tools.py, contagem) | `browser-mcp-diagnosticos-e-ferramentas` |

## Mapa dos 3 modos

| Modo | Browser controlado | Como ativar | Processo(s) |
|---|---|---|---|
| 1. Playwright (padrão) | Chromium lançado pelo servidor | Nada — é o default ao subir o servidor | `python -m browser_mcp.server` |
| 2. CDP | Chrome já aberto pelo usuário | Tool `browser_connect_to_existing` | Servidor MCP + Chrome com `--remote-debugging-port` |
| 3. Extensão | Chrome real do usuário (sessão, cookies) | Tool `browser_connect_to_extension` | Servidor MCP (ou WS standalone) + extensão instalada |

O servidor MCP fala **stdio** com o client (Claude, Hermes etc.). O WebSocket
na porta 8765 é um canal paralelo só para a extensão Chrome.

---

## Modo 1 — Playwright (padrão)

### Comando confiável

```bash
cd /caminho/do/repo/mcp_browser
.venv/bin/python -m browser_mcp.server
```

### ATENÇÃO: o console script `browser-mcp-server` está quebrado

`pyproject.toml:62` registra `browser-mcp-server = "browser_mcp.server:main"`,
mas `main` é `async def` (`server.py:49`). O entry point chama `main()` sem
`asyncio.run()`, o que apenas cria uma coroutine e sai imediatamente (com
`RuntimeWarning: coroutine 'main' was never awaited`). O caminho que funciona
é `python -m browser_mcp.server`, que passa pelo bloco
`if __name__ == "__main__": asyncio.run(main())` (`server.py:86-88`).
Verificado por leitura estática em 2026-07-12 — se o entry point for corrigido
para uma função síncrona, atualize esta seção.

### O que o startup faz, na ordem (server.py:49-83)

1. Registra handlers de SIGINT/SIGTERM para shutdown gracioso
   (`browser_manager.stop()` → `websocket_server.stop()` → `sys.exit(0)`).
2. `await browser_manager.start()` — lança o Chromium Playwright
   (headless conforme `BROWSER_HEADLESS`, default `true`).
3. `await llm_client.initialize()` — prepara o client LLM
   (necessário só para `browser_agent_task`).
4. `await websocket_server.start()` — abre `ws://localhost:8765` para a
   extensão.
5. Abre o `stdio_server` MCP e fica aguardando o client.

**Ponto crítico (server.py:68-75):** os passos 2-4 estão num único
`try/except` tratado como *inicialização opcional*. Se qualquer um falhar, o
servidor imprime apenas `[SERVER] Aviso: Falha na inicialização opcional: ...`
em stderr e **segue rodando** o stdio server. Ou seja: o servidor MCP pode
estar "no ar" com browser, LLM ou WebSocket mortos. Se as tools falharem logo
após o start, procure esse aviso no stderr antes de qualquer outra coisa.

### Logs

- Tudo vai para **stderr** (stdout é reservado ao protocolo MCP stdio —
  nunca escreva em stdout num processo MCP).
- Prefixos: `[SERVER]` (server.py), `[WS-SERVER]` (websocket_server.py),
  `[EXTENSION-BRIDGE]` (extension_bridge.py).
- Rodando via client MCP, o stderr aparece no log do client (ex.: log de MCP
  servers do Claude Code).

### Integração com clients MCP

Config típica de `mcpServers` (o `command` deve resolver para o venv do repo):

```json
{
  "mcpServers": {
    "browser-mcp": {
      "command": "/caminho/do/repo/mcp_browser/.venv/bin/python",
      "args": ["-m", "browser_mcp.server"],
      "env": { "BROWSER_HEADLESS": "true" }
    }
  }
}
```

Env vars aceitas: ver catálogo em `browser-mcp-config-e-flags` (principais:
`BROWSER_HEADLESS`, `EXTENSION_WS_URL`, `LLM_PROVIDER`/`LLM_API_KEY`/
`LLM_MODEL`/`LLM_BASE_URL`, `IFOOD_RESTRICTED_MODE`,
`BROWSER_MCP_DOWNLOAD_DIR`).

### hermes-mcp.sh — launcher para o Hermes

`hermes-mcp.sh` (raiz do repo) existe porque o Hermes injeta um `PYTHONPATH`
com site-packages de Python 3.11 que quebra `pydantic_core` no Python do venv.
O script:

1. `cd` para o diretório do repo (caminho absoluto hard-coded — ajuste se o
   repo estiver em outro lugar);
2. `unset PYTHONPATH PYTHONSTARTUP VIRTUAL_ENV`;
3. `exec .venv/bin/python -s -m browser_mcp.server` (`-s` ignora o user
   site-packages).

Use-o como `command` no client quando o ambiente do client contamina o env
Python. É o padrão a copiar para qualquer client que injete env conflitante.

---

## Modo 2 — CDP (Chrome existente)

1. Inicie o Chrome com debugging remoto e **perfil separado** (o Chrome
   recusa CDP no perfil padrão em versões recentes):

```bash
# macOS
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.chrome-mcp-profile"
```

2. Com o servidor MCP rodando (Modo 1), chame a tool:

```
browser_connect_to_existing  { "cdp_url": "http://localhost:9222" }
```

`cdp_url` é opcional; default `http://localhost:9222` (tools.py:134-160).
Internamente usa `playwright.chromium.connect_over_cdp` e muda o modo interno
para `"cdp"` (browser_manager.py:213-252). A partir daí as mesmas tools
(`browser_navigate`, `browser_click`, ...) operam no Chrome conectado.

---

## Modo 3 — Extensão Chrome

### Passo 1: instalar a extensão

1. `chrome://extensions` → ativar "Developer mode".
2. "Load unpacked" → selecionar o diretório `extension/` do repo
   (contém `manifest.json`, `background.js`, `content.js`, `popup.js`).

### Passo 2: subir o WebSocket server (porta 8765)

Duas opções — escolha UMA (ambas usam o mesmo singleton `websocket_server`):

**Opção A — o próprio servidor MCP.** O Modo 1 já sobe o WS na porta 8765
como parte do startup. Nada extra a fazer.

**Opção B — standalone**, quando você quer a porta 8765 aberta sem o servidor
MCP (ex.: testar só a extensão):

```bash
.venv/bin/python websocket_server_standalone.py
```

O que ele realmente faz (websocket_server_standalone.py): insere
`<repo>/src` no `sys.path` via caminho absoluto **hard-coded da máquina do
autor** (linha 15 — edite se o repo estiver em outro path), chama
`websocket_server.start()` e entra num loop infinito que imprime
`[WS] Clientes: N` sempre que o número de conexões muda. Ctrl+C encerra.

**Opção B via gerenciador — `manage_mcp_browser.py`:**

```bash
python manage_mcp_browser.py start     # sobe o WS standalone em background
python manage_mcp_browser.py status    # verifica WS (lsof :8765) e MCP (pgrep browser_mcp.server)
python manage_mcp_browser.py stop      # kill nos PIDs da porta 8765 e dos processos browser_mcp.server
python manage_mcp_browser.py restart   # stop + sleep 1 + start
```

O que cada subcomando realmente faz (manage_mcp_browser.py:105-160):

| Subcomando | Ação real |
|---|---|
| `start` | `Popen` de `websocket_server_standalone.py` com stdout/stderr em DEVNULL, espera 2s, confere `lsof -i :8765`. **Não inicia o servidor MCP** — só o WS. |
| `stop` | `kill` em todos os PIDs de `lsof -i :8765 -t` **e** em todos os `pgrep -f browser_mcp.server` (este pega o MCP também). |
| `status` | Imprime status dos dois; exit code 0 só se ambos rodando. |
| `restart` | `stop` + `start` (portanto derruba o MCP mas só religa o WS). |

Avisos: `PROJECT_DIR` e `VENV_PYTHON` são hard-coded para a máquina do autor
(linhas 16-17) — edite antes de usar em outro ambiente. O `stop` usa
`pgrep -f browser_mcp.server`, então mata qualquer processo cuja linha de
comando contenha essa string.

### Passo 3: token de autenticação

O WS server exige token em **todas** as conexões (não só em modo restrito).

- Geração (websocket_server.py:53-67): na primeira subida, se
  `~/.mcp_browser_token` não existe, gera `secrets.token_urlsafe(32)`, grava
  no arquivo com `chmod 0600` e loga `[WS-SERVER] Token gerado em ...`.
  Subidas seguintes reutilizam o arquivo (e re-forçam 0600).
- O handshake aceita o token de 3 formas (websocket_server.py:241-257):
  header `Authorization: Bearer <token>`, subprotocolo
  `Sec-WebSocket-Protocol: mcp-token.<token>`, ou query `?token=<token>`.
  Comparação via `hmac.compare_digest`; falha → HTTP 401.
- Origin: se o header `Origin` vier preenchido e não começar com
  `chrome-extension://`, a conexão recebe 403 (websocket_server.py:219-239).
- A extensão lê o token de `chrome.storage.local` (chave `mcpToken`,
  extension/background.js:28-48) e conecta com `?token=`. Cole o conteúdo de
  `~/.mcp_browser_token` no popup/options da extensão; sem token ela loga
  `Token ausente — configure em Options/Popup` e fica reconectando.

```bash
cat ~/.mcp_browser_token   # copie e cole no popup da extensão
```

### Passo 4: ativar o modo no servidor

Com a extensão conectada (stderr mostra `[WS-SERVER] Cliente conectado` e
`Cliente identificado`), chame:

```
browser_connect_to_extension  { "ws_url": "ws://localhost:8765" }
```

`ws_url` é opcional; default `ws://localhost:8765` (tools.py:166-192; o
default também respeita `EXTENSION_WS_URL`, browser_manager.py:40). Para
voltar ao Playwright: `browser_disconnect_extension`.

Limites de operação: `MAX_PAYLOAD_SIZE` de 64 MiB por frame — payloads
maiores derrubam a conexão (websocket_server.py:49, 371-376). Comandos para a
extensão têm timeout default de 10s (`execute_command`,
websocket_server.py:552).

---

## Modo restrito iFood (IFOOD_RESTRICTED_MODE=1)

Muda o comportamento **operacional** do sistema
(src/browser_mcp/restricted_profile.py). Efeitos verificados em 2026-07-12:

- **Loopback forçado:** WS binda só em `127.0.0.1`; `host` diferente é
  ignorado com WARNING.
- **Startup pode abortar:** `check_startup_conditions()` exige
  `~/.mcp_browser_token` existente com permissão `0600` (ou `0400`); caso
  contrário o processo faz `sys.exit(1)` com `[WS-SERVER] FATAL:`
  (restricted_profile.py:122-152, 294-307). Fix: `chmod 600 ~/.mcp_browser_token`.
- **Origin obrigatório:** conexão sem header `Origin`, ou com origin que não
  seja `chrome-extension://`, recebe 403 (no modo normal, origin vazio passa).
- **Tools permitidas (5 no working tree):** `browser_navigate`,
  `browser_get_content`, `browser_execute_javascript`, `browser_type`,
  `browser_click` (restricted_profile.py:76-82). Navegação só HTTPS para
  4 hosts exatos: `gestordepedidos.ifood.com.br`, `portal.ifood.com.br`,
  `partners-auth.ifood.com.br`, `developer.ifood.com.br`.
  **NOTA WIP:** HEAD (`4c534b3`) ainda tem 3 tools / 2 hosts; a expansão
  (type/click + 2 hosts) é WIP intencional não commitado. Valores exatos e
  estado canônico: [[browser-mcp-perfil-restrito]] — re-verifique lá antes de
  citar.
- **Todo JS rejeitado por default:** `ALLOWED_SCRIPT_HASHES` está vazio
  (restricted_profile.py:97), e allowlist vazia = rejeita tudo
  (secure-by-default, restricted_profile.py:105-112). Para aprovar um script,
  adicione o SHA-256 do código exato ao set.
- **Logs sanitizados:** chaves com token/auth/cookie/localStorage viram
  `[REDACTED]`; strings truncadas em 200 chars.

**NOTA DE ESTADO (2026-07-12):** a integração do `RestrictedProfile` em
`tools.py` e `websocket_server.py` é **WIP não commitado** nesta branch
(`etapa-1-ifood-restricted-profile`); `restricted_profile.py` em si está
commitado. Não assuma que o enforcement existe em `main`. Detalhes de
segurança: skill `browser-mcp-perfil-restrito`.

---

## Onde os artefatos aterrissam

| Artefato | Tool | Destino |
|---|---|---|
| Screenshot | `browser_screenshot { path?, full_page? }` | No `path` passado (diretórios pai criados automaticamente); sem `path`, arquivo temporário `.png` via `tempfile.mkstemp` — a tool responde `Screenshot salvo em: <caminho absoluto>` (browser_manager.py:884-901) |
| HAR | `browser_export_har { path }` (obrigatório) | No `path` passado; formato HAR 1.2. No modo extensão o HAR é reconstruído a partir do log da extensão, com headers/timings vazios (browser_manager.py:472-528) |
| Download | `browser_download { url, filename? }` | `BROWSER_MCP_DOWNLOAD_DIR` ou `$TMPDIR/browser_mcp_downloads`; anti-colisão com sufixo `_1`, `_2`...; retorna JSON `{path, size, url}` (browser_manager.py:903-941) |
| Relatório do agente | `browser_agent_task { ..., output_dir? }` | `output_dir` default `./agent_output` **relativo ao cwd do processo servidor**; grava `report.md` e screenshots `iter_N_<tool>.png` / `screenshot_<ts>.png` (tools.py:1063-1116, agent.py:89-99, 411-417) |

Diretórios `agent_output/` e `agent_output_*/` são gerados por execuções do
agente e estão no `.gitignore` (linhas 36-37) — nunca commite; pode apagar
livremente. Como o default é relativo, ao rodar via client MCP o
`agent_output` aparece no cwd que o client usou para lançar o servidor —
passe `output_dir` absoluto se quiser previsibilidade.

---

## ws_client.py — cliente de teste manual (DESATUALIZADO)

Uso documentado no próprio script:

```bash
python ws_client.py <tool> '<params_json>'
# ex: python ws_client.py navigate '{"url":"https://example.com"}'
```

O que ele faz (ws_client.py:9-33): conecta em `ws://localhost:8765` com a lib
`websockets`, envia `{"tool": ..., "params": ...}` e espera uma resposta
(timeout 10s).

**Estado real em 2026-07-12: incompatível com o servidor atual.** Dois
problemas verificados por leitura:

1. Não envia token — o handshake do servidor responde 401 e a conexão morre
   (websocket_server.py:259).
2. A mensagem não tem campo `"type"` — `_handle_message` só roteia mensagens
   com `type` (`hello`, `identify`, `event`, `request`, `command`,
   `response`, `ping`/`pong`; websocket_server.py:418-503), então mesmo
   autenticado o servidor ignoraria o payload.

Para teste manual hoje, conecte com
`ws://localhost:8765?token=$(cat ~/.mcp_browser_token)` e envie o envelope
atual: `{"type": "command", "id": "<uuid>", "tool": "...", "params": {...}}`
— o servidor repassa para a extensão e devolve `{"type": "response", ...}`.
Trate ws_client.py como ponto de partida a corrigir, não como ferramenta
pronta.

---

## Checklist rápido de operação

- [ ] Subir servidor: `.venv/bin/python -m browser_mcp.server` (NÃO o console
      script `browser-mcp-server` — quebrado, ver acima).
- [ ] Conferir no stderr: ausência de `Falha na inicialização opcional`.
- [ ] Modo CDP: Chrome com `--remote-debugging-port=9222 --user-data-dir`
      separado → `browser_connect_to_existing`.
- [ ] Modo extensão: extensão carregada, token de `~/.mcp_browser_token`
      colado no popup, `[WS-SERVER] Cliente conectado` no stderr →
      `browser_connect_to_extension`.
- [ ] Modo restrito: `chmod 600 ~/.mcp_browser_token` ANTES de subir, ou o
      processo sai com FATAL.
- [ ] Artefatos: passar sempre `path`/`output_dir` absolutos para saída
      previsível.

## Proveniência e manutenção

Fatos datados de 2026-07-12, branch `etapa-1-ifood-restricted-profile`;
re-verificados em 2026-07-17. Re-verificações de uma linha:

- Startup e falha "opcional": ler `src/browser_mcp/server.py:68-75`.
- Console script quebrado: `pyproject.toml:62` aponta para `main` e
  `server.py:49` ainda é `async def main` → segue quebrado.
- Token: `grep -n "_load_or_create_token" src/browser_mcp/websocket_server.py` (linhas 53-67).
- Porta/limite WS: `grep -n "MAX_PAYLOAD_SIZE\|port: int" src/browser_mcp/websocket_server.py` (64 MiB, 8765).
- Nº de tools: `grep -c '^@app.tool' src/browser_mcp/tools.py` → **39**
  (sem a âncora `^` dá 41 por contar 2 docstrings).
- Tools do modo restrito: `grep -n "ALLOWED_TOOLS" src/browser_mcp/restricted_profile.py` (linhas 76-82; 5 tools no working tree — lar canônico [[browser-mcp-perfil-restrito]]).
- WIP restrito integrado? `git diff main -- src/browser_mcp/tools.py src/browser_mcp/websocket_server.py` — se vazio em `main`, a nota de WIP pode ser removida.
- ws_client ainda quebrado? conferir se `ws_client.py` ganhou token e campo `"type"`.
- Paths hard-coded: `grep -n "PROJECT_DIR\|sys.path.insert" manage_mcp_browser.py websocket_server_standalone.py`.
