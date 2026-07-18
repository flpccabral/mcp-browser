---
name: browser-mcp-config-e-flags
description: >
  Catálogo exaustivo de configuração do MCP Browser: qual env var existe, default de
  cada uma, onde é lida (file:line), efeito e quando mudar. Use para perguntas como
  "qual env var controla X", "default de BROWSER_TIMEOUT", "como rodar headless",
  "como configurar o LLM (LLM_PROVIDER/LLM_API_KEY/LLM_MODEL/LLM_BASE_URL)",
  "por que meu .env não tem efeito",
  "onde fica o token / porta 8765 / MAX_PAYLOAD_SIZE / viewport / STEALTH_MODE",
  e para o checklist de adicionar um novo eixo de configuração.
---

# Config e flags do MCP Browser

Catálogo de TODOS os eixos de configuração do servidor MCP de automação de browser:
variáveis de ambiente, constantes hardcoded que agem como flags, config da extensão
Chrome e defaults do agente. Cada fato abaixo foi verificado no código em 2026-07-17.
Linhas podem derivar — re-verifique com os comandos da seção final antes de citar em
PR/doc.

**Termos usados uma vez:**
- **Truthy booleano** = o padrão do repo para env vars booleanas: `valor.lower() in ("1", "true", "yes", "on")` (ex.: `src/browser_mcp/browser_manager.py:36`). Qualquer outra coisa (inclusive `"True "` com espaço ou `"y"`) é `False`.

## Quando NÃO usar esta skill

- **Setup do ambiente/venv/instalação** → [[browser-mcp-build-e-ambiente]].
- **Como iniciar/operar o servidor no dia a dia** → [[browser-mcp-executar-e-operar]].
- **Semântica de segurança das allowlists do modo restrito** (por que HTTPS-only, por que hash de script, modelo de ameaça) → [[browser-mcp-perfil-restrito]]. Aqui só catalogamos ONDE elas moram e seus valores.
- **Depurar comportamento errado em runtime** → [[browser-mcp-playbook-de-depuracao]].
- **Arquitetura geral / contratos entre módulos** → [[browser-mcp-contrato-de-arquitetura]].
- **Processo de mudança/commits** → [[browser-mcp-controle-de-mudancas]].

## Comando que regenera o catálogo

```bash
cd <raiz-do-repo>
grep -rn "os.environ\|os.getenv" src/ extension/ *.py
```

Resultado em 2026-07-12: **14 leituras de env**, todas em `src/browser_mcp/` (nenhuma em `extension/` nem nos `*.py` da raiz). Se o grep retornar algo fora desta tabela, o catálogo está desatualizado — atualize esta skill.

## AVISO CRÍTICO: `.env` NÃO é carregado automaticamente

`python-dotenv` está declarado como dependência (`pyproject.toml:43`), mas **nenhum módulo chama `load_dotenv`**:

```bash
grep -rn "dotenv" src/ *.py   # → zero hits em código (2026-07-12)
```

Consequência: as env vars precisam chegar ao **ambiente do processo** — via config do cliente MCP (bloco `env` do `mcpServers`), via shell que lança o servidor, ou via `hermes-mcp.sh` (que hoje só faz `unset PYTHONPATH/PYTHONSTARTUP/VIRTUAL_ENV` e não exporta nada). Editar `.env` na raiz não tem efeito no servidor Python.

## Tabela mestra: variáveis de ambiente

Todas verificadas no código em 2026-07-12.

| Variável | Default real | Onde é lida | Efeito | Quando mudar |
|---|---|---|---|---|
| `BROWSER_HEADLESS` | `true` (truthy booleano) | `src/browser_mcp/browser_manager.py:36` | Chromium Playwright sem UI (`headless=` em `browser_manager.py:147`) | `false` para depurar visualmente ou driblar detecção de headless |
| `BROWSER_VIEWPORT_WIDTH` | `1280` (int) | `browser_manager.py:37` | Largura do viewport (`browser_manager.py:151` e `:235`) | Testar layouts responsivos |
| `BROWSER_VIEWPORT_HEIGHT` | `720` (int) | `browser_manager.py:38` | Altura do viewport | Idem |
| `BROWSER_TIMEOUT` | `30000` (ms, int) | `browser_manager.py:39` | Timeout de `goto`/`click`/`fill`/`reload` etc. (usos em `:583`, `:601`, `:609`, `:617`, `:711`, `:783`…) | Sites lentos → aumentar; suites rápidas → reduzir |
| `EXTENSION_WS_URL` | `ws://localhost:8765` | `browser_manager.py:40` | URL default de `connect_to_extension` (`browser_manager.py:254`) | Só se mudar porta/host do bridge — e aí mude também extensão e servidor (ver abaixo) |
| `ENABLE_VISUAL_INDICATOR` | `true` (truthy booleano) | `browser_manager.py:41` | Injeta overlay visual após navegação Playwright (`browser_manager.py:585`) | `false` se o overlay interferir em screenshots/scraping |
| `STEALTH_MODE` | `true` (truthy booleano) | `browser_manager.py:42` | Injeta script anti-detecção e user-agent aleatório do pool `_USER_AGENTS` (`browser_manager.py:45-49`; usos em `:138`, `:153`, `:163`) | `false` para depurar diferenças de fingerprint |
| `BROWSER_MCP_DOWNLOAD_DIR` | `<tempdir>/browser_mcp_downloads` | `browser_manager.py:910-913` (dentro de `download()`) | Diretório de destino de `browser_download` | Persistir downloads fora do temp |
| `LLM_PROVIDER` | `deepseek` | `src/browser_mcp/llm_client.py:18` | Seleciona provedor: `deepseek`, `openai`, `anthropic`, `ollama` (outros caem no fallback OpenAI) | Trocar de provedor do agente |
| `LLM_API_KEY` | `""` (vazio) | `llm_client.py:19` | Bearer token enviado ao provedor | Obrigatória para qualquer provedor pago |
| `LLM_MODEL` | por provedor: `deepseek-chat` / `gpt-4o-mini` / `claude-sonnet-4-20250514` / `llama3.1`; fallback `gpt-4o-mini` | `llm_client.py:20` (defaults em `:25-32`) | Modelo do chat do agente | Trocar modelo |
| `LLM_BASE_URL` | por provedor: `https://api.deepseek.com/v1` / `https://api.openai.com/v1` / `http://localhost:11434/v1`; fallback OpenAI | `llm_client.py:21` (defaults em `:34-40`) | Endpoint OpenAI-compatible | Proxies, gateways, endpoints self-hosted |

Guards de parsing: `BROWSER_VIEWPORT_*` e `BROWSER_TIMEOUT` usam `int(...)` sem try — valor não numérico derruba o import do módulo com `ValueError`. Não há validação de range.

## AVISO DESTACADO: `.env.example` está ERRADO

Verificado em 2026-07-12: `.env.example` documenta 4 variáveis que **o código não lê em lugar nenhum** (confirme: `grep -rn "HEADLESS\|PLAYWRIGHT_BROWSER\|DEFAULT_TIMEOUT\|USER_AGENT" src/` — só aparece `BROWSER_HEADLESS` e o pool hardcoded `_USER_AGENTS`).

| No `.env.example` (errado) | Realidade no código |
|---|---|
| `HEADLESS` (`.env.example:11`) | Não lida. O correto é `BROWSER_HEADLESS` (`browser_manager.py:36`) |
| `DEFAULT_TIMEOUT` (`.env.example:14`) | Não lida. O correto é `BROWSER_TIMEOUT` (`browser_manager.py:39`) |
| `PLAYWRIGHT_BROWSER` (`.env.example:17`) | Não lida. O navegador é Chromium hardcoded — não existe eixo de config para firefox/webkit |
| `USER_AGENT` (`.env.example:20`) | Não lida. O UA vem do pool hardcoded `_USER_AGENTS` (`browser_manager.py:45-49`), sorteado só quando `STEALTH_MODE` ativo (`:155`) |

Além disso `.env.example` sugere `LLM_PROVIDER=openai` como exemplo, enquanto o default real do código é `deepseek` (`llm_client.py:18`), e omite `LLM_BASE_URL`, todas as `BROWSER_*`, `EXTENSION_WS_URL`, `ENABLE_VISUAL_INDICATOR`, `STEALTH_MODE` e `BROWSER_MCP_DOWNLOAD_DIR`.

**Corrigir `.env.example` é pendência aberta** (e lembre: mesmo corrigido, `.env` não é auto-carregado — ver aviso acima). Ao corrigir, use os nomes da tabela mestra.

## Constantes hardcoded que agem como flags

Não há env var para nenhuma destas — mudar exige editar código.

| Constante | Valor (2026-07-17) | Onde | Efeito |
|---|---|---|---|
| `TOKEN_PATH` | `~/.mcp_browser_token` | `src/browser_mcp/websocket_server.py:50` | Arquivo do token de autenticação do WebSocket; criado com `secrets.token_urlsafe(32)` se ausente (`websocket_server.py:53-67`) |
| Permissões do token | `0o600` aplicado na criação/leitura (`websocket_server.py:59` e `:65`) | — | Guard de segurança de arquivo |
| `MAX_PAYLOAD_SIZE` | `64 * 1024 * 1024` (64 MiB) | `websocket_server.py:49` (checado no frame loop) | Anti-exaustão de memória no WS |
| Porta / host do WS | `port=8765`, `host="localhost"` — defaults do construtor `WebSocketServer.__init__` (`websocket_server.py:73`) | — | Endereço do bridge WebSocket |

## Config da extensão Chrome

Verificado em `extension/background.js` e `extension/popup.js` (2026-07-12):

- **URL do WS**: hardcoded em `STATE.wsUrl = 'ws://localhost:8765'` (`extension/background.js:14`). **Não** há UI nem storage para mudar — `EXTENSION_WS_URL` do lado Python não afeta a extensão. Se mudar a porta, mude nos três lugares: `WebSocketServer(port=...)`, `EXTENSION_WS_URL` e `background.js:14`.
- **Token**: lido de `chrome.storage.local`, chave `mcpToken` (`background.js:30-31`, `getAuthToken`). Sem token a extensão não conecta e loga "Token ausente" (`background.js:42-46`). O token vai na query string: `${wsUrl}?token=...` (`background.js:48`).
- **Nada no repo grava `mcpToken`** — `grep -n "storage.local.set" extension/*.js` retorna zero (2026-07-12). O popup (`extension/popup.js`) só exibe status/contadores e botões record/export/reset/reconnect; não tem campo de token, apesar do log sugerir "configure em Options/Popup". Setup manual: abra o console do service worker da extensão e rode `chrome.storage.local.set({mcpToken: '<conteúdo de ~/.mcp_browser_token>'})`.
- O servidor envia `{"type": "config", "wsUrl": ...}` à extensão após conectar (`websocket_server.py:442`) — informativo; a extensão não persiste isso.

## Config do agente (defaults em código, sem env vars)

- `BrowserAgent.__init__` (`src/browser_mcp/agent.py:83-97`): `max_iterations=30`, `max_consecutive_errors=3`, `screenshot_on_action=False`, `output_dir="/tmp/browser_agent"`.
- `LLMClient.__init__` (`llm_client.py:15-16`): `max_tokens=4096`, `temperature=0.1` — não configuráveis por env.
- A tool MCP `browser_agent_task` **sobrepõe** os defaults do agente: `max_iterations=50` e `output_dir="./agent_output"` (`src/browser_mcp/tools.py:1048-1077`). Ou seja: o default efetivo via MCP é 50 iterações, não 30.

## Produção vs experimental

| Eixo | Status (2026-07-17) |
|---|---|
| `BROWSER_*`, `EXTENSION_WS_URL`, `ENABLE_VISUAL_INDICATOR`, `STEALTH_MODE`, `LLM_*` | **Estável/produção** — commitados, documentados na tabela do README (`README.md:42-51`; note que o README cita `browser_manager.py:34-40`, mas as linhas reais hoje são 36-42 — drift a corrigir junto) |
| `BROWSER_MCP_DOWNLOAD_DIR` | Estável, mas **ausente do README e do `.env.example`** |

## Checklist: adicionando um novo eixo de config

1. **Módulo certo**: leia a env no módulo dono do comportamento, no topo, com default explícito — padrão existente: `os.getenv("NOME", "default")` em `browser_manager.py:36-42` (browser), `llm_client.py:18-21` (LLM). Booleana? Use o truthy booleano do repo, não `bool(os.getenv(...))`.
2. **Prefixo**: `BROWSER_*` para comportamento do navegador, `LLM_*` para o provedor. Evite nomes genéricos (`HEADLESS`, `DEFAULT_TIMEOUT`) — foi exatamente esse o erro do `.env.example`.
3. **README**: adicione à tabela de env vars (`README.md:42-51`) no estilo existente: nome | default | efeito com `file:line`.
4. **`.env.example`**: adicione com o nome CORRETO e o default real comentado (e aproveite para pagar a pendência das 4 vars fantasma).
5. **Teste**: cubra default + override (padrão: `monkeypatch.setenv`). Cuidado: constantes de módulo lidas no import (`browser_manager.py:36-42`) exigem reload ou injeção para testar override.
6. **Re-verifique o catálogo** (comandos abaixo) e atualize esta skill.

## Comandos de re-verificação

```bash
cd <raiz-do-repo>

# 1. Catálogo completo de env vars lidas pelo código
grep -rn "os.environ\|os.getenv" src/ extension/ *.py

# 2. Vars fantasma do .env.example (deve continuar SEM hits além de BROWSER_HEADLESS/_USER_AGENTS)
grep -rn "HEADLESS\|PLAYWRIGHT_BROWSER\|DEFAULT_TIMEOUT\|USER_AGENT" src/

# 3. .env é auto-carregado? (deve continuar zero em código)
grep -rn "dotenv" src/ *.py

# 4. Constantes de segurança do WebSocket
grep -n "TOKEN_PATH\|MAX_PAYLOAD_SIZE" src/browser_mcp/websocket_server.py

# 5. Config da extensão
grep -n "wsUrl\|mcpToken\|storage.local" extension/background.js extension/popup.js

# 6. Defaults do agente
grep -n "max_iterations\|max_consecutive_errors\|output_dir" src/browser_mcp/agent.py src/browser_mcp/tools.py
```

## Proveniência e manutenção

- Levantamento feito em **2026-07-17**.
- Fonte primária: o grep de uma linha `grep -rn "os.environ\|os.getenv" src/ extension/ *.py` + leitura de cada hit. Rode-o antes de confiar na tabela; qualquer hit novo ou linha deslocada ⇒ atualize esta skill no mesmo PR que mudou a config.
- Pendências abertas registradas aqui: (1) corrigir `.env.example`; (2) documentar `BROWSER_MCP_DOWNLOAD_DIR` no README; (3) drift de linhas na tabela do README (`:34-40` → `36-42`).
