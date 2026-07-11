#!/bin/bash
# Hermes MCP Browser Server — launch script
# Isola o ambiente Python do Hermes para evitar conflitos de versão

cd /Users/felipecc/Documents/kimi/Workspaces/mcp_browser

# CRÍTICO: PYTHONPATH do Hermes injeta site-packages Python 3.11 no path
# do Python 3.14, quebrando pydantic_core (compilado pra 3.11, não 3.14)
unset PYTHONPATH
unset PYTHONSTARTUP
unset VIRTUAL_ENV

# -s: não adiciona user site-packages (segurança extra)
exec .venv/bin/python -s -m browser_mcp.server
