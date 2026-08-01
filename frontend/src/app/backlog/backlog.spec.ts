import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { BacklogPage } from './backlog';
import { BacklogPbi } from '../products/pbi.service';
import { ProductService, ProductSummary } from '../products/product.service';

const SANDBOX: ProductSummary = { productId: 'prd_sandbox', name: 'サンドボックス', role: 'member' };
const BASE = `/api/products/${SANDBOX.productId}`;

/** バックログ 1 行分のダミー（`_etag` を持つのが単一 Pbi との違い）。 */
function pbi(id: string, title: string, rank: string): BacklogPbi {
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
});
