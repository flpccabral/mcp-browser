# MCP Browser Server — API Reference

Documentação completa de todas as 36 ferramentas (tools) expostas pelo servidor MCP Browser. Baseado em `src/browser_mcp/tools.py`.

---

## Índice

| # | Ferramenta | Categoria |
|---|-----------|----------|
| 1 | [browser_navigate](#1-browser_navigate) | Navegação |
| 2 | [browser_connect_to_existing](#2-browser_connect_to_existing) | Conexão |
| 3 | [browser_connect_to_extension](#3-browser_connect_to_extension) | Conexão |
| 4 | [browser_disconnect_extension](#4-browser_disconnect_extension) | Conexão |
| 5 | [browser_go_back](#5-browser_go_back) | Navegação |
| 6 | [browser_go_forward](#6-browser_go_forward) | Navegação |
| 7 | [browser_reload](#7-browser_reload) | Navegação |
| 8 | [browser_click](#8-browser_click) | Interação |
| 9 | [browser_type](#9-browser_type) | Interação |
| 10 | [browser_select_option](#10-browser_select_option) | Interação |
| 11 | [browser_hover](#11-browser_hover) | Interação |
| 12 | [browser_accessibility_tree](#12-browser_accessibility_tree) | Inspeção |
| 13 | [browser_press_key](#13-browser_press_key) | Interação |
| 14 | [browser_upload_file](#14-browser_upload_file) | Interação |
| 15 | [browser_get_content](#15-browser_get_content) | Inspeção |
| 16 | [browser_execute_javascript](#16-browser_execute_javascript) | Inspeção |
| 17 | [browser_get_attributes](#17-browser_get_attributes) | Inspeção |
| 18 | [browser_screenshot](#18-browser_screenshot) | Inspeção |
| 19 | [browser_network_start](#19-browser_network_start) | Rede |
| 20 | [browser_network_stop](#20-browser_network_stop) | Rede |
| 21 | [browser_network_list](#21-browser_network_list) | Rede |
| 22 | [browser_network_clear](#22-browser_network_clear) | Rede |
| 23 | [browser_get_network_log](#23-browser_get_network_log) | Rede |
| 24 | [browser_export_har](#24-browser_export_har) | Rede |
| 25 | [browser_manage_session](#25-browser_manage_session) | Sessão |
| 26 | [browser_wait](#26-browser_wait) | Sessão |
| 27 | [browser_get_url](#27-browser_get_url) | Inspeção |
| 28 | [browser_get_title](#28-browser_get_title) | Inspeção |
| 29 | [browser_agent_task](#29-browser_agent_task) | Agente |
| 30 | [browser_extension_get_network_log](#30-browser_extension_get_network_log) | Extensão |
| 31 | [browser_extension_get_dom_snapshot](#31-browser_extension_get_dom_snapshot) | Extensão |
| 32 | [browser_new_tab](#32-browser_new_tab) | Sessão |
| 33 | [browser_inject_indicator](#33-browser_inject_indicator) | Visual |
| 34 | [browser_remove_indicator](#34-browser_remove_indicator) | Visual |
| 35 | [browser_highlight_element](#35-browser_highlight_element) | Visual |
| 36 | [browser_set_security_level](#36-browser_set_security_level) | Visual |

---

## 1. browser_navigate

**Descrição:** Navega o browser para uma URL específica.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `url` | `string` | ✅ | — | URL completa para navegar (ex: `https://example.com`) |

**Exemplo de uso:**

```json
{
  "name": "browser_navigate",
  "arguments": {
    "url": "https://www.google.com"
  }
}
```

**Retorno:** Confirmação textual da navegação.

---

## 2. browser_connect_to_existing

**Descrição:** Conecta ao Chrome do usuário via CDP (Chrome DevTools Protocol) em vez de iniciar um novo browser.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `cdp_url` | `string` | ❌ | `http://localhost:9222` | URL do endpoint CDP do Chrome |

**Exemplo de uso:**

```json
{
  "name": "browser_connect_to_existing",
  "arguments": {
    "cdp_url": "http://localhost:9222"
  }
}
```

**Retorno:** Status da conexão ao browser existente.

---

## 3. browser_connect_to_extension

**Descrição:** Conecta ao browser real do usuário via Chrome Extension + WebSocket. Usa o Chrome do usuário com sua sessão, cookies e extensões ativas.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `ws_url` | `string` | ❌ | `ws://localhost:8765` | URL do WebSocket server |

**Exemplo de uso:**

```json
{
  "name": "browser_connect_to_extension",
  "arguments": {
    "ws_url": "ws://localhost:8765"
  }
}
```

**Retorno:** Status da conexão WebSocket com a extensão.

---

## 4. browser_disconnect_extension

**Descrição:** Desconecta do modo Chrome Extension e volta ao Playwright padrão.

**Parâmetros:** Nenhum.

**Exemplo de uso:**

```json
{
  "name": "browser_disconnect_extension",
  "arguments": {}
}
```

**Retorno:** Confirmação de desconexão.

---

## 5. browser_go_back

**Descrição:** Navega para a página anterior no histórico do browser.

**Parâmetros:** Nenhum.

**Exemplo de uso:**

```json
{
  "name": "browser_go_back",
  "arguments": {}
}
```

**Retorno:** Confirmação da navegação.

---

## 6. browser_go_forward

**Descrição:** Navega para a página seguinte no histórico do browser.

**Parâmetros:** Nenhum.

**Exemplo de uso:**

```json
{
  "name": "browser_go_forward",
  "arguments": {}
}
```

**Retorno:** Confirmação da navegação.

---

## 7. browser_reload

**Descrição:** Recarrega a página atual.

**Parâmetros:** Nenhum.

**Exemplo de uso:**

```json
{
  "name": "browser_reload",
  "arguments": {}
}
```

**Retorno:** Confirmação do recarregamento.

---

## 8. browser_click

**Descrição:** Clica em um elemento na página. Pode usar seletor CSS, referência `@e` (ex: `@e3`), texto visível ou coordenadas. Prefira `@e ref` quando disponível no accessibility tree — é mais estável. Se o seletor falhar, tenta fallback automático por texto visível.

> ⚠️ **Indicador de segurança:** Seletores contendo palavras como `login`, `password`, `delete`, `submit`, `payment`, etc., acionam automaticamente o overlay laranja (nível de segurança elevado).

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `selector` | `string` | ✅ | — | Seletor do elemento: CSS, `@e ref` (ex: `@e3`), texto visível ou coordenadas `x,y` |
| `by` | `string` (enum) | ❌ | `css` | Método de localização: `css`, `xpath`, `text`, `coordinates` ou `ref` |

**Exemplo de uso:**

```json
{
  "name": "browser_click",
  "arguments": {
    "selector": "#submit-button",
    "by": "css"
  }
}
```

```json
{
  "name": "browser_click",
  "arguments": {
    "selector": "@e3",
    "by": "ref"
  }
}
```

**Retorno:** Confirmação do clique.

---

## 9. browser_type

**Descrição:** Digita texto em um campo de input. Suporta seletores CSS e referências `@e` do accessibility tree.

> ⚠️ **Indicador de segurança:** Seletores contendo `password`, `senha`, `credit` ou `card` acionam o overlay laranja.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `selector` | `string` | ✅ | — | Seletor CSS do campo ou `@e ref` (ex: `@e3`) |
| `text` | `string` | ✅ | — | Texto a ser digitado |
| `clear` | `boolean` | ❌ | `true` | Se `true`, limpa o campo antes de digitar |
| `by` | `string` (enum) | ❌ | `css` | Método de localização: `css` ou `ref` |

**Exemplo de uso:**

```json
{
  "name": "browser_type",
  "arguments": {
    "selector": "#username",
    "text": "john.doe",
    "clear": true,
    "by": "css"
  }
}
```

```json
{
  "name": "browser_type",
  "arguments": {
    "selector": "@e5",
    "text": "hello world",
    "by": "ref"
  }
}
```

**Retorno:** Confirmação da digitação.

---

## 10. browser_select_option

**Descrição:** Seleciona uma opção em um dropdown (elemento `<select>`).

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `selector` | `string` | ✅ | — | Seletor CSS do `<select>` |
| `value` | `string` | ✅ | — | Valor da opção a ser selecionada |

**Exemplo de uso:**

```json
{
  "name": "browser_select_option",
  "arguments": {
    "selector": "#country-select",
    "value": "BR"
  }
}
```

**Retorno:** Confirmação da seleção.

---

## 11. browser_hover

**Descrição:** Move o mouse sobre um elemento (hover). Suporta seletores CSS e referências `@e`.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `selector` | `string` | ✅ | — | Seletor CSS ou `@e ref` (ex: `@e3`) |
| `by` | `string` (enum) | ❌ | `css` | Método de localização: `css` ou `ref` |

**Exemplo de uso:**

```json
{
  "name": "browser_hover",
  "arguments": {
    "selector": ".dropdown-menu",
    "by": "css"
  }
}
```

```json
{
  "name": "browser_hover",
  "arguments": {
    "selector": "@e7",
    "by": "ref"
  }
}
```

**Retorno:** Confirmação do hover.

---

## 12. browser_accessibility_tree

**Descrição:** Retorna o snapshot de acessibilidade da página atual. Inclui referências `@e` para elementos interativos, roles ARIA e nomes acessíveis. Ideal para descobrir refs estáveis antes de clicar/digitar.

**Parâmetros:** Nenhum.

**Exemplo de uso:**

```json
{
  "name": "browser_accessibility_tree",
  "arguments": {}
}
```

**Retorno (exemplo):**

```json
{
  "role": "WebArea",
  "name": "Example Page",
  "children": [
    {
      "role": "button",
      "name": "Submit",
      "@e_ref": "@e1"
    },
    {
      "role": "textbox",
      "name": "Username",
      "@e_ref": "@e2"
    }
  ]
}
```

---

## 13. browser_press_key

**Descrição:** Pressiona uma tecla (Enter, Tab, Escape, ArrowDown, etc.).

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `key` | `string` | ✅ | — | Nome da tecla: `Enter`, `Tab`, `Escape`, `ArrowDown`, `ArrowUp`, etc. |
| `selector` | `string` | ❌ | — | Seletor CSS opcional do elemento alvo |

**Exemplo de uso:**

```json
{
  "name": "browser_press_key",
  "arguments": {
    "key": "Enter"
  }
}
```

```json
{
  "name": "browser_press_key",
  "arguments": {
    "key": "Tab",
    "selector": "#search-input"
  }
}
```

**Retorno:** Confirmação do pressionamento.

---

## 14. browser_upload_file

**Descrição:** Faz upload de um arquivo para um input file.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `selector` | `string` | ✅ | — | Seletor CSS do `<input type="file">` |
| `file_path` | `string` | ✅ | — | Caminho absoluto do arquivo no sistema |

**Exemplo de uso:**

```json
{
  "name": "browser_upload_file",
  "arguments": {
    "selector": "#file-upload",
    "file_path": "/home/user/documents/report.pdf"
  }
}
```

**Retorno:** Confirmação do upload.

---

## 15. browser_get_content

**Descrição:** Obtém o conteúdo de um elemento específico ou da página inteira.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `selector` | `string` | ❌ | — | Seletor CSS opcional. Se omitido, retorna o conteúdo da página inteira |
| `as_html` | `boolean` | ❌ | `false` | Se `true`, retorna HTML ao invés de texto puro |

**Exemplo de uso:**

```json
{
  "name": "browser_get_content",
  "arguments": {
    "selector": ".main-content",
    "as_html": false
  }
}
```

```json
{
  "name": "browser_get_content",
  "arguments": {
    "as_html": true
  }
}
```

**Retorno:** Conteúdo textual ou HTML.

---

## 16. browser_execute_javascript

**Descrição:** Executa código JavaScript na página e retorna o resultado.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `code` | `string` | ✅ | — | Código JavaScript a ser executado |

**Exemplo de uso:**

```json
{
  "name": "browser_execute_javascript",
  "arguments": {
    "code": "document.title"
  }
}
```

```json
{
  "name": "browser_execute_javascript",
  "arguments": {
    "code": "return Array.from(document.querySelectorAll('a')).map(a => ({href: a.href, text: a.textContent.trim()}))"
  }
}
```

**Retorno:** Resultado da execução JavaScript (serializado como string).

---

## 17. browser_get_attributes

**Descrição:** Obtém atributos de um elemento HTML.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `selector` | `string` | ✅ | — | Seletor CSS do elemento |
| `attribute` | `string` | ❌ | — | Nome do atributo específico. Se omitido, retorna todos os atributos |

**Exemplo de uso:**

```json
{
  "name": "browser_get_attributes",
  "arguments": {
    "selector": "#login-button",
    "attribute": "disabled"
  }
}
```

```json
{
  "name": "browser_get_attributes",
  "arguments": {
    "selector": "a.main-link"
  }
}
```

**Retorno:** Valor do(s) atributo(s).

---

## 18. browser_screenshot

**Descrição:** Captura um screenshot da página.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `path` | `string` | ❌ | — | Caminho para salvar o screenshot. Se omitido, gera arquivo temporário |
| `full_page` | `boolean` | ❌ | `false` | Se `true`, captura a página inteira (com scroll) |

**Exemplo de uso:**

```json
{
  "name": "browser_screenshot",
  "arguments": {
    "path": "/tmp/homepage.png",
    "full_page": true
  }
}
```

```json
{
  "name": "browser_screenshot",
  "arguments": {}
}
```

**Retorno:** Caminho onde o screenshot foi salvo.

---

## 19. browser_network_start

**Descrição:** Inicia a captura de tráfego de rede em tempo real.

**Parâmetros:** Nenhum.

**Exemplo de uso:**

```json
{
  "name": "browser_network_start",
  "arguments": {}
}
```

**Retorno:** Confirmação de início da captura.

---

## 20. browser_network_stop

**Descrição:** Para a captura de tráfego de rede.

**Parâmetros:** Nenhum.

**Exemplo de uso:**

```json
{
  "name": "browser_network_stop",
  "arguments": {}
}
```

**Retorno:** Confirmação de parada da captura.

---

## 21. browser_network_list

**Descrição:** Lista as requisições de rede capturadas.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `filter_url` | `string` | ❌ | — | Filtrar por substring na URL |
| `filter_method` | `string` | ❌ | — | Filtrar por método HTTP (`GET`, `POST`, etc.) |

**Exemplo de uso:**

```json
{
  "name": "browser_network_list",
  "arguments": {
    "filter_url": "api",
    "filter_method": "POST"
  }
}
```

```json
{
  "name": "browser_network_list",
  "arguments": {}
}
```

**Retorno:** JSON com lista de requisições capturadas.

---

## 22. browser_network_clear

**Descrição:** Limpa o log de requisições de rede.

**Parâmetros:** Nenhum.

**Exemplo de uso:**

```json
{
  "name": "browser_network_clear",
  "arguments": {}
}
```

**Retorno:** Confirmação da limpeza.

---

## 23. browser_get_network_log

**Descrição:** Obtém o log detalhado de requisições de rede capturadas.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `filter_url` | `string` | ❌ | — | Filtrar por substring na URL |
| `filter_method` | `string` | ❌ | — | Filtrar por método HTTP (`GET`, `POST`, etc.) |

**Exemplo de uso:**

```json
{
  "name": "browser_get_network_log",
  "arguments": {
    "filter_url": "/graphql"
  }
}
```

```json
{
  "name": "browser_get_network_log",
  "arguments": {
    "filter_method": "POST"
  }
}
```

**Retorno:** Log detalhado das requisições de rede.

---

## 24. browser_export_har

**Descrição:** Exporta o log de rede no formato HAR (HTTP Archive).

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `path` | `string` | ✅ | — | Caminho do arquivo HAR a ser exportado |

**Exemplo de uso:**

```json
{
  "name": "browser_export_har",
  "arguments": {
    "path": "/tmp/network-trace.har"
  }
}
```

**Retorno:** Caminho do arquivo HAR exportado.

---

## 25. browser_manage_session

**Descrição:** Gerencia a sessão do browser: cookies, abas, viewport e gravação.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `action` | `string` (enum) | ✅ | — | Ação a executar |

**Ações disponíveis:**

| Ação | Descrição |
|------|-----------|
| `get_cookies` | Obtém todos os cookies da página atual |
| `set_cookies` | Define cookies na sessão |
| `new_tab` | Abre uma nova aba |
| `list_tabs` | Lista todas as abas abertas |
| `close_tab` | Fecha uma aba específica |
| `resize_viewport` | Redimensiona o viewport do browser |
| `start_recording` | Inicia a gravação de vídeo da sessão |
| `stop_recording` | Para a gravação de vídeo |

**Exemplo de uso:**

```json
{
  "name": "browser_manage_session",
  "arguments": {
    "action": "get_cookies"
  }
}
```

```json
{
  "name": "browser_manage_session",
  "arguments": {
    "action": "resize_viewport",
    "width": 1920,
    "height": 1080
  }
}
```

```json
{
  "name": "browser_manage_session",
  "arguments": {
    "action": "start_recording",
    "path": "/tmp/session.webm"
  }
}
```

**Retorno:** Resultado da ação executada.

---

## 26. browser_wait

**Descrição:** Aguarda uma condição específica na página.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `condition` | `string` (enum) | ✅ | — | Condição a aguardar |
| `selector` | `string` | ❌ | — | Seletor CSS (necessário para `element_visible` / `element_hidden`) |
| `timeout` | `integer` | ❌ | `30000` | Timeout em milissegundos |

**Condições disponíveis:**

| Condição | Descrição |
|----------|-----------|
| `element_visible` | Aguarda até que o elemento fique visível |
| `element_hidden` | Aguarda até que o elemento fique oculto |
| `network_idle` | Aguarda até que a rede fique ociosa |
| `timeout` | Aguarda um tempo fixo |

**Exemplo de uso:**

```json
{
  "name": "browser_wait",
  "arguments": {
    "condition": "element_visible",
    "selector": "#loading-spinner",
    "timeout": 5000
  }
}
```

```json
{
  "name": "browser_wait",
  "arguments": {
    "condition": "network_idle",
    "timeout": 30000
  }
}
```

```json
{
  "name": "browser_wait",
  "arguments": {
    "condition": "timeout",
    "timeout": 2000
  }
}
```

**Retorno:** Confirmação de que a condição foi satisfeita.

---

## 27. browser_get_url

**Descrição:** Obtém a URL atual da página em navegação.

**Parâmetros:** Nenhum.

**Exemplo de uso:**

```json
{
  "name": "browser_get_url",
  "arguments": {}
}
```

**Retorno:** URL atual (string).

---

## 28. browser_get_title

**Descrição:** Obtém o título da página atual.

**Parâmetros:** Nenhum.

**Exemplo de uso:**

```json
{
  "name": "browser_get_title",
  "arguments": {}
}
```

**Retorno:** Título da página (string).

---

## 29. browser_agent_task

**Descrição:** Executa uma tarefa complexa de browser usando um agente autônomo com LLM. O agente decide quais ações tomar de forma iterativa para completar a tarefa descrita.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `task` | `string` | ✅ | — | Descrição da tarefa a ser executada |
| `max_iterations` | `integer` | ❌ | `50` | Número máximo de iterações do agente |
| `take_screenshots` | `boolean` | ❌ | `true` | Se `true`, o agente tira screenshots durante a execução |
| `capture_network` | `boolean` | ❌ | `true` | Se `true`, captura log de rede |
| `output_dir` | `string` | ❌ | `./agent_output` | Diretório para salvar relatórios e screenshots |

**Exemplo de uso:**

```json
{
  "name": "browser_agent_task",
  "arguments": {
    "task": "Acesse https://example.com, encontre o link 'Documentation', clique nele e salve um screenshot",
    "max_iterations": 20,
    "take_screenshots": true,
    "capture_network": false,
    "output_dir": "./task-output"
  }
}
```

**Retorno:** Relatório Markdown com status, ações executadas, screenshots e erros. Salvo em `{output_dir}/report.md`.

---

## 30. browser_extension_get_network_log

**Descrição:** Obtém o log de rede capturado pela extensão Chrome (XHR/fetch). **Requer modo extension ativo** (previamente conectado via `browser_connect_to_extension`).

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `filter_url` | `string` | ❌ | — | Filtrar por substring na URL |
| `filter_method` | `string` | ❌ | — | Filtrar por método HTTP (`GET`, `POST`, etc.) |

**Exemplo de uso:**

```json
{
  "name": "browser_extension_get_network_log",
  "arguments": {
    "filter_url": "/api/v1",
    "filter_method": "GET"
  }
}
```

**Retorno:** Log de rede capturado pela extensão.

---

## 31. browser_extension_get_dom_snapshot

**Descrição:** Obtém snapshot do DOM atual via extensão Chrome. **Requer modo extension ativo** (previamente conectado via `browser_connect_to_extension`).

**Parâmetros:** Nenhum.

**Exemplo de uso:**

```json
{
  "name": "browser_extension_get_dom_snapshot",
  "arguments": {}
}
```

**Retorno:** Snapshot do DOM da página atual.

---

## 32. browser_new_tab

**Descrição:** Abre uma nova aba no navegador e opcionalmente agrupa com um título de sessão.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `url` | `string` | ✅ | — | URL para abrir na nova aba |
| `group_title` | `string` | ❌ | `"MCP Browser"` | Título do grupo de abas (ex: `"Sessão MCP"`) |

**Exemplo de uso:**

```json
{
  "name": "browser_new_tab",
  "arguments": {
    "url": "https://docs.example.com",
    "group_title": "Documentação"
  }
}
```

**Retorno:** Confirmação da abertura da nova aba.

---

## 33. browser_inject_indicator

**Descrição:** Injeta overlay visual pulsante na página indicando que o agente está controlando o navegador. Útil para feedback visual durante automação.

**Parâmetros:** Nenhum.

**Exemplo de uso:**

```json
{
  "name": "browser_inject_indicator",
  "arguments": {}
}
```

**Retorno:** Confirmação da injeção do indicador.

---

## 34. browser_remove_indicator

**Descrição:** Remove o overlay visual de automação da página.

**Parâmetros:** Nenhum.

**Exemplo de uso:**

```json
{
  "name": "browser_remove_indicator",
  "arguments": {}
}
```

**Retorno:** Confirmação da remoção do indicador.

---

## 35. browser_highlight_element

**Descrição:** Destaca visualmente um elemento na página com borda azul temporária. Útil para depuração e feedback visual durante automação.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `selector` | `string` | ✅ | — | Seletor CSS do elemento a destacar |

**Exemplo de uso:**

```json
{
  "name": "browser_highlight_element",
  "arguments": {
    "selector": ".product-card"
  }
}
```

**Retorno:** Confirmação do destaque.

---

## 36. browser_set_security_level

**Descrição:** Altera a cor do overlay visual por nível de segurança. As cores indicam o contexto da operação em andamento.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Padrão | Descrição |
|------|------|:----------:|--------|-----------|
| `level` | `string` | ❌ | `"blue"` | Nível de segurança: `blue`, `orange`, `red` ou `green` |

**Cores e significados:**

| Cor | Significado |
|-----|------------|
| `blue` | Operação normal / segura (padrão) |
| `orange` | Atenção — operação sensível (ex: campos de senha, login, pagamento) |
| `red` | Perigo — operação crítica |
| `green` | Sucesso / concluído |

**Exemplo de uso:**

```json
{
  "name": "browser_set_security_level",
  "arguments": {
    "level": "orange"
  }
}
```

**Retorno:** Confirmação da alteração do nível.

---

## Categorias

### Navegação (3)
`browser_navigate` · `browser_go_back` · `browser_go_forward` · `browser_reload`

### Conexão (3)
`browser_connect_to_existing` · `browser_connect_to_extension` · `browser_disconnect_extension`

### Interação (5)
`browser_click` · `browser_type` · `browser_select_option` · `browser_hover` · `browser_press_key` · `browser_upload_file`

### Inspeção (6)
`browser_accessibility_tree` · `browser_get_content` · `browser_execute_javascript` · `browser_get_attributes` · `browser_screenshot` · `browser_get_url` · `browser_get_title`

### Rede (6)
`browser_network_start` · `browser_network_stop` · `browser_network_list` · `browser_network_clear` · `browser_get_network_log` · `browser_export_har`

### Sessão (3)
`browser_manage_session` · `browser_wait` · `browser_new_tab`

### Agente (1)
`browser_agent_task`

### Extensão (2)
`browser_extension_get_network_log` · `browser_extension_get_dom_snapshot`

### Visual (4)
`browser_inject_indicator` · `browser_remove_indicator` · `browser_highlight_element` · `browser_set_security_level`

---

## Tratamento de Erros

Todas as ferramentas retornam erros no formato:

```
ERROR: [TipoDoErro] - mensagem descritiva - sugestão de correção
```

**Exemplos de mensagens de erro:**

- `ERROR: [TimeoutError] - Navegação excedeu o tempo limite - Aumente o timeout ou verifique se o elemento está presente.`
- `ERROR: [ElementNotFound] - Elemento '#missing-btn' não encontrado - Verifique se o seletor está correto e o elemento está visível.`
- `ERROR: [FileNotFoundError] - Arquivo não encontrado - Verifique se o caminho ou arquivo existe.`
- `ERROR: [NotImplementedError] - Funcionalidade não disponível - Este recurso ainda não foi implementado.`

---

> **Nota:** Esta documentação é gerada a partir de `src/browser_mcp/tools.py`. Para a versão mais atualizada, consulte o código-fonte.
