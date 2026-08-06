/**
 * HTTP エラーを**ユーザー向けの一文**に整形する共通処理（D-24・D-20）。
 *
 * 楽観排他（`If-Match`）が衝突した **412**（および稀に起きるドメイン競合 **409**）は、
 * 個々の画面ごとに文言を書き分けず、ここに一本化する。D-24 の方針——**黙って上書きせず、
 * 画面を最新に更新して事実を見せ、次の一手は人に委ねる（再操作を促す）**——を、文言の面でも
 * 一貫させるため。呼び出し側（バックログ B-17・ボード B-23…）は、このメッセージを表示した
 * うえで**集約 GET を引き直す**（「再取得して事実を見せる」動き自体は各画面が持つ）。
 *
 * 412 以外は、サーバーが返した problem+json（RFC 9457）の `detail` を尊重し、無ければ
 * 呼び出し側が渡す `fallback` を使う。信頼境界はサーバーで、フロントは problem を**読むだけ**
 * （不変条件やエラー文言を再実装しない — D-20）。
 */
import { HttpErrorResponse } from '@angular/common/http';

import { isProblem } from './problem';

/**
 * 楽観排他の衝突（412／409）でユーザーに見せる一文（D-24）。
 *
 * 強制も警告もせず、起きた事実（他の人が更新した・最新に更新した）と次にできること
 * （必要ならもう一度）だけを伝える。警告色は使わない（色は種別の区別のみ — D-13）。
 */
export const CONCURRENCY_CONFLICT_MESSAGE =
  '他の人が先に更新したため、最新の状態に更新しました。必要ならもう一度操作してください。';

/**
 * HTTP エラーを表示用メッセージに変換する。
 *
 * - **412 / 409**（楽観排他の衝突・ドメイン競合）→ {@link CONCURRENCY_CONFLICT_MESSAGE}。
 * - problem+json の本文があれば `detail` を返す。
 * - どちらでもなければ `fallback`。
 *
 * `err` は `HttpClient` が投げる {@link HttpErrorResponse} を想定するが、それ以外
 * （ネットワーク断の素の値など）でも `fallback` に落ちて安全に扱える。
 */
export function messageForError(err: unknown, fallback: string): string {
  if (err instanceof HttpErrorResponse && (err.status === 412 || err.status === 409)) {
    return CONCURRENCY_CONFLICT_MESSAGE;
  }
  const body = err instanceof HttpErrorResponse ? err.error : err;
  return isProblem(body) && body.detail ? body.detail : fallback;
}
