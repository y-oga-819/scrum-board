import { HttpClient } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { messageForError } from '../api/errors';
import { ProductService, ProductSummary } from '../products/product.service';
import {
  Board,
  BoardTask,
  SprintListItem,
  SprintService,
} from '../products/sprint.service';
import { TaskService, TaskStatus } from '../products/task.service';

/** `GET /api/me` の応答のうち、この画面が必要とする所属一覧だけ（B-10・D-21）。 */
interface MeResponse {
  products: ProductSummary[];
}

/** ボードの 3 カラム（提案書 図5 の状態語彙）。並び順＝画面での左→右。 */
const COLUMNS: { status: TaskStatus; label: string }[] = [
  { status: 'todo', label: '未着手' },
  { status: 'doing', label: '進行中' },
  { status: 'done', label: '完了' },
];

/**
 * スプリント画面のボード（画面B。B-23）。2画面構成の2枚目（D-21）。
 *
 * 選んだスプリントのタスクを **todo / doing / done** の 3 カラムに並べ、ドラッグで状態を
 * 移し、ブロック中フラグを立てられる。読み取りは**画面単位**（`GET /board` で 1 往復）で、
 * カラムへの振り分けは `status` からの**導出**（サーバーは並びだけ保証する — D-20）。
 *
 * 書き込みは汎用の `PATCH /tasks`（B-20）を通す。移動は `status`、ブロックは `isBlocked` を
 * 送り、`If-Match` には集約 GET の各タスクが持つ `_etag` を使う（楽観排他）。**版がずれて
 * 412 になったら黙って上書きせず、ボードを引き直して最新を見せ、再操作を促す**（D-24）。
 * 操作の成否に関わらず後で `GET /board` を引き直し、サーバーが確定した状態を正とする
 * （楽観的な差分計算で二重の真実を作らない）。
 *
 * productId はサーバー由来（`GET /api/me`）でハードコードしない。直接遷移・再読込で
 * :class:`ProductService` が空なら `/api/me` で温め直す（backlog と同じ入口 — D-21）。
 */
@Component({
  selector: 'app-board',
  imports: [RouterLink],
  templateUrl: './board.html',
  styleUrl: './board.scss',
})
export class BoardPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly sprintApi = inject(SprintService);
  private readonly taskApi = inject(TaskService);
  private readonly products = inject(ProductService);

  protected readonly columns = COLUMNS;

  /** 画面の状態。読み込み中／表示／所属なし／スプリントなし／エラーを出し分ける。 */
  protected readonly state = signal<
    'loading' | 'ready' | 'no-product' | 'no-sprint' | 'error'
  >('loading');
  /** 直近の操作でサーバーが返した問題の説明（あれば表示する）。 */
  protected readonly errorMessage = signal<string>('');

  /** スプリント一覧（番号順。セレクタ用）。 */
  protected readonly sprints = signal<SprintListItem[]>([]);
  /** 表示中のスプリント id。 */
  protected readonly selectedSprintId = signal<string | null>(null);
  /** 表示中スプリントのボード（スプリント情報＋タスク）。 */
  protected readonly board = signal<Board | null>(null);

  protected readonly selectedProduct = this.products.selected;
  protected readonly productId = computed(() => this.selectedProduct()?.productId ?? '');

  /** カラム（status）→ そのタスク列（サーバーの並びを保つ。ここでは再ソートしない）。 */
  protected readonly tasksByStatus = computed(() => {
    const grouped = new Map<TaskStatus, BoardTask[]>(
      COLUMNS.map((column) => [column.status, [] as BoardTask[]]),
    );
    for (const task of this.board()?.tasks ?? []) {
      grouped.get(task.status)?.push(task);
    }
    return grouped;
  });

  /** ドラッグ中のタスク id（ドロップ先カラムの計算に使う）。 */
  private draggingId: string | null = null;

  ngOnInit(): void {
    const selected = this.products.selected();
    if (selected) {
      this.loadSprints(selected.productId);
      return;
    }
    // 直接遷移・再読込で所属一覧が未取得なら、サーバー（正）から温め直す（D-21）。
    this.http.get<MeResponse>('/api/me').subscribe({
      next: (me) => {
        this.products.setProducts(me.products);
        const p = this.products.selected();
        if (p) {
          this.loadSprints(p.productId);
        } else {
          this.state.set('no-product');
        }
      },
      error: () => this.fail('所属プロダクトを読み込めませんでした。'),
    });
  }

  /**
   * スプリント一覧を読み、表示するスプリントを決める。選択が未設定／消失していれば
   * **実行中（active）を優先**し、無ければ番号が最大（一覧の末尾）に寄せる。
   */
  private loadSprints(productId: string): void {
    this.state.set('loading');
    this.sprintApi.list(productId).subscribe({
      next: (sprints) => {
        this.sprints.set(sprints);
        if (sprints.length === 0) {
          this.selectedSprintId.set(null);
          this.board.set(null);
          this.state.set('no-sprint');
          return;
        }
        const current = this.selectedSprintId();
        const stillThere = current !== null && sprints.some((s) => s.id === current);
        const target = stillThere ? current : this.defaultSprintId(sprints);
        this.selectedSprintId.set(target);
        this.loadBoard(productId, target);
      },
      error: () => this.fail('スプリントを読み込めませんでした。'),
    });
  }

  /** 既定で表示するスプリント（実行中を優先し、無ければ番号最大＝一覧の末尾）。 */
  private defaultSprintId(sprints: SprintListItem[]): string {
    const active = sprints.find((s) => s.status === 'active');
    return (active ?? sprints[sprints.length - 1]).id;
  }

  /** ボードを引き直す（移動・ブロック・スプリント切替のあとにも呼ぶ）。 */
  private loadBoard(productId: string, sprintId: string): void {
    this.state.set('loading');
    this.sprintApi.board(productId, sprintId).subscribe({
      next: (board) => {
        this.board.set(board);
        this.state.set('ready');
      },
      error: () => this.fail('ボードを読み込めませんでした。'),
    });
  }

  /** セレクタで表示スプリントを切り替える。 */
  protected selectSprint(event: Event): void {
    const sprintId = (event.target as HTMLSelectElement).value;
    this.selectedSprintId.set(sprintId);
    this.errorMessage.set('');
    this.loadBoard(this.productId(), sprintId);
  }

  // --- ドラッグでの状態移動（ネイティブ HTML5 DnD） ---------------------------

  protected onDragStart(task: BoardTask): void {
    this.draggingId = task.id;
  }

  protected onDragEnd(): void {
    this.draggingId = null;
  }

  /** カラムの上にドラッグしたらドロップを許可する（既定は禁止のため打ち消す）。 */
  protected onDragOver(event: DragEvent): void {
    event.preventDefault();
  }

  /**
   * ``target`` カラムにドロップして状態を移す。同じカラムへの移動は何もしない。
   *
   * `status` を送るだけで、``done`` への出入りに伴う `completedAt` の刻印はサーバーが
   * 行う（I-1・I-2 をフロントで再実装しない — B-20）。`If-Match` は対象タスクの `_etag`。
   * 版がずれて 412 になったらボードを引き直して最新を見せ、再操作を促す（D-24）。
   */
  protected onDrop(target: TaskStatus): void {
    const draggingId = this.draggingId;
    this.draggingId = null;
    if (draggingId === null) {
      return;
    }
    const task = this.board()?.tasks.find((t) => t.id === draggingId);
    if (!task || task.status === target) {
      return;
    }
    const productId = this.productId();
    this.errorMessage.set('');
    this.taskApi.update(productId, task.id, task._etag, { status: target }).subscribe({
      next: () => this.reloadBoard(),
      error: (err) => {
        this.reportProblem(err, 'タスクを移動できませんでした。');
        this.reloadBoard();
      },
    });
  }

  /**
   * ブロック中フラグを切り替える（`PATCH isBlocked`）。事実の可視化であり、警告ではない
   * （色は種別の区別のみ — D-13）。版がずれたら 412 → 引き直して再操作を促す（D-24）。
   */
  protected toggleBlocked(task: BoardTask): void {
    const productId = this.productId();
    this.errorMessage.set('');
    this.taskApi
      .update(productId, task.id, task._etag, { isBlocked: !task.isBlocked })
      .subscribe({
        next: () => this.reloadBoard(),
        error: (err) => {
          this.reportProblem(err, 'ブロック状態を変更できませんでした。');
          this.reloadBoard();
        },
      });
  }

  /** 現在の選択スプリントのボードを引き直す（サーバーの状態を正とする — D-24）。 */
  private reloadBoard(): void {
    const sprintId = this.selectedSprintId();
    if (sprintId !== null) {
      this.loadBoard(this.productId(), sprintId);
    }
  }

  private fail(message: string): void {
    this.errorMessage.set(message);
    this.state.set('error');
  }

  /**
   * HTTP エラーを表示メッセージに整形する（共通処理 — D-24）。412（版ずれ）は「最新に更新した・
   * 必要なら再操作」を示し、それ以外は problem+json の detail か既定文を出す。呼び出し側は
   * この直後にボードを引き直し、サーバーの状態を正とする（黙って上書きしない）。
   */
  private reportProblem(err: unknown, fallback: string): void {
    this.errorMessage.set(messageForError(err, fallback));
  }
}
