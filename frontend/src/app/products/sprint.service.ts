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
/** スプリント更新の入力（部分更新。状態遷移・期間・ゴール）。 */
export type SprintUpdate = components['schemas']['SprintUpdate'];
/** スプリントの状態（`planned` / `active` / `closed`）。 */
export type SprintStatus = components['schemas']['SprintStatus'];
/** スプリント画面のボード集約（スプリント情報＋タスク。B-23）。 */
export type Board = components['schemas']['BoardResponse'];
/** ボードに並ぶタスク（単一 Task に `_etag` を足したもの）。 */
export type BoardTask = components['schemas']['BoardTask'];
/** スプリント終了で持ち越されるタスクのプレビュー行（B-25）。 */
export type CarryOverTask = components['schemas']['CarryOverTask'];
/** スプリント終了の持ち越しプレビュー（未完了タスク一覧。B-25）。 */
export type ClosePreview = components['schemas']['ClosePreview'];
/** スプリント終了の結果（締めたスプリント＋持ち越した件数。B-25）。 */
export type CloseResult = components['schemas']['CloseResult'];

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
   * スプリントを部分更新する（`PATCH .../{sprintId}`。B-21）。
   *
   * 状態遷移（`planned → active → closed`）・期間・ゴールを動かす。ボードでは
   * 「スプリントを開始」（`status='active'`）に使う。`If-Match` には一覧要素の `_etag` を
   * 渡す（版がずれれば 412 → 画面を引き直して再操作を促す — D-24）。
   */
  update(
    productId: string,
    sprintId: string,
    etag: string,
    body: SprintUpdate,
  ): Observable<Sprint> {
    return this.http.patch<Sprint>(
      `${this.base(productId)}/${encodeURIComponent(sprintId)}`,
      body,
      { headers: { 'If-Match': etag } },
    );
  }

  /**
   * スプリント画面のボードを**1 往復**で読む（`GET .../{sprintId}/board`。B-23・D-20）。
   *
   * スプリント情報とそのスプリントのタスク（各タスクは `_etag` を本文に持つ）を返す。
   * `todo` / `doing` / `done` の 3 カラムへの振り分けは `status` からの導出のため、画面側で
   * 束ねる（サーバーは並びだけ保証する — D-20）。ボード操作（移動・ブロック）は `TaskService`
   * の `PATCH /tasks` を通し、その `If-Match` にここで得た各タスクの `_etag` を使う。
   */
  board(productId: string, sprintId: string): Observable<Board> {
    return this.http.get<Board>(
      `${this.base(productId)}/${encodeURIComponent(sprintId)}/board`,
    );
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

  /**
   * スプリント終了で**持ち越される一覧**をプレビューする（`GET .../{sid}/close/preview`。B-25）。
   *
   * 締めたときに次スプリントへ移る未完了タスクを返す（読み取りのみ・状態は変えない）。
   * 完了タスクは含まれない（I-5）。「スプリントを終了」を押した時点でこれを見せ、確定は別手
   * （{@link close}）に分ける（D-20。強制も警告もせず事実だけ見せる — P-1）。
   */
  closePreview(productId: string, sprintId: string): Observable<ClosePreview> {
    return this.http.get<ClosePreview>(this.closeUrl(productId, sprintId) + '/preview');
  }

  /**
   * スプリントを終了する（`POST .../{sid}/close`。B-25）。
   *
   * 未完了タスクを `nextSprintId` へ移し、スプリントを `closed` にする。**完了タスクは
   * 動かさない**（I-5。規則はサーバーに閉じる）。複数タスクを束ねるサーバー所有の操作のため
   * `If-Match` は取らない。応答は締めたスプリントと持ち越した件数。
   */
  close(productId: string, sprintId: string, nextSprintId: string): Observable<CloseResult> {
    return this.http.post<CloseResult>(this.closeUrl(productId, sprintId), { nextSprintId });
  }

  private closeUrl(productId: string, sprintId: string): string {
    return `${this.base(productId)}/${encodeURIComponent(sprintId)}/close`;
  }
}
