---
name: browser-mcp-build-e-ambiente
description: >
  Recriar do zero o ambiente de desenvolvimento do browser-mcp-server e evitar
  as armadilhas conhecidas. Use quando precisar de: setup inicial (venv, pip
  install -e, playwright install chromium), testes de browser falhando em massa
  após clone, diferença de versão de Python entre .venv local (3.14) e CI
  (3.11/3.12/3.13), .env.example com variáveis erradas (HEADLESS vs
  BROWSER_HEADLESS), verificar se o ambiente está saudável, ruff check falhando
  com erros pré-existentes, build de distribuição (python -m build, dist/,
  PUBLISH.md) ou carregar a extensão Chrome em modo desenvolvedor.
---

# Build e ambiente do browser-mcp-server

Guia para recriar o ambiente de desenvolvimento do zero e reconhecer os
sintomas de ambiente quebrado vs dívida conhecida do repositório.

**Termos usados uma vez e reaproveitados:**
- **repo raiz** — diretório que contém `pyproject.toml`.
- **suíte completa** — `pytest tests/` (43 testes em 3 arquivos).
- **testes de browser** — os testes de `tests/test_smoke.py`,
  `tests/test_tools.py` e a maioria de `tests/test_agent.py`, que iniciam um
  Chromium real via `browser_manager.start()`.

## Quando NÃO usar esta skill

| Necessidade | Use em vez desta |
|---|---|
| Rodar/operar o servidor MCP, modos de execução | `browser-mcp-executar-e-operar` |
| Catálogo completo de variáveis de ambiente e flags | `browser-mcp-config-e-flags` |
| Depurar comportamento em runtime | `browser-mcp-playbook-de-depuracao` |
| Entender falha histórica ou regressão | `browser-mcp-arqueologia-de-falhas` |
| Regras de arquitetura e limites de mudança | `browser-mcp-contrato-de-arquitetura` / `browser-mcp-controle-de-mudancas` |
| Validação/QA de uma mudança | `browser-mcp-validacao-e-qa` |
| Referência das ferramentas de automação | `browser-automacao-referencia` |
| Diagnóstico com ferramentas embutidas | `browser-mcp-diagnosticos-e-ferramentas` |

## Requisitos

| Item | Valor | Fonte |
|---|---|---|
| Python mínimo | `>= 3.11` | `pyproject.toml` (`requires-python`) |
| Python no CI | matriz 3.11 / 3.12 / 3.13 | `.github/workflows/ci.yml` |
| Python no `.venv` local | 3.14 (verificado em 2026-07-12) | `.venv/bin/python --version` |
| Build backend | hatchling | `pyproject.toml` `[build-system]` |
| Pacote | `src/browser_mcp` | `[tool.hatch.build.targets.wheel]` |
| Entry point CLI | `browser-mcp-server = browser_mcp.server:main` | `[project.scripts]` |
| Pytest | `asyncio_mode = "auto"`, `testpaths = ["tests"]` | `[tool.pytest.ini_options]` |

**Diferença local vs CI:** o `.venv` do repo roda Python 3.14, mas o CI só
testa 3.11–3.13 e os classifiers do `pyproject.toml` param em 3.13. Algo que
passa localmente pode se comportar diferente nas versões oficialmente
suportadas — na dúvida, trate 3.11–3.13 como o alvo de compatibilidade.
Confirme sua versão antes de investigar qualquer diferença de comportamento:

```bash
.venv/bin/python --version
```

## Setup completo do zero

Execute na repo raiz:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

### Armadilha #1 — pular `playwright install chromium`

`pip install` instala o pacote Python `playwright`, mas **não** baixa o
binário do navegador. Sem `playwright install chromium`, os testes de
browser da suíte falham na inicialização do fixture (erro do Playwright
informando executável ausente) — apenas os testes que não sobem browser (ex.:
parsing/prune em `tests/test_agent.py`) passam. Sintoma clássico: dezenas de
falhas idênticas logo após um clone fresco. Correção: rodar o comando acima;
os binários vão para o cache do Playwright (no macOS,
`~/Library/Caches/ms-playwright/`).

## Dependências reais (de `pyproject.toml`)

Runtime:

| Pacote | Versão mínima |
|---|---|
| mcp | >=1.0.0 |
| playwright | >=1.40.0 |
| httpx | >=0.27.0 |
| python-dotenv | >=1.0.0 |

(`websockets>=12.0` está só no extra `dev`, para `ws_client.py` — o servidor não
o usa em runtime.)

Dev (`.[dev]`):

| Pacote | Versão mínima |
|---|---|
| pytest | >=8.0 |
| pytest-asyncio | >=0.23 |
| ruff | >=0.3 |
| mypy | >=1.8 |

### Armadilha #2 — DeprecationWarnings do `websockets` (RESOLVIDO em 2026-07-18)

Até 2026-07-18 o servidor importava uma API deprecada da biblioteca `websockets`
(`from websockets.server import WebSocketServerProtocol`), gerando dois
`DeprecationWarning`. A biblioteca era vestigial (o servidor sempre usou asyncio
puro) e foi **removida** das dependências de runtime — ficou só no extra `dev`,
para o utilitário `ws_client.py`. O import do servidor hoje é limpo:

```bash
.venv/bin/python -W error::DeprecationWarning -c "import browser_mcp.websocket_server"
```

Se você ainda vê esses warnings ou `import websockets` em `websocket_server.py`,
seu checkout está desatualizado.

### Armadilha #3 — `.env.example` documenta variáveis ERRADAS

O `.env.example` na repo raiz sugere `HEADLESS`, `DEFAULT_TIMEOUT` e
`PLAYWRIGHT_BROWSER` — **nenhuma dessas é lida pelo código**. As variáveis
reais estão em `src/browser_mcp/browser_manager.py` (~linhas 36–42):

| `.env.example` diz (errado) | Código lê de fato |
|---|---|
| `HEADLESS` | `BROWSER_HEADLESS` |
| `DEFAULT_TIMEOUT` | `BROWSER_TIMEOUT` |
| `PLAYWRIGHT_BROWSER` | (não existe equivalente; Chromium é fixo) |

Outras lidas no mesmo bloco: `BROWSER_VIEWPORT_WIDTH`,
`BROWSER_VIEWPORT_HEIGHT`, `EXTENSION_WS_URL`, `ENABLE_VISUAL_INDICATOR`,
`STEALTH_MODE`. Se você setar `HEADLESS=false` e nada mudar, o problema é
esse. Para o catálogo completo e autoritativo de variáveis, use a skill
`browser-mcp-config-e-flags` — não duplique aqui.

## Verificar que o ambiente está bom

**Checagem rápida (sem browser, <1 s):**

```bash
.venv/bin/python -m pytest tests/test_agent.py -q -k "parse or prune"
```

Verificado em 2026-07-17: 8 testes passam em ~0,2 s. Esses casos não iniciam
navegador (parsing de resposta do LLM e prune de mensagens), então servem
como smoke test do venv e das dependências Python sem exigir Chromium.

**Checagem completa (exige Chromium instalado e rede — testes usam
httpbin.org e example.com):**

```bash
.venv/bin/python -m pytest tests/ -q
```

Coleta 43 testes (2026-07-17); a maioria sobe browser. Se dezenas falharem
logo após clone, volte à Armadilha #1.

## Estado do lint

Verificado 2026-07-17: `ruff check src/browser_mcp tests` (o escopo do CI)
**passa limpo** — a dívida de lint foi quitada. `ruff check .` na raiz ainda
acusa alguns erros em scripts fora do escopo do CI (`manage_mcp_browser.py` e
os scripts das skills), que **não** bloqueiam o CI. Correções de lint são
mudanças de código e seguem [[browser-mcp-controle-de-mudancas]]; não as
misture com setup.

**Reconciliação de escopo:** o CI roda `ruff check src/browser_mcp tests`
(limpo hoje); a raiz `ruff check .` inclui scripts da raiz e das skills que o
CI não checa. Não são medições em conflito — são
escopos diferentes. **Lar canônico do estado de lint/CI:**
[[browser-mcp-controle-de-mudancas]] §3.

## Build de distribuição

Documentado em `PUBLISH.md` (repo raiz). Resumo:

```bash
pip install build twine   # ferramentas de publicação não estão em .[dev]
rm -rf dist/
python -m build
twine check dist/*
```

Artefatos gerados em `dist/` (sdist `.tar.gz` + wheel `py3-none-any.whl`);
`dist/` está no `.gitignore`. Para upload (TestPyPI/PyPI), siga o passo a
passo completo de `PUBLISH.md`.

## Extensão Chrome (modo bridge)

A extensão em `extension/` é JavaScript puro — **não há build step**: não
existe `package.json`, nem bundler (verificado em 2026-07-12; conteúdo:
`manifest.json` Manifest V3 "MCP Browser Bridge", `background.js`,
`content.js`, `injected.js`, `popup.*`, `styles.css`, `icons/`).

Para carregar:
1. Abra `chrome://extensions`.
2. Ative **Modo do desenvolvedor**.
3. Clique em **Carregar sem compactação** e aponte para o diretório
   `extension/` da repo raiz.

Como operá-la junto com o servidor é assunto de
`browser-mcp-executar-e-operar`.

## Checklist de setup

- [ ] `python3 --version` ≥ 3.11 (ideal: 3.11–3.13 para casar com o CI)
- [ ] `python -m venv .venv && source .venv/bin/activate`
- [ ] `pip install -e ".[dev]"`
- [ ] `playwright install chromium` (Armadilha #1)
- [ ] `pytest tests/test_agent.py -q -k "parse or prune"` → 8 passam em <1 s
- [ ] `pytest tests/ -q` → 43 coletados (~min, exige rede/Chromium)
- [ ] `import browser_mcp.websocket_server` sem DeprecationWarning (Armadilha #2 resolvida)
- [ ] `ruff check src/browser_mcp tests` limpo (escopo do CI)
- [ ] Não copiar `.env.example` cegamente (Armadilha #3) — validar nomes em
      `browser-mcp-config-e-flags`

## Proveniência e manutenção

Fatos voláteis datados de **2026-07-12**. Re-verifique com uma linha cada:

```bash
# Python mínimo e dependências
grep -A2 'requires-python' pyproject.toml && grep -A8 '^dependencies' pyproject.toml
# Versão do venv local
.venv/bin/python --version
# Matriz de Python do CI
grep -n 'python-version' .github/workflows/ci.yml
# Servidor não depende mais de websockets (espere 0)
grep -c 'import websockets' src/browser_mcp/websocket_server.py
# Variáveis de ambiente reais vs .env.example
grep -n 'os.getenv' src/browser_mcp/browser_manager.py && cat .env.example
# Contagem total de testes
.venv/bin/python -m pytest tests/ --collect-only -q | tail -1
# Testes rápidos sem browser
.venv/bin/python -m pytest tests/test_agent.py -q -k "parse or prune"
# Estado do lint (escopo do CI)
.venv/bin/ruff check src/browser_mcp tests | tail -1
# Extensão sem build step
ls extension/package.json 2>&1
```
