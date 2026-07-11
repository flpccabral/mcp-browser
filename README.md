# MCP Browser Bridge

> Ponte entre Model Context Protocol (MCP) e automação de navegador.
> 37 ferramentas. 3 modos de operação. Chrome real ou headless.

## ✨ Funcionalidades

- **37 ferramentas MCP** registradas em `src/browser_mcp/tools.py` via `@app.tool(...)` e expostas pelo servidor MCP em `src/browser_mcp/server.py:18` e `src/browser_mcp/server.py:24`.
- **3 modos de operação**: Playwright/headless por padrão (`src/browser_mcp/browser_manager.py:126`), CDP para Chrome existente (`src/browser_mcp/browser_manager.py:211`) e Chrome Extension via WebSocket (`src/browser_mcp/browser_manager.py:252`).
- **Network monitoring** com captura de request/response, filtros e exportação HAR no Playwright (`src/browser_mcp/network.py:11`, `src/browser_mcp/network.py:178`) e no modo extensão (`src/browser_mcp/extension_bridge.py:196`, `src/browser_mcp/extension_bridge.py:360`).
- **Indicadores visuais** por injeção JavaScript em 5 componentes/fases documentáveis no código: overlay, highlight, status, ripple e segurança por cor (`src/browser_mcp/visual_indicator.py:8`, `src/browser_mcp/visual_indicator.py:69`, `src/browser_mcp/visual_indicator.py:86`, `src/browser_mcp/visual_indicator.py:113`, `src/browser_mcp/browser_manager.py:1097`).
- **Captura de erros e warnings de console** no modo extensão (`extension/injected.js:96`, `extension/background.js:703`, `src/browser_mcp/tools.py:1129`).
- **Agente autônomo** com loop `OBSERVE -> THINK -> CHECK -> ACT -> RECORD` (`src/browser_mcp/agent.py:107`) exposto pela ferramenta `browser_agent_task` (`src/browser_mcp/tools.py:990`).
- **Accessibility tree** com refs `@e1`, `@e2`, etc. geradas pelo BrowserManager (`src/browser_mcp/browser_manager.py:312`) e usadas por clique, digitação e hover (`src/browser_mcp/tools.py:271`, `src/browser_mcp/tools.py:317`, `src/browser_mcp/tools.py:407`).
- **Suporte multi-provedor de LLM**: DeepSeek, OpenAI, Anthropic, Ollama e endpoints customizados via `LLM_BASE_URL` (`src/browser_mcp/llm_client.py:18`, `src/browser_mcp/llm_client.py:25`, `src/browser_mcp/llm_client.py:34`, `src/browser_mcp/llm_client.py:48`).
- **Stealth mode** ativado por padrão com launch args, user-agent realista, `navigator.webdriver` removido e CSP bypass no contexto Playwright (`src/browser_mcp/browser_manager.py:40`, `src/browser_mcp/browser_manager.py:49`, `src/browser_mcp/browser_manager.py:136`, `src/browser_mcp/browser_manager.py:151`).
- **Integração Hermes Agent** por launcher dedicado que limpa variáveis conflitantes e executa `browser_mcp.server` no `.venv` (`hermes-mcp.sh:5`, `hermes-mcp.sh:9`, `hermes-mcp.sh:14`).

## 📦 Instalação

O pacote é definido em `pyproject.toml`: Python `>=3.11`, dependências `mcp`, `playwright`, `httpx`, `python-dotenv` e `websockets`, extras de desenvolvimento e script `browser-mcp-server` (`pyproject.toml:5`, `pyproject.toml:39`, `pyproject.toml:47`, `pyproject.toml:61`).

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

Execução direta:

```bash
python -m browser_mcp.server
# ou, após instalar o pacote:
browser-mcp-server
```

Variáveis úteis:

| Variável | Padrão | Uso |
|---|---:|---|
| `BROWSER_HEADLESS` | `true` | Define se o Chromium Playwright abre sem UI (`src/browser_mcp/browser_manager.py:34`). |
| `BROWSER_VIEWPORT_WIDTH` / `BROWSER_VIEWPORT_HEIGHT` | `1280` / `720` | Viewport inicial (`src/browser_mcp/browser_manager.py:35`). |
| `BROWSER_TIMEOUT` | `30000` | Timeout padrão em ms (`src/browser_mcp/browser_manager.py:37`). |
| `EXTENSION_WS_URL` | `ws://localhost:8765` | URL do bridge WebSocket (`src/browser_mcp/browser_manager.py:38`). |
| `ENABLE_VISUAL_INDICATOR` | `true` | Injeta overlay após navegação Playwright (`src/browser_mcp/browser_manager.py:39`, `src/browser_mcp/browser_manager.py:583`). |
| `STEALTH_MODE` | `true` | Ativa ajustes anti-detecção (`src/browser_mcp/browser_manager.py:40`). |
| `LLM_PROVIDER` | `deepseek` | Provedor do agente (`src/browser_mcp/llm_client.py:18`). |
| `LLM_API_KEY` | vazio | Chave enviada ao provedor LLM (`src/browser_mcp/llm_client.py:19`). |
| `LLM_MODEL` | por provedor | Modelo usado no chat (`src/browser_mcp/llm_client.py:20`, `src/browser_mcp/llm_client.py:25`). |
| `LLM_BASE_URL` | por provedor | Endpoint OpenAI-compatible customizado (`src/browser_mcp/llm_client.py:21`, `src/browser_mcp/llm_client.py:34`). |

## 🚀 Uso

### 1. Playwright, modo padrão

O servidor inicializa `BrowserManager`, `LLMClient` e o WebSocket server opcional antes de abrir o stdio MCP (`src/browser_mcp/server.py:68`, `src/browser_mcp/server.py:77`). Em uma chamada MCP:

```json
{
  "name": "browser_navigate",
  "arguments": { "url": "https://example.com" }
}
```

```json
{
  "name": "browser_screenshot",
  "arguments": { "path": "./example.png", "full_page": true }
}
```

### 2. CDP, Chrome existente

Inicie o Chrome com remote debugging e conecte a ferramenta MCP:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/mcp-chrome-cdp
```

```json
{
  "name": "browser_connect_to_existing",
  "arguments": { "cdp_url": "http://localhost:9222" }
}
```

Esse modo usa `chromium.connect_over_cdp(...)`, aproveita contextos/páginas já existentes quando disponíveis e passa a marcar `_mode = "cdp"` (`src/browser_mcp/browser_manager.py:226`, `src/browser_mcp/browser_manager.py:228`, `src/browser_mcp/browser_manager.py:245`).

### 3. Chrome Extension, navegador real do usuário

1. Instale a extensão em `chrome://extensions` carregando a pasta `extension/`.
2. Inicie o WebSocket standalone ou o servidor MCP:

```bash
python websocket_server_standalone.py
# ou
python manage_mcp_browser.py start
```

3. Configure na extensão o token de `~/.mcp_browser_token` e conecte:

```json
{
  "name": "browser_connect_to_extension",
  "arguments": { "ws_url": "ws://localhost:8765" }
}
```

O modo extensão usa a sessão real do Chrome via `ExtensionBridge`, fecha Playwright se necessário e alterna `_mode = "extension"` (`src/browser_mcp/browser_manager.py:258`, `src/browser_mcp/browser_manager.py:278`, `src/browser_mcp/browser_manager.py:280`).

## 🛠️ Ferramentas

Os nomes abaixo são os nomes reais registrados em `src/browser_mcp/tools.py`. A contagem verificada é 37.

| Categoria | Ferramenta | Implementação |
|---|---|---|
| Navegação | `browser_navigate` | `src/browser_mcp/tools.py:97` |
| Navegação | `browser_go_back` | `src/browser_mcp/tools.py:211` |
| Navegação | `browser_go_forward` | `src/browser_mcp/tools.py:231` |
| Navegação | `browser_reload` | `src/browser_mcp/tools.py:251` |
| Navegação | `browser_new_tab` | `src/browser_mcp/tools.py:1156` |
| Interação | `browser_click` | `src/browser_mcp/tools.py:271` |
| Interação | `browser_type` | `src/browser_mcp/tools.py:317` |
| Interação | `browser_select_option` | `src/browser_mcp/tools.py:372` |
| Interação | `browser_hover` | `src/browser_mcp/tools.py:407` |
| Interação | `browser_press_key` | `src/browser_mcp/tools.py:488` |
| Interação | `browser_upload_file` | `src/browser_mcp/tools.py:523` |
| Leitura | `browser_get_content` | `src/browser_mcp/tools.py:558` |
| Leitura | `browser_get_url` | `src/browser_mcp/tools.py:948` |
| Leitura | `browser_get_title` | `src/browser_mcp/tools.py:969` |
| Leitura | `browser_get_attributes` | `src/browser_mcp/tools.py:629` |
| Leitura | `browser_extension_get_dom_snapshot` | `src/browser_mcp/tools.py:1111` |
| Screenshot & Visual | `browser_screenshot` | `src/browser_mcp/tools.py:664` |
| Screenshot & Visual | `browser_inject_indicator` | `src/browser_mcp/tools.py:1183` |
| Screenshot & Visual | `browser_remove_indicator` | `src/browser_mcp/tools.py:1198` |
| Screenshot & Visual | `browser_highlight_element` | `src/browser_mcp/tools.py:1213` |
| Screenshot & Visual | `browser_set_security_level` | `src/browser_mcp/tools.py:1228` |
| Network | `browser_network_start` | `src/browser_mcp/tools.py:700` |
| Network | `browser_network_stop` | `src/browser_mcp/tools.py:721` |
| Network | `browser_network_list` | `src/browser_mcp/tools.py:741` |
| Network | `browser_network_clear` | `src/browser_mcp/tools.py:781` |
| Network | `browser_get_network_log` | `src/browser_mcp/tools.py:801` |
| Network | `browser_export_har` | `src/browser_mcp/tools.py:836` |
| Network | `browser_extension_get_network_log` | `src/browser_mcp/tools.py:1075` |
| Console | `browser_get_console_errors` | `src/browser_mcp/tools.py:1129` |
| Sessão | `browser_manage_session` | `src/browser_mcp/tools.py:865` |
| Sessão | `browser_connect_to_existing` | `src/browser_mcp/tools.py:127` |
| Sessão | `browser_connect_to_extension` | `src/browser_mcp/tools.py:159` |
| Sessão | `browser_disconnect_extension` | `src/browser_mcp/tools.py:191` |
| Agente | `browser_agent_task` | `src/browser_mcp/tools.py:990` |
| Agente | `browser_wait` | `src/browser_mcp/tools.py:906` |
| Accessibility | `browser_accessibility_tree` | `src/browser_mcp/tools.py:450` |
| JavaScript | `browser_execute_javascript` | `src/browser_mcp/tools.py:594` |

Observações verificáveis:

- Não há ferramenta MCP pública chamada `browser_scroll`; a extensão tem helper interno `scroll` em `src/browser_mcp/extension_bridge.py:162`, mas ele não é registrado em `tools.py`.
- `browser_get_visible_text` e `browser_get_interactive_elements` existem como métodos auxiliares do BrowserManager (`src/browser_mcp/browser_manager.py:980`, `src/browser_mcp/browser_manager.py:1009`), mas não como ferramentas MCP públicas.
- `browser_get_console_errors` requer modo extensão, porque chama `extension_get_console_errors` (`src/browser_mcp/browser_manager.py:1067`).

## 🔌 Integração com Hermes Agent

Use o launcher do projeto:

```bash
./hermes-mcp.sh
```

Ele entra no diretório do projeto, limpa `PYTHONPATH`, `PYTHONSTARTUP` e `VIRTUAL_ENV`, e executa `.venv/bin/python -s -m browser_mcp.server` (`hermes-mcp.sh:5`, `hermes-mcp.sh:9`, `hermes-mcp.sh:14`). Isso evita misturar pacotes do ambiente Hermes com o Python do `.venv`.

Para usar no Hermes Agent, configure o engine de browser para MCP no lado do Hermes (`browser.engine=mcp`) e aponte o comando do MCP server para `hermes-mcp.sh`. Este repositório fornece o servidor e o launcher; a leitura de `browser.engine=mcp` é responsabilidade do Hermes, não deste pacote.

## 🏗️ Arquitetura

Fluxo principal:

```text
MCP Client
  -> MCP Server stdio (src/browser_mcp/server.py)
    -> ToolRegistry (src/browser_mcp/tools.py)
      -> BrowserManager
        -> Playwright Chromium
        -> Chrome via CDP
        -> ExtensionBridge -> WebSocketServer -> Chrome Extension MV3 -> Chrome real
```

O servidor MCP usa `mcp.server.Server`, registra handlers `list_tools` e `call_tool`, inicia componentes opcionais e roda via stdio (`src/browser_mcp/server.py:15`, `src/browser_mcp/server.py:18`, `src/browser_mcp/server.py:24`, `src/browser_mcp/server.py:77`).

O WebSocket server escuta em `localhost:8765`, usa implementação built-in em asyncio por padrão, implementa handshake/frame WebSocket compatível com RFC 6455, valida Origin, exige token e encaminha comandos/respostas entre servidor e extensão (`src/browser_mcp/websocket_server.py:71`, `src/browser_mcp/websocket_server.py:97`, `src/browser_mcp/websocket_server.py:174`, `src/browser_mcp/websocket_server.py:180`, `src/browser_mcp/websocket_server.py:202`, `src/browser_mcp/websocket_server.py:228`, `src/browser_mcp/websocket_server.py:516`).

A extensão Chrome é Manifest V3, usa service worker, content script em `<all_urls>`, permissões `activeTab`, `tabs`, `storage`, `scripting`, `alarms` e `debugger`, e expõe `injected.js` como recurso acessível (`extension/manifest.json:4`, `extension/manifest.json:6`, `extension/manifest.json:17`, `extension/manifest.json:20`, `extension/manifest.json:42`).

O `switch` de comandos da extensão tem **21 comandos** no código atual, não 20: `navigate`, `new_tab`, `click`, `type`, `screenshot`, `get_content`, `execute_javascript`, `get_dom_snapshot`, `press_key`, `get_url`, `get_title`, `go_back`, `go_forward`, `reload`, `get_visible_text`, `get_interactive_elements`, `get_attributes`, `wait`, `list_tabs`, `activate_tab`, `manage_session` (`extension/background.js:200` a `extension/background.js:572`).

## 🔐 Segurança

- **Token auth no WebSocket**: token em `~/.mcp_browser_token`, criado com `secrets.token_urlsafe(32)` e permissões `0600` (`src/browser_mcp/websocket_server.py:48`, `src/browser_mcp/websocket_server.py:51`, `src/browser_mcp/websocket_server.py:61`, `src/browser_mcp/websocket_server.py:63`).
- **Validação de Origin**: conexões com `Origin` diferente de `chrome-extension://...` recebem `403 Forbidden` (`src/browser_mcp/websocket_server.py:202`).
- **Formas de autenticação aceitas**: bearer token, subprotocolo `mcp-token.*` ou query string `?token=...` (`src/browser_mcp/websocket_server.py:210`, `src/browser_mcp/websocket_server.py:215`, `src/browser_mcp/websocket_server.py:221`).
- **Comparação constante**: token validado com `hmac.compare_digest(...)` (`src/browser_mcp/websocket_server.py:228`).
- **Limite de payload**: frames maiores que 64 MiB são rejeitados (`src/browser_mcp/websocket_server.py:46`, `src/browser_mcp/websocket_server.py:331`).
- **CSP bypass no modo extensão**: `execute_javascript` tenta `chrome.scripting.executeScript`; se CSP bloquear `eval`, usa `chrome.debugger` com `Runtime.evaluate` (`extension/background.js:300`, `extension/background.js:321`, `extension/background.js:635`).

## 📊 Métricas

Estado verificado neste checkout:

- **37 ferramentas MCP** em `src/browser_mcp/tools.py`.
- **43 testes coletáveis** em `tests/` com `env -u PYTHONPATH -u PYTHONSTARTUP -u VIRTUAL_ENV .venv/bin/pytest --collect-only -q`.
- **mypy configurado** em `pyproject.toml` com `disallow_untyped_defs = true`, mas a execução atual de `env -u PYTHONPATH -u PYTHONSTARTUP -u VIRTUAL_ENV .venv/bin/mypy src` reporta 43 erros. Portanto, não é correto afirmar “mypy strict: 0 errors” neste estado.
- **ruff configurado** em `pyproject.toml`, mas `env -u PYTHONPATH -u PYTHONSTARTUP -u VIRTUAL_ENV .venv/bin/ruff check src tests` reporta 12 erros. Portanto, não é correto afirmar “ruff: 0 errors” neste estado.
- **Metadados de pacote** presentes para wheel/sdist via Hatchling e script `browser-mcp-server` (`pyproject.toml:1`, `pyproject.toml:61`, `pyproject.toml:64`, `pyproject.toml:67`).

## 📄 Licença

MIT (`LICENSE`).
