import { HttpErrorResponse } from '@angular/common/http';

import { CONCURRENCY_CONFLICT_MESSAGE, messageForError } from './errors';
import type { Problem } from './problem';

// 楽観排他の衝突は本文の有無に関わらず共通文言に寄せる（D-24）。
function httpError(status: number, error: unknown): HttpErrorResponse {
  return new HttpErrorResponse({ status, error });
}

const PROBLEM: Problem = {
  type: 'https://github.com/y-oga-819/scrum-board/errors/invariant-violation',
  title: '不変条件に違反しています',
  status: 422,
  detail: 'サーバーからの説明',
  instance: '/api/products/prd_x/tasks',
  violations: null,
};

describe('messageForError', () => {
  it('412（版ずれ）は再操作を促す共通文言にする（D-24）', () => {
    // 412 の本文（problem の detail）より D-24 の文言を優先する。
    expect(messageForError(httpError(412, PROBLEM), '既定')).toBe(CONCURRENCY_CONFLICT_MESSAGE);
  });

  it('409（ドメイン競合）も同じ共通文言にする', () => {
    expect(messageForError(httpError(409, null), '既定')).toBe(CONCURRENCY_CONFLICT_MESSAGE);
  });

  it('problem+json があれば detail を返す（422 等）', () => {
    expect(messageForError(httpError(422, PROBLEM), '既定')).toBe('サーバーからの説明');
  });

  it('problem でなければ fallback を返す', () => {
    expect(messageForError(httpError(500, 'なにか'), '既定')).toBe('既定');
  });

  it('HttpErrorResponse でない素の値でも fallback に落ちる', () => {
    expect(messageForError(new Error('network'), '既定')).toBe('既定');
  });
});
