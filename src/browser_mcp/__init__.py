"""Browser MCP Server - Automação de browser via Model Context Protocol."""

# Carrega variáveis de um arquivo .env (se existir) ANTES de qualquer submódulo
# ler os.getenv no import — browser_manager lê defaults no nível do módulo.
from dotenv import load_dotenv

load_dotenv()

__version__ = "0.1.0"
