import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { TaskService } from './task.service';

const PRODUCT = 'prd_sandbox';
const BASE = `/api/products/${PRODUCT}`;

describe('TaskService', () => {
  let service: TaskService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(TaskService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('creates a pbi task via POST /tasks (taskType is the discriminator)', () => {
    service.create(PRODUCT, { taskType: 'pbi', pbiId: 'pbi_1', title: '実装' }).subscribe();

    const req = httpMock.expectOne(`${BASE}/tasks`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ taskType: 'pbi', pbiId: 'pbi_1', title: '実装' });
    req.flush({});
  });

  it('creates a team task with no parent PBI', () => {
    service.create(PRODUCT, { taskType: 'team', title: '環境整備' }).subscribe();

    const req = httpMock.expectOne(`${BASE}/tasks`);
    expect(req.request.body).toEqual({ taskType: 'team', title: '環境整備' });
    req.flush({});
  });

  it('patches a task with If-Match and surfaces the new ETag', () => {
    let etag: string | null = null;
    service.update(PRODUCT, 'tsk_1', '"etag-1"', { status: 'done' }).subscribe((res) => {
      etag = res.headers.get('ETag');
    });

    const req = httpMock.expectOne(`${BASE}/tasks/tsk_1`);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.headers.get('If-Match')).toBe('"etag-1"');
    expect(req.request.body).toEqual({ status: 'done' });
    // completedAt はサーバーが刻む（フロントは送らない）。版はヘッダで返る（D-20）。
    req.flush({ id: 'tsk_1' }, { headers: { ETag: '"etag-2"' } });
    expect(etag).toBe('"etag-2"');
  });

  it('deletes a task with If-Match', () => {
    service.delete(PRODUCT, 'tsk_1', '"etag-1"').subscribe();

    const req = httpMock.expectOne(`${BASE}/tasks/tsk_1`);
    expect(req.request.method).toBe('DELETE');
    expect(req.request.headers.get('If-Match')).toBe('"etag-1"');
    req.flush(null);
  });

  it('encodes ids into the URL path', () => {
    service.delete(PRODUCT, 'tsk/odd id', '"e"').subscribe();

    httpMock.expectOne(`${BASE}/tasks/tsk%2Fodd%20id`).flush(null);
  });
});
