#!/usr/bin/env python3
"""report.py の純粋関数を CI 抜きで検証する（stdlib unittest）。

差分パース・行カバレッジ抽出・patch 集計・整形は、CI（Actions / artifact 取得）に
依存せずローカルで確かめられる。ここが壊れると PR コメントの「事実」が誤るため、
境界（削除のみ行・実行対象でない変更行・複数ステートメント行・base 未取得）を突く。

    python3 -m unittest discover scripts/coverage/tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import report  # noqa: E402


class ParseDiffAddedLines(unittest.TestCase):
    def test_collects_added_lines_on_new_side(self) -> None:
        diff = (
            "diff --git a/backend/app/foo.py b/backend/app/foo.py\n"
            "--- a/backend/app/foo.py\n"
            "+++ b/backend/app/foo.py\n"
            "@@ -10,0 +11,2 @@\n"
            "+new line 11\n"
            "+new line 12\n"
        )
        self.assertEqual(report.parse_diff_added_lines(diff), {"backend/app/foo.py": {11, 12}})

    def test_deletion_only_hunk_has_no_added_lines(self) -> None:
        diff = "--- a/x.py\n+++ b/x.py\n@@ -5,2 +4,0 @@\n-gone\n-gone too\n"
        # 削除のみ → 追加行なし → ファイルごと除外される（消えた行にテストは書けない）。
        self.assertEqual(report.parse_diff_added_lines(diff), {})

    def test_deleted_file_is_ignored(self) -> None:
        diff = "--- a/gone.py\n+++ /dev/null\n@@ -1,1 +0,0 @@\n-was here\n"
        self.assertEqual(report.parse_diff_added_lines(diff), {})

    def test_single_line_hunk_without_count(self) -> None:
        # "+7" は "+7,1" と同義。カウント省略時に 1 行として扱えること。
        diff = "--- a/y.py\n+++ b/y.py\n@@ -6 +7 @@\n+changed\n"
        self.assertEqual(report.parse_diff_added_lines(diff), {"y.py": {7}})


class BackendLineCoverage(unittest.TestCase):
    def test_executable_is_executed_union_missing(self) -> None:
        cov = {
            "files": {
                "app/foo.py": {"executed_lines": [1, 2], "missing_lines": [3, 4]},
            }
        }
        result = report.backend_line_coverage(cov, Path("/repo"), "backend")
        executable, covered = result["backend/app/foo.py"]
        self.assertEqual(executable, {1, 2, 3, 4})
        self.assertEqual(covered, {1, 2})


class FrontendLineCoverage(unittest.TestCase):
    def test_line_covered_if_any_statement_hit(self) -> None:
        final = {
            "/repo/frontend/src/x.ts": {
                "path": "/repo/frontend/src/x.ts",
                "statementMap": {
                    "0": {"start": {"line": 5}},
                    "1": {"start": {"line": 5}},  # 同じ行に 2 ステートメント
                    "2": {"start": {"line": 6}},
                },
                "s": {"0": 0, "1": 3, "2": 0},
            }
        }
        result = report.frontend_line_coverage(final, Path("/repo"), "frontend")
        executable, covered = result["frontend/src/x.ts"]
        self.assertEqual(executable, {5, 6})
        # 5 行目はどれか 1 つでもヒットしていればカバー済み、6 行目は未カバー。
        self.assertEqual(covered, {5})

    def test_build_output_path_maps_back_to_source(self) -> None:
        # Angular+Vitest の istanbul は dist/test-out/<ts>/src/... を指す。
        # これを frontend/src/... に戻せないと diff と一生一致しない（回帰防止）。
        final = {
            "/runner/frontend/dist/test-out/20260101T0Z-abc/src/app/board.ts": {
                "path": "/runner/frontend/dist/test-out/20260101T0Z-abc/src/app/board.ts",
                "statementMap": {"0": {"start": {"line": 9}}},
                "s": {"0": 0},
            }
        }
        result = report.frontend_line_coverage(final, Path("/runner"), "frontend", strip_to="src")
        self.assertIn("frontend/src/app/board.ts", result)


class ComputePatch(unittest.TestCase):
    def setUp(self) -> None:
        # foo: 1-3 実行対象・1,2 カバー / bar: 10-11 実行対象・全カバー
        self.line_cov = {
            "backend/app/foo.py": ({1, 2, 3}, {1, 2}),
            "backend/app/bar.py": ({10, 11}, {10, 11}),
        }

    def test_counts_only_executable_changed_lines(self) -> None:
        # 変更行 = foo:{2,3,4}。4 は実行対象外（空行等）なので分母から外れる。
        added = {"backend/app/foo.py": {2, 3, 4}}
        patch = report.compute_patch(self.line_cov, added)
        self.assertEqual(patch["total"], 2)  # 2,3
        self.assertEqual(patch["covered"], 1)  # 2
        self.assertEqual(patch["uncovered"], ["backend/app/foo.py:3"])
        self.assertEqual(patch["pct"], 50.0)

    def test_file_without_coverage_is_skipped(self) -> None:
        added = {"docs/readme.md": {1, 2}}
        patch = report.compute_patch(self.line_cov, added)
        self.assertEqual(patch, {"total": 0, "covered": 0, "pct": None, "uncovered": []})

    def test_all_covered_changed_lines(self) -> None:
        added = {"backend/app/bar.py": {10, 11}}
        patch = report.compute_patch(self.line_cov, added)
        self.assertEqual((patch["total"], patch["covered"], patch["uncovered"]), (2, 2, []))
        self.assertEqual(patch["pct"], 100.0)


class RenderComment(unittest.TestCase):
    def _report(self, kind: str, pct: float, patch: dict | None) -> dict:
        return {
            "kind": kind,
            "label": report._LABELS[kind],
            "totals": {"Lines": {"pct": pct, "covered": int(pct), "total": 100}},
            "patch": patch,
        }

    def test_delta_direction_and_uncovered_listing(self) -> None:
        cur = [
            self._report(
                "backend",
                86.0,
                {"total": 4, "covered": 3, "pct": 75.0, "uncovered": ["app/foo.py:3"]},
            )
        ]
        base = [self._report("backend", 87.5, None)]
        md = report.render_comment(cur, base, "abcdef1234", "9998887776")
        self.assertIn(report.MARKER, md)
        self.assertIn("▼ 1.50%", md)  # 87.5 → 86.0 は減少
        self.assertIn("Base (main)", md)
        self.assertIn("`app/foo.py:3`", md)  # 未カバー変更行の名指し
        self.assertIn("変更したのにテストが通っていない行 (1)", md)
        self.assertIn("base = `9998887`", md)

    def test_no_baseline_shows_first_time_delta(self) -> None:
        cur = [
            self._report("frontend", 80.0, {"total": 0, "covered": 0, "pct": None, "uncovered": []})
        ]
        md = report.render_comment(cur, [], "abcdef1234", "")
        self.assertIn("— _(初回)_", md)
        self.assertIn("base 未取得", md)
        self.assertIn("変更行に計測対象のコードなし", md)

    def test_all_covered_message(self) -> None:
        cur = [
            self._report("backend", 90.0, {"total": 3, "covered": 3, "pct": 100.0, "uncovered": []})
        ]
        md = report.render_comment(cur, cur, "aaaaaaa", "aaaaaaa")
        self.assertIn("変更した実行行はすべてテストで通っています", md)
        self.assertIn("– (±0)", md)  # 自分と比較すれば Δ はゼロ


if __name__ == "__main__":
    unittest.main()
