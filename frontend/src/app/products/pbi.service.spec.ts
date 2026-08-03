import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { PbiService } from './pbi.service';

const PRODUCT = 'prd_sandbox';
const BASE = `/api/products/${PRODUCT}`;

describe('PbiService', () => {
  let service: PbiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(PbiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('reads the backlog via the screen-scoped aggregate GET (one round-trip)', () => {
    service.getBacklog(PRODUCT).subscribe();

    const req = httpMock.expectOne(`${BASE}/backlog`);
    expect(req.request.method).toBe('GET');
    req.flush({ pbis: [] });
  });

  it('creates a PBI via POST /pbis', () => {
    service.create(PRODUCT, { title: 'ログイン', description: '', acceptanceCriteria: [] }).subscribe();

    const req = httpMock.expectOne(`${BASE}/pbis`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body.title).toBe('ログイン');
    req.flush({});
  });

  it('splits a PBI via POST .../{parent}/split without If-Match (create, not update)', () => {
    service
      .split(PRODUCT, 'pbi_parent', { title: '切り出し', description: '', acceptanceCriteria: [] })
      .subscribe();

    const req = httpMock.expectOne(`${BASE}/pbis/pbi_parent/split`);
    expect(req.request.method).toBe('POST');
    // 分割元は変更しないので If-Match は載せない（B-19・D-20）。
    expect(req.request.headers.has('If-Match')).toBe(false);
    expect(req.request.body.title).toBe('切り出し');
    req.flush({});
  });

  it('sends If-Match when changing status (optimistic concurrency is required)', () => {
    service.updateStatus(PRODUCT, 'pbi_1', '"etag-1"', 'ready').subscribe();

    const req = httpMock.expectOne(`${BASE}/pbis/pbi_1`);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.headers.get('If-Match')).toBe('"etag-1"');
    expect(req.request.body).toEqual({ status: 'ready' });
    req.flush({});
  });

  it('reorders via the dedicated rank endpoint with If-Match and neighbor ids', () => {
    service
      .reorder(PRODUCT, 'pbi_c', '"etag-c"', { beforeId: 'pbi_a', afterId: 'pbi_b' })
      .subscribe();

    const req = httpMock.expectOne(`${BASE}/pbis/pbi_c/rank`);
    expect(req.request.method).toBe('POST');
    expect(req.request.headers.get('If-Match')).toBe('"etag-c"');
    expect(req.request.body).toEqual({ beforeId: 'pbi_a', afterId: 'pbi_b' });
    req.flush({});
  });

  it('encodes ids into the URL path', () => {
    service.updateStatus(PRODUCT, 'pbi/odd id', '"e"', 'new').subscribe();

    httpMock.expectOne(`${BASE}/pbis/pbi%2Fodd%20id`).flush({});
  });

  it('reads a single PBI observing the response so the ETag header is available (B-18)', () => {
    let etag: string | null = null;
    service.getOne(PRODUCT, 'pbi_1').subscribe((res) => {
      etag = res.headers.get('ETag');
    });

    const req = httpMock.expectOne(`${BASE}/pbis/pbi_1`);
    expect(req.request.method).toBe('GET');
    // 単一 GET の版は本文でなくヘッダで返る（D-20）。応答全体を観測して取り出せる。
    req.flush({ id: 'pbi_1' }, { headers: { ETag: '"etag-1"' } });
    expect(etag).toBe('"etag-1"');
  });

  it('patches detail fields with If-Match and surfaces the new ETag (B-18)', () => {
    let etag: string | null = null;
    service
      .update(PRODUCT, 'pbi_1', '"etag-1"', {
        description: '概要',
        estimate: 3,
        acceptanceCriteria: [{ id: 'ac_1', text: '条件', checked: false }],
      })
      .subscribe((res) => {
        etag = res.headers.get('ETag');
      });

    const req = httpMock.expectOne(`${BASE}/pbis/pbi_1`);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.headers.get('If-Match')).toBe('"etag-1"');
    expect(req.request.body).toEqual({
      description: '概要',
      estimate: 3,
      acceptanceCriteria: [{ id: 'ac_1', text: '条件', checked: false }],
    });
    // 更新後の版がヘッダで返り、続けて編集できるよう呼び出し側へ運ばれる。
    req.flush({ id: 'pbi_1' }, { headers: { ETag: '"etag-2"' } });
    expect(etag).toBe('"etag-2"');
  });
});
