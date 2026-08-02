#!/usr/bin/env python3
"""カバレッジ結果を PR コメント用に「事実」へ翻訳する（D-19・D-23）。

D-19 は **カバレッジ率に下限を置かない**（P-1: 事実を見せ、判断は書き手に返す）。
したがってこのスクリプトは Pass/Fail を判定せず、ビルドも落とさない。代わりに
受け手が行動できる 2 つの事実だけを出す:

1. **base(main) からの変化 (Δ)** — 「元の状態はどうで、今回どう変わったか」
2. **未カバーの変更行** — 「今回あなたが変更した行のうち、テストが通っていない行」

とりわけ 2 は、率という代理指標ではなく「このPRが足すべきテスト」を行番号で名指す。
変更行の中にはテスト不要な行もある以上、足すかどうかの判断は書き手に返す。

サブコマンド:

    report.py collect --kind {backend|frontend} \
        --coverage <生カバレッジ> [--summary <json-summary>] \
        [--base-ref origin/main] [--path-prefix backend] \
        --out coverage-report.json

    report.py render --current a.json b.json \
        [--baseline base_a.json base_b.json] \
        [--sha <commit> --base-sha <commit>] \
        --out comment.md

``collect`` は生のカバレッジ（backend: coverage.json / frontend: istanbul の
coverage-final.json ＋ json-summary）と ``git diff`` を突き合わせ、正規化した
レポート JSON を吐く。``render`` は現在と base のレポートを比べて Markdown にする。
純粋関数（差分パース・行カバレッジ抽出・整形）に切り出してあるため、CI を待たず
ローカルの unittest で検証できる。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ``@@ -a,b +c,d @@`` のハンクヘッダ。新側 (+c,d) の追加行範囲だけを見る。
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


# ---------------------------------------------------------------------------
# 差分（変更行）の抽出
# ---------------------------------------------------------------------------
def parse_diff_added_lines(diff_text: str) -> dict[str, set[int]]:
    """``git diff --unified=0`` の出力から、ファイルごとの「新側の追加行番号」を返す。

    削除のみの行は行番号を持たないため patch coverage の対象にならない（消えた行に
    テストは書けない）。追加・変更された行だけを新側の行番号として集める。
    """
    added: dict[str, set[int]] = {}
    current: str | None = None
    next_line = 0
    remaining = 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            # "+++ b/path" → "path"。/dev/null（ファイル削除）は対象外。
            path = raw[4:].strip()
            if path == "/dev/null":
                current = None
            else:
                current = path[2:] if path.startswith(("a/", "b/")) else path
                added.setdefault(current, set())
            remaining = 0
            continue
        m = _HUNK.match(raw)
        if m:
            next_line = int(m.group(1))
            remaining = int(m.group(2)) if m.group(2) is not None else 1
            continue
        if current is None or remaining <= 0:
            continue
        if raw.startswith("+"):
            added[current].add(next_line)
            next_line += 1
            remaining -= 1
    return {p: lines for p, lines in added.items() if lines}


def get_added_lines(base_ref: str, repo_root: Path) -> dict[str, set[int]]:
    """``base_ref`` のマージベースから HEAD までの追加行を取得する。

    ``A...HEAD`` の三点記法はマージベースからの差分を意味する。base を直接使うと
    「main が進んだ分」まで自分の変更として数えてしまうため、必ずマージベース基準にする。
    """
    diff = subprocess.run(
        ["git", "diff", "--unified=0", "--no-color", f"{base_ref}...HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return parse_diff_added_lines(diff)


# ---------------------------------------------------------------------------
# 行カバレッジの抽出（生カバレッジ → path→(実行対象行, カバー済み行)）
# ---------------------------------------------------------------------------
def _norm_path(path: str, repo_root: Path, path_prefix: str, strip_to: str = "") -> str:
    """カバレッジ内のパスを、git diff と同じ「リポジトリ相対」に揃える。

    backend(coverage.py) は "app/foo.py" のようにサブディレクトリ相対で出るので
    ``path_prefix``（例: backend）を前置するだけでよい。

    frontend(Angular+Vitest)の istanbul は **ビルド出力先の絶対パス**
    （例: ``…/frontend/dist/test-out/<ts>/src/app/x.ts``）で出るため、単純な
    relpath ではソース（``frontend/src/app/x.ts``）に戻らず、差分と一生一致しない。
    そこで ``strip_to``（例: src）を渡し、そのセグメント以降だけを取り出して
    ``path_prefix`` の下に貼り直す。
    """
    p = path.replace(os.sep, "/")
    if strip_to:
        idx = p.rfind(f"/{strip_to}/")
        if idx != -1:
            rest = p[idx + 1 :]  # "src/app/x.ts"
            return f"{path_prefix}/{rest}" if path_prefix else rest
    if os.path.isabs(p):
        return os.path.relpath(p, repo_root).replace(os.sep, "/")
    return (os.path.join(path_prefix, p) if path_prefix else p).replace(os.sep, "/")


def backend_line_coverage(
    coverage_json: dict, repo_root: Path, path_prefix: str
) -> dict[str, tuple[set[int], set[int]]]:
    """coverage.py の JSON → path→(実行対象行, カバー済み行)。

    ``executed_lines`` がカバー済み、``executed_lines ∪ missing_lines`` が実行対象。
    コメントや空行など実行対象でない行は最初から含まれない。
    """
    result: dict[str, tuple[set[int], set[int]]] = {}
    for path, data in coverage_json.get("files", {}).items():
        executed = set(data.get("executed_lines", []))
        missing = set(data.get("missing_lines", []))
        result[_norm_path(path, repo_root, path_prefix)] = (executed | missing, executed)
    return result


def frontend_line_coverage(
    final_json: dict, repo_root: Path, path_prefix: str, strip_to: str = "src"
) -> dict[str, tuple[set[int], set[int]]]:
    """istanbul の coverage-final.json → path→(実行対象行, カバー済み行)。

    ``statementMap[id].start.line`` が行、``s[id] > 0`` がヒット。1 行に複数の
    ステートメントが乗る場合は「どれか 1 つでもヒットしていればその行はカバー済み」とみなす。
    """
    result: dict[str, tuple[set[int], set[int]]] = {}
    for path, data in final_json.items():
        stmt_map = data.get("statementMap", {})
        hits = data.get("s", {})
        executable: set[int] = set()
        covered: set[int] = set()
        for sid, loc in stmt_map.items():
            line = loc.get("start", {}).get("line")
            if line is None:
                continue
            executable.add(line)
            if hits.get(sid, 0) > 0:
                covered.add(line)
        key = _norm_path(data.get("path", path), repo_root, path_prefix, strip_to)
        result[key] = (executable, covered)
    return result


# ---------------------------------------------------------------------------
# patch coverage（変更行 ∩ 行カバレッジ）
# ---------------------------------------------------------------------------
def compute_patch(
    line_cov: dict[str, tuple[set[int], set[int]]],
    added_lines: dict[str, set[int]],
) -> dict:
    """変更した「実行対象行」のうち、テストで通っている割合と、通っていない行を返す。

    変更行のうち実行対象でない行（空行・型宣言のみ 等）は分母から外す。率で縛らないため
    Pass/Fail は付けず、未カバー行を ``uncovered`` に名指しで列挙するのが主目的。
    """
    total = 0
    covered = 0
    uncovered: list[str] = []
    for path, added in added_lines.items():
        cov = line_cov.get(path)
        if cov is None:
            continue
        executable, covered_lines = cov
        changed_exec = added & executable
        total += len(changed_exec)
        covered += len(changed_exec & covered_lines)
        for line in sorted(changed_exec - covered_lines):
            uncovered.append(f"{path}:{line}")
    pct = round(covered / total * 100, 2) if total else None
    return {"total": total, "covered": covered, "pct": pct, "uncovered": sorted(uncovered)}


# ---------------------------------------------------------------------------
# totals（全体カバレッジ）の正規化
# ---------------------------------------------------------------------------
def backend_totals(coverage_json: dict) -> dict[str, dict]:
    t = coverage_json.get("totals", {})
    lines_total = t.get("num_statements", 0)
    lines_cov = t.get("covered_lines", 0)
    br_total = t.get("num_branches", 0)
    br_cov = t.get("covered_branches", 0)
    out: dict[str, dict] = {
        "Lines": {
            "pct": round(t.get("percent_covered", 0.0), 2),
            "covered": lines_cov,
            "total": lines_total,
        }
    }
    if br_total:
        out["Branches"] = {
            "pct": round(br_cov / br_total * 100, 2),
            "covered": br_cov,
            "total": br_total,
        }
    return out


def frontend_totals(summary_json: dict) -> dict[str, dict]:
    total = summary_json.get("total", {})
    out: dict[str, dict] = {}
    for label, key in (
        ("Statements", "statements"),
        ("Branches", "branches"),
        ("Functions", "functions"),
        ("Lines", "lines"),
    ):
        m = total.get(key)
        if m:
            out[label] = {
                "pct": m.get("pct", 0.0),
                "covered": m.get("covered", 0),
                "total": m.get("total", 0),
            }
    return out


# ---------------------------------------------------------------------------
# collect サブコマンド
# ---------------------------------------------------------------------------
_LABELS = {"backend": "Backend (pytest)", "frontend": "Frontend (Vitest)"}


def collect(args: argparse.Namespace) -> int:
    repo_root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    coverage_json = json.loads(Path(args.coverage).read_text(encoding="utf-8"))

    if args.kind == "backend":
        totals = backend_totals(coverage_json)
        line_cov = backend_line_coverage(coverage_json, repo_root, args.path_prefix)
    else:
        summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
        totals = frontend_totals(summary)
        line_cov = frontend_line_coverage(coverage_json, repo_root, args.path_prefix, args.strip_to)

    patch = None
    if args.base_ref:
        added = get_added_lines(args.base_ref, repo_root)
        patch = compute_patch(line_cov, added)

    report = {"kind": args.kind, "label": _LABELS[args.kind], "totals": totals, "patch": patch}
    Path(args.out).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


# ---------------------------------------------------------------------------
# render サブコマンド（レポート → Markdown）
# ---------------------------------------------------------------------------
MARKER = "<!-- coverage-report -->"


def _fmt_cell(metric: dict | None) -> str:
    if not metric:
        return "—"
    return f"{metric['pct']}% ({metric['covered']}/{metric['total']})"


def _fmt_delta(cur: dict | None, base: dict | None) -> str:
    if cur is None:
        return "—"
    if base is None:
        return "— _(初回)_"
    d = round(cur["pct"] - base["pct"], 2)
    if abs(d) < 0.005:
        return "– (±0)"
    arrow = "▲" if d > 0 else "▼"
    return f"{arrow} {abs(d):.2f}%"


def render_section(current: dict, baseline: dict | None) -> str:
    lines = [f"### {current['label']}", ""]
    base_totals = (baseline or {}).get("totals", {})
    cur_totals = current.get("totals", {})
    lines.append("| Metric | Base (main) | This PR | Δ |")
    lines.append("| --- | --- | --- | --- |")
    for name, metric in cur_totals.items():
        base_metric = base_totals.get(name)
        row = f"| {name} | {_fmt_cell(base_metric)} | {_fmt_cell(metric)} |"
        lines.append(f"{row} {_fmt_delta(metric, base_metric)} |")

    patch = current.get("patch")
    if patch is not None:
        lines.append("")
        if patch["total"] == 0:
            lines.append("**Patch coverage:** 変更行に計測対象のコードなし。")
        else:
            lines.append(
                f"**Patch coverage:** {patch['covered']}/{patch['total']} "
                f"changed lines covered ({patch['pct']}%)"
            )
            if patch["uncovered"]:
                n = len(patch["uncovered"])
                lines.append("")
                lines.append(
                    f"<details><summary>変更したのにテストが通っていない行 ({n})</summary>"
                )
                lines.append("")
                for entry in patch["uncovered"]:
                    lines.append(f"- `{entry}`")
                lines.append("")
                lines.append("</details>")
            else:
                lines.append("")
                lines.append("変更した実行行はすべてテストで通っています。")
    return "\n".join(lines)


def render_comment(current: list[dict], baseline: list[dict], sha: str, base_sha: str) -> str:
    base_by_kind = {r["kind"]: r for r in baseline}
    parts = [MARKER, "## 🧪 Coverage report", ""]
    for cur in current:
        parts.append(render_section(cur, base_by_kind.get(cur["kind"])))
        parts.append("")
    if base_sha:
        footer = f"<sub>Updated for {sha[:7]}. base = `{base_sha[:7]}` (main) と比較。</sub>"
    else:
        footer = f"<sub>Updated for {sha[:7]}. base 未取得のため Δ は初回表示。</sub>"
    parts.append(footer)
    return "\n".join(parts)


def _load_reports(paths: list[str]) -> list[dict]:
    reports = []
    for p in paths or []:
        try:
            reports.append(json.loads(Path(p).read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return reports


def render(args: argparse.Namespace) -> int:
    current = _load_reports(args.current)
    baseline = _load_reports(args.baseline)
    body = render_comment(current, baseline, args.sha or "", args.base_sha or "")
    Path(args.out).write_text(body + "\n", encoding="utf-8")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("collect", help="生カバレッジ＋差分 → 正規化レポート JSON")
    c.add_argument("--kind", choices=["backend", "frontend"], required=True)
    c.add_argument(
        "--coverage", required=True, help="backend: coverage.json / frontend: coverage-final.json"
    )
    c.add_argument("--summary", help="frontend: coverage-summary.json（json-summary）")
    c.add_argument(
        "--base-ref", default="", help="Δ/patch の基準（例: origin/main）。空なら totals のみ"
    )
    c.add_argument(
        "--path-prefix", default="", help="カバレッジパスの repo 相対プレフィックス（例: backend）"
    )
    c.add_argument(
        "--strip-to",
        default="src",
        help="frontend 用。ビルド出力パスからこのセグメント以降を抽出（既定: src）",
    )
    c.add_argument("--out", required=True)
    c.set_defaults(func=collect)

    r = sub.add_parser("render", help="現在＋base のレポート → PR コメント Markdown")
    r.add_argument("--current", nargs="+", required=True)
    r.add_argument("--baseline", nargs="*", default=[])
    r.add_argument("--sha", default="")
    r.add_argument("--base-sha", default="")
    r.add_argument("--out", required=True)
    r.set_defaults(func=render)

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
