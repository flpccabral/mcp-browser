# MCP Browser Server

Servidor [Model Context Protocol (MCP)](https://modelcontextprotocol.io) para automação de navegador com agente autônomo. Permite que LLMs controlem um navegador real via Playwright — naveguem, cliquem, preencham formulários, extraiam dados e tomem decisões de forma autônoma com base em objetivos definidos em linguagem natural.

---

## Funcionalidades

- **18 ferramentas determinísticas** para controle preciso do navegador
- **Agente autônomo** capaz de planejar e executar tarefas complexas de navegação
- Suporte a múltiplos provedores de LLM (OpenAI, Anthropic, OpenRouter, DeepSeek)
- Screenshots, extração de texto, interação com formulários, scroll e muito mais

### Ferramentas disponíveis

| Ferramenta | Descrição |
|------------|-----------|
| `browser_navigate` | Navegar para uma URL |
| `browser_click` | Clicar em um elemento |
| `browser_type` | Digitar texto em um campo de entrada |
| `browser_select` | Selecionar uma opção em um `<select>` |
| `browser_scroll` | Rolar a página (para cima, baixo, esquerda, direita) |
| `browser_screenshot` | Capturar screenshot da página atual |
| `browser_get_text` | Extrair texto visível da página |
| `browser_get_html` | Obter o HTML completo da página |
| `browser_get_attribute` | Obter o valor de um atributo de um elemento |
| `browser_get_url` | Retornar a URL atual |
| `browser_go_back` | Voltar para a página anterior |
| `browser_go_forward` | Avançar para a próxima página |
| `browser_refresh` | Recarregar a página atual |
| `browser_wait` | Aguardar por um seletor ou tempo definido |
| `browser_press_key` | Simular pressionamento de tecla (Enter, Escape, Tab, etc.) |
| `browser_evaluate` | Executar JavaScript arbitrário na página |
| `browser_set_viewport` | Definir dimensões da janela do navegador |
| `browser_download` | Baixar um arquivo a partir de uma URL |
| `browser_agent` | Executar o agente autônomo com um objetivo em linguagem natural |

---

## Stack tecnológico

- **Python 3.11+**
- **Playwright** — automação de navegador
- **FastMCP** — framework MCP para Python
- **Pydantic** — validação de dados e serialização
- **OpenAI / Anthropic / OpenRouter / DeepSeek APIs** — provedores de LLM para o agente autônomo

---

## Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/mcp-browser-server.git
cd mcp-browser-server
```

### 2. Crie e ative um ambiente virtual

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Instale os navegadores do Playwright

```bash
playwright install chromium
```

---

## Configuração

1. Copie o arquivo de exemplo:

```bash
cp .env.example .env
```

2. Edite o `.env` e preencha as variáveis obrigatórias:

```env
# Provedor de LLM: openai | anthropic | openrouter | deepseek
LLM_PROVIDER=openai

# Chave de API do provedor escolhido
LLM_API_KEY=sk-...

# Modelo a ser usado pelo agente autônomo
LLM_MODEL=gpt-4o

# (Opcional) Headless: true para rodar sem interface gráfica
HEADLESS=true

# (Opcional) Timeout padrão para operações do navegador (ms)
DEFAULT_TIMEOUT=30000
```

---

## Execução

Inicie o servidor MCP:

```bash
python -m browser_mcp.server
```

O servidor iniciará no modo **stdio** (padrão MCP) e estará pronto para receber requisições de qualquer cliente MCP compatível.

---

## Uso via MCP Client

### Exemplo de chamada de ferramentas (modo determinístico)

```json
{
  "name": "browser_navigate",
  "arguments": {
    "url": "https://example.com"
  }
}
```

```json
{
  "name": "browser_screenshot",
  "arguments": {
    "full_page": true
  }
}
```

```json
{
  "name": "browser_type",
  "arguments": {
    "selector": "#search-input",
    "text": "MCP Browser Server"
  }
}
```

```json
{
  "name": "browser_click",
  "arguments": {
    "selector": "button[type=submit]"
  }
}
```

---

## Exemplos de uso do agente autônomo

O agente recebe um objetivo em linguagem natural e executa a sequência de ações necessária de forma autônoma.

### 1. Investigação de site

```json
{
  "name": "browser_agent",
  "arguments": {
    "objective": "Acesse https://news.ycombinator.com e me diga os títulos dos 5 posts mais populares da página inicial, incluindo o número de upvotes de cada um."
  }
}
```

**Resultado esperado:** o agente navega até o Hacker News, extrai os títulos e upvotes dos 5 primeiros posts e retorna uma lista estruturada.

### 2. Scraping de documentação

```json
{
  "name": "browser_agent",
  "arguments": {
    "objective": "Navegue até https://docs.python.org/3/tutorial/ e extraia o texto completo do sumário (tabela de conteúdo) da página. Retorne apenas os títulos e subtítulos em formato de lista hierárquica."
  }
}
```

**Resultado esperado:** o agente acessa a documentação do Python, localiza a seção de sumário, extrai todos os títulos e subtítulos e organiza em uma lista estruturada.

### 3. Teste de formulário

```json
{
  "name": "browser_agent",
  "arguments": {
    "objective": "Acesse https://httpbin.org/forms/post, preencha o formulário com nome 'João Silva', e-mail 'joao@email.com' e mensagem 'Teste de automação'. Envie o formulário e confirme que a página de resposta exibe os dados enviados corretamente."
  }
}
```

**Resultado esperado:** o agente preenche todos os campos, envia o formulário, verifica a página de resposta e confirma que os dados foram submetidos corretamente.

---

## Estrutura do projeto

```
mcp-browser-server/
├── browser_mcp/
│   ├── __init__.py
│   ├── server.py          # Ponto de entrada do servidor MCP
│   ├── tools.py           # Definição das 18 ferramentas determinísticas
│   ├── agent.py           # Lógica do agente autônomo (planning + execução)
│   ├── llm.py             # Cliente genérico para provedores de LLM
│   ├── browser.py         # Wrapper do Playwright (página, contexto, navegador)
│   └── utils.py           # Funções utilitárias
├── tests/
│   ├── test_tools.py
│   ├── test_agent.py
│   └── conftest.py
├── .env.example
├── requirements.txt
├── README.md
└── pyproject.toml
```

---

## Variáveis de ambiente

| Variável | Obrigatória | Padrão | Descrição |
|----------|-------------|--------|-----------|
| `LLM_PROVIDER` | Sim | `openai` | Provedor de LLM: `openai`, `anthropic`, `openrouter`, `deepseek` |
| `LLM_API_KEY` | Sim | — | Chave de API do provedor selecionado |
| `LLM_MODEL` | Sim | `gpt-4o` | Modelo a ser usado pelo agente autônomo |
| `HEADLESS` | Não | `true` | Executar o navegador em modo headless (sem interface) |
| `DEFAULT_TIMEOUT` | Não | `30000` | Timeout padrão para operações do navegador (ms) |
| `PLAYWRIGHT_BROWSER` | Não | `chromium` | Navegador a ser usado: `chromium`, `firefox`, `webkit` |
| `USER_AGENT` | Não | — | User-Agent customizado para o navegador |

---

## Providers LLM suportados

| Provedor | `LLM_PROVIDER` | Modelos recomendados | Observação |
|----------|---------------|----------------------|------------|
| **OpenAI** | `openai` | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo` | Requer `OPENAI_API_KEY` |
| **Anthropic** | `anthropic` | `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229` | Requer `ANTHROPIC_API_KEY` |
| **OpenRouter** | `openrouter` | `openai/gpt-4o`, `anthropic/claude-3.5-sonnet` | Requer `OPENROUTER_API_KEY` |
| **DeepSeek** | `deepseek` | `deepseek-chat`, `deepseek-reasoner` | Requer `DEEPSEEK_API_KEY` |

> **Nota:** a chave de API é sempre lida da variável `LLM_API_KEY`, independentemente do provedor. Certifique-se de que a chave corresponda ao provedor configurado em `LLM_PROVIDER`.

---

## Licença

[MIT](LICENSE)
