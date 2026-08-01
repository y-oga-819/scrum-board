/**
 * タスクの読み書きを 1 か所に閉じ込める HTTP サービス（B-20・D-20）。
 *
 * 読み取りは**画面単位**（バックログの配下タスクは `GET /backlog` が PBI ごとに束ねて返す
 * ため、この画面には個別取得の導線を置かない）、書き込みは**リソース単位**
 * （`POST/PATCH/DELETE /tasks`）という D-20 の非対称を PBI と同じく持つ。型は OpenAPI 生成
 * （`schema.d.ts`）を正とし、手書きしない（Python と TS で 2 つの真実を作らない — D-20）。
 *
 * `productId` は呼び出し側が渡す（パーティションキーであり認可の単位。URL に明示する — D-20）。
 * 楽観排他は `If-Match` 必須で、値は集約 GET の各タスクが持つ `_etag`（このサービスは規則を
 * 判断せず、サーバーが返した版を運ぶだけ）。不変条件（I-1〜I-4）の判定もサーバーが持つため、
 * フロントは 422 の problem を読んで示すだけで再実装しない。
 */
import { HttpClient, HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import type { components } from '../api/schema';

/** バックログの PBI 配下に並ぶタスク（単一 Task に `_etag` を足したもの）。 */
export type BacklogTask = components['schemas']['BacklogTask'];
/** 単一リソースのタスク応答。 */
export type Task = components['schemas']['Task'];
/** タスク作成の入力（`taskType` が判別子）。 */
export type TaskCreate = components['schemas']['TaskCreate'];
/** タスクの部分更新の入力（タイトル・状態・ブロック等。ボード操作は B-23）。 */
export type TaskUpdate = components['schemas']['TaskUpdate'];
/** タスクの種別（`pbi` / `team`）。 */
export type TaskType = components['schemas']['TaskType'];
/** タスクの状態（`todo` / `doing` / `done`）。 */
export type TaskStatus = components['schemas']['TaskStatus'];

@Injectable({ providedIn: 'root' })
export class TaskService {
  private readonly http = inject(HttpClient);

  private base(productId: string): string {
    return `/api/products/${encodeURIComponent(productId)}/tasks`;
  }

  /**
   * タスクを 1 件作成する。状態は必ずサーバー側で `todo` から始まる。`taskType='pbi'` は
   * `pbiId` 必須・`taskType='team'` は親 PBI なし（整合はサーバーが判定し、不正なら 422）。
   */
  create(productId: string, body: TaskCreate): Observable<Task> {
    return this.http.post<Task>(this.base(productId), body);
  }

  /**
   * タスクを部分更新する（`PATCH`）。`etag` は対象タスクの `_etag`（`If-Match` 必須。欠落は
   * 428・不一致は 412）。`status` を `done` に動かすと `completedAt` はサーバーが刻む
   * （I-1・I-2 をフロントで再実装しない）。応答は更新後のタスクと新しい `ETag` ヘッダなので、
   * 続けて編集できるよう応答全体を返す。
   */
  update(
    productId: string,
    taskId: string,
    etag: string,
    changes: TaskUpdate,
  ): Observable<HttpResponse<Task>> {
    return this.http.patch<Task>(
      `${this.base(productId)}/${encodeURIComponent(taskId)}`,
      changes,
      { headers: { 'If-Match': etag }, observe: 'response' },
    );
  }

  /** タスクを論理削除する（`DELETE`）。`etag` は対象の `_etag`（`If-Match` 必須）。 */
  delete(productId: string, taskId: string, etag: string): Observable<void> {
    return this.http.delete<void>(`${this.base(productId)}/${encodeURIComponent(taskId)}`, {
      headers: { 'If-Match': etag },
    });
  }
}
