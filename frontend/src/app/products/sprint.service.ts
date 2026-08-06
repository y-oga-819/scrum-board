/**
 * スプリントの読み書きとプランニング操作を 1 か所に閉じ込める HTTP サービス（B-21・B-22・D-20）。
 *
 * 読み取りは一覧（`GET /sprints`。セレクタ用の最小情報）、書き込みは**リソース単位**
 * （`POST /sprints`）と**ドメイン操作**（`POST/DELETE /sprints/{sid}/pbis/{pbiId}` の
 * プランニング取り込み／外す）という D-20 の非対称を PBI・タスクと同じく持つ。型は OpenAPI
 * 生成（`schema.d.ts`）を正とし、手書きしない（Python と TS で 2 つの真実を作らない — D-20）。
 *
 * `productId` は呼び出し側が渡す（パーティションキーであり認可の単位。URL に明示する — D-20）。
 * プランニングは複数タスクの `sprintId` を 1 規則で束ねて動かす**サーバー所有の操作**で、
 * 「配下の未完了タスクに sprintId を付ける／タスク0件なら『タスク分解』を生成する」（D-15）
 * という規則はサーバーに閉じる。フロントは取り込み／外すを呼ぶだけで、規則を再実装しない。
 */
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import type { components } from '../api/schema';

/** 単一リソースのスプリント応答。 */
export type Sprint = components['schemas']['Sprint'];
/** 一覧の1要素（単一 Sprint に `_etag` を足したもの）。 */
export type SprintListItem = components['schemas']['SprintListItem'];
/** スプリント作成の入力（ゴール・期間は任意）。 */
export type SprintCreate = components['schemas']['SprintCreate'];
/** スプリントの状態（`planned` / `active` / `closed`）。 */
export type SprintStatus = components['schemas']['SprintStatus'];

@Injectable({ providedIn: 'root' })
export class SprintService {
  private readonly http = inject(HttpClient);

  private base(productId: string): string {
    return `/api/products/${encodeURIComponent(productId)}/sprints`;
  }

  /** スプリントを**番号順**で一覧する（プランニングのセレクタ用）。各要素が `_etag` を持つ。 */
  list(productId: string): Observable<SprintListItem[]> {
    return this.http.get<SprintListItem[]>(this.base(productId));
  }

  /** スプリントを 1 件作成する。番号はサーバーが採番し、状態は必ず `planned` から始まる。 */
  create(productId: string, body: SprintCreate): Observable<Sprint> {
    return this.http.post<Sprint>(this.base(productId), body);
  }

  /**
   * PBI をスプリントに**取り込む**（`POST .../{sprintId}/pbis/{pbiId}`。B-22・D-15）。
   *
   * 配下の未完了タスクに `sprintId` が付き、タスク0件なら「タスク分解」が1件生成される
   * （規則はサーバーに閉じる — D-20）。複数タスクを束ねるドメイン操作のため `If-Match` は
   * 取らない（分割と同じく単一リソースの更新ではない）。応答は 204 No Content。
   */
  includePbi(productId: string, sprintId: string, pbiId: string): Observable<void> {
    return this.http.post<void>(this.planningUrl(productId, sprintId, pbiId), null);
  }

  /**
   * PBI をスプリントから**外す**（`DELETE .../{sprintId}/pbis/{pbiId}`。B-22）。
   *
   * このスプリントにいる未完了タスクのみ `sprintId=null` に戻る。**完了タスクは動かさない**
   * （I-5。規則はサーバーに閉じる）。応答は 204 No Content。
   */
  excludePbi(productId: string, sprintId: string, pbiId: string): Observable<void> {
    return this.http.delete<void>(this.planningUrl(productId, sprintId, pbiId));
  }

  private planningUrl(productId: string, sprintId: string, pbiId: string): string {
    return (
      `${this.base(productId)}/${encodeURIComponent(sprintId)}` +
      `/pbis/${encodeURIComponent(pbiId)}`
    );
  }
}
