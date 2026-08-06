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
import { SprintListItem, SprintService } from '../products/sprint.service';
import { TaskService } from '../products/task.service';

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
  private readonly taskApi = inject(TaskService);
  private readonly sprintApi = inject(SprintService);
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

  /** タスク追加フォームを開いている PBI の id（無ければ null）。1 つずつ開く。 */
  protected readonly taskFormPbiId = signal<string | null>(null);
  /** 入力中のタスクタイトル。 */
  protected newTaskTitle = '';

  /** 分割フォームを開いている PBI の id（無ければ null）。1 つずつ開く。 */
  protected readonly splitFormPbiId = signal<string | null>(null);
  /** 入力中の子 PBI タイトル。 */
  protected newChildTitle = '';

  /** id → title の索引。分割元（`parentPbiId`）の名前を一覧上で辿るために引く。 */
  protected readonly titleById = computed(
    () => new Map(this.pbis().map((pbi) => [pbi.id, pbi.title])),
  );

  // --- プランニング（右ペイン。B-22） ---------------------------------------
  //
  // プランニングは「どの PBI を今スプリントで回すか」を決める。PBI 自身はスプリントへの参照
  // を持たず（D-08）、「今スプリントにいる」は配下タスクの sprintId から**導出**する。だから
  // チェックの状態は保持せず isInSprint() で毎回導出し、二重の真実を作らない。取り込み／外す
  // の規則（未完了だけ動かす・タスク0件なら「タスク分解」生成）はサーバーに閉じる（D-15/D-20）。

  /** プランニング右ペインの開閉。開いたときにだけスプリントを読む（既存の初期表示を変えない）。 */
  protected readonly planningMode = signal(false);
  /** スプリント一覧（番号順。セレクタ用。開いたときに読む）。 */
  protected readonly sprints = signal<SprintListItem[]>([]);
  /** 取り込み先に選んでいるスプリントの id（無ければ null）。 */
  protected readonly selectedSprintId = signal<string | null>(null);

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

  // --- 配下タスクの追加（B-20） ----------------------------------------------

  /** ある PBI のタスク追加フォームを開く（同時に開くのは 1 つ）。 */
  protected openTaskForm(pbi: BacklogPbi): void {
    this.errorMessage.set('');
    this.newTaskTitle = '';
    this.taskFormPbiId.set(pbi.id);
  }

  protected cancelTask(): void {
    this.taskFormPbiId.set(null);
  }

  /**
   * PBI 配下に pbi タスクを 1 件足す。`taskType='pbi'` と `pbiId` はサーバーの語彙どおり
   * 渡す（判別は taskType — I-4）。作成後は集約 GET を引き直し、サーバーの並び・版を正とする。
   */
  protected submitTask(pbi: BacklogPbi): void {
    const title = this.newTaskTitle.trim();
    const productId = this.productId();
    if (title === '' || productId === '') {
      return;
    }
    this.errorMessage.set('');
    this.taskApi.create(productId, { taskType: 'pbi', pbiId: pbi.id, title }).subscribe({
      next: () => {
        this.taskFormPbiId.set(null);
        this.load(productId);
      },
      error: (err) => this.reportProblem(err, 'タスクの追加に失敗しました。'),
    });
  }

  // --- 分割（B-19） ----------------------------------------------------------

  /** ある PBI の分割フォームを開く（同時に開くのは 1 つ）。 */
  protected openSplitForm(pbi: BacklogPbi): void {
    this.errorMessage.set('');
    this.newChildTitle = '';
    this.splitFormPbiId.set(pbi.id);
  }

  protected cancelSplit(): void {
    this.splitFormPbiId.set(null);
  }

  /**
   * 分割元 `pbi` から子 PBI を切り出す。子は `parentPbiId` に分割元を刻んだ通常の PBI で、
   * バックログ末尾に積まれる（位置ではなく参照で辿る — B-19）。作成後は集約 GET を引き直し、
   * サーバーの並び・版を正とする。
   */
  protected submitSplit(pbi: BacklogPbi): void {
    const title = this.newChildTitle.trim();
    const productId = this.productId();
    if (title === '' || productId === '') {
      return;
    }
    this.errorMessage.set('');
    this.pbiApi
      .split(productId, pbi.id, { title, description: '', acceptanceCriteria: [] })
      .subscribe({
        next: () => {
          this.splitFormPbiId.set(null);
          this.load(productId);
        },
        error: (err) => this.reportProblem(err, '分割に失敗しました。'),
      });
  }

  /** 分割元の表示名（一覧に無ければ空文字＝辿れないことを示す）。 */
  protected parentTitle(parentPbiId: string): string {
    return this.titleById().get(parentPbiId) ?? '';
  }

  // --- プランニング（右ペイン。B-22） ---------------------------------------

  /** プランニング右ペインを開閉する。開くときにスプリント一覧を（正から）読み直す。 */
  protected togglePlanning(): void {
    const next = !this.planningMode();
    this.planningMode.set(next);
    if (next) {
      this.loadSprints(this.productId());
    }
  }

  /** スプリント一覧を読み、選択が未設定／消失していれば先頭（番号順の最初）に寄せる。 */
  private loadSprints(productId: string): void {
    if (productId === '') {
      return;
    }
    this.sprintApi.list(productId).subscribe({
      next: (sprints) => {
        this.sprints.set(sprints);
        const current = this.selectedSprintId();
        if (current === null || !sprints.some((s) => s.id === current)) {
          this.selectedSprintId.set(sprints[0]?.id ?? null);
        }
      },
      error: () => this.errorMessage.set('スプリントを読み込めませんでした。'),
    });
  }

  /** セレクタで取り込み先スプリントを選ぶ。 */
  protected selectSprint(event: Event): void {
    this.selectedSprintId.set((event.target as HTMLSelectElement).value || null);
  }

  /** スプリントを1件作る（ゴール・期間は後から編集。番号と状態はサーバーが決める）。 */
  protected createSprint(): void {
    const productId = this.productId();
    if (productId === '') {
      return;
    }
    this.errorMessage.set('');
    this.sprintApi.create(productId, { goal: '' }).subscribe({
      next: (sprint) => {
        this.selectedSprintId.set(sprint.id);
        this.loadSprints(productId);
      },
      error: (err) => this.reportProblem(err, 'スプリントの作成に失敗しました。'),
    });
  }

  /**
   * PBI が選択中スプリントにいるか（**導出**。配下タスクに sprintId=選択中 が1つでもあるか）。
   * 状態を別に保持せず毎回導出することで、サーバーとフロントに2つの真実を作らない（D-08）。
   */
  protected isInSprint(pbi: BacklogPbi): boolean {
    const sid = this.selectedSprintId();
    return sid !== null && pbi.tasks.some((task) => task.sprintId === sid);
  }

  /**
   * チェックで PBI を取り込む／外す（サーバーの専用エンドポイント。規則はサーバーに閉じる）。
   * 取り込むと配下の未完了タスクに sprintId が付き、タスク0件なら「タスク分解」が生成される
   * （D-15）。外すと未完了タスクのみ戻る（完了タスクは動かさない — I-5）。操作後は集約 GET を
   * 引き直し、サーバーが確定した状態を正とする。
   */
  protected togglePbi(pbi: BacklogPbi, event: Event): void {
    const sid = this.selectedSprintId();
    const productId = this.productId();
    if (sid === null || productId === '') {
      return;
    }
    const checked = (event.target as HTMLInputElement).checked;
    this.errorMessage.set('');
    const op = checked
      ? this.sprintApi.includePbi(productId, sid, pbi.id)
      : this.sprintApi.excludePbi(productId, sid, pbi.id);
    op.subscribe({
      next: () => this.load(productId),
      error: (err) => {
        this.reportProblem(
          err,
          checked ? 'スプリントに入れられませんでした。' : 'スプリントから外せませんでした。',
        );
        this.load(productId);
      },
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
