import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { BacklogPage } from './backlog';
import { BacklogPbi } from '../products/pbi.service';
import { BacklogTask } from '../products/task.service';
import { ProductService, ProductSummary } from '../products/product.service';

const SANDBOX: ProductSummary = { productId: 'prd_sandbox', name: 'サンドボックス', role: 'member' };
const BASE = `/api/products/${SANDBOX.productId}`;

/** バックログ 1 行分のダミー（`_etag` と配下タスクを持つのが単一 Pbi との違い）。 */
function pbi(id: string, title: string, rank: string, tasks: BacklogTask[] = []): BacklogPbi {
  return {
    id,
    type: 'pbi',
    productId: SANDBOX.productId,
    isDeleted: false,
    createdAt: '2026-08-01T00:00:00Z',
    createdBy: 'oid',
    updatedAt: '2026-08-01T00:00:00Z',
    updatedBy: 'oid',
    title,
    description: '',
    acceptanceCriteria: [],
    status: 'new',
    estimate: null,
    rank,
    completedAt: null,
    completedSprintId: null,
    parentPbiId: null,
    _etag: `"etag-${id}"`,
    tasks,
  };
}

/** PBI 配下タスクのダミー。 */
function task(id: string, title: string, pbiId: string): BacklogTask {
  return {
    id,
    type: 'task',
    productId: SANDBOX.productId,
    isDeleted: false,
    createdAt: '2026-08-01T00:00:00Z',
    createdBy: 'oid',
    updatedAt: '2026-08-01T00:00:00Z',
    updatedBy: 'oid',
    taskType: 'pbi',
    pbiId,
    sprintId: null,
    status: 'todo',
    completedAt: null,
    title,
    todo: '',
    memo: '',
    assigneeId: null,
    rank: null,
    isBlocked: false,
    blockedReason: '',
    _etag: `"etag-${id}"`,
  };
}

describe('BacklogPage', () => {
  let httpMock: HttpTestingController;
  let products: ProductService;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      imports: [BacklogPage],
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

  /** コンポーネントを立ち上げ、初回 `GET /backlog` に `items` を返す。 */
  function render(items: BacklogPbi[]): ComponentFixture<BacklogPage> {
    const fixture = TestBed.createComponent(BacklogPage);
    fixture.detectChanges(); // ngOnInit → getBacklog
    httpMock.expectOne(`${BASE}/backlog`).flush({ pbis: items });
    fixture.detectChanges();
    return fixture;
  }

  function rows(fixture: ComponentFixture<BacklogPage>): HTMLElement[] {
    return Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('.pbi-row'));
  }

  it('lists PBIs in the order the server returned (no client re-sort)', () => {
    const fixture = render([pbi('pbi_a', 'A', '0|a:'), pbi('pbi_b', 'B', '0|b:')]);
    const titles = rows(fixture).map((r) => r.querySelector('.title')?.textContent?.trim());
    expect(titles).toEqual(['A', 'B']);
  });

  it('shows an empty hint when there are no PBIs', () => {
    const fixture = render([]);
    expect((fixture.nativeElement as HTMLElement).querySelector('.empty')).not.toBeNull();
  });

  it('bootstraps the product from /api/me on direct navigation', () => {
    products.setProducts([]); // 直接遷移で ProductService が空
    const fixture = TestBed.createComponent(BacklogPage);
    fixture.detectChanges();
    httpMock.expectOne('/api/me').flush({ products: [SANDBOX] });
    httpMock.expectOne(`${BASE}/backlog`).flush({ pbis: [] });
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('h1')?.textContent).toContain(
      'プロダクトバックログ',
    );
  });

  it('shows the invitation hint when the user has no products', () => {
    products.setProducts([]);
    const fixture = TestBed.createComponent(BacklogPage);
    fixture.detectChanges();
    httpMock.expectOne('/api/me').flush({ products: [] });
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('.hint')?.textContent).toContain(
      '属していません',
    );
  });

  it('creates a PBI and reloads the backlog', () => {
    const fixture = render([]);
    const host = fixture.nativeElement as HTMLElement;

    host.querySelector<HTMLButtonElement>('.add .primary')!.click();
    fixture.detectChanges();

    const input = host.querySelector<HTMLInputElement>('#pbi-title')!;
    input.value = '最初の PBI';
    input.dispatchEvent(new Event('input')); // ngModel → newTitle
    fixture.detectChanges();

    host.querySelector<HTMLFormElement>('.add-form')!.dispatchEvent(
      new Event('submit', { cancelable: true }),
    );

    const create = httpMock.expectOne(`${BASE}/pbis`);
    expect(create.request.method).toBe('POST');
    expect(create.request.body.title).toBe('最初の PBI');
    create.flush({});

    // 作成後は集約 GET を引き直す（サーバーの並びを正とする）。
    httpMock.expectOne(`${BASE}/backlog`).flush({ pbis: [pbi('pbi_new', '最初の PBI', '0|a:')] });
    fixture.detectChanges();
    expect(host.querySelector('.title')?.textContent).toContain('最初の PBI');
  });

  it('changes status via PATCH with the item _etag as If-Match', () => {
    const fixture = render([pbi('pbi_a', 'A', '0|a:')]);
    const select = (fixture.nativeElement as HTMLElement).querySelector<HTMLSelectElement>(
      '.pbi-row select',
    )!;
    select.value = 'ready';
    select.dispatchEvent(new Event('change'));

    const patch = httpMock.expectOne(`${BASE}/pbis/pbi_a`);
    expect(patch.request.method).toBe('PATCH');
    expect(patch.request.headers.get('If-Match')).toBe('"etag-pbi_a"');
    expect(patch.request.body).toEqual({ status: 'ready' });
    patch.flush({});

    httpMock.expectOne(`${BASE}/backlog`).flush({ pbis: [] });
  });

  it('reorders by dragging a row down onto a lower row', () => {
    const fixture = render([
      pbi('pbi_a', 'A', '0|a:'),
      pbi('pbi_b', 'B', '0|b:'),
      pbi('pbi_c', 'C', '0|c:'),
    ]);
    const [rowA, , rowC] = rows(fixture);

    // A を C の上へドラッグ&ドロップ（下方向）→ A は C の直後（末尾）へ。
    rowA.dispatchEvent(new Event('dragstart'));
    rowC.dispatchEvent(new Event('drop'));

    const reorder = httpMock.expectOne(`${BASE}/pbis/pbi_a/rank`);
    expect(reorder.request.method).toBe('POST');
    expect(reorder.request.headers.get('If-Match')).toBe('"etag-pbi_a"');
    expect(reorder.request.body).toEqual({ beforeId: 'pbi_c', afterId: null });
    reorder.flush({});

    httpMock.expectOne(`${BASE}/backlog`).flush({ pbis: [] });
  });

  it('reorders by dragging a row up onto a higher row', () => {
    const fixture = render([
      pbi('pbi_a', 'A', '0|a:'),
      pbi('pbi_b', 'B', '0|b:'),
      pbi('pbi_c', 'C', '0|c:'),
    ]);
    const [rowA, , rowC] = rows(fixture);

    // C を A の上へ（上方向）→ C は A の直前（先頭）へ。
    rowC.dispatchEvent(new Event('dragstart'));
    rowA.dispatchEvent(new Event('drop'));

    const reorder = httpMock.expectOne(`${BASE}/pbis/pbi_c/rank`);
    expect(reorder.request.body).toEqual({ beforeId: null, afterId: 'pbi_a' });
    reorder.flush({});

    httpMock.expectOne(`${BASE}/backlog`).flush({ pbis: [] });
  });

  it('ignores a drop onto the same row (no request)', () => {
    const fixture = render([pbi('pbi_a', 'A', '0|a:'), pbi('pbi_b', 'B', '0|b:')]);
    const [rowA] = rows(fixture);
    rowA.dispatchEvent(new Event('dragstart'));
    rowA.dispatchEvent(new Event('drop'));
    // 同じ行へのドロップは何も送らない（httpMock.verify() が余分な要求を検出する）。
  });

  // --- 配下タスク（B-20） ----------------------------------------------------

  it('renders tasks nested under their PBI in the server order', () => {
    const fixture = render([
      pbi('pbi_a', 'A', '0|a:', [task('tsk_1', '実装', 'pbi_a'), task('tsk_2', 'テスト', 'pbi_a')]),
    ]);
    const [rowA] = rows(fixture);
    const titles = Array.from(rowA.querySelectorAll('.task-title')).map((t) =>
      t.textContent?.trim(),
    );
    expect(titles).toEqual(['実装', 'テスト']);
  });

  it('adds a task to a PBI via POST /tasks and reloads the backlog', () => {
    const fixture = render([pbi('pbi_a', 'A', '0|a:')]);
    const [rowA] = rows(fixture);

    rowA.querySelector<HTMLButtonElement>('.add-task')!.click();
    fixture.detectChanges();

    const input = rowA.querySelector<HTMLInputElement>('input')!;
    input.value = '実装';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    rowA
      .querySelector<HTMLFormElement>('.task-form')!
      .dispatchEvent(new Event('submit', { cancelable: true }));

    const create = httpMock.expectOne(`${BASE}/tasks`);
    expect(create.request.method).toBe('POST');
    expect(create.request.body).toEqual({ taskType: 'pbi', pbiId: 'pbi_a', title: '実装' });
    create.flush({});

    // 作成後は集約 GET を引き直す（サーバーの並びを正とする）。
    httpMock
      .expectOne(`${BASE}/backlog`)
      .flush({ pbis: [pbi('pbi_a', 'A', '0|a:', [task('tsk_1', '実装', 'pbi_a')])] });
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('.task-title')?.textContent).toContain(
      '実装',
    );
  });

  // --- 分割（B-19） ----------------------------------------------------------

  it('splits a PBI via POST .../split (no If-Match) and reloads the backlog', () => {
    const fixture = render([pbi('pbi_a', '大きな PBI', '0|a:')]);
    const [rowA] = rows(fixture);

    rowA.querySelector<HTMLButtonElement>('.split')!.click();
    fixture.detectChanges();

    const input = rowA.querySelector<HTMLInputElement>('.split-form input')!;
    input.value = '切り出し';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    rowA
      .querySelector<HTMLFormElement>('.split-form')!
      .dispatchEvent(new Event('submit', { cancelable: true }));

    const split = httpMock.expectOne(`${BASE}/pbis/pbi_a/split`);
    expect(split.request.method).toBe('POST');
    // 作成であって更新ではないため If-Match は載せない（B-19）。
    expect(split.request.headers.has('If-Match')).toBe(false);
    expect(split.request.body.title).toBe('切り出し');
    split.flush({});

    // 作成後は集約 GET を引き直す（サーバーの並びを正とする）。
    const child = { ...pbi('pbi_child', '切り出し', '0|b:'), parentPbiId: 'pbi_a' };
    httpMock
      .expectOne(`${BASE}/backlog`)
      .flush({ pbis: [pbi('pbi_a', '大きな PBI', '0|a:'), child] });
    fixture.detectChanges();
    expect(rows(fixture).length).toBe(2);
  });

  it('traces a split child back to its parent via a link', () => {
    const parent = pbi('pbi_parent', '親 PBI', '0|a:');
    const child = { ...pbi('pbi_child', '子 PBI', '0|b:'), parentPbiId: 'pbi_parent' };
    const fixture = render([parent, child]);

    const link = rows(fixture)[1].querySelector<HTMLAnchorElement>('.parent-link')!;
    expect(link).not.toBeNull();
    // 分割元の名前を一覧から解決して示す。
    expect(link.textContent).toContain('親 PBI');
    // 分割元の詳細（B-18）へ辿れる。
    expect(link.getAttribute('href')).toContain('/backlog/pbi_parent');
  });

  it('does not show a parent link for a PBI without a parent', () => {
    const fixture = render([pbi('pbi_a', 'A', '0|a:')]);
    expect(rows(fixture)[0].querySelector('.parent-link')).toBeNull();
  });
});
