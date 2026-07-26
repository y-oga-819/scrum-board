/**
 * problem+json（RFC 9457）をフロントで型付きに扱う入口（B-12・D-20）。
 *
 * 型の正は OpenAPI であり、`schema.d.ts` は `make gen-types` の生成物。ここでは
 * その生成型に**名前を与えて**再エクスポートし、アプリ側が
 * `components['schemas']['Problem']` の深い添字を書かずに済むようにする。手書きの
 * エラー型は作らない（Python と TS で 2 つの真実が生まれ、ずれても気づけない — D-20）。
 *
 * 信頼境界はサーバー。フロントは正を持たず、API が返した problem を**読むだけ**にする。
 * `violations` の規則 ID（`I-4` 等）はサーバーが機械可読に載せてくるので、フロントは
 * それを再判定せず参照する（不変条件のロジックを二重実装しない — D-20）。
 */
import type { components } from './schema';

/** RFC 9457 の problem 本体（`GET/PATCH/...` がエラー時に返す）。 */
export type Problem = components['schemas']['Problem'];

/** `violations[]` の 1 要素。`rule` が不変条件 ID（`I-4` 等）。 */
export type Violation = components['schemas']['Violation'];

/**
 * 値が problem+json かを実行時に判定する型ガード。
 *
 * `fetch` のエラー本文や `HttpErrorResponse.error` は `unknown` 扱いになるため、
 * ここで RFC 9457 の必須メンバー（`type` / `title` / `status`）の形を確かめてから
 * 型付きで扱う。サーバーはこの 3 つを必ず載せる（`app/http/handlers.py`）。
 */
export function isProblem(value: unknown): value is Problem {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate['type'] === 'string' &&
    typeof candidate['title'] === 'string' &&
    typeof candidate['status'] === 'number'
  );
}

/**
 * problem が特定の不変条件（`rule`）違反を含むかを返す。
 *
 * 例: 楽観排他や不変条件の分岐で `hasViolation(problem, 'I-4')` のように使う。
 * 判定の正はサーバーの `violations`。フロントは規則を再評価しない。
 */
export function hasViolation(problem: Problem, rule: string): boolean {
  return (problem.violations ?? []).some((violation) => violation.rule === rule);
}
