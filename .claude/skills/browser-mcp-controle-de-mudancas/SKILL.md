---
name: browser-mcp-controle-de-mudancas
description: >-
  Controle de mudanças do repo do browser MCP server: como classificar uma
  mudança (nova tool MCP, mudança no agente, mudança na extensão, docs), o que
  é obrigatório antes do merge (testes, lint/format com ruff, atualização do
  README no estilo da casa), os inegociáveis com racional e os incidentes por
  trás deles (chave extension.pem vazada e purgada com git filter-repo;
  execute_javascript nunca para interação), o estado REAL do gate de CI (só
  dispara em main/master), o estilo de docs da casa (PT-BR, citações file:line,
  contagens verificadas), publicação no PyPI via PUBLISH.md e convenções de
  branch/commit. Use ao mergear, ao dar push, ao revisar, ao publicar release,
  ao adicionar uma tool, ou ao atualizar o README.
---

# Controle de Mudanças — browser MCP server

Como mudanças são classificadas, condicionadas e revisadas neste repositório;
os inegociáveis (com racional e incidente histórico); o estilo da casa para
docs; e o processo de publicação. Fatos voláteis estão datados de
**2026-07-18** — re-verifique com os comandos da última seção.

**Definições usadas uma vez, valendo para o documento inteiro:**

- **Tool MCP** — função registrada com decorator `@app.tool(...)` em
  `src/browser_mcp/tools.py`.
- **Gate de CI** — `.github/workflows/ci.yml` (jobs `lint`, `test`).
- **README na convenção da casa** — ver seção "Estilo da casa para docs".

---

## Quando NÃO usar esta skill

| Sua pergunta é sobre... | Use a irmã |
|---|---|
| Design, invariantes de arquitetura, onde uma feature deve viver | `browser-mcp-contrato-de-arquitetura` |
| Instalar, criar venv, `playwright install`, dependências | `browser-mcp-build-e-ambiente` |
| Subir o servidor, operar em produção | `browser-mcp-executar-e-operar` |
| Variáveis de ambiente e flags | `browser-mcp-config-e-flags` |
| Depurar uma falha em andamento | `browser-mcp-playbook-de-depuracao` |
| A crônica completa dos incidentes (aqui só há o resumo por inegociável) | `browser-mcp-arqueologia-de-falhas` |
| O que conta como evidência de que algo funciona | `browser-mcp-validacao-e-qa` |
| Confiabilidade do agente autônomo | `browser-mcp-campanha-confiabilidade-do-agente` |
| Referência de automação de browser em geral | `browser-automacao-referencia` |

Esta skill responde uma pergunta só: **"o que precisa ser verdade antes de
esta mudança entrar em main ou virar release?"**

---

## 1. Classes de mudança e o que é obrigatório antes de mergear

Toda mudança cai em exatamente uma classe primária (a mais restritiva que se
aplique). Requisitos são cumulativos com a linha "Todas".

| Classe | Exemplos | Obrigatório antes de mergear |
|---|---|---|
| **Todas** | — | `ruff check src/browser_mcp tests` e `ruff format --check src/browser_mcp tests` limpos localmente (o CI NÃO vai pegar na branch — ver seção 3); commit convencional (`feat:`/`fix:`/`docs:`/`ci:`/`chore:`) |
| **Nova tool MCP** | novo `@app.tool(...)` em `tools.py` | Teste cobrindo a tool em `tests/test_tools.py`; atualizar a tabela de tools do README **e** a contagem declarada (README cita a contagem em 4 lugares — linhas 4, 8, 116 e 211 hoje); se a tool for exposta ao agente, atualizar o catálogo no system prompt de `src/browser_mcp/agent.py` |
| **Mudança no agente** | loop, system prompt, dispatch em `agent.py` | Teste em `tests/test_agent.py`; se mexer no system prompt, preservar a regra do `isTrusted` (inegociável 2); rodar a suíte completa `pytest tests/` local (o job `test` do CI roda só smoke/tools/agent) |
| **Mudança na extensão** | `extension/background.js`, `injected.js`, `manifest.json` | Não há suíte automatizada para `extension/` (`tests/` só cobre Python) — evidência manual obrigatória seguindo `browser-mcp-validacao-e-qa`; JAMAIS commitar `.pem`/`.crx` (inegociável 1); se mudar comportamento visível, atualizar seção da extensão no README |
| **Docs** | README, PUBLISH.md, docs/ | Toda alegação nova com referência `arquivo:linha` conferida; contagens re-conferidas contra o código (ver seção 4 — há divergência aberta hoje) |

**Checklist pré-push (copie e execute):**

```bash
cd /caminho/do/repo
.venv/bin/ruff check src/browser_mcp tests
.venv/bin/ruff format --check src/browser_mcp tests
.venv/bin/pytest tests/            # 85 testes coletados em 2026-07-12; ~1 min; requer: playwright install chromium
```

Se qualquer um falhar, o push está bloqueado por convenção — mesmo que o CI
não rode na sua branch (ele não roda; seção 3).

---

## 2. Inegociáveis — com racional e incidente

### Inegociável 1 — NUNCA commitar segredos

**Regra.** Nenhuma chave, token, senha ou artefato assinado entra no git.
`.gitignore` já bloqueia `extension.pem`, `*.pem`, `extension.crx`, `*.crx`,
`.env` e `~/.mcp_browser_token` nunca deve ser copiado para o repo.

**Incidente real (2026-07-12).** A chave privada de assinatura da extensão
Chrome, `extension.pem`, esteve commitada no histórico e replicada em **2
remotes**. O histórico foi purgado com `git filter-repo` em 2026-07-12 — os
artefatos da purga ainda existem em `.git/filter-repo/` e o histórico atual
tem apenas 5 commits (raiz `cbc8e28`), evidências verificáveis localmente.
**A chave foi considerada comprometida**: purgar histórico não des-vaza um
segredo que já esteve em remote. As entradas `*.pem`/`*.crx` no `.gitignore`
existem por causa disso.

**Racional.** Um segredo commitado é irrecuperável: qualquer clone/fork/CI
cache pode tê-lo. A única resposta correta é rotacionar a credencial; a purga
de histórico é limpeza, não remediação. Custo de prevenir: um `git status`
antes do commit. Custo de falhar: rotação de chave + reescrita de histórico
em todos os remotes + invalidação de todos os clones.

**Na revisão:** rode `git diff --cached --stat` e recuse qualquer arquivo
binário ou com extensão de credencial. Cronologia completa do incidente:
`browser-mcp-arqueologia-de-falhas`.

### Inegociável 2 — `execute_javascript` nunca vira mecanismo de interação

**Regra.** `browser_execute_javascript` é só para **extração de dados**.
Clique, navegação e digitação usam as tools dedicadas (`browser_click` etc.),
que despacham eventos reais via CDP.

**Racional + incidente.** Eventos sintéticos de JS (`element.click()`) têm
`isTrusted=false` e são ignorados/bloqueados por Google News e muitas SPAs —
o agente "clicava" e nada acontecia. A lição está gravada no system prompt de
`src/browser_mcp/agent.py` em dois pontos (verificados 2026-07-12):

- `agent.py:38` — "NEVER use browser_execute_javascript to click links or
  navigate. JS click events (element.click()) have isTrusted=false...".
- `agent.py:64` — a descrição da tool no catálogo repete: "DATA EXTRACTION
  only. NEVER use for clicking/navigation".

**Na revisão:** qualquer mudança que faça o agente, um exemplo de doc, ou uma
tool nova usar `execute_javascript` para interagir é rejeitada. Mudanças no
system prompt que removam essas duas menções são rejeitadas.

---

## 3. Estado REAL do gate de CI (sem eufemismo)

Leia isto antes de confiar que "o CI pega". Verificado em 2026-07-18 contra
`.github/workflows/ci.yml`:

1. **O CI só dispara em push/PR para `main`/`master`** (`ci.yml:3-7`).
   **Branches de trabalho nunca são validadas.** O primeiro feedback do CI
   chega no momento do merge — tarde demais.

2. **O que o CI roda quando roda** (matriz Python 3.11/3.12/3.13):
   - job `lint`: `ruff check src/browser_mcp tests` e
     `ruff format --check src/browser_mcp tests`;
   - job `test`: **só** `tests/test_smoke.py tests/test_tools.py
     tests/test_agent.py` — não é a suíte completa.

3. **Lint está limpo (2026-07-18).** `ruff check src/browser_mcp tests` e
   `ruff format --check src/browser_mcp tests` passam no escopo do CI. A dívida
   histórica de lint foi quitada num commit dedicado. `ruff check .` na raiz
   ainda acusa erros em scripts fora do escopo do CI (`manage_mcp_browser.py`,
   scripts de skills) — não bloqueiam o CI.

4. **mypy é aspiracional.** `pyproject.toml:78-82` configura
   `disallow_untyped_defs = true`, mas **mypy não roda no CI** (nenhuma menção
   em `ci.yml`). Não afirme "type-checked" em doc nenhuma.

**Instruções operacionais decorrentes:**

- Rode `ruff check` e `ruff format --check` **localmente antes de todo push**
  (comandos no checklist da seção 1). Você é o gate na sua branch; o CI não é.
- **Correções de lint entram como mudança separada e revisável** (classe
  `chore:`), sem mudança funcional misturada. Não embuta num PR de feature.
- Config ruff relevante para não brigar com a ferramenta: line-length 100,
  `select = ["E","F","W","I","N","UP","B","C4","SIM"]`, `ignore = ["E501"]`
  (`pyproject.toml:70-76`).

---

## 4. Estilo da casa para docs

Extraído do `README.md` real (que é o exemplar da convenção):

1. **PT-BR** no corpo. (Frontmatter/chaves técnicas podem ficar em inglês.)
2. **Toda alegação verificável carrega referência `arquivo:linha`** em crase.
   Exemplo real do README:8: "37 ferramentas MCP registradas em
   `src/browser_mcp/tools.py` via `@app.tool(...)` e expostas pelo servidor
   MCP em `src/browser_mcp/server.py:18`...".
3. **Contagens são conferidas contra o código, com o comando de conferência
   declarado.** O README:212 registra até o comando `pytest --collect-only`
   usado. Quando o número real contradiz o marketing, o README declara a
   contradição (README:213-214 admite que mypy e ruff **não** estão limpos em
   vez de fingir).
4. **Negrito no termo-chave da bullet, tabelas para variáveis/opções,
   comandos em blocos ```bash copiáveis.**

**Divergências abertas hoje (2026-07-12) — quem tocar no README quita junto:**

- README declara **37 tools** (linhas 4, 8, 116, 211). A contagem real de
  decorators é **39**: `grep -c '^@app.tool(' src/browser_mcp/tools.py` → 39,
  tanto no working tree quanto em HEAD. (Um grep ingênuo por `@app.tool` dá
  41, mas 2 são menções em docstrings — `tools.py:20` e `tools.py:35`; use o
  padrão ancorado.) A diferença de 2 corresponde às tools adicionadas em
  `efa0df5` ("feat: add browser_scroll + browser_download") sem atualizar o
  README.
- README:212 declara "43 testes coletáveis"; hoje `pytest --collect-only -q`
  coleta **85**.

Isso ilustra a regra operacional: **número em doc sem comando de conferência
ao lado apodrece silenciosamente.** Sempre cole o comando junto do número.

---

## 5. Publicação (PyPI)

O processo canônico está em `PUBLISH.md`. Resumo do que é inegociável no
processo (conferido contra `PUBLISH.md` em 2026-07-12):

1. **Versão em DOIS lugares, sempre juntos** (hoje ambos `0.1.0`):
   - `pyproject.toml` → `version = "X.Y.Z"` (linha 7)
   - `src/browser_mcp/__init__.py` → `__version__ = "X.Y.Z"` (linha 2)
2. **SemVer**: PATCH = bug fix; MINOR = feature backward-compatible;
   MAJOR = breaking change.
3. **Build + verificação + upload**:

```bash
rm -rf dist/
python -m build
twine check dist/*        # deve exibir "Passed"
twine upload dist/*       # username: __token__, password: token PyPI
```

4. TestPyPI antes do oficial é opcional-recomendado; tag
   `git tag vX.Y.Z && git push origin vX.Y.Z` faz parte do checklist do
   PUBLISH.md; token PyPI segue o inegociável 1 (nunca no repo).
5. O workflow `publish.yml` descrito no PUBLISH.md é **exemplo, não
   realidade**: só existe `ci.yml` em `.github/workflows/` hoje.

**Antes de publicar**, o checklist da seção 1 vale em dobro — nunca publique de
um estado que o próprio CI reprova (lint/testes; ver seção 3).

---

## 6. Convenção de branch e commit (observável no repo)

- **Branches de etapa**: `etapa-<n>-<tema>`.
- **Commits convencionais**: `feat:`, `docs:`, `ci:`, `chore:`, `style:`,
  `fix:`. Use o prefixo que casa com a classe da mudança da seção 1.
- Corpo do commit em uma linha descritiva; quando resume um lote, enumera
  ("4 P0 fixes — security, CSP bypass, navigate, future leak").
- **Item aberto**: não há doc de convenção de branch/commit no repo — esta
  seção descreve o padrão observado, não uma regra escrita. Se o padrão
  mudar, atualize aqui.

---

## Proveniência e manutenção

Escrito em 2026-07-18.

Re-verificação de uma linha por fato (rode da raiz do repo):

```bash
# Gate de CI dispara só em main/master
sed -n '3,7p' .github/workflows/ci.yml
# Lint no escopo do CI (deve passar limpo)
.venv/bin/ruff check src/browser_mcp tests | tail -1 && .venv/bin/ruff format --check src/browser_mcp tests | tail -1
# mypy fora do CI
grep -c mypy .github/workflows/ci.yml
# Contagem real de tools vs README
grep -c '^@app.tool(' src/browser_mcp/tools.py; grep -n '37 ferramentas' README.md
# Regra isTrusted no system prompt do agente
grep -n 'isTrusted' src/browser_mcp/agent.py
# Evidência da purga filter-repo
ls .git/filter-repo && git rev-list --count HEAD
# .gitignore bloqueia chaves da extensão
grep -n 'pem\|crx' .gitignore
# Testes coletáveis (hoje: 85)
.venv/bin/pytest tests/ --collect-only -q | tail -1
# Versão nos 2 lugares
grep -n '^version' pyproject.toml; grep -n '__version__' src/browser_mcp/__init__.py
```

Fatos que expiram rápido: contagens (tools, testes, erros de ruff/mypy),
estado da dívida de lint, rótulo "Phase 7/8". Ao quitar a dívida de lint ou
corrigir o README, atualize as seções 3 e 4 desta skill no mesmo PR.
