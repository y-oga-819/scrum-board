import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { DailyNoteService } from './daily-note.service';

const PRODUCT = 'prd_sandbox';
const SPRINT = 'spr_1';
const DATE = '2026-08-05';
const URL = `/api/products/${PRODUCT}/sprints/${SPRINT}/daily/${DATE}`;

describe('DailyNoteService', () => {
  let service: DailyNoteService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(DailyNoteService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('gets the note (get-or-create) and surfaces the ETag header', () => {
    let etag: string | null = null;
    service.get(PRODUCT, SPRINT, DATE).subscribe((res) => {
      etag = res.headers.get('ETag');
    });

    const req = httpMock.expectOne(URL);
    expect(req.request.method).toBe('GET');
    // 単一ドキュメント応答の版はヘッダで返る（D-20）。
    req.flush(
      { id: `dly_${SPRINT}_${DATE}`, agenda: [], minutes: '' },
      { headers: { ETag: '"etag-1"' } },
    );
    expect(etag).toBe('"etag-1"');
  });

  it('patches the note with If-Match and surfaces the new ETag', () => {
    let etag: string | null = null;
    service
      .update(PRODUCT, SPRINT, DATE, '"etag-1"', {
        agenda: [{ id: 'a1', text: 'x', done: false }],
        minutes: '議事録',
      })
      .subscribe((res) => {
        etag = res.headers.get('ETag');
      });

    const req = httpMock.expectOne(URL);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.headers.get('If-Match')).toBe('"etag-1"');
    expect(req.request.body).toEqual({
      agenda: [{ id: 'a1', text: 'x', done: false }],
      minutes: '議事録',
    });
    req.flush({ id: `dly_${SPRINT}_${DATE}` }, { headers: { ETag: '"etag-2"' } });
    expect(etag).toBe('"etag-2"');
  });

  it('encodes ids and date into the URL path', () => {
    service.get(PRODUCT, 'spr/odd', DATE).subscribe();

    httpMock
      .expectOne(`/api/products/${PRODUCT}/sprints/spr%2Fodd/daily/${DATE}`)
      .flush({ id: 'x', agenda: [], minutes: '' });
  });
});
