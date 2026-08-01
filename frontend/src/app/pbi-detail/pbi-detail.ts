import { HttpClient, HttpErrorResponse, HttpResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { isProblem } from '../api/problem';
import { AcceptanceCriterion, Pbi, PbiService, PbiUpdate } from '../products/pbi.service';
import { ProductService, ProductSummary } from '../products/product.service';

/** `GET /api/me` の応答のうち、この画面が必要とする所属一覧だけ（B-10・D-21）。 */
interface MeResponse {
  products: ProductSummary[];
}

/**
 * PBI 詳細画面（B-18）。
 *
 * プロダクトバックログ（画面A）から 1 件の PBI に**ドリルダウン**し、概要・完了条件の
 * チェックリスト・見積りを編集する（提案書「リファインメント＝書く」は画面Aの作業。
 * 新しいモードではなく画面Aの掘り下げで、2画面原則は壊さない — D-21）。
 *
 * 版（`ETag`）はサーバーが正で、単一ドキュメント応答では**ヘッダ**で返る（集約 GET が
 * 各要素で `_etag` を返すのとは非対称 — D-20）。保存のたびに新しい版を受け取り、続けて
 * 編集できるよう保持する。他者の更新で版がずれたら（412）最新を読み直す（黙って上書き
 * しない）。バリデーションの正はサーバーにあり、フロントは 422 の problem を読んで示すだけ
 * （タイトル必須の再実装はしない — D-20）。見積りは**任意入力で、未設定でも警告を出さない**
 * （D-06）。
 *
 * productId はサーバー由来（`GET /api/me` の `products`）で、ハードコードしない（D-21）。
 * 直接遷移・再読込で :class:`ProductService` が空なら、この画面が `/api/me` で温め直す。
 */
@Component({
  selector: 'app-pbi-detail',
  imports: [RouterLink],
  templateUrl: './pbi-detail.html',
  styleUrl: './pbi-detail.scss',
})
export class PbiDetailPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly pbiApi = inject(PbiService);
  private readonly products = inject(ProductService);
  private readonly route = inject(ActivatedRoute);

  /** URL の PBI id（この画面は 1 件に固定される。ドリルダウンごとに新しいインスタンス）。 */
  private readonly pbiId = this.route.snapshot.paramMap.get('pbiId') ?? '';

  /** 画面の状態。読み込み中／表示／未存在／所属なし／エラーを出し分ける。 */
  protected readonly state = signal<'loading' | 'ready' | 'not-found' | 'no-product' | 'error'>(
    'loading',
  );
  /** 直近の操作でサーバーが返した問題の説明（あれば表示する）。 */
  protected readonly errorMessage = signal<string>('');
  /** 保存成功の一時的な通知。 */
  protected readonly savedNotice = signal<boolean>(false);
  /** 保存中はボタンを無効化して二重送信を防ぐ。 */
  protected readonly saving = signal<boolean>(false);

  /** 読み込んだ PBI（見出し・メタ情報の表示用。編集値は下の signal が持つ）。 */
  protected readonly pbi = signal<Pbi | null>(null);
  /** サーバーが返した現在の版（`If-Match` に載せる）。 */
  private etag = '';

  // --- 編集中の値（サーバーから初期化し、入力で更新する） --------------------
  protected readonly title = signal<string>('');
  protected readonly description = signal<string>('');
  /** 見積りは文字列で保持する（空欄＝未設定。数値化は保存時。D-06）。 */
  protected readonly estimateInput = signal<string>('');
  protected readonly criteria = signal<AcceptanceCriterion[]>([]);

  protected readonly selectedProduct = this.products.selected;
  protected readonly productId = computed(() => this.selectedProduct()?.productId ?? '');

  ngOnInit(): void {
    if (this.pbiId === '') {
      this.state.set('not-found');
      return;
    }
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

  /** PBI を読み込み、編集値と版を初期化する（保存後の 412 再取得でも呼ぶ）。 */
  private load(productId: string): void {
    this.state.set('loading');
    this.pbiApi.getOne(productId, this.pbiId).subscribe({
      next: (res) => this.applyLoaded(res),
      error: (err) => {
        if (err instanceof HttpErrorResponse && err.status === 404) {
          this.state.set('not-found');
          return;
        }
        this.fail('PBI を読み込めませんでした。');
      },
    });
  }

  /** 応答（本文＋`ETag` ヘッダ）を編集フォームへ流し込む。 */
  private applyLoaded(res: HttpResponse<Pbi>): void {
    const doc = res.body;
    if (doc === null) {
      this.fail('PBI を読み込めませんでした。');
      return;
    }
    this.etag = res.headers.get('ETag') ?? '';
    this.pbi.set(doc);
    this.title.set(doc.title);
    this.description.set(doc.description);
    this.estimateInput.set(doc.estimate === null ? '' : String(doc.estimate));
    // 参照を切ってから持つ（編集が応答オブジェクトを書き換えないように）。
    this.criteria.set(doc.acceptanceCriteria.map((c) => ({ ...c })));
    this.state.set('ready');
  }

  // --- 概要・見積り ----------------------------------------------------------

  protected onTitleInput(value: string): void {
    this.title.set(value);
    this.dirtied();
  }

  protected onDescriptionInput(value: string): void {
    this.description.set(value);
    this.dirtied();
  }

  protected onEstimateInput(value: string): void {
    this.estimateInput.set(value);
    this.dirtied();
  }

  // --- 完了条件チェックリスト -------------------------------------------------

  /** チェックリストに空の項目を1つ足す（id はクライアントで採番する — 不透明な識別子）。 */
  protected addCriterion(): void {
    this.criteria.update((list) => [
      ...list,
      { id: crypto.randomUUID(), text: '', checked: false },
    ]);
    this.dirtied();
  }

  protected toggleCriterion(id: string, checked: boolean): void {
    this.criteria.update((list) => list.map((c) => (c.id === id ? { ...c, checked } : c)));
    this.dirtied();
  }

  protected editCriterionText(id: string, text: string): void {
    this.criteria.update((list) => list.map((c) => (c.id === id ? { ...c, text } : c)));
    this.dirtied();
  }

  protected removeCriterion(id: string): void {
    this.criteria.update((list) => list.filter((c) => c.id !== id));
    this.dirtied();
  }

  // --- 保存 ------------------------------------------------------------------

  /**
   * 編集内容を 1 リクエストで保存する（`PATCH`。版は `If-Match`）。
   *
   * タイトルは必須（サーバーが `min_length=1` を保証する）ため、空欄のままでは送らず
   * その場で示す。見積りは空欄なら `null`（未設定でも警告しない — D-06）。空文字の完了条件は
   * 保存時に落とす（入力途中の空行を残さない）。成功したら新しい版を受け取って保持する。
   */
  protected save(): void {
    if (this.state() !== 'ready' || this.saving()) {
      return;
    }
    const title = this.title().trim();
    if (title === '') {
      this.errorMessage.set('タイトルは必須です。');
      return;
    }
    const changes: PbiUpdate = {
      title,
      description: this.description(),
      estimate: this.parseEstimate(),
      acceptanceCriteria: this.criteria()
        .map((c) => ({ ...c, text: c.text.trim() }))
        .filter((c) => c.text !== ''),
    };

    this.errorMessage.set('');
    this.savedNotice.set(false);
    this.saving.set(true);
    this.pbiApi.update(this.productId(), this.pbiId, this.etag, changes).subscribe({
      next: (res) => {
        this.saving.set(false);
        this.applyLoaded(res);
        this.savedNotice.set(true);
      },
      error: (err) => {
        this.saving.set(false);
        if (err instanceof HttpErrorResponse && err.status === 412) {
          // 他者の更新で版がずれた。黙って上書きせず、最新を読み直す（P-1）。
          this.errorMessage.set('ほかの人がこの PBI を更新しました。最新の内容を読み込みました。');
          this.load(this.productId());
          return;
        }
        this.reportProblem(err, '保存できませんでした。');
      },
    });
  }

  /** 見積り入力を数値へ。空欄は未設定（`null`）。数値でなければ未設定として扱う（D-06）。 */
  private parseEstimate(): number | null {
    const raw = this.estimateInput().trim();
    if (raw === '') {
      return null;
    }
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }

  /** 入力があったら保存済み通知を消す（古い「保存しました」を残さない）。 */
  private dirtied(): void {
    if (this.savedNotice()) {
      this.savedNotice.set(false);
    }
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
