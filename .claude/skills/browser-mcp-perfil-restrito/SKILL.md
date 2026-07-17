---
name: browser-mcp-perfil-restrito
description: >
  Perfil restrito de segurança do MCP Browser (piloto iFood). Use quando o assunto for:
  modo restrito, IFOOD_RESTRICTED_MODE, segurança, allowlist de domínios ou de tools,
  mensagem "REJECTED", hash de script SHA-256, ALLOWED_SCRIPT_HASHES, ALLOWED_HOSTS,
  permissões do token file (0600), bind loopback 127.0.0.1, sanitização de logs,
  aprovar um script JS, adicionar um domínio permitido, ou verificar se o modo restrito
  está ativo. Cobre a semântica exata dos 6 controles, os runbooks de mudança e o
  estado da integração WIP.
---

# Perfil Restrito de Segurança (Piloto iFood)

Esta skill documenta a categoria de domínio mais crítica do projeto: o perfil restrito
que limita o que um agente LLM pode fazer com o browser quando o servidor roda na
máquina de um parceiro.

**Fonte de verdade única do enforcement:** `src/browser_mcp/restricted_profile.py`
(commitado). A integração nos pontos de chamada (`tools.py`, `websocket_server.py`)
é **WIP não commitado** na branch `etapa-1-ifood-restricted-profile` — ver seção
"Estado da integração" (fato datado de 2026-07-12/13).

## Quando NÃO usar esta skill

- **Processo de aprovação/gates de mudança** — isso é `browser-mcp-controle-de-mudancas`.
  Esta skill diz O QUE não pode relaxar; aquela diz COMO propor a mudança.
- **Catálogo geral de flags/config** — `browser-mcp-config-e-flags`. Esta skill detalha
  apenas a semântica de segurança de `IFOOD_RESTRICTED_MODE`.
- **Operação geral do servidor** (subir, parar, portas) — `browser-mcp-executar-e-operar`.
- **Depurar um REJECTED sem saber a causa** — comece por
  `browser-mcp-playbook-de-depuracao` (sintoma REJECTED) e volte aqui para a semântica.
- **Calcular hashes/utilitários** — `browser-mcp-diagnosticos-e-ferramentas`
  (terá `hash_script.py`).
- **Arquitetura geral do sistema** — `browser-mcp-contrato-de-arquitetura`.

## Modelo de ameaça implícito

Cenário: um agente LLM (potencialmente injetável via conteúdo de página) controla um
browser Chrome na máquina de um parceiro iFood, via extensão + servidor WebSocket local.
Cada controle existe contra um vetor específico:

| Vetor de ataque | Controle que o bloqueia |
|---|---|
| Prompt injection manda o agente navegar para site malicioso / phishing look-alike | Allowlist de domínios com match EXATO de hostname |
| Downgrade para HTTP (MITM na rede do parceiro) | HTTPS obrigatório |
| Agente acessa `chrome://settings`, IPs internos, intranet | Match exato rejeita qualquer hostname fora da lista (e `chrome://` falha no check de scheme) |
| Agente usa tools de alto risco (screenshot, sessão, rede) para exfiltrar/agir | Allowlist de tools (5 permitidas no working tree — ver "Os 6 controles" §2) |
| Agente injeta JS arbitrário na página logada do parceiro | Allowlist de scripts por SHA-256 (vazia = tudo rejeitado) |
| Outro processo/máquina da rede conecta no servidor WS | Bind forçado em 127.0.0.1 + origin `chrome-extension://` obrigatório + token obrigatório |
| Outro usuário local lê o token | Permissões do token file (0600/0400) checadas no startup, senão o servidor recusa iniciar |
| Dados sensíveis (token, cookies, localStorage, DOM) vazam para logs | Sanitização: truncamento a 200 chars + redação por keyword |

## Ativação

```bash
export IFOOD_RESTRICTED_MODE=1
```

Semântica exata (`src/browser_mcp/restricted_profile.py:29-31`): ativo somente se o
valor, após `strip()`, for exatamente a string `"1"`. Qualquer outra coisa
(`"true"`, `"yes"`, ausente) = modo padrão SEM restrições. O modo padrão não valida
nada (`restricted_profile.py:247-248` retorna `(True, "")` cedo).

## Os 6 controles — semântica exata

Todos em `src/browser_mcp/restricted_profile.py`. Ponto de entrada centralizado:
`RestrictedProfile.validate_tool_call(tool_name, arguments)` (linhas 240-283),
que retorna `(allowed: bool, reason: str)` — rejeições vêm com texto iniciado em
`REJECTED:`.

### 1. Allowlist de domínios (HTTPS + hostname exato)

`is_domain_allowed(url)` — `restricted_profile.py:45-66`:

- Scheme DEVE ser `https` (linha 58). `http://` é rejeitado mesmo para host permitido.
  `chrome://` também cai aqui.
- Hostname (via `urllib.parse.urlparse().hostname`) deve estar **exatamente** em
  `ALLOWED_HOSTS` (linha 66). Sem wildcard, sem sufixo, sem subdomínio.

`ALLOWED_HOSTS` no **working tree** (`restricted_profile.py:39-44`), verificado
2026-07-17 — **4 hosts**:

```python
ALLOWED_HOSTS: set[str] = {
    "gestordepedidos.ifood.com.br",
    "portal.ifood.com.br",
    "partners-auth.ifood.com.br",
    "developer.ifood.com.br",
}
```

**Estado divergente HEAD vs working tree** (expansão intencional do dono,
2026-07-13, WIP não commitado): o commit em HEAD (`4c534b3`) ainda tem apenas
**2 hosts** (`gestordepedidos`, `portal`). Os 2 hosts adicionais
(`partners-auth`, `developer`) vivem só no working tree — re-verifique com
`grep -A6 "ALLOWED_HOSTS" src/browser_mcp/restricted_profile.py` e
`git diff HEAD -- src/browser_mcp/restricted_profile.py`.

Consequências do match exato (todas cobertas por teste):

| URL | Resultado | Teste |
|---|---|---|
| `https://portal.ifood.com.br/dashboard` | PERMITIDO | `test_restricted_profile.py:49` |
| `http://portal.ifood.com.br/` | REJEITADO (HTTP) | `test_restricted_profile.py:54` |
| `https://api.portal.ifood.com.br` | REJEITADO (subdomínio) | `test_restricted_profile.py:68` |
| `https://portal.ifood.com.br.hacker.net` | REJEITADO (look-alike) | `test_restricted_profile.py:64` |
| `https://gestordepedidos.ifood.com.br.evil.com` | REJEITADO (look-alike) | `test_restricted_profile.py:63` |
| `chrome://settings` | REJEITADO | `test_restricted_profile.py:58` |
| IPs, `evil.com`, URL malformada, vazia | REJEITADO | `test_restricted_profile.py:72-81` |
| `https://portal.ifood.com.br:443/test` | PERMITIDO (porta não afeta hostname) | `test_restricted_profile.py:91` |

Path e query string são ignorados na validação (`test_restricted_profile.py:83-86`).

### 2. Allowlist de tools

`ALLOWED_TOOLS` no **working tree** (`restricted_profile.py:76-82`) — **5 tools**:

- `browser_navigate`
- `browser_get_content`
- `browser_execute_javascript`
- `browser_type`
- `browser_click`

**Estado divergente HEAD vs working tree** (expansão intencional do dono,
2026-07-13, WIP não commitado): HEAD (`4c534b3`) tem apenas **3** (`navigate`,
`get_content`, `execute_javascript`); `browser_type` e `browser_click` foram
adicionados só no working tree. **Dívida de sincronização declarada:** essa
expansão fez 2 testes adversariais FALHAREM hoje —
`test_unauthorized_tool_rejected` (`test_restricted_profile.py:106`) e
`test_disallowed_tool_rejected_in_restricted_mode`
(`test_restricted_profile.py:179`) — porque ambos assumiam que `type`/`click`
estavam FORA da lista. Quem commitar a expansão DEVE atualizar esses testes
(mudança de segurança → passa pelo gate de [[browser-mcp-controle-de-mudancas]]).

Qualquer outra tool (`browser_screenshot`, `browser_network_start`,
`browser_manage_session`, ...) é rejeitada (`is_tool_allowed`, linhas 90-92).
`PASSTHROUGH_TOOLS` existe mas está vazio (linhas 85-87).
`browser_get_content` passa sem checagem adicional de domínio
(`test_restricted_profile.py:241-247`).

### 3. Allowlist de JavaScript por SHA-256

`is_script_allowed(code)` — `restricted_profile.py:105-112`:

- Hash: `hashlib.sha256(code.encode("utf-8")).hexdigest()` (`compute_script_hash`,
  linhas 100-102). Sensível a QUALQUER byte: espaço, quebra de linha, aspas.
- O hash deve estar em `ALLOWED_SCRIPT_HASHES` (`restricted_profile.py:97`).
- **`ALLOWED_SCRIPT_HASHES` está VAZIO hoje** (verificado 2026-07-17). Allowlist vazia
  = **todo JS rejeitado** (secure-by-default, linhas 110-111; teste que trava isso:
  `test_restricted_profile.py:141-144` assere `len(ALLOWED_SCRIPT_HASHES) == 0`).
- Código vazio também é rejeitado (`restricted_profile.py:274-275`).
- A mensagem de rejeição expõe só os 12 primeiros chars do hash
  (`restricted_profile.py:279`).

### 4. Rede: loopback + origin + token

- **Bind forçado 127.0.0.1**: `RestrictedProfile.get_bind_host()` retorna sempre
  `"127.0.0.1"` (`restricted_profile.py:232-238`; teste `test_restricted_profile.py:352-354`).
  O enforcement real no `WebSocketServer.__init__` é WIP (ver "Estado da integração").
- **Origin `chrome-extension://` obrigatório**: no WIP, em modo restrito, origin vazio
  → `403 Forbidden`; origin que não começa com `chrome-extension://` → `403`.
  (No código commitado, origin vazio é tolerado.)
- **Token obrigatório**: comparação com `hmac.compare_digest`; no WIP, ausência de
  token em modo restrito gera `401` com mensagem explícita
  (`Authorization: Bearer <token>` ou `?token=` na query).

### 5. Permissões do token file (gate de startup)

`check_token_permissions()` — `restricted_profile.py:122-152`:

- Token em `~/.mcp_browser_token` (`TOKEN_PATH`, linha 119).
- Arquivo ausente → falha (linhas 128-129).
- Modo POSIX deve ser exatamente `0o400` ou `0o600` (linhas 140-147). `0644` falha
  (teste `test_restricted_profile.py:290-306`).
- Windows: check sempre passa (linhas 131-132).
- `check_startup_conditions()` (linhas 293-307) roda isso no boot; se falhar,
  **o servidor recusa iniciar** — no WIP, `websocket_server.py` faz
  `sys.exit(1)` com `FATAL` no stderr.

Correção padrão:

```bash
chmod 600 ~/.mcp_browser_token
```

### 6. Logs sanitizados

- `sanitize_log_message` (`restricted_profile.py:169-183`): trunca mensagens acima de
  **200 chars** com sufixo `...[truncated]` — bloqueia dump de DOM/código nos logs.
- `RestrictedProfile.sanitize_log_dict` (`restricted_profile.py:208-225`): redige
  recursivamente para `[REDACTED]` toda chave cujo nome (case-insensitive) contenha
  uma das keywords de `_SENSITIVE_KEYWORDS` (`restricted_profile.py:159-166`):
  `token`, `auth`, `bearer`, `localstorage`, `sessionstorage`, `cookie`.
  Valores string não sensíveis passam pelo truncamento de 200 chars.
- Testes: `TestLogSanitization` (`test_restricted_profile.py:367-402`), incluindo
  dicts aninhados.

## Estado da integração (verificado 2026-07-13)

- `src/browser_mcp/restricted_profile.py` está **commitado**
  (commit `4c534b3`, branch `etapa-1-ifood-restricted-profile`).
- A **integração** é **WIP não commitado** (`git status` mostra `M` em
  `src/browser_mcp/tools.py` e `src/browser_mcp/websocket_server.py`). Para inspecionar:

```bash
git diff src/browser_mcp/tools.py src/browser_mcp/websocket_server.py
```

Conteúdo do WIP (lido do diff em 2026-07-13):

| Arquivo | Mudança WIP |
|---|---|
| `tools.py` | `ToolRegistry.call_tool` chama `RestrictedProfile.validate_tool_call(name, arguments)` ANTES do dispatch; se rejeitado, retorna `TextContent` com a razão `REJECTED: ...` sem tocar extensão/Playwright |
| `websocket_server.py` (`__init__`) | Modo restrito: força `self.host = "127.0.0.1"` (warning se host pedido era outro) e roda `check_startup_conditions()`; falha → `FATAL` no stderr + `sys.exit(1)` |
| `websocket_server.py` (handshake) | Modo restrito: origin vazio → 403; origin não-`chrome-extension://` → 403; token ausente → 401 com mensagem explicativa |
| `websocket_server.py` (`_handle_message`) | Modo restrito: aplica `sanitize_log_dict` na mensagem antes do log |

**Implicação prática**: sem esse WIP aplicado, setar `IFOOD_RESTRICTED_MODE=1` NÃO
bloqueia nada — o módulo existe mas ninguém o chama. Não trate o modo restrito como
ativo em produção até esse diff virar commit (ver "Proveniência e manutenção").

**Observação sobre o WIP** (não corrigir sem processo — ver
`browser-mcp-controle-de-mudancas`): em `_handle_message`, o dict sanitizado
substitui `msg` e segue para o processamento, não só para o log — payloads com chaves
sensíveis podem chegar redigidos/truncados ao handler. Avaliar antes de commitar.

## Runbooks

### (a) Adicionar um domínio à allowlist

1. Justifique por escrito (por que o piloto precisa; siga o gate de
   `browser-mcp-controle-de-mudancas`).
2. Edite `ALLOWED_HOSTS` em `src/browser_mcp/restricted_profile.py:39-44` com o
   hostname EXATO (sem scheme, sem path, minúsculas):
   ```python
   ALLOWED_HOSTS: set[str] = {
       "gestordepedidos.ifood.com.br",
       "portal.ifood.com.br",
       "partners-auth.ifood.com.br",
       "developer.ifood.com.br",
       "novo.host.ifood.com.br",  # ticket/justificativa
   }
   ```
3. **Obrigatório**: adicione os testes adversariais correspondentes em
   `tests/test_restricted_profile.py` seguindo o padrão existente
   (`TestDomainAllowlist`, linhas 43-91):
   - positivo HTTPS: `is_domain_allowed("https://novo.host.ifood.com.br/x") is True`
   - HTTP rejeitado (padrão da linha 53)
   - look-alike rejeitado, ex. `https://novo.host.ifood.com.br.hacker.net`
     (padrão das linhas 63-64: `...ifood.com.br.evil.com`, `...ifood.com.br.hacker.net`)
   - subdomínio rejeitado, ex. `https://api.novo.host.ifood.com.br`
     (padrão das linhas 68-70)
4. Rode:
   ```bash
   pytest tests/test_restricted_profile.py -v
   ```
5. Um teste de segurança sem caso adversarial não conta como teste de segurança.

### (b) Aprovar um script JS

1. Congele o texto EXATO do script (o hash quebra com 1 byte de diferença).
2. Calcule o hash (mesma fórmula de `restricted_profile.py:100-102`):
   ```bash
   python3 -c "import hashlib,sys; print(hashlib.sha256(sys.stdin.read().encode()).hexdigest())" < script.js
   ```
   Atenção: `< script.js` inclui o `\n` final do arquivo — o código enviado pela tool
   precisa ser byte-a-byte idêntico ao que foi hasheado. A skill
   `browser-mcp-diagnosticos-e-ferramentas` terá o utilitário `hash_script.py` para isso.
3. Adicione o hash a `ALLOWED_SCRIPT_HASHES` (`restricted_profile.py:97`) com
   comentário dizendo o que o script faz e quem aprovou.
4. Ajuste/adicione testes: o teste `test_script_rejected_when_allowlist_empty`
   (`test_restricted_profile.py:141-144`) assere allowlist vazia — ao popular a lista,
   esse teste PRECISA ser atualizado deliberadamente (é o gate de secure-by-default).
   Adicione um positivo no padrão de `test_execute_js_allowed_hash_passes`
   (`test_restricted_profile.py:226-239`) e mantenha um negativo para hash desconhecido.
5. Rode `pytest tests/test_restricted_profile.py -v`.

### (c) Verificar que o modo está ativo DE FATO

Não confie no env var sozinho — verifique o comportamento:

```bash
# 1. Env var presente e igual a "1"?
echo "IFOOD_RESTRICTED_MODE=[$IFOOD_RESTRICTED_MODE]"   # deve imprimir [1]

# 2. O módulo reconhece o modo?
IFOOD_RESTRICTED_MODE=1 python3 -c "
import sys; sys.path.insert(0, 'src')
from browser_mcp.restricted_profile import RestrictedProfile
print('ativo:', RestrictedProfile.is_active())
ok, reason = RestrictedProfile.validate_tool_call('browser_screenshot', {})
print('browser_screenshot bloqueado:', not ok, '|', reason)
ok, reason = RestrictedProfile.validate_tool_call('browser_navigate', {'url': 'https://evil.com'})
print('evil.com bloqueado:', not ok)
"
# Esperado: ativo: True / browser_screenshot bloqueado: True / evil.com bloqueado: True
# (browser_screenshot segue FORA da allowlist; browser_click/browser_type NÃO
#  servem mais de exemplo — foram adicionados à lista no working tree.)

# 3. A INTEGRAÇÃO está no código que roda? (enquanto for WIP, isto é essencial)
grep -n "RestrictedProfile" src/browser_mcp/tools.py src/browser_mcp/websocket_server.py
# Sem hits em tools.py = o enforcement NÃO está ligado, mesmo com env var setado.
```

Prova end-to-end: com o servidor rodando em modo restrito, chame `browser_screenshot`
via MCP e confirme resposta `REJECTED: Tool 'browser_screenshot' is not in the
restricted allowlist...` (formato definido em `restricted_profile.py:251-256`). Use uma
tool que continue FORA da allowlist — `browser_click`/`browser_type` entraram nela no
working tree.

## Inegociáveis

1. **Nenhuma mudança relaxa um default sem gate.** Adicionar host, popular
   `ALLOWED_SCRIPT_HASHES`, ampliar `ALLOWED_TOOLS`, tocar em `PASSTHROUGH_TOOLS` —
   tudo passa pelo processo de `browser-mcp-controle-de-mudancas`. Esta skill não
   define o processo; define que ele é obrigatório.
2. **Testes de segurança são adversariais.** Todo controle novo/alterado precisa de
   casos que tentem burlá-lo (look-alike, subdomínio, HTTP, hash errado, permissão
   0644), não só o caminho feliz. O arquivo `test_restricted_profile.py` é o padrão.
3. **Secure-by-default não regride.** Allowlist vazia rejeita tudo; modo padrão só é
   "aberto" porque o modo restrito é opt-in explícito e exato (`== "1"`).

## Cobertura de testes

`tests/test_restricted_profile.py` (440 linhas), 8 classes:

| Classe (linha) | Cobre |
|---|---|
| `TestDomainAllowlist` (43) | HTTPS ok, HTTP/chrome:// rejeitados, look-alikes, subdomínios, domínio não autorizado, URL malformada, path/query ignorados, porta explícita |
| `TestToolAllowlist` (98) | tools permitidas passam; tools de alto risco (screenshot/network/session) e tool inexistente rejeitados. **2 testes desta classe/pipeline falham hoje** (`test_unauthorized_tool_rejected`, `test_disallowed_tool_rejected_in_restricted_mode`) porque o working tree adicionou `type`/`click` à allowlist — dívida de sincronização declarada |
| `TestJavaScriptAllowlist` (124) | hash determinístico (64 hex), allowlist vazia rejeita tudo, registro de hash permite, hash desconhecido rejeita |
| `TestValidateToolCall` (167) | pipeline completo com env var: modo padrão passa tudo; restrito rejeita tool fora da lista, HTTP, domínio não autorizado, JS sem hash, args ausentes; permite domínio/hash aprovados e get_content |
| `TestTokenPermissions` (272) | arquivo ausente falha; 0644 falha; 0600 e 0400 passam (skip no Windows) |
| `TestBindRestrictions` (349) | `get_bind_host() == "127.0.0.1"`; startup passa com modo off |
| `TestLogSanitization` (367) | truncamento >200 chars, mensagens curtas intactas, redação de token/auth_token/localStorage, dicts aninhados |
| `TestDefaultMode` (409) | sem env var: modo inativo, todas as tools passam, qualquer URL/JS passa |

**O que os testes NÃO cobrem hoje**: o WIP de integração (nenhum teste exercita
`ToolRegistry.call_tool` nem o handshake do `WebSocketServer` em modo restrito).

CI: `.github/workflows/ci.yml` tem job dedicado `restricted-profile` (matriz Python
3.11/3.12/3.13), step "Run restricted profile tests (Phase 7 — iFood security)",
rodando `pytest tests/test_restricted_profile.py -v`.

```bash
pytest tests/test_restricted_profile.py -v
```

## Pendências abertas declaradas (2026-07-13)

| Pendência | Estado |
|---|---|
| `ALLOWED_SCRIPT_HASHES` vazio | Todo JS rejeitado; o piloto precisa popular a lista via runbook (b) antes de qualquer uso de `browser_execute_javascript` |
| Allowlists hardcoded | `ALLOWED_HOSTS`/`ALLOWED_TOOLS`/`ALLOWED_SCRIPT_HASHES` vivem no código; não há config externa. Mudar = editar código + testes + PR |
| Plano de fases "Phase 7/8" | Mencionado em CI (`ci.yml`: "Phase 7 — iFood security"), no commit `4c534b3` ("Phase 8") e no docstring de teste; o plano em si NÃO está documentado no repo |
| WIP não commitado | Integração em `tools.py`/`websocket_server.py` só existe no working tree da branch `etapa-1-ifood-restricted-profile`; sem ela o modo restrito não bloqueia nada |
| Sanitização em `_handle_message` (WIP) | O dict sanitizado substitui a mensagem processada, não só o log — revisar antes de commitar |

## Proveniência e manutenção

- Verificado em **2026-07-17**, branch `etapa-1-ifood-restricted-profile`, contra:
  - `src/browser_mcp/restricted_profile.py` (307 linhas em HEAD `4c534b3` /
    311 linhas no working tree com o WIP das allowlists expandidas)
  - `tests/test_restricted_profile.py` (440 linhas; 2 testes falhando hoje pelo WIP)
  - `git diff src/browser_mcp/tools.py src/browser_mcp/websocket_server.py` (WIP)
  - `.github/workflows/ci.yml` (job `restricted-profile`)
- **Re-verificar se o WIP já foi commitado** (primeira coisa a checar ao usar esta skill):
  ```bash
  git status --short src/browser_mcp/tools.py src/browser_mcp/websocket_server.py
  # Saída vazia = WIP commitado (ou descartado!) — confirme com:
  grep -n "RestrictedProfile" src/browser_mcp/tools.py src/browser_mcp/websocket_server.py
  # Hits presentes = integração no código. Atualize a seção "Estado da integração".
  ```
- Re-verificar allowlists antes de citar valores: `ALLOWED_HOSTS`
  (`restricted_profile.py:39-44`), `ALLOWED_TOOLS` (76-82),
  `ALLOWED_SCRIPT_HASHES` (97). Line numbers podem deslocar após edições — confirme
  com `grep -n "ALLOWED_" src/browser_mcp/restricted_profile.py`.
- Atualize esta skill quando: allowlists mudarem, o WIP for commitado,
  `ALLOWED_SCRIPT_HASHES` for populado, ou o plano de fases for documentado.
