/**
 * デイリーノートの読み書きを 1 か所に閉じ込める HTTP サービス（B-27・D-27）。
 *
 * デイリーノートは**その日の**アジェンダと議事録を持つ 1 ドキュメント。id は (スプリント, 日付)
 * から決定的で、同じ日には構造的に 1 件しかない（1日1件 — 提案書04章・D-27）。読み取りは
 * **get-or-create**（`GET .../daily/{date}` は無ければ空のノートを作って返す）で、パネルが常に
 * 編集対象と版（`ETag`）を持てるようにする。書き込みは単一リソースの汎用 `PATCH`＋`If-Match`
 * （B-18 の PBI 詳細と同型）に乗せ、専用経路を新設しない（D-20）。
 *
 * 型は OpenAPI 生成（`schema.d.ts`）を正とし、手書きしない（Python と TS で 2 つの真実を作らない
 * — D-20）。単一ドキュメント応答の版は**本文でなく `ETag` ヘッダ**で返るため、更新に載せる
 * `If-Match` を取り出せるよう本文だけでなく**応答全体**（`HttpResponse`）を観測して返す。
 */
import { HttpClient, HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import type { components } from '../api/schema';

/** デイリーノートの応答表現（アジェンダ＋議事録）。 */
export type DailyNote = components['schemas']['DailyNote'];
/** 朝会アジェンダの1項目（`{id, text, done}`。id はクライアント採番）。 */
export type AgendaItem = components['schemas']['AgendaItem'];
/** ノート更新の入力（部分更新。アジェンダ・議事録）。 */
export type DailyNoteUpdate = components['schemas']['DailyNoteUpdate'];

@Injectable({ providedIn: 'root' })
export class DailyNoteService {
  private readonly http = inject(HttpClient);

  private url(productId: string, sprintId: string, date: string): string {
    return (
      `/api/products/${encodeURIComponent(productId)}` +
      `/sprints/${encodeURIComponent(sprintId)}/daily/${encodeURIComponent(date)}`
    );
  }

  /**
   * その日のノートを取得する（`GET .../daily/{date}`。B-27）。
   *
   * **get-or-create**——無ければサーバーが空のノートを1件作って返す（冪等。D-27）。版は
   * `ETag` ヘッダで返るため、以降の更新に載せる `If-Match` を取り出せるよう**応答全体**を返す。
   */
  get(productId: string, sprintId: string, date: string): Observable<HttpResponse<DailyNote>> {
    return this.http.get<DailyNote>(this.url(productId, sprintId, date), {
      observe: 'response',
    });
  }

  /**
   * アジェンダ・議事録を部分更新する（`PATCH .../daily/{date}`。B-27）。
   *
   * `etag` は対象の版（`If-Match` 必須。欠落は 428・不一致は 412）。`changes` に載せた
   * フィールドだけが反映される。応答は更新後のノートと**新しい `ETag` ヘッダ**なので、`get` と
   * 同じく応答全体を返し、呼び出し側が続けて編集できるよう版を運ぶ。
   */
  update(
    productId: string,
    sprintId: string,
    date: string,
    etag: string,
    changes: DailyNoteUpdate,
  ): Observable<HttpResponse<DailyNote>> {
    return this.http.patch<DailyNote>(this.url(productId, sprintId, date), changes, {
      headers: { 'If-Match': etag },
      observe: 'response',
    });
  }
}
