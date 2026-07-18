#!/usr/bin/env python3
"""Imprime o valor EFETIVO de cada variável de ambiente que o código realmente lê,
e cruza com o que .env.example documenta.

Fatos que este script torna visíveis (verificados 2026-07-13):
  1. O código NUNCA chama load_dotenv (grep 'load_dotenv' em src/ = zero matches).
     Logo, um arquivo .env NÃO é carregado automaticamente. As variáveis só têm
     efeito se estiverem exportadas no ambiente do processo (ex.: no mcpServers.env
     do cliente MCP, ou 'export' no shell).
  2. .env.example está ERRADO: documenta HEADLESS, DEFAULT_TIMEOUT, PLAYWRIGHT_BROWSER,
     USER_AGENT — nomes que o código não lê. O código lê BROWSER_HEADLESS,
     BROWSER_TIMEOUT etc. Variáveis do .env.example marcadas [NÃO LIDA] são ignoradas.

Uso:
    python .../scripts/check_env.py
"""
from __future__ import annotations

import os
from pathlib import Path

# Variáveis que o código REALMENTE lê. (var, default, onde: file:line)
# Fonte: grep os.getenv/os.environ em src/browser_mcp/ (2026-07-13).
READ_VARS: list[tuple[str, str, str]] = [
    ("BROWSER_HEADLESS", "true", "browser_manager.py:36"),
    ("BROWSER_VIEWPORT_WIDTH", "1280", "browser_manager.py:37"),
    ("BROWSER_VIEWPORT_HEIGHT", "720", "browser_manager.py:38"),
    ("BROWSER_TIMEOUT", "30000", "browser_manager.py:39"),
    ("EXTENSION_WS_URL", "ws://localhost:8765", "browser_manager.py:40"),
    ("ENABLE_VISUAL_INDICATOR", "true", "browser_manager.py:41"),
    ("STEALTH_MODE", "true", "browser_manager.py:42"),
    ("BROWSER_MCP_DOWNLOAD_DIR", "<tmp>/browser_mcp_downloads", "browser_manager.py:910"),
    ("LLM_PROVIDER", "deepseek", "llm_client.py:26"),
    ("LLM_API_KEY", "", "llm_client.py:27"),
    ("LLM_MODEL", "<provider default>", "llm_client.py:28"),
    ("LLM_BASE_URL", "<provider default>", "llm_client.py:29"),
]

# Nomes documentados em .env.example que o código NÃO lê (2026-07-13).
STALE_VARS = ["HEADLESS", "DEFAULT_TIMEOUT", "PLAYWRIGHT_BROWSER", "USER_AGENT"]

SECRET_KEYS = {"LLM_API_KEY"}


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "src" / "browser_mcp").is_dir():
            return parent
    return Path.cwd()


def mask(key: str, value: str) -> str:
    if key in SECRET_KEYS and value:
        return value[:4] + "…" + f"(len={len(value)})"
    return value


def main() -> None:
    root = repo_root()
    print("=== Variáveis que o CÓDIGO lê (valor efetivo no ambiente atual) ===")
    print(f"{'VARIÁVEL':<28} {'VALOR EFETIVO':<32} {'ORIGEM'}")
    for key, default, where in READ_VARS:
        raw = os.environ.get(key)
        if raw is None:
            effective = f"(default) {default}"
        else:
            effective = mask(key, raw)
        print(f"{key:<28} {effective:<32} {where}")

    print("\n=== Nomes em .env.example que o código IGNORA ===")
    for key in STALE_VARS:
        present = "presente no ambiente" if key in os.environ else "ausente"
        print(f"{key:<28} [NÃO LIDA]  ({present} — sem efeito)")

    env_example = root / ".env.example"
    print(f"\nload_dotenv chamado no código? {'SIM' if _uses_dotenv(root) else 'NÃO'} "
          "(se NÃO, .env não é carregado automaticamente)")
    print(f".env.example: {env_example if env_example.exists() else 'ausente'}")


def _uses_dotenv(root: Path) -> bool:
    src = root / "src" / "browser_mcp"
    for py in src.rglob("*.py"):
        if "load_dotenv" in py.read_text(encoding="utf-8"):
            return True
    return False


if __name__ == "__main__":
    main()
