/**
 * PBI の読み書きを 1 か所に閉じ込める HTTP サービス（B-17・D-20）。
 *
 * 読み取りは**画面単位**（`GET /backlog` で 1 往復・N+1 にしない）、書き込みは
 * **リソース単位**（`POST/PATCH /pbis` とドメイン操作 `POST .../rank`）という D-20 の
 * 非対称をそのまま持つ。型は OpenAPI 生成（`schema.d.ts`）を正とし、手書きしない
 * （Python と TS で 2 つの真実を作らない — D-20）。
 *
 * `productId` は呼び出し側が渡す（パーティションキーであり認可の単位。サーバー側で暗黙
 * 解決しないのと同じく、URL に明示する — D-20）。楽観排他は `If-Match` 必須で、値は集約
 * GET の各要素が持つ `_etag`（このサービスは規則を判断せず、サーバーが返した版を運ぶだけ）。
 */
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import type { components } from '../api/schema';

/** 集約 GET `/backlog` の応答（PBI 一覧。各要素は `_etag` を持つ）。 */
export type BacklogResponse = components['schemas']['BacklogResponse'];
/** バックログ 1 行分の PBI（単一 GET の Pbi に `_etag` を足したもの）。 */
export type BacklogPbi = components['schemas']['BacklogPbi'];
/** 単一リソースの PBI 応答。 */
export type Pbi = components['schemas']['Pbi'];
/** PBI 作成の入力。 */
export type PbiCreate = components['schemas']['PbiCreate'];
/** PBI の状態（`new` / `ready` / `inProgress` / `done`）。 */
export type PbiStatus = components['schemas']['PbiStatus'];
/** 並び替えの移動先（前後の要素 ID）。 */
export type RankMove = components['schemas']['RankMove'];

@Injectable({ providedIn: 'root' })
export class PbiService {
  private readonly http = inject(HttpClient);

  private base(productId: string): string {
    return `/api/products/${encodeURIComponent(productId)}/pbis`;
  }

  /**
   * バックログを**優先順位順**（サーバーの `ORDER BY rank, id`）で 1 往復取得する。
   * 並びの正はサーバー。受け取った順序をそのまま描画し、フロントで再ソートしない（D-20）。
   */
  getBacklog(productId: string): Observable<BacklogResponse> {
    return this.http.get<BacklogResponse>(
      `/api/products/${encodeURIComponent(productId)}/backlog`,
    );
  }

  /** PBI を 1 件作成する。状態は必ずサーバー側で `new` から始まる。 */
  create(productId: string, body: PbiCreate): Observable<Pbi> {
    return this.http.post<Pbi>(this.base(productId), body);
  }

  /**
   * PBI の状態を変更する（`PATCH`）。`etag` は対象要素の `_etag`（`If-Match` 必須）。
   * 正当な遷移かの判定はサーバーが持つ（不正なら 422・`violations`。フロントは再実装しない）。
   */
  updateStatus(
    productId: string,
    pbiId: string,
    etag: string,
    status: PbiStatus,
  ): Observable<Pbi> {
    return this.http.patch<Pbi>(
      `${this.base(productId)}/${encodeURIComponent(pbiId)}`,
      { status },
      { headers: { 'If-Match': etag } },
    );
  }

  /**
   * PBI を前後の要素の**間**へ並び替える（`POST .../rank`）。新しいランクはサーバーが
   * 生成し、更新は移動した 1 件だけ（D-20）。`etag` は移動対象の `_etag`（`If-Match` 必須）。
   */
  reorder(
    productId: string,
    pbiId: string,
    etag: string,
    move: RankMove,
  ): Observable<Pbi> {
    return this.http.post<Pbi>(
      `${this.base(productId)}/${encodeURIComponent(pbiId)}/rank`,
      move,
      { headers: { 'If-Match': etag } },
    );
  }
}
