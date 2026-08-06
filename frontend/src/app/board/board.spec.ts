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

  function board(sprintId: string, tasks: BoardTask[]): Board {
    return { sprint: { ...sprint(sprintId, 1, 'active') }, tasks };
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
});
