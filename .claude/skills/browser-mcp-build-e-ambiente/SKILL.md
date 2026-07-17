---
name: browser-mcp-build-e-ambiente
description: >
  Recriar do zero o ambiente de desenvolvimento do browser-mcp-server e evitar
  as armadilhas conhecidas. Use quando precisar de: setup inicial (venv, pip
  install -e, playwright install chromium), testes de browser falhando em massa
  após clone, diferença de versão de Python entre .venv local (3.14) e CI
  (3.11/3.12/3.13), DeprecationWarnings do pacote websockets, upgrade de
  websockets bloqueado, .env.example com variáveis erradas (HEADLESS vs
  BROWSER_HEADLESS), verificar se o ambiente está saudável, ruff check falhando
  com erros pré-existentes, build de distribuição (python -m build, dist/,
  PUBLISH.md) ou carregar a extensão Chrome em modo desenvolvedor.
---

# Build e ambiente do browser-mcp-server

Guia para recriar o ambiente de desenvolvimento do zero e reconhecer os
sintomas de ambiente quebrado vs dívida conhecida do repositório.

**Termos usados uma vez e reaproveitados:**
- **repo raiz** — diretório que contém `pyproject.toml`.
- **suíte completa** — `pytest tests/` (85 testes em 4 arquivos).
- **testes de browser** — os 43 testes de `tests/test_smoke.py` (10),
  `tests/test_tools.py` (22) e `tests/test_agent.py` (11), que iniciam um
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
| Perfil restrito (iFood) em si | `browser-mcp-perfil-restrito` |
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
binário do navegador. Sem `playwright install chromium`, os 43 testes de
browser da suíte completa falham na inicialização do fixture (erro do
Playwright informando executável ausente) — apenas os 42 testes de
`tests/test_restricted_profile.py` passam. Sintoma clássico: dezenas de
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
| websockets | >=12.0 |

Dev (`.[dev]`):

| Pacote | Versão mínima |
|---|---|
| pytest | >=8.0 |
| pytest-asyncio | >=0.23 |
| ruff | >=0.3 |
| mypy | >=1.8 |

### Armadilha #2 — DeprecationWarnings do `websockets` (NÃO faça upgrade cego)

O código importa API deprecada em
`src/browser_mcp/websocket_server.py:39`:

```python
from websockets.server import WebSocketServerProtocol
```

Com o `websockets` 16.0 instalado no `.venv` (verificado em 2026-07-12),
isso emite dois avisos reais:

- `websockets.server.WebSocketServerProtocol is deprecated`
- `websockets.legacy is deprecated` (deprecado desde a 14.0)

**Esses warnings são esperados** — não indicam ambiente quebrado.
**NÃO** faça upgrade/pin de `websockets` para uma versão que remova a API
legacy sem antes migrar `websocket_server.py` para a API `asyncio` nova
(`websockets.asyncio.server`). Essa migração é **pendência aberta** do repo;
até ela acontecer, conviva com os warnings.

Reproduza os warnings para confirmar que são esses (e não outra coisa):

```bash
.venv/bin/python -W error::DeprecationWarning -c "from websockets.server import WebSocketServerProtocol"
```

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
.venv/bin/python -m pytest tests/test_restricted_profile.py -q
```

Verificado em 2026-07-12: 42 testes passam em ~0,02 s. Esse arquivo não
inicia navegador (usa apenas `unittest.mock`, `tempfile` e imports de
`browser_mcp.restricted_profile`), então serve como smoke test do venv e das
dependências Python sem exigir Chromium.

**Checagem completa (exige Chromium instalado e rede — testes usam
httpbin.org e example.com):**

```bash
.venv/bin/python -m pytest tests/ -q
```

Coleta 85 testes; duração de referência ~56 s (medição reportada em
2026-07-12; varia com a rede). Se só os 43 testes de browser falharem,
volte à Armadilha #1.

## Estado do lint — falha esperada, não é ambiente quebrado

Em 2026-07-12 (re-verificado 2026-07-17), `ruff check .` na repo raiz reporta
**19 erros** (16 auto-corrigíveis), espalhados por `browser_manager.py`,
`restricted_profile.py`, `websocket_server.py`, testes e
`manage_mcp_browser.py`. Isso é **dívida do repo**, não sinal de setup
errado — o mesmo resultado ocorre num clone limpo. Não "conserte" o lint
como parte do setup; correções de lint são mudanças de código e seguem
[[browser-mcp-controle-de-mudancas]].

**Reconciliação de escopo (por que você vê 17 num lugar e 19 noutro):** o CI
roda `ruff check src/browser_mcp tests` → **17 erros** (escopo restrito); a
raiz `ruff check .` → **19** porque inclui scripts da raiz (ex.:
`manage_mcp_browser.py`) que o CI não checa. Não são medições em conflito — são
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
- [ ] `pytest tests/test_restricted_profile.py -q` → 42 passam em <1 s
- [ ] `pytest tests/ -q` → 85 passam (~56 s, exige rede)
- [ ] DeprecationWarnings de `websockets` aparecem? Esperado (Armadilha #2)
- [ ] `ruff check .` com erros? Esperado — dívida do repo, não seu setup
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
# Import deprecado do websockets
grep -n 'WebSocketServerProtocol' src/browser_mcp/websocket_server.py
# Variáveis de ambiente reais vs .env.example
grep -n 'os.getenv' src/browser_mcp/browser_manager.py && cat .env.example
# Contagem total de testes
.venv/bin/python -m pytest tests/ --collect-only -q | tail -1
# Testes rápidos sem browser
.venv/bin/python -m pytest tests/test_restricted_profile.py -q
# Estado do lint
.venv/bin/ruff check . | tail -1
# Extensão sem build step
ls extension/package.json 2>&1
```
