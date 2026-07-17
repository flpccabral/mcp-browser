---
name: browser-mcp-controle-de-mudancas
description: >-
  Controle de mudanças do repo do browser MCP server: como classificar uma
  mudança (nova tool MCP, mudança no agente, mudança de segurança no perfil
  restrito, mudança na extensão, docs), o que é obrigatório antes do merge
  (testes, lint/format com ruff, atualização do README no estilo da casa), os
  inegociáveis com racional e os incidentes por trás deles (chave extension.pem
  vazada e purgada com git filter-repo; ALLOWED_SCRIPT_HASHES secure-by-default;
  execute_javascript nunca para interação), o estado REAL do gate de CI (só
  dispara em main/master; lint hoje falhando por dívida), o estilo de docs da
  casa (PT-BR, citações file:line, contagens verificadas), publicação no PyPI
  via PUBLISH.md e convenções de branch/commit. Use ao mergear, ao dar push, ao
  revisar, ao publicar release, ao adicionar uma tool, ao tocar em
  restricted_profile.py, ou ao atualizar o README.
---

# Controle de Mudanças — browser MCP server

Como mudanças são classificadas, condicionadas e revisadas neste repositório;
os inegociáveis (com racional e incidente histórico); o estilo da casa para
docs; e o processo de publicação. Fatos voláteis estão datados de
**2026-07-12** — re-verifique com os comandos da última seção.

**Definições usadas uma vez, valendo para o documento inteiro:**

- **Tool MCP** — função registrada com decorator `@app.tool(...)` em
  `src/browser_mcp/tools.py`.
- **Perfil restrito** — modo de segurança ativado por `IFOOD_RESTRICTED_MODE=1`,
  implementado em `src/browser_mcp/restricted_profile.py`.
- **Gate de CI** — `.github/workflows/ci.yml` (jobs `lint`, `test`,
  `restricted-profile`).
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
| Regras de segurança detalhadas do perfil restrito | `browser-mcp-perfil-restrito` |
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
| **Mudança no agente** | loop, system prompt, dispatch em `agent.py` | Teste em `tests/test_agent.py`; se mexer no system prompt, preservar a regra do `isTrusted` (inegociável 3); rodar a suíte completa `pytest tests/` local (o job `test` do CI roda só smoke/tools/agent) |
| **Mudança de segurança (perfil restrito)** | `restricted_profile.py`, allowlists, token, WebSocket auth | Teste em `tests/test_restricted_profile.py` (job dedicado `restricted-profile` no CI, `ci.yml:58-79`); NUNCA relaxar default (inegociável 2); revisão explícita de outra pessoa/agente — mudança de segurança não entra por self-merge. **Nota (2026-07-17):** o WIP intencional que expandiu as allowlists já deixou 2 testes adversariais falhando — quem commitar DEVE ressincronizá-los (ver [[browser-mcp-perfil-restrito]]) |
| **Mudança na extensão** | `extension/background.js`, `injected.js`, `manifest.json` | Não há suíte automatizada para `extension/` (verificado 2026-07-12: `tests/` só cobre Python) — evidência manual obrigatória seguindo `browser-mcp-validacao-e-qa`; JAMAIS commitar `.pem`/`.crx` (inegociável 1); se mudar comportamento visível, atualizar seção da extensão no README |
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

### Inegociável 2 — Segurança do perfil restrito nunca relaxa o default

**Regra.** O perfil restrito é secure-by-default e mudanças só podem
**estreitar** ou manter o comportamento padrão, nunca ampliá-lo. Âncoras no
código (verificadas 2026-07-12):

- `ALLOWED_SCRIPT_HASHES: set[str] = set()` — vazio
  (`src/browser_mcp/restricted_profile.py:97`), e allowlist vazia **rejeita
  todo script**: `if not ALLOWED_SCRIPT_HASHES: return False`
  (`restricted_profile.py:110-112`).
- `ALLOWED_HOSTS` e `ALLOWED_TOOLS` com match exato de hostname e HTTPS
  obrigatório (`restricted_profile.py:39-44`, `:58`, `:76-82`). Estado atual:
  **4 hosts / 5 tools** no working tree (expansão intencional WIP; HEAD tem
  2/3). Os valores mudam — lar canônico e re-verificação:
  [[browser-mcp-perfil-restrito]] (não reproduzir a lista aqui).

Exemplos de PR que devem ser **recusados**: fazer allowlist vazia significar
"permitir tudo"; aceitar subdomínios por sufixo; adicionar tool ao
`ALLOWED_TOOLS` "para facilitar teste"; aceitar `http://`.

**Racional.** O perfil restrito existe para um piloto em ambiente de terceiro
(iFood): o modo de falha aceitável é "bloqueou demais" (operador reclama),
nunca "permitiu demais" (incidente de segurança em ambiente alheio). Um
default frouxo não é detectável em teste de caminho feliz — só aparece
quando explorado.

**Incidente por trás.** Este inegociável é preventivo, endurecido no mesmo
ciclo dos 4 P0 fixes de segurança (commit `cbc8e28`, "feat: 4 P0 fixes —
security, CSP bypass, navigate, future leak") e do vazamento da chave
(inegociável 1): o repositório já provou que "depois a gente aperta" não
acontece a tempo. Detalhes das regras: `browser-mcp-perfil-restrito`.

### Inegociável 3 — `execute_javascript` nunca vira mecanismo de interação

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

Leia isto antes de confiar que "o CI pega". Verificado em 2026-07-12 contra
`.github/workflows/ci.yml` e contra o código commitado (HEAD `ddf9bc1`):

1. **O CI só dispara em push/PR para `main`/`master`** (`ci.yml:3-7`).
   **Branches de trabalho nunca são validadas.** Todo o trabalho na branch
   `etapa-1-ifood-restricted-profile` está sem nenhuma validação automática.
   O primeiro feedback do CI chega no momento do merge — tarde demais.

2. **O que o CI roda quando roda** (matriz Python 3.11/3.12/3.13):
   - job `lint`: `ruff check src/browser_mcp tests` (`ci.yml:30`) e
     `ruff format --check src/browser_mcp tests` (`ci.yml:33`);
   - job `test`: **só** `tests/test_smoke.py tests/test_tools.py
     tests/test_agent.py` (`ci.yml:56`) — não é a suíte completa;
   - job `restricted-profile`: `tests/test_restricted_profile.py`
     (`ci.yml:79`).

3. **HOJE o lint falha no código commitado.** Medido em 2026-07-12 contra uma
   cópia limpa de HEAD (sem o WIP do working tree):
   - `ruff check src/browser_mcp tests` → **17 erros** (14 auto-corrigíveis
     com `--fix`; mix de UP045, F841, F401, I001, W293, N806, SIM102, SIM105);
   - `ruff format --check src/browser_mcp tests` → **14 arquivos seriam
     reformatados** (3 já formatados).

   **Conclusão sem rodeio: o próximo push a `main` VAI FALHAR o job `lint`,
   independentemente do conteúdo do push.** Não é risco, é fato mecânico.

4. **mypy é aspiracional.** `pyproject.toml:78-82` configura
   `disallow_untyped_defs = true`, mas **mypy não roda no CI** (verificado:
   nenhuma menção em `ci.yml`) e `mypy src` reporta **44 erros** hoje.
   Não afirme "type-checked" em doc nenhuma.

5. **Rótulo de fase inconsistente.** O step do job restricted-profile diz
   "Phase 7" (`ci.yml:78`); o commit que o criou (`4c534b3`) diz "Phase 8";
   e **não existe plano de fases em nenhum doc do repo** (verificado por grep
   em `docs/`, `README.md` e raiz). Trate numeração de fase como não
   confiável até alguém criar o doc — item **aberto**.

**Instruções operacionais decorrentes:**

- Rode `ruff check` e `ruff format --check` **localmente antes de todo push**
  (comandos no checklist da seção 1). Você é o gate; o CI não é.
- **A dívida de lint deve ser quitada como mudança separada e revisável**:
  um PR só de `ruff check --fix` + `ruff format` (classe `chore:`), sem
  nenhuma mudança funcional misturada, revisado por diff. Não embuta a
  quitação num PR de feature — mata a revisabilidade dos dois.
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

**Antes de publicar**, o checklist da seção 1 vale em dobro — publicar com o
lint quebrado em main (seção 3, item 3) é publicar de um estado que o próprio
CI reprova.

---

## 6. Convenção de branch e commit (observável no repo)

- **Branches de etapa**: `etapa-<n>-<tema>`. Exemplo real e atual:
  `etapa-1-ifood-restricted-profile`.
- **Commits convencionais**, todos os 5 commits do histórico atual seguem:
  `feat:` (`cbc8e28`, `efa0df5`), `docs:` (`bb2fd1c`), `ci:` (`4c534b3`),
  `chore:` (`ddf9bc1`). Use o prefixo que casa com a classe da mudança da
  seção 1.
- Corpo do commit em uma linha descritiva; quando resume um lote, enumera
  ("4 P0 fixes — security, CSP bypass, navigate, future leak").
- **Item aberto**: não há doc de convenção de branch/commit no repo — esta
  seção descreve o padrão observado, não uma regra escrita. Se o padrão
  mudar, atualize aqui.

---

## Proveniência e manutenção

Escrito em 2026-07-12 contra HEAD `ddf9bc1` na branch
`etapa-1-ifood-restricted-profile`. Working tree tinha WIP não commitado em
`src/browser_mcp/tools.py` e `src/browser_mcp/websocket_server.py`; todos os
números "no código commitado" foram medidos numa cópia limpa de HEAD.

Re-verificação de uma linha por fato (rode da raiz do repo):

```bash
# Gate de CI dispara só em main/master
sed -n '3,7p' .github/workflows/ci.yml
# Lint hoje: 17 erros / 14 arquivos a reformatar
.venv/bin/ruff check src/browser_mcp tests | tail -1 && .venv/bin/ruff format --check src/browser_mcp tests | tail -1
# mypy fora do CI e com erros
grep -c mypy .github/workflows/ci.yml; .venv/bin/mypy src 2>&1 | tail -1
# Contagem real de tools vs README
grep -c '^@app.tool(' src/browser_mcp/tools.py; grep -n '37 ferramentas' README.md
# Secure-by-default do perfil restrito
sed -n '97p;110,112p' src/browser_mcp/restricted_profile.py
# Regra isTrusted no system prompt do agente
grep -n 'isTrusted' src/browser_mcp/agent.py
# Evidência da purga filter-repo e histórico de 5 commits
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
