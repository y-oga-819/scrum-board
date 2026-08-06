import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { SprintService } from './sprint.service';

const PRODUCT = 'prd_sandbox';
const BASE = `/api/products/${PRODUCT}`;

describe('SprintService', () => {
  let service: SprintService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(SprintService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('lists sprints via GET /sprints', () => {
    service.list(PRODUCT).subscribe();

    const req = httpMock.expectOne(`${BASE}/sprints`);
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('creates a sprint via POST /sprints (server owns number and status)', () => {
    service.create(PRODUCT, { goal: '回す' }).subscribe();

    const req = httpMock.expectOne(`${BASE}/sprints`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ goal: '回す' });
    req.flush({});
  });

  it('includes a PBI into a sprint via POST .../pbis/{pbiId} (no If-Match)', () => {
    service.includePbi(PRODUCT, 'spr_1', 'pbi_1').subscribe();

    const req = httpMock.expectOne(`${BASE}/sprints/spr_1/pbis/pbi_1`);
    expect(req.request.method).toBe('POST');
    // 複数タスクを束ねるドメイン操作のため単一リソースの版は載せない（分割と同じ — D-20）。
    expect(req.request.headers.has('If-Match')).toBe(false);
    req.flush(null);
  });

  it('excludes a PBI from a sprint via DELETE .../pbis/{pbiId}', () => {
    service.excludePbi(PRODUCT, 'spr_1', 'pbi_1').subscribe();

    const req = httpMock.expectOne(`${BASE}/sprints/spr_1/pbis/pbi_1`);
    expect(req.request.method).toBe('DELETE');
    req.flush(null);
  });

  it('encodes ids into the URL path', () => {
    service.includePbi(PRODUCT, 'spr/odd', 'pbi 1').subscribe();

    httpMock.expectOne(`${BASE}/sprints/spr%2Fodd/pbis/pbi%201`).flush(null);
  });
});
