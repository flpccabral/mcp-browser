#!/usr/bin/env python3
"""Script de gerenciamento do MCP Browser — inicia/para/verifica servidores.

Comandos:
    python manage_mcp_browser.py start       # Inicia todos os servidores
    python manage_mcp_browser.py stop        # Para todos os servidores
    python manage_mcp_browser.py status      # Verifica status
    python manage_mcp_browser.py restart     # Reinicia tudo
"""

import subprocess
import sys
import os
import time

PROJECT_DIR = "/Users/felipecc/Documents/kimi/workspaces/mcp_browser"
VENV_PYTHON = f"{PROJECT_DIR}/.venv/bin/python"
WS_PORT = 8765


def check_ws_server():
    """Verifica se o WebSocket server está rodando na porta 8765."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{WS_PORT}", "-t"],
            capture_output=True, text=True, timeout=5
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def check_mcp_server():
    """Verifica se o MCP Browser server está rodando (stdio)."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "browser_mcp.server"],
            capture_output=True, text=True, timeout=5
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def start_ws_server():
    """Inicia o WebSocket server standalone em background."""
    if check_ws_server():
        print("[WS] WebSocket server já está rodando na porta 8765")
        return True

    print("[WS] Iniciando WebSocket server...")
    proc = subprocess.Popen(
        [VENV_PYTHON, "websocket_server_standalone.py"],
        cwd=PROJECT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    if check_ws_server():
        print(f"[WS] WebSocket server iniciado (PID {proc.pid})")
        return True
    else:
        print("[WS] ERRO: Falha ao iniciar WebSocket server")
        return False


def stop_ws_server():
    """Para o WebSocket server."""
    if not check_ws_server():
        print("[WS] WebSocket server não está rodando")
        return True

    try:
        result = subprocess.run(
            ["lsof", "-i", f":{WS_PORT}", "-t"],
            capture_output=True, text=True, timeout=5
        )
        for pid in result.stdout.strip().split("\n"):
            if pid:
                subprocess.run(["kill", pid], timeout=5)
                print(f"[WS] WebSocket server encerrado (PID {pid})")
        return True
    except Exception as e:
        print(f"[WS] ERRO ao parar: {e}")
        return False


def stop_all_mcp():
    """Para todos os processos do MCP Browser server."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "browser_mcp.server"],
            capture_output=True, text=True, timeout=5
        )
        for pid in result.stdout.strip().split("\n"):
            if pid:
                subprocess.run(["kill", pid], timeout=5)
                print(f"[MCP] Server encerrado (PID {pid})")
        return True
    except Exception as e:
        print(f"[MCP] ERRO ao parar: {e}")
        return False


def status():
    """Mostra status de todos os componentes."""
    print("=" * 50)
    print("MCP Browser — Status")
    print("=" * 50)
    ws_ok = check_ws_server()
    mcp_ok = check_mcp_server()
    print(f"WebSocket Server (porta {WS_PORT}): {'✅ RODANDO' if ws_ok else '❌ PARADO'}")
    print(f"MCP Browser Server (stdio):       {'✅ RODANDO' if mcp_ok else '❌ PARADO'}")
    print("=" * 50)
    return ws_ok and mcp_ok


def start():
    """Inicia todos os servidores necessários."""
    print("Iniciando MCP Browser...")
    ws_ok = start_ws_server()
    if ws_ok:
        print("\n✅ MCP Browser pronto para uso!")
        print(f"   WebSocket: ws://localhost:{WS_PORT}")
        print("   Para modo extensão: conecte o Chrome com a extensão em chrome://extensions")
    else:
        print("\n⚠️  WebSocket server falhou. O modo extensão não estará disponível.")
        print("   O modo Playwright (padrão) continua funcional via Hermes.")
    return ws_ok


def stop():
    """Para todos os servidores."""
    print("Parando MCP Browser...")
    stop_ws_server()
    stop_all_mcp()
    print("✅ Todos os servidores parados.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "restart":
        stop()
        time.sleep(1)
        start()
    elif cmd == "status":
        ok = status()
        sys.exit(0 if ok else 1)
    else:
        print(f"Comando desconhecido: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
