import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { isProblem } from '../api/problem';
import {
  BacklogPbi,
  PbiService,
  PbiStatus,
} from '../products/pbi.service';
import { ProductService, ProductSummary } from '../products/product.service';

/** `GET /api/me` の応答のうち、この画面が必要とする所属一覧だけ（B-10・D-21）。 */
interface MeResponse {
  products: ProductSummary[];
}

/** ステータス選択に並べる語彙。正当な遷移かの判定はサーバーが持つ（D-20・フロントで再実装しない）。 */
const STATUS_LABELS: { value: PbiStatus; label: string }[] = [
  { value: 'new', label: '未着手' },
  { value: 'ready', label: '準備完了' },
  { value: 'inProgress', label: '進行中' },
  { value: 'done', label: '完了' },
];

/**
 * プロダクトバックログ画面（画面A。B-17）。
 *
 * PBI を**優先順位順**に並べ、ドラッグで並び替え・ステータス変更・新規追加ができる。
 * 並びの正はサーバー（`GET /backlog` の `ORDER BY rank, id`）で、フロントは受け取った
 * 順序をそのまま描画し再ソートしない（D-20）。並び替え／ステータス変更／追加のあとは
 * **集約 GET を引き直す**（サーバーが確定した並び・版を正とし、楽観的な差分計算で二重の
 * 真実を作らない）。楽観排他は各要素の `_etag` を `If-Match` に載せて満たす。
 *
 * productId はサーバー由来（`GET /api/me` の `products`）で、ハードコードしない（D-21）。
 * 直接遷移・再読込で :class:`ProductService` が空なら、この画面が `/api/me` で温め直す。
 */
@Component({
  selector: 'app-backlog',
  imports: [RouterLink],
  templateUrl: './backlog.html',
  styleUrl: './backlog.scss',
})
export class BacklogPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly pbiApi = inject(PbiService);
  private readonly products = inject(ProductService);

  protected readonly statuses = STATUS_LABELS;

  /** バックログ（サーバーの並び順のまま。フロントで再ソートしない）。 */
  protected readonly pbis = signal<BacklogPbi[]>([]);
  /** 画面の状態。読み込み中／表示／所属なし／エラーを出し分ける。 */
  protected readonly state = signal<'loading' | 'ready' | 'no-product' | 'error'>('loading');
  /** 直近の操作でサーバーが返した問題の説明（あれば表示する）。 */
  protected readonly errorMessage = signal<string>('');

  protected readonly selectedProduct = this.products.selected;
  protected readonly productId = computed(() => this.selectedProduct()?.productId ?? '');

  /** 追加フォームの開閉。 */
  protected readonly showAddForm = signal(false);
  /** 入力中のタイトル（template-driven フォームの双方向バインド）。 */
  protected newTitle = '';

  /** ドラッグ中の PBI id（ドロップ先の計算に使う）。 */
  private draggingId: string | null = null;

  ngOnInit(): void {
    const selected = this.products.selected();
    if (selected) {
      this.load(selected.productId);
      return;
    }
    // 直接遷移・再読込で所属一覧が未取得なら、サーバー（正）から温め直す（D-21）。
    this.http.get<MeResponse>('/api/me').subscribe({
      next: (me) => {
        this.products.setProducts(me.products);
        const p = this.products.selected();
        if (p) {
          this.load(p.productId);
        } else {
          this.state.set('no-product');
        }
      },
      error: () => this.fail('所属プロダクトを読み込めませんでした。'),
    });
  }

  /** バックログを引き直す（並び替え・ステータス変更・追加のあとにも呼ぶ）。 */
  private load(productId: string): void {
    this.state.set('loading');
    this.pbiApi.getBacklog(productId).subscribe({
      next: (res) => {
        this.pbis.set(res.pbis);
        this.state.set('ready');
      },
      error: () => this.fail('バックログを読み込めませんでした。'),
    });
  }

  /** 追加フォームを開く（`PBI を追加`）。 */
  protected openAddForm(): void {
    this.errorMessage.set('');
    this.newTitle = '';
    this.showAddForm.set(true);
  }

  protected cancelAdd(): void {
    this.showAddForm.set(false);
  }

  /** タイトルだけの PBI を作る（詳細・完了条件の編集は B-18）。作成後は末尾に積まれる。 */
  protected submitAdd(): void {
    const title = this.newTitle.trim();
    const productId = this.productId();
    if (title === '' || productId === '') {
      return;
    }
    this.errorMessage.set('');
    this.pbiApi.create(productId, { title, description: '', acceptanceCriteria: [] }).subscribe({
      next: () => {
        this.showAddForm.set(false);
        this.load(productId);
      },
      error: (err) => this.reportProblem(err, '追加に失敗しました。'),
    });
  }

  /** ステータスを変更する。遷移の正当性はサーバーが判定し、不正なら 422 を表示する。 */
  protected changeStatus(pbi: BacklogPbi, event: Event): void {
    const target = (event.target as HTMLSelectElement).value as PbiStatus;
    if (target === pbi.status) {
      return;
    }
    const productId = this.productId();
    this.errorMessage.set('');
    this.pbiApi.updateStatus(productId, pbi.id, pbi._etag, target).subscribe({
      next: () => this.load(productId),
      // 失敗（422 の不正遷移・412 の版ずれ）はサーバー由来のメッセージで示し、再取得で戻す。
      error: (err) => {
        this.reportProblem(err, 'ステータスを変更できませんでした。');
        this.load(productId);
      },
    });
  }

  // --- ドラッグ並び替え（ネイティブ HTML5 DnD） -------------------------------

  protected onDragStart(pbi: BacklogPbi): void {
    this.draggingId = pbi.id;
  }

  protected onDragEnd(): void {
    this.draggingId = null;
  }

  /** 行の上にドラッグしたらドロップを許可する（既定は禁止のため打ち消す）。 */
  protected onDragOver(event: DragEvent): void {
    event.preventDefault();
  }

  /**
   * `target` の行にドロップして並び替える。
   *
   * 前後の要素 ID はサーバーに渡す語彙（D-20）。ドラッグ中の要素を一旦除いた並びの中で、
   * 「下へ動かす＝対象の後ろ」「上へ動かす＝対象の前」に挿入したときの直前・直後 ID を
   * 求める。ランクの生成はサーバーが担い、更新は移動した 1 件だけ（提案書 06章）。
   */
  protected onDrop(target: BacklogPbi): void {
    const draggingId = this.draggingId;
    this.draggingId = null;
    if (draggingId === null || draggingId === target.id) {
      return;
    }
    const list = this.pbis();
    const from = list.findIndex((p) => p.id === draggingId);
    const to = list.findIndex((p) => p.id === target.id);
    if (from === -1 || to === -1) {
      return;
    }
    const dragged = list[from];
    const without = list.filter((p) => p.id !== draggingId);
    const targetIndex = without.findIndex((p) => p.id === target.id);
    // 下へ動かすなら対象の直後、上へ動かすなら対象の直前へ挿入する。
    const insertAt = from < to ? targetIndex + 1 : targetIndex;
    const beforeId = insertAt > 0 ? without[insertAt - 1].id : null;
    const afterId = insertAt < without.length ? without[insertAt].id : null;

    const productId = this.productId();
    this.errorMessage.set('');
    this.pbiApi.reorder(productId, dragged.id, dragged._etag, { beforeId, afterId }).subscribe({
      next: () => this.load(productId),
      error: (err) => {
        this.reportProblem(err, '並び替えできませんでした。');
        this.load(productId);
      },
    });
  }

  private fail(message: string): void {
    this.errorMessage.set(message);
    this.state.set('error');
  }

  /** HTTP エラー本文が problem+json なら detail を、そうでなければ既定文を表示する。 */
  private reportProblem(err: unknown, fallback: string): void {
    const body = err instanceof HttpErrorResponse ? err.error : err;
    this.errorMessage.set(isProblem(body) && body.detail ? body.detail : fallback);
  }
}
