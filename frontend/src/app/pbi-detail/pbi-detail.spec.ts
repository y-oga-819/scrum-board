import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';

import { PbiDetailPage } from './pbi-detail';
import { Pbi } from '../products/pbi.service';
import { ProductService, ProductSummary } from '../products/product.service';

const SANDBOX: ProductSummary = { productId: 'prd_sandbox', name: 'サンドボックス', role: 'member' };
const BASE = `/api/products/${SANDBOX.productId}`;
const PBI_ID = 'pbi_1';

/** 単一 GET が返す PBI（版は本文でなく `ETag` ヘッダで返る）。 */
function pbi(overrides: Partial<Pbi> = {}): Pbi {
  return {
    id: PBI_ID,
    type: 'pbi',
    productId: SANDBOX.productId,
    isDeleted: false,
    createdAt: '2026-08-01T00:00:00Z',
    createdBy: 'oid',
    updatedAt: '2026-08-01T00:00:00Z',
    updatedBy: 'oid',
    title: 'ログイン機能',
    description: '',
    acceptanceCriteria: [],
    status: 'new',
    estimate: null,
    rank: '0|a:',
    completedAt: null,
    completedSprintId: null,
    parentPbiId: null,
    ...overrides,
  };
}

describe('PbiDetailPage', () => {
  let httpMock: HttpTestingController;
  let products: ProductService;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      imports: [PbiDetailPage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ pbiId: PBI_ID }) } },
        },
      ],
    });
    httpMock = TestBed.inject(HttpTestingController);
    products = TestBed.inject(ProductService);
    products.setProducts([SANDBOX]);
  });

  afterEach(() => {
    httpMock.verify();
    sessionStorage.clear();
  });

  /** コンポーネントを立ち上げ、初回 `GET /pbis/{id}` に `doc` を版ヘッダ付きで返す。 */
  function render(doc: Pbi, etag = '"etag-1"'): ComponentFixture<PbiDetailPage> {
    const fixture = TestBed.createComponent(PbiDetailPage);
    fixture.detectChanges(); // ngOnInit → getOne
    httpMock.expectOne(`${BASE}/pbis/${PBI_ID}`).flush(doc, { headers: { ETag: etag } });
    fixture.detectChanges();
    return fixture;
  }

  function host(fixture: ComponentFixture<PbiDetailPage>): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function type(el: HTMLInputElement | HTMLTextAreaElement, value: string): void {
    el.value = value;
    el.dispatchEvent(new Event('input'));
  }

  function submit(fixture: ComponentFixture<PbiDetailPage>): void {
    host(fixture)
      .querySelector<HTMLFormElement>('.detail-form')!
      .dispatchEvent(new Event('submit', { cancelable: true }));
  }

  it('loads a PBI and fills the form (title, description, estimate, criteria)', () => {
    const fixture = render(
      pbi({
        title: '検索機能',
        description: '全文検索を行う',
        estimate: 5,
        acceptanceCriteria: [{ id: 'ac_1', text: 'キーワードで絞れる', checked: true }],
      }),
    );
    const h = host(fixture);
    expect(h.querySelector<HTMLInputElement>('#pbi-title')!.value).toBe('検索機能');
    expect(h.querySelector<HTMLTextAreaElement>('#pbi-description')!.value).toBe('全文検索を行う');
    expect(h.querySelector<HTMLInputElement>('#pbi-estimate')!.value).toBe('5');
    const criterion = h.querySelector<HTMLInputElement>('.criterion-text')!;
    expect(criterion.value).toBe('キーワードで絞れる');
    expect(h.querySelector<HTMLInputElement>('.criterion-check')!.checked).toBe(true);
  });

  it('saves edited fields with the loaded ETag as If-Match and refreshes the version (B-18)', () => {
    const fixture = render(pbi());
    const h = host(fixture);

    type(h.querySelector<HTMLInputElement>('#pbi-title')!, '検索機能');
    type(h.querySelector<HTMLTextAreaElement>('#pbi-description')!, '全文検索');
    type(h.querySelector<HTMLInputElement>('#pbi-estimate')!, '8');
    h.querySelector<HTMLButtonElement>('.add-criterion')!.click();
    fixture.detectChanges();
    type(h.querySelector<HTMLInputElement>('.criterion-text')!, 'キーワードで絞れる');

    submit(fixture);

    const req = httpMock.expectOne(`${BASE}/pbis/${PBI_ID}`);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.headers.get('If-Match')).toBe('"etag-1"');
    expect(req.request.body.title).toBe('検索機能');
    expect(req.request.body.description).toBe('全文検索');
    expect(req.request.body.estimate).toBe(8);
    expect(req.request.body.acceptanceCriteria.length).toBe(1);
    expect(req.request.body.acceptanceCriteria[0]).toMatchObject({
      text: 'キーワードで絞れる',
      checked: false,
    });
    // 新しい版がヘッダで返り、続けて編集できるよう保持される。
    req.flush(pbi({ title: '検索機能' }), { headers: { ETag: '"etag-2"' } });
    fixture.detectChanges();
    expect(h.querySelector('.saved')).not.toBeNull();
  });

  it('sends estimate as null when left empty (optional, no warning — D-06)', () => {
    const fixture = render(pbi({ title: 'そのまま' }));
    submit(fixture);
    const req = httpMock.expectOne(`${BASE}/pbis/${PBI_ID}`);
    expect(req.request.body.estimate).toBeNull();
    req.flush(pbi({ title: 'そのまま' }), { headers: { ETag: '"etag-2"' } });
  });

  it('drops empty checklist rows on save (no blank criteria persisted)', () => {
    const fixture = render(pbi());
    const h = host(fixture);
    h.querySelector<HTMLButtonElement>('.add-criterion')!.click(); // 空行を1つ足すだけ
    fixture.detectChanges();

    submit(fixture);
    const req = httpMock.expectOne(`${BASE}/pbis/${PBI_ID}`);
    expect(req.request.body.acceptanceCriteria).toEqual([]);
    req.flush(pbi(), { headers: { ETag: '"etag-2"' } });
  });

  it('does not save when the title is cleared (server requires it — surfaced client-side)', () => {
    const fixture = render(pbi());
    const h = host(fixture);
    type(h.querySelector<HTMLInputElement>('#pbi-title')!, '   ');
    submit(fixture);
    fixture.detectChanges();
    // PATCH は飛ばない（httpMock.verify() が余分な要求を検出する）。
    expect(h.querySelector('.error')?.textContent).toContain('タイトルは必須');
  });

  it('shows a not-found message on 404', () => {
    const fixture = TestBed.createComponent(PbiDetailPage);
    fixture.detectChanges();
    httpMock
      .expectOne(`${BASE}/pbis/${PBI_ID}`)
      .flush({ detail: '見つかりません' }, { status: 404, statusText: 'Not Found' });
    fixture.detectChanges();
    expect(host(fixture).textContent).toContain('PBI が見つかりません');
  });

  it('reloads the latest on a 412 version conflict instead of overwriting', () => {
    const fixture = render(pbi());
    submit(fixture);
    httpMock
      .expectOne(`${BASE}/pbis/${PBI_ID}`)
      .flush({ detail: '版がずれています' }, { status: 412, statusText: 'Precondition Failed' });
    fixture.detectChanges();
    // 黙って上書きせず、最新を読み直す（GET が再度飛ぶ）。
    httpMock
      .expectOne(`${BASE}/pbis/${PBI_ID}`)
      .flush(pbi({ title: '他者が更新' }), { headers: { ETag: '"etag-9"' } });
    fixture.detectChanges();
    expect(host(fixture).querySelector<HTMLInputElement>('#pbi-title')!.value).toBe('他者が更新');
  });

  it('bootstraps the product from /api/me on direct navigation', () => {
    products.setProducts([]); // 直接遷移で ProductService が空
    const fixture = TestBed.createComponent(PbiDetailPage);
    fixture.detectChanges();
    httpMock.expectOne('/api/me').flush({ products: [SANDBOX] });
    httpMock.expectOne(`${BASE}/pbis/${PBI_ID}`).flush(pbi(), { headers: { ETag: '"etag-1"' } });
    fixture.detectChanges();
    expect(host(fixture).querySelector<HTMLInputElement>('#pbi-title')!.value).toBe('ログイン機能');
  });
});
