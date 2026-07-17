#!/usr/bin/env python
"""Benchmark de confiabilidade do BrowserAgent (Fase 0 da campanha).

Roda N tarefas reproduzíveis contra fixtures HTML locais (servidas por um
http.server embutido) + 1 tarefa contra example.com, e produz métricas:

  - taxa de sucesso (tarefas completas / N)
  - iterações médias (action_count)
  - causa de falha categorizada, extraída dos strings REAIS de
    agent.py::_build_final_result e do loop execute_task:
        parse_error      -> "consecutive parse errors" no report
        llm_error        -> "consecutive errors" (sem "parse") no report
        max_iterations   -> "max iterations" no report
        false_complete   -> agente declarou is_complete=true mas o check
                            programático da tarefa falhou (wrong_action)
        harness_timeout  -> asyncio.wait_for estourou o teto por tarefa
        crash            -> exceção não tratada fora do agente
  - incidentes de parse por run (entradas "Could not parse LLM response"
    em result["errors"], mesmo em tarefas que terminaram com sucesso) —
    insumo obrigatório da Fase 1.

Uso (requer LLM configurado — LLM_PROVIDER/LLM_API_KEY/LLM_MODEL):

    PYTHONPATH=src .venv/bin/python \
        .claude/skills/browser-mcp-campanha-confiabilidade-do-agente/scripts/benchmark_agent.py \
        --out /tmp/agent_benchmark

    # listar tarefas sem executar nada:
    ... benchmark_agent.py --list

    # subconjunto:
    ... benchmark_agent.py --tasks extract_code,cascade_slow

O resultado é gravado como JSON em <out>/run_<timestamp>.json e um resumo é
impresso no stdout. Rode 2x: você tem linha de base quando os dois runs
diferem em no máximo ±1 tarefa no total de sucessos.
"""

from __future__ import annotations

import argparse
import asyncio
import http.server
import json
import os
import socketserver
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DEFAULT_PORT = 8763
DEFAULT_TASK_TIMEOUT = 300  # segundos por tarefa
DEFAULT_MAX_ITERATIONS = 15  # teto POR TAREFA no benchmark (não é solução de
                             # confiabilidade — é só o orçamento do experimento)

# ---------------------------------------------------------------------------
# Definição de tarefas
# ---------------------------------------------------------------------------

CheckFn = Callable[[Any, dict[str, Any]], Awaitable[bool]]


@dataclass
class Task:
    id: str
    prompt: str
    check: CheckFn
    notes: str = ""
    max_iterations: int = DEFAULT_MAX_ITERATIONS


def _report_contains(*needles: str) -> CheckFn:
    async def check(bm: Any, result: dict[str, Any]) -> bool:
        report = (result.get("report") or "")
        return all(n.lower() in report.lower() for n in needles)
    return check


def _page_contains(*needles: str) -> CheckFn:
    async def check(bm: Any, result: dict[str, Any]) -> bool:
        try:
            content = await bm.get_content()
        except Exception:
            return False
        return all(n in content for n in needles)
    return check


def build_tasks(base_url: str) -> list[Task]:
    return [
        Task(
            id="extract_code",
            prompt=(
                f"Navegue para {base_url}/extract_fact.html e extraia o "
                "código de verificação do relatório. Inclua o código exato no report final."
            ),
            check=_report_contains("FX-7731-KappaBravo"),
            notes="extração simples de texto estático",
        ),
        Task(
            id="extract_table",
            prompt=(
                f"Navegue para {base_url}/extract_fact.html e informe no report "
                "o total de vendas da região Sul, exatamente como aparece na tabela."
            ),
            check=_report_contains("87.310"),
            notes="extração de célula de tabela",
        ),
        Task(
            id="login_ok",
            prompt=(
                f"Navegue para {base_url}/form_login.html e faça login com "
                "usuário 'admin' e senha 'segredo123'. Confirme que o login funcionou."
            ),
            check=_page_contains("LOGIN_OK"),
            notes="preencher 2 campos + submit + verificar resultado",
        ),
        Task(
            id="search_filter",
            prompt=(
                f"Navegue para {base_url}/search_list.html, busque por 'M4' e "
                "informe no report quantos produtos foram encontrados."
            ),
            check=_report_contains("2"),
            notes="digitar + clicar + ler resultado dinâmico",
        ),
        Task(
            id="multi_step_price",
            prompt=(
                f"Navegue para {base_url}/search_list.html, busque por 'trena' e "
                "informe no report o preço exato da trena."
            ),
            check=_report_contains("22,90"),
            notes="2 interações + extração",
        ),
        Task(
            id="cascade_fast",
            prompt=(
                f"Navegue para {base_url}/cascade_ajax.html?delay=300 e complete a "
                "matrícula: escola 'EM Machado de Assis', série '1º ano', turma "
                "'Turma 1A', depois clique em Confirmar matrícula. Cada select é "
                "populado por AJAX após o anterior — espere carregar antes de selecionar."
            ),
            check=_page_contains("MATRICULA_OK"),
            notes="cascata AJAX rápida (modo de falha histórico i-Educar)",
        ),
        Task(
            id="cascade_slow",
            prompt=(
                f"Navegue para {base_url}/cascade_ajax.html?delay=2500 e complete a "
                "matrícula: escola 'EM Cora Coralina', série '5º ano', turma "
                "'Turma 5A', depois clique em Confirmar matrícula. Os selects "
                "demoram alguns segundos para carregar via AJAX."
            ),
            check=_page_contains("MATRICULA_OK"),
            notes="cascata AJAX lenta — estressa browser_wait/network_idle",
        ),
        Task(
            id="example_com",
            prompt=(
                "Navegue para https://example.com e informe no report o texto "
                "exato do título principal (h1) da página."
            ),
            check=_report_contains("Example Domain"),
            notes="site externo estável (única tarefa com rede real)",
        ),
    ]


# ---------------------------------------------------------------------------
# Categorização de falhas (strings reais de agent.py — re-verifique se mudar)
# ---------------------------------------------------------------------------

def categorize(result: dict[str, Any] | None, check_ok: bool, timed_out: bool,
               crashed: bool) -> str:
    if crashed:
        return "crash"
    if timed_out:
        return "harness_timeout"
    assert result is not None
    report = result.get("report") or ""
    if result.get("success"):
        return "success" if check_ok else "false_complete"
    if "consecutive parse errors" in report:
        return "parse_error"
    if "consecutive errors" in report:
        return "llm_error"
    if "max iterations" in report.lower():
        return "max_iterations"
    return "other"


def count_parse_incidents(result: dict[str, Any] | None) -> int:
    if not result:
        return 0
    return sum(1 for e in result.get("errors", [])
               if "Could not parse LLM response" in e)


# ---------------------------------------------------------------------------
# Servidor de fixtures
# ---------------------------------------------------------------------------

class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(FIXTURES_DIR), **kwargs)

    def log_message(self, *args: Any) -> None:  # silencia stdout
        pass


def start_fixture_server(port: int) -> socketserver.TCPServer:
    server = socketserver.TCPServer(("127.0.0.1", port), _QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

async def run_benchmark(tasks: list[Task], task_timeout: int,
                        output_dir: Path) -> dict[str, Any]:
    # Imports adiados para que --list funcione sem dependências instaladas.
    from browser_mcp.agent import BrowserAgent
    from browser_mcp.browser_manager import BrowserManager
    from browser_mcp.llm_client import LLMClient

    bm = BrowserManager()
    await bm.start()
    llm = LLMClient()

    records: list[dict[str, Any]] = []
    try:
        for task in tasks:
            agent = BrowserAgent(
                bm,
                llm,
                max_iterations=task.max_iterations,
                screenshot_on_action=False,
                output_dir=str(output_dir / "artifacts" / task.id),
            )
            result: dict[str, Any] | None = None
            timed_out = crashed = False
            check_ok = False
            t0 = time.time()
            try:
                result = await asyncio.wait_for(
                    agent.execute_task(task.prompt), timeout=task_timeout
                )
                check_ok = await task.check(bm, result)
            except asyncio.TimeoutError:
                timed_out = True
            except Exception as exc:
                crashed = True
                print(f"  [crash] {task.id}: {exc}", file=sys.stderr)
            elapsed = round(time.time() - t0, 1)

            category = categorize(result, check_ok, timed_out, crashed)
            rec = {
                "task": task.id,
                "category": category,
                "success": category == "success",
                "iterations": (result or {}).get("action_count", None),
                "parse_incidents": count_parse_incidents(result),
                "errors": (result or {}).get("errors", []),
                "elapsed_s": elapsed,
                "report_head": ((result or {}).get("report") or "")[:300],
            }
            records.append(rec)
            print(f"  {task.id:<18} {category:<16} "
                  f"iters={rec['iterations']} parse_inc={rec['parse_incidents']} "
                  f"{elapsed}s")

            # reset de estado entre tarefas
            try:
                await bm.navigate("about:blank")
            except Exception:
                pass
    finally:
        await bm.stop()

    n = len(records)
    successes = sum(1 for r in records if r["success"])
    iter_values = [r["iterations"] for r in records if r["iterations"] is not None]
    categories: dict[str, int] = {}
    for r in records:
        categories[r["category"]] = categories.get(r["category"], 0) + 1

    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "llm_provider": os.getenv("LLM_PROVIDER", "deepseek"),
        "llm_model": os.getenv("LLM_MODEL", "(default)"),
        "n_tasks": n,
        "successes": successes,
        "success_rate": round(successes / n, 3) if n else 0.0,
        "mean_iterations": round(sum(iter_values) / len(iter_values), 2)
        if iter_values else None,
        "total_parse_incidents": sum(r["parse_incidents"] for r in records),
        "failure_categories": categories,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default="/tmp/agent_benchmark",
                        help="diretório de saída (JSON + artefatos)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"porta do servidor de fixtures (default {DEFAULT_PORT})")
    parser.add_argument("--tasks", default="",
                        help="ids separados por vírgula (default: todas)")
    parser.add_argument("--task-timeout", type=int, default=DEFAULT_TASK_TIMEOUT,
                        help="teto em segundos por tarefa")
    parser.add_argument("--list", action="store_true",
                        help="lista as tarefas e sai (não requer LLM/browser)")
    parser.add_argument("--offline", action="store_true",
                        help="omite example_com (única tarefa com rede real): "
                             "linha de base 100%% local e determinística")
    args = parser.parse_args()

    base_url = f"http://127.0.0.1:{args.port}"
    tasks = build_tasks(base_url)
    if args.offline:
        tasks = [t for t in tasks if t.id != "example_com"]
    if args.tasks:
        wanted = {t.strip() for t in args.tasks.split(",") if t.strip()}
        unknown = wanted - {t.id for t in tasks}
        if unknown:
            print(f"Tarefas desconhecidas: {sorted(unknown)}", file=sys.stderr)
            return 2
        tasks = [t for t in tasks if t.id in wanted]

    if args.list:
        for t in tasks:
            print(f"{t.id:<18} max_iter={t.max_iterations:<3} {t.notes}")
        return 0

    if not os.getenv("LLM_API_KEY") and os.getenv("LLM_PROVIDER", "deepseek") != "ollama":
        print("AVISO: LLM_API_KEY não definido — o run vai falhar como llm_error "
              "a menos que LLM_PROVIDER=ollama.", file=sys.stderr)

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    server = start_fixture_server(args.port)
    try:
        print(f"Fixtures em {base_url} | {len(tasks)} tarefa(s)")
        summary = asyncio.run(run_benchmark(tasks, args.task_timeout, output_dir))
    finally:
        server.shutdown()

    out_file = output_dir / f"run_{int(time.time())}.json"
    out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    print("\n=== RESUMO ===")
    print(f"sucesso: {summary['successes']}/{summary['n_tasks']} "
          f"({summary['success_rate']:.0%})")
    print(f"iterações médias: {summary['mean_iterations']}")
    print(f"incidentes de parse (total): {summary['total_parse_incidents']}")
    print(f"categorias: {summary['failure_categories']}")
    print(f"JSON: {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
