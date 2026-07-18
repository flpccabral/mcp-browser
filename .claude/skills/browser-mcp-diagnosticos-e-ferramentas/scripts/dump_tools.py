#!/usr/bin/env python3
"""Lista as ferramentas MCP registradas em src/browser_mcp/tools.py.

Por que parsing estático e não importar tools.py:
    tools.py cria singletons no topo do módulo (browser_manager = BrowserManager(),
    llm_client = LLMClient()). Importar dispara esses efeitos colaterais e pode
    exigir dependências instaladas (playwright etc.). Aqui lemos a AST e extraímos
    apenas os decorators @app.tool(name=..., description=...), sem executar nada.

Contagem correta:
    grep '^@app.tool' conta 39 decorators — o número real de ferramentas.
    Um grep ingênuo por 'app.tool(' pode pegar 2 ocorrências extras (a definição
    do próprio decorator e docstrings), por isso preferimos a AST.

Uso:
    python .claude/skills/browser-mcp-diagnosticos-e-ferramentas/scripts/dump_tools.py
    python .../dump_tools.py --json
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path


def find_tools_py() -> Path:
    """Localiza src/browser_mcp/tools.py subindo a partir deste script."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "src" / "browser_mcp" / "tools.py"
        if candidate.exists():
            return candidate
    print("ERRO: não encontrei src/browser_mcp/tools.py", file=sys.stderr)
    sys.exit(2)


def _kwarg(call: ast.Call, key: str) -> str | None:
    for kw in call.keywords:
        if kw.arg == key and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return None


def extract_tools(path: Path) -> list[dict[str, str]]:
    """Extrai (name, description) de cada decorator @app.tool(...)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tools: list[dict[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            is_app_tool = (
                isinstance(func, ast.Attribute)
                and func.attr == "tool"
                and isinstance(func.value, ast.Name)
                and func.value.id == "app"
            )
            if not is_app_tool:
                continue
            name = _kwarg(dec, "name") or node.name
            desc = (_kwarg(dec, "description") or (ast.get_docstring(node) or "")).strip()
            desc = " ".join(desc.split())
            tools.append({"name": name, "description": desc})
    return tools


def main() -> None:
    ap = argparse.ArgumentParser(description="Lista as ferramentas MCP registradas.")
    ap.add_argument("--json", action="store_true", help="Saída em JSON")
    args = ap.parse_args()

    path = find_tools_py()
    tools = extract_tools(path)

    if args.json:
        print(json.dumps(tools, ensure_ascii=False, indent=2))
    else:
        for t in tools:
            print(f"{t['name']:<38} {t['description']}")
        print(f"\nTotal: {len(tools)} ferramentas ({path})", file=sys.stderr)


if __name__ == "__main__":
    main()
