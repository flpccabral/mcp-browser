#!/usr/bin/env python3
"""Calcula o SHA-256 de um snippet JS no MESMO formato que o perfil restrito usa
para a allowlist ALLOWED_SCRIPT_HASHES.

Fórmula (idêntica a restricted_profile.compute_script_hash, restricted_profile.py:104):
    hashlib.sha256(code.encode("utf-8")).hexdigest()

IMPORTANTE — o hash é do texto EXATO. Qualquer diferença (espaço, quebra de linha,
aspas, indentação) muda o hash. Passe o snippet exatamente como será enviado à tool
browser_execute_javascript, sem reformatar.

Uso:
    # de um arquivo:
    python .../scripts/hash_script.py caminho/do/snippet.js
    # de stdin:
    echo -n 'document.title' | python .../scripts/hash_script.py -
    # literal na linha de comando (cuidado com o shell alterar aspas):
    python .../scripts/hash_script.py -c 'document.title'

Depois cole o hash em ALLOWED_SCRIPT_HASHES (restricted_profile.py:101).
"""
from __future__ import annotations

import argparse
import hashlib
import sys


def compute_script_hash(code: str) -> str:
    """Réplica de restricted_profile.compute_script_hash (restricted_profile.py:104)."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description="SHA-256 de snippet JS para a allowlist.")
    ap.add_argument("source", nargs="?", help="arquivo .js, ou '-' para stdin")
    ap.add_argument("-c", "--code", help="snippet literal na linha de comando")
    args = ap.parse_args()

    if args.code is not None:
        code = args.code
    elif args.source == "-":
        code = sys.stdin.read()
    elif args.source:
        with open(args.source, encoding="utf-8") as f:
            code = f.read()
    else:
        ap.error("forneça um arquivo, '-' (stdin), ou -c '<código>'")
        return

    digest = compute_script_hash(code)
    print(digest)
    print(
        f"# {len(code)} bytes de código. Adicione em ALLOWED_SCRIPT_HASHES "
        f"(restricted_profile.py:101):\n#     \"{digest}\",",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
