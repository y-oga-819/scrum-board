import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { BoardPage } from './board';
import { CONCURRENCY_CONFLICT_MESSAGE } from '../api/errors';
import { ProductService, ProductSummary } from '../products/product.service';
import { Board, BoardTask, SprintListItem } from '../products/sprint.service';
import { TaskStatus } from '../products/task.service';

const SANDBOX: ProductSummary = { productId: 'prd_sandbox', name: 'サンドボックス', role: 'member' };
const BASE = `/api/products/${SANDBOX.productId}`;

function sprint(id: string, number: number, status: 'planned' | 'active' | 'closed'): SprintListItem {
  return {
    id,
    type: 'sprint',
    productId: SANDBOX.productId,
    isDeleted: false,
    createdAt: '2026-08-01T00:00:00Z',
    createdBy: 'oid',
    updatedAt: '2026-08-01T00:00:00Z',
    updatedBy: 'oid',
    number,
    goal: '',
    startDate: null,
    endDate: null,
    status,
    _etag: `"etag-${id}"`,
  };
}

function boardTask(id: string, title: string, status: TaskStatus, isBlocked = false): BoardTask {
  return {
    id,
    type: 'task',
    productId: SANDBOX.productId,
    isDeleted: false,
    createdAt: '2026-08-01T00:00:00Z',
    createdBy: 'oid',
    updatedAt: '2026-08-01T00:00:00Z',
    updatedBy: 'oid',
    taskType: 'team',
    pbiId: null,
    sprintId: 'spr_1',
    status,
    completedAt: null,
    title,
    todo: '',
    memo: '',
    assigneeId: null,
    rank: null,
    isBlocked,
    blockedReason: '',
    _etag: `"etag-${id}"`,
  };
}

describe('BoardPage', () => {
  let httpMock: HttpTestingController;
  let products: ProductService;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      imports: [BoardPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    httpMock = TestBed.inject(HttpTestingController);
    products = TestBed.inject(ProductService);
    products.setProducts([SANDBOX]);
  });

  afterEach(() => {
    httpMock.verify();
    sessionStorage.clear();
  });

  /** 立ち上げ → GET /sprints → GET board を順に応答して ready にする。 */
  function render(sprints: SprintListItem[], board: Board): ComponentFixture<BoardPage> {
    const fixture = TestBed.createComponent(BoardPage);
    fixture.detectChanges(); // ngOnInit → list()
    httpMock.expectOne(`${BASE}/sprints`).flush(sprints);
    fixture.detectChanges();
    httpMock.expectOne(`${BASE}/sprints/${board.sprint.id}/board`).flush(board);
    fixture.detectChanges();
    return fixture;
  }

  function column(fixture: ComponentFixture<BoardPage>, label: string): HTMLElement {
    return (fixture.nativeElement as HTMLElement).querySelector(
      `.column-drop[aria-label="${label}"]`,
    )!;
  }

  /** ラベル一致のボタンを1つ拾う（B-25 のライフサイクル操作用）。 */
  function button(fixture: ComponentFixture<BoardPage>, label: string): HTMLButtonElement | null {
    return (
      (Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('button')).find(
        (b) => b.textContent?.trim() === label,
      ) as HTMLButtonElement) ?? null
    );
  }

  function progress(overrides?: Partial<Board['progress']>): Board['progress'] {
    return {
      planned: { done: 0, total: 0 },
      team: { done: 0, total: 0 },
      elapsedBusinessDays: null,
      totalBusinessDays: null,
      ...overrides,
    };
  }

  function board(sprintId: string, tasks: BoardTask[], prog = progress()): Board {
    return { sprint: { ...sprint(sprintId, 1, 'active') }, tasks, progress: prog };
  }

  it('groups tasks into the todo/doing/done columns by status (derived)', () => {
    const fixture = render(
      [sprint('spr_1', 1, 'active')],
      board('spr_1', [
        boardTask('t1', 'やること', 'todo'),
        boardTask('t2', 'やってる', 'doing'),
      ]),
    );
    expect(column(fixture, '未着手').textContent).toContain('やること');
    expect(column(fixture, '進行中').textContent).toContain('やってる');
    expect(column(fixture, '未着手').textContent).not.toContain('やってる');
  });

  it('defaults to the active sprint when selection is unset', () => {
    // 一覧は番号順（planned が先）。既定は実行中（active）を優先して選ぶ。
    const fixture = TestBed.createComponent(BoardPage);
    fixture.detectChanges();
    httpMock.expectOne(`${BASE}/sprints`).flush([sprint('spr_1', 1, 'planned'), sprint('spr_2', 2, 'active')]);
    fixture.detectChanges();
    httpMock.expectOne(`${BASE}/sprints/spr_2/board`).flush(board('spr_2', []));
    fixture.detectChanges();
    expect(fixture.componentInstance['selectedSprintId']()).toBe('spr_2');
  });

  it('shows the no-sprint hint when there are no sprints', () => {
    const fixture = TestBed.createComponent(BoardPage);
    fixture.detectChanges();
    httpMock.expectOne(`${BASE}/sprints`).flush([]);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('.hint')?.textContent).toContain(
      'スプリントがありません',
    );
  });

  it('moves a task to the dropped column with If-Match, then reloads the board', () => {
    const fixture = render([sprint('spr_1', 1, 'active')], board('spr_1', [boardTask('t1', 'カード', 'todo')]));
    const host = fixture.nativeElement as HTMLElement;

    // カードをつまんで（dragstart）、doing カラムへドロップ（drop）。
    host.querySelector<HTMLElement>('.task-card')!.dispatchEvent(new Event('dragstart'));
    column(fixture, '進行中').dispatchEvent(new Event('drop'));

    const patch = httpMock.expectOne(`${BASE}/tasks/t1`);
    expect(patch.request.method).toBe('PATCH');
    expect(patch.request.body).toEqual({ status: 'doing' });
    expect(patch.request.headers.get('If-Match')).toBe('"etag-t1"');
    patch.flush(boardTask('t1', 'カード', 'doing'));

    // 移動後はボードを引き直し、サーバーの状態を正とする（D-24）。
    httpMock.expectOne(`${BASE}/sprints/spr_1/board`).flush(board('spr_1', [boardTask('t1', 'カード', 'doing')]));
    fixture.detectChanges();
    expect(column(fixture, '進行中').textContent).toContain('カード');
  });

  it('does nothing when a task is dropped on its current column', () => {
    const fixture = render([sprint('spr_1', 1, 'active')], board('spr_1', [boardTask('t1', 'カード', 'todo')]));
    const host = fixture.nativeElement as HTMLElement;

    host.querySelector<HTMLElement>('.task-card')!.dispatchEvent(new Event('dragstart'));
    column(fixture, '未着手').dispatchEvent(new Event('drop')); // 同じカラム

    httpMock.expectNone(`${BASE}/tasks/t1`); // PATCH は飛ばない
  });

  it('on 412 shows the concurrency message and reloads (D-24)', () => {
    const fixture = render([sprint('spr_1', 1, 'active')], board('spr_1', [boardTask('t1', 'カード', 'todo')]));
    const host = fixture.nativeElement as HTMLElement;

    host.querySelector<HTMLElement>('.task-card')!.dispatchEvent(new Event('dragstart'));
    column(fixture, '完了').dispatchEvent(new Event('drop'));

    httpMock.expectOne(`${BASE}/tasks/t1`).flush(
      { type: 't', title: 'conflict', status: 412 },
      { status: 412, statusText: 'Precondition Failed' },
    );
    // 黙って上書きせず、最新を引き直す（D-24）。
    httpMock.expectOne(`${BASE}/sprints/spr_1/board`).flush(board('spr_1', [boardTask('t1', 'カード', 'todo')]));
    fixture.detectChanges();

    expect((host.querySelector('.error') as HTMLElement)?.textContent).toContain(
      CONCURRENCY_CONFLICT_MESSAGE,
    );
  });

  // --- 進捗の2本バー（提案書 05章・B-24） ---------------------------------------

  it('renders the two progress bars with server-provided counts', () => {
    const fixture = render(
      [sprint('spr_1', 1, 'active')],
      board('spr_1', [], progress({ planned: { done: 12, total: 22 }, team: { done: 3, total: 5 } })),
    );
    const host = fixture.nativeElement as HTMLElement;
    const counts = Array.from(host.querySelectorAll('.progress .bar-count')).map(
      (el) => el.textContent?.trim(),
    );
    expect(counts).toEqual(['完了 12 / 22', '完了 3 / 5']);
  });

  it('scales both bars on a common unit so lengths are comparable', () => {
    // 共通目盛は分母の大きい方（22）。計画の outline は 100%、チームは 5/22 の幅になる。
    const fixture = render(
      [sprint('spr_1', 1, 'active')],
      board('spr_1', [], progress({ planned: { done: 12, total: 22 }, team: { done: 3, total: 5 } })),
    );
    const host = fixture.nativeElement as HTMLElement;
    const outlines = host.querySelectorAll<HTMLElement>('.progress .bar-outline');
    expect(outlines[0].style.width).toBe('100%');
    expect(parseFloat(outlines[1].style.width)).toBeCloseTo((5 / 22) * 100, 3);
    // 計画バーの完了ぶんは outline 内で done/total。
    const plannedFill = host.querySelector<HTMLElement>('.bar-fill.planned')!;
    expect(parseFloat(plannedFill.style.width)).toBeCloseTo((12 / 22) * 100, 3);
  });

  it('places the business-day marker at elapsed / total on the planned bar', () => {
    const fixture = render(
      [sprint('spr_1', 1, 'active')],
      board('spr_1', [], progress({ elapsedBusinessDays: 8, totalBusinessDays: 10 })),
    );
    const host = fixture.nativeElement as HTMLElement;
    const marker = host.querySelector<HTMLElement>('.bar-marker')!;
    expect(marker).not.toBeNull();
    expect(parseFloat(marker.style.left)).toBeCloseTo(80, 3); // 8/10
    expect(host.querySelector('.bar-note')?.textContent).toContain('8 / 10 営業日が経過');
  });

  it('hides the marker and notes an unset period when the sprint has no dates', () => {
    const fixture = render([sprint('spr_1', 1, 'active')], board('spr_1', []));
    const host = fixture.nativeElement as HTMLElement;
    expect(host.querySelector('.bar-marker')).toBeNull();
    expect(host.querySelector('.bar-note')?.textContent).toContain('期間が未設定');
  });

  it('toggles the blocked flag with If-Match, then reloads', () => {
    const fixture = render([sprint('spr_1', 1, 'active')], board('spr_1', [boardTask('t1', 'カード', 'todo')]));
    const host = fixture.nativeElement as HTMLElement;

    host.querySelector<HTMLButtonElement>('.block-toggle')!.click();

    const patch = httpMock.expectOne(`${BASE}/tasks/t1`);
    expect(patch.request.method).toBe('PATCH');
    expect(patch.request.body).toEqual({ isBlocked: true });
    patch.flush(boardTask('t1', 'カード', 'todo', true));

    httpMock.expectOne(`${BASE}/sprints/spr_1/board`).flush(board('spr_1', [boardTask('t1', 'カード', 'todo', true)]));
    fixture.detectChanges();
    expect(host.querySelector('.blocked-badge')?.textContent).toContain('ブロック中');
  });

  // --- スプリントのライフサイクル（開始・終了。B-25） ---------------------------

  it('activates a planned sprint with If-Match, then reloads sprints', () => {
    // 一覧が planned のみなら「スプリントを開始」を出す（active は「終了」を出す）。
    const fixture = render([sprint('spr_1', 1, 'planned')], board('spr_1', []));
    expect(button(fixture, 'スプリントを終了')).toBeNull();
    const start = button(fixture, 'スプリントを開始');
    expect(start).not.toBeNull();

    start!.click();
    const patch = httpMock.expectOne(`${BASE}/sprints/spr_1`);
    expect(patch.request.method).toBe('PATCH');
    expect(patch.request.body).toEqual({ status: 'active' });
    expect(patch.request.headers.get('If-Match')).toBe('"etag-spr_1"');
    patch.flush(sprint('spr_1', 1, 'active'));

    // 開始後は一覧を読み直して状態と操作ボタンを最新化する。
    httpMock.expectOne(`${BASE}/sprints`).flush([sprint('spr_1', 1, 'active')]);
    fixture.detectChanges();
    httpMock.expectOne(`${BASE}/sprints/spr_1/board`).flush(board('spr_1', []));
    fixture.detectChanges();
    expect(button(fixture, 'スプリントを終了')).not.toBeNull();
  });

  it('opens the carry-over preview listing the incomplete tasks the server returns', () => {
    const fixture = render(
      [sprint('spr_1', 1, 'active'), sprint('spr_2', 2, 'planned')],
      board('spr_1', []),
    );
    button(fixture, 'スプリントを終了')!.click();

    const preview = httpMock.expectOne(`${BASE}/sprints/spr_1/close/preview`);
    expect(preview.request.method).toBe('GET');
    // 完了タスクは含まれない（サーバーが未完了だけを返す — I-5）。
    preview.flush({ tasks: [{ id: 't1', title: '未着手のカード', taskType: 'team', status: 'todo' }] });
    fixture.detectChanges();

    const dialog = (fixture.nativeElement as HTMLElement).querySelector('.close-dialog');
    expect(dialog).not.toBeNull();
    expect(dialog!.textContent).toContain('未着手のカード');
    // 持ち越し先の候補は自分以外・終了済み以外（spr_2 のみ）。
    const options = dialog!.querySelectorAll('.next-select option');
    expect(options.length).toBe(1);
  });

  it('confirms close: posts nextSprintId, switches to the target, and shows a notice', () => {
    const fixture = render(
      [sprint('spr_1', 1, 'active'), sprint('spr_2', 2, 'planned')],
      board('spr_1', []),
    );
    button(fixture, 'スプリントを終了')!.click();
    httpMock.expectOne(`${BASE}/sprints/spr_1/close/preview`).flush({ tasks: [] });
    fixture.detectChanges();

    button(fixture, '確定')!.click();
    const post = httpMock.expectOne(`${BASE}/sprints/spr_1/close`);
    expect(post.request.method).toBe('POST');
    expect(post.request.body).toEqual({ nextSprintId: 'spr_2' }); // 候補の先頭が既定
    post.flush({ sprint: sprint('spr_1', 1, 'closed'), carriedOver: 2 });

    // 締めた後は持ち越し先（spr_2）を表示スプリントにして読み直す。
    httpMock
      .expectOne(`${BASE}/sprints`)
      .flush([sprint('spr_1', 1, 'closed'), sprint('spr_2', 2, 'planned')]);
    fixture.detectChanges();
    httpMock.expectOne(`${BASE}/sprints/spr_2/board`).flush(board('spr_2', []));
    fixture.detectChanges();

    expect(fixture.componentInstance['selectedSprintId']()).toBe('spr_2');
    const notice = (fixture.nativeElement as HTMLElement).querySelector('.notice');
    expect(notice?.textContent).toContain('2 件を持ち越しました');
  });

  it('closes cannot proceed with no carry-over target and shows a hint', () => {
    // 候補が無い（自分だけ／他は closed）なら確定を出さず、次スプリント作成を促す。
    const fixture = render(
      [sprint('spr_1', 1, 'active'), sprint('spr_0', 0, 'closed')],
      board('spr_1', []),
    );
    button(fixture, 'スプリントを終了')!.click();
    httpMock.expectOne(`${BASE}/sprints/spr_1/close/preview`).flush({ tasks: [] });
    fixture.detectChanges();

    expect(button(fixture, '確定')).toBeNull();
    const dialog = (fixture.nativeElement as HTMLElement).querySelector('.close-dialog');
    expect(dialog!.textContent).toContain('持ち越し先のスプリントがありません');
  });

  // --- デイリーパネル（B-27・D-27） --------------------------------------------

  /** 日付は Asia/Tokyo の「今日」で動的なので、URL の前方一致で拾う（日付に結合しない）。 */
  function expectDailyGet(sprintId: string) {
    return httpMock.expectOne((req) => req.url.startsWith(`${BASE}/sprints/${sprintId}/daily/`));
  }

  it('opens the daily panel and get-or-creates today\'s note (ETag from header)', () => {
    const fixture = render([sprint('spr_1', 1, 'active')], board('spr_1', []));

    button(fixture, 'デイリー')!.click();
    // 開くと当日のノートを get-or-create する（無ければサーバーが空を作って返す — D-27）。
    const get = expectDailyGet('spr_1');
    expect(get.request.method).toBe('GET');
    get.flush(
      { id: 'dly_spr_1_x', agenda: [], minutes: '既存の議事録' },
      { headers: { ETag: '"d1"' } },
    );
    fixture.detectChanges();

    const panel = (fixture.nativeElement as HTMLElement).querySelector('.daily-panel');
    expect(panel).not.toBeNull();
    expect(panel!.querySelector<HTMLTextAreaElement>('.minutes')!.value).toBe('既存の議事録');
  });

  it('saves the daily note via PATCH with If-Match, dropping empty agenda rows', () => {
    const fixture = render([sprint('spr_1', 1, 'active')], board('spr_1', []));
    button(fixture, 'デイリー')!.click();
    expectDailyGet('spr_1').flush(
      { id: 'dly_spr_1_x', agenda: [], minutes: '' },
      { headers: { ETag: '"d1"' } },
    );
    fixture.detectChanges();
    const host = fixture.nativeElement as HTMLElement;

    // アジェンダを1件足してテキストを入れ、議事録も書く。
    button(fixture, 'アジェンダを追加')!.click();
    fixture.detectChanges();
    const text = host.querySelector<HTMLInputElement>('.agenda-text')!;
    text.value = '昨日の進捗';
    text.dispatchEvent(new Event('input'));
    const minutes = host.querySelector<HTMLTextAreaElement>('.minutes')!;
    minutes.value = '## 決定事項';
    minutes.dispatchEvent(new Event('input'));

    button(fixture, '保存')!.click();
    const patch = expectDailyGet('spr_1');
    expect(patch.request.method).toBe('PATCH');
    expect(patch.request.headers.get('If-Match')).toBe('"d1"');
    expect(patch.request.body.minutes).toBe('## 決定事項');
    expect(patch.request.body.agenda.length).toBe(1);
    expect(patch.request.body.agenda[0].text).toBe('昨日の進捗');
    patch.flush(
      { id: 'dly_spr_1_x', agenda: patch.request.body.agenda, minutes: '## 決定事項' },
      { headers: { ETag: '"d2"' } },
    );
    fixture.detectChanges();

    expect(host.querySelector('.saved-notice')?.textContent).toContain('保存しました');
  });

  it('on 412 shows a message and reloads the daily note (D-24)', () => {
    const fixture = render([sprint('spr_1', 1, 'active')], board('spr_1', []));
    button(fixture, 'デイリー')!.click();
    expectDailyGet('spr_1').flush(
      { id: 'dly_spr_1_x', agenda: [], minutes: '' },
      { headers: { ETag: '"d1"' } },
    );
    fixture.detectChanges();

    button(fixture, '保存')!.click();
    expectDailyGet('spr_1').flush(
      { type: 't', title: 'conflict' },
      { status: 412, statusText: 'Precondition Failed' },
    );
    // 黙って上書きせず最新を読み直す（D-24）。
    expectDailyGet('spr_1').flush(
      { id: 'dly_spr_1_x', agenda: [], minutes: '他者の議事録' },
      { headers: { ETag: '"d2"' } },
    );
    fixture.detectChanges();

    const panel = (fixture.nativeElement as HTMLElement).querySelector('.daily-panel')!;
    expect(panel.querySelector('.error')?.textContent).toContain('ほかの人がこのノートを更新');
    expect(panel.querySelector<HTMLTextAreaElement>('.minutes')!.value).toBe('他者の議事録');
  });
});
