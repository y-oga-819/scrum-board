import { HttpClient, HttpErrorResponse, HttpResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { messageForError } from '../api/errors';
import {
  AgendaItem,
  DailyNote,
  DailyNoteService,
  DailyNoteUpdate,
} from '../products/daily-note.service';
import { ProductService, ProductSummary } from '../products/product.service';
import {
  Board,
  BoardTask,
  CarryOverTask,
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

/** 2本バーの1本ぶんの描画モデル（提案書 05章）。件数はサーバー由来、幅は描画のための導出。 */
interface BarView {
  /** バーの見出し（計画タスク / チームタスク）。 */
  label: string;
  /** 完了数（分子）。 */
  done: number;
  /** 総数（分母）。 */
  total: number;
  /** 種別（色の出し分けに使う。**警告ではなく種別の区別のみ** — P-1 / D-13）。 */
  kind: 'planned' | 'team';
  /** 共通目盛に対するこのバー（トラック）の幅（%）。2本の長さの対比が読めるようにする。 */
  trackPct: number;
  /** トラック内での完了ぶんの幅（% = done / total）。 */
  fillPct: number;
}

/** 進捗パネル全体の描画モデル（2本バー＋営業日マーカー）。 */
interface ProgressView {
  planned: BarView;
  team: BarView;
  elapsedBusinessDays: number | null;
  totalBusinessDays: number | null;
  /** 計画タスクのトラック内でのマーカー位置（% = 経過営業日 / 総営業日）。期間未設定なら null。 */
  markerPct: number | null;
}

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
  private readonly dailyApi = inject(DailyNoteService);
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
  /** 直近の操作の中立な事実（例: 「N 件を持ち越しました」）。警告ではない（P-1）。 */
  protected readonly notice = signal<string>('');

  /** 終了処理のプレビューを開いているか（持ち越しダイアログの表示制御。B-25）。 */
  protected readonly closingOpen = signal(false);
  /** 締めたときに持ち越される未完了タスク（プレビュー。完了は含まない — I-5）。 */
  protected readonly carryOver = signal<CarryOverTask[]>([]);
  /** 持ち越し先に選んでいるスプリント id。 */
  protected readonly nextSprintId = signal<string>('');

  // --- デイリーパネル（B-27。デイリースクラムをこの画面だけで完結させる — M6） -------
  /** デイリーパネルを開いているか。 */
  protected readonly dailyOpen = signal(false);
  /** 表示中のノートの日付（`YYYY-MM-DD`。Asia/Tokyo の「今日」。D-25/D-27）。 */
  protected readonly dailyDate = signal<string>('');
  /** 編集中のアジェンダ（`{id, text, done}`。id はクライアント採番）。 */
  protected readonly dailyAgenda = signal<AgendaItem[]>([]);
  /** 編集中の議事録（markdown 想定のプレーンテキスト）。 */
  protected readonly dailyMinutes = signal<string>('');
  /** 保存中はボタンを無効化して二重送信を防ぐ。 */
  protected readonly dailySaving = signal(false);
  /** 保存成功の一時的な通知。 */
  protected readonly dailySaved = signal(false);
  /** デイリーパネル内の問題の説明（本体のエラーとは分けて出す）。 */
  protected readonly dailyMessage = signal<string>('');
  /** サーバーが返した現在のノートの版（`If-Match` に載せる）。 */
  private dailyEtag = '';

  protected readonly selectedProduct = this.products.selected;
  protected readonly productId = computed(() => this.selectedProduct()?.productId ?? '');

  /** 表示中スプリントの一覧要素（`_etag` を持つ。状態遷移の `If-Match` に使う）。 */
  protected readonly currentSprint = computed<SprintListItem | null>(
    () => this.sprints().find((s) => s.id === this.selectedSprintId()) ?? null,
  );
  /** 「スプリントを開始」を出すか（計画中＝ `planned` のときだけ活性化できる）。 */
  protected readonly canActivate = computed(() => this.currentSprint()?.status === 'planned');
  /** 「スプリントを終了」を出すか（実行中＝ `active` のときだけ締められる — B-21 の状態機械）。 */
  protected readonly canClose = computed(() => this.currentSprint()?.status === 'active');
  /** 持ち越し先の候補（締める対象・終了済みを除く。無ければ先に次スプリントを作る必要がある）。 */
  protected readonly closeTargets = computed(() =>
    this.sprints().filter(
      (s) => s.id !== this.selectedSprintId() && s.status !== 'closed',
    ),
  );

  /**
   * 進捗の2本バー＋営業日マーカーの描画モデル（提案書 05章・B-24）。
   *
   * 件数（分子・分母）と営業日はサーバーが数えて返す（`GET /board` の `progress`）。ここでは
   * **描画のための導出だけ**を行う——2本のバーを**共通目盛**（分母の大きい方）で並べ、長さが
   * そのまま件数比になるようにする。マーカーは計画タスクのトラック内で経過営業日 ÷ 総営業日の
   * 位置に置く。期間が未設定（`totalBusinessDays === null`）ならマーカーは描かない（P-1）。
   */
  protected readonly progressView = computed<ProgressView | null>(() => {
    const progress = this.board()?.progress;
    if (!progress) {
      return null;
    }
    // 共通目盛は2本の分母の大きい方（0 のときも割れないよう 1 で下支え）。
    const scale = Math.max(progress.planned.total, progress.team.total, 1);
    const bar = (label: string, b: { done: number; total: number }, kind: 'planned' | 'team') => ({
      label,
      done: b.done,
      total: b.total,
      kind,
      trackPct: (b.total / scale) * 100,
      fillPct: b.total > 0 ? (b.done / b.total) * 100 : 0,
    });
    const total = progress.totalBusinessDays;
    const elapsed = progress.elapsedBusinessDays;
    const markerPct =
      total !== null && total > 0 && elapsed !== null
        ? Math.min(elapsed / total, 1) * 100
        : null;
    return {
      planned: bar('計画タスク', progress.planned, 'planned'),
      team: bar('チームタスク', progress.team, 'team'),
      elapsedBusinessDays: elapsed,
      totalBusinessDays: total,
      markerPct,
    };
  });

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

  /** セレクタで表示スプリントを切り替える。開いていた終了プレビューは閉じる。 */
  protected selectSprint(event: Event): void {
    const sprintId = (event.target as HTMLSelectElement).value;
    this.selectedSprintId.set(sprintId);
    this.errorMessage.set('');
    this.notice.set('');
    this.cancelClose();
    this.closeDaily();
    this.loadBoard(this.productId(), sprintId);
  }

  // --- スプリントのライフサイクル（開始・終了。B-25） ------------------------

  /**
   * スプリントを開始する（`planned → active`）。M5 の「1 周回る」を締めまで進めるための入口。
   *
   * `If-Match` には一覧要素の `_etag` を渡す（版がずれれば 412 → 引き直して再操作を促す — D-24）。
   * 成功後は一覧を読み直し、状態（active）と操作ボタン（終了）を最新化する。
   */
  protected activateSprint(): void {
    const sprint = this.currentSprint();
    if (sprint === null) {
      return;
    }
    this.errorMessage.set('');
    this.notice.set('');
    this.sprintApi
      .update(this.productId(), sprint.id, sprint._etag, { status: 'active' })
      .subscribe({
        next: () => this.loadSprints(this.productId()),
        error: (err) => {
          this.reportProblem(err, 'スプリントを開始できませんでした。');
          this.loadSprints(this.productId());
        },
      });
  }

  /**
   * 終了処理のプレビューを開く（`GET .../close/preview`。B-25・D-20）。
   *
   * 締めたときに次スプリントへ持ち越される**未完了タスク**を先に見せる（完了は含まない — I-5）。
   * 強制も警告もせず事実だけを見せてから確定に進む（P-1）。持ち越し先は候補の先頭を既定にする。
   */
  protected openClose(): void {
    const sprint = this.currentSprint();
    if (sprint === null) {
      return;
    }
    this.errorMessage.set('');
    this.notice.set('');
    this.nextSprintId.set(this.closeTargets()[0]?.id ?? '');
    this.sprintApi.closePreview(this.productId(), sprint.id).subscribe({
      next: (preview) => {
        this.carryOver.set(preview.tasks);
        this.closingOpen.set(true);
      },
      error: (err) => this.reportProblem(err, '持ち越しプレビューを取得できませんでした。'),
    });
  }

  /** 終了プレビューを閉じる（確定しない）。 */
  protected cancelClose(): void {
    this.closingOpen.set(false);
    this.carryOver.set([]);
  }

  /** 持ち越し先スプリントを選ぶ。 */
  protected selectNextSprint(event: Event): void {
    this.nextSprintId.set((event.target as HTMLSelectElement).value);
  }

  /**
   * スプリント終了を確定する（`POST .../close`。B-25）。
   *
   * 未完了タスクを `nextSprintId` へ移し、スプリントを `closed` にする（完了タスクは動かさない
   * — I-5。規則はサーバーに閉じる）。確定後は**持ち越し先を表示スプリントにして**、移った未完了
   * タスクをそのまま確認できるようにし、一覧を読み直してサーバーの状態を正とする。
   */
  protected confirmClose(): void {
    const sprint = this.currentSprint();
    const next = this.nextSprintId();
    if (sprint === null || next === '') {
      return;
    }
    this.errorMessage.set('');
    this.sprintApi.close(this.productId(), sprint.id, next).subscribe({
      next: (result) => {
        this.cancelClose();
        this.selectedSprintId.set(next);
        this.notice.set(`スプリントを終了しました（${result.carriedOver} 件を持ち越しました）。`);
        this.loadSprints(this.productId());
      },
      error: (err) => {
        this.reportProblem(err, 'スプリントを終了できませんでした。');
        this.loadSprints(this.productId());
      },
    });
  }

  // --- デイリーパネル（アジェンダ・議事録。B-27・D-27） ------------------------

  /**
   * デイリーパネルを開き、**その日（Asia/Tokyo の「今日」）**のノートを読み込む。
   *
   * `GET .../daily/{date}` は **get-or-create**——初回は空のノートをサーバーが作って返すので、
   * パネルは常に編集対象と版（`ETag`）を持てる（D-27）。既に開いていれば読み直さない（入力中の
   * 値を捨てない）。表示スプリントに紐づくため、スプリントを切り替えると閉じる（`selectSprint`）。
   */
  protected openDaily(): void {
    const sprintId = this.selectedSprintId();
    if (sprintId === null || this.dailyOpen()) {
      return;
    }
    const date = this.todayInTokyo();
    this.dailyDate.set(date);
    this.dailyMessage.set('');
    this.dailySaved.set(false);
    this.dailyApi.get(this.productId(), sprintId, date).subscribe({
      next: (res) => {
        this.applyDaily(res);
        this.dailyOpen.set(true);
      },
      error: () => this.dailyMessage.set('デイリーノートを読み込めませんでした。'),
    });
  }

  /** デイリーパネルを閉じる（保存しない変更は破棄される）。 */
  protected closeDaily(): void {
    this.dailyOpen.set(false);
    this.dailyMessage.set('');
    this.dailySaved.set(false);
  }

  /** 応答（本文＋`ETag` ヘッダ）を編集フォームへ流し込む（保存後・412 再取得でも呼ぶ）。 */
  private applyDaily(res: HttpResponse<DailyNote>): void {
    const note = res.body;
    if (note === null) {
      this.dailyMessage.set('デイリーノートを読み込めませんでした。');
      return;
    }
    this.dailyEtag = res.headers.get('ETag') ?? '';
    // 参照を切ってから持つ（編集が応答オブジェクトを書き換えないように）。
    this.dailyAgenda.set(note.agenda.map((item) => ({ ...item })));
    this.dailyMinutes.set(note.minutes);
  }

  /** アジェンダに空の項目を1つ足す（id はクライアントで採番する — 不透明な識別子）。 */
  protected addAgendaItem(): void {
    this.dailyAgenda.update((list) => [
      ...list,
      { id: crypto.randomUUID(), text: '', done: false },
    ]);
    this.dailyDirtied();
  }

  protected toggleAgendaItem(id: string, done: boolean): void {
    this.dailyAgenda.update((list) => list.map((it) => (it.id === id ? { ...it, done } : it)));
    this.dailyDirtied();
  }

  protected editAgendaText(id: string, text: string): void {
    this.dailyAgenda.update((list) => list.map((it) => (it.id === id ? { ...it, text } : it)));
    this.dailyDirtied();
  }

  protected removeAgendaItem(id: string): void {
    this.dailyAgenda.update((list) => list.filter((it) => it.id !== id));
    this.dailyDirtied();
  }

  protected onMinutesInput(value: string): void {
    this.dailyMinutes.set(value);
    this.dailyDirtied();
  }

  /**
   * デイリーノートを 1 リクエストで保存する（`PATCH`。版は `If-Match`）。
   *
   * 空文字のアジェンダ項目は保存時に落とす（入力途中の空行を残さない — B-18 と同じ）。他者の
   * 更新で版がずれたら（412）黙って上書きせず最新を読み直す（D-24）。成功したら新しい版を受け取る。
   */
  protected saveDaily(): void {
    const sprintId = this.selectedSprintId();
    if (sprintId === null || this.dailySaving()) {
      return;
    }
    const changes: DailyNoteUpdate = {
      agenda: this.dailyAgenda()
        .map((it) => ({ ...it, text: it.text.trim() }))
        .filter((it) => it.text !== ''),
      minutes: this.dailyMinutes(),
    };
    this.dailyMessage.set('');
    this.dailySaved.set(false);
    this.dailySaving.set(true);
    this.dailyApi
      .update(this.productId(), sprintId, this.dailyDate(), this.dailyEtag, changes)
      .subscribe({
        next: (res) => {
          this.dailySaving.set(false);
          this.applyDaily(res);
          this.dailySaved.set(true);
        },
        error: (err) => {
          this.dailySaving.set(false);
          if (err instanceof HttpErrorResponse && err.status === 412) {
            // 他者の更新で版がずれた。黙って上書きせず、最新を読み直す（P-1 / D-24）。
            this.dailyMessage.set(
              'ほかの人がこのノートを更新しました。最新の内容を読み込みました。',
            );
            this.reloadDaily();
            return;
          }
          this.dailyMessage.set(messageForError(err, 'デイリーノートを保存できませんでした。'));
        },
      });
  }

  /** 現在の日付のノートを引き直す（412 の後にサーバーの状態を正とする）。 */
  private reloadDaily(): void {
    const sprintId = this.selectedSprintId();
    if (sprintId === null) {
      return;
    }
    this.dailyApi.get(this.productId(), sprintId, this.dailyDate()).subscribe({
      next: (res) => this.applyDaily(res),
      error: () => this.dailyMessage.set('デイリーノートを読み込めませんでした。'),
    });
  }

  /** 入力があったら保存済み通知を消す（古い「保存しました」を残さない）。 */
  private dailyDirtied(): void {
    if (this.dailySaved()) {
      this.dailySaved.set(false);
    }
  }

  /**
   * **Asia/Tokyo の「今日」**を `YYYY-MM-DD` で返す（D-25。サーバーの営業日計算と暦を合わせる）。
   *
   * `en-CA` ロケールは `YYYY-MM-DD` 形で日付を出す。タイムゾーンを固定するのは、UTC 深夜〜朝
   * （日本時間の午前）で「今日」が 1 日ずれないようにするため（B-24 と同じ理由）。
   */
  private todayInTokyo(): string {
    return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo' }).format(new Date());
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
