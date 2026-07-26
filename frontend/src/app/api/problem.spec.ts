import { hasViolation, isProblem, type Problem } from './problem';

// サーバー（app/http/handlers.py）が返す problem+json の代表例。type/title/status を
// 必ず持ち、不変条件違反のときは violations に規則 ID を載せる（D-20）。
const INVARIANT_PROBLEM: Problem = {
  type: 'https://github.com/y-oga-819/scrum-board/errors/invariant-violation',
  title: '不変条件に違反しています',
  status: 422,
  detail: "taskType='team' のとき pbiId は null",
  instance: '/api/products/prd_x/tasks',
  violations: [{ rule: 'I-4', field: 'pbiId', message: "taskType='team' のとき pbiId は null" }],
};

describe('isProblem', () => {
  it('recognizes a problem+json body', () => {
    expect(isProblem(INVARIANT_PROBLEM)).toBe(true);
  });

  it('recognizes a problem without violations (e.g. 404/412)', () => {
    const notFound: Problem = {
      type: 'https://github.com/y-oga-819/scrum-board/errors/not-found',
      title: 'リソースが見つかりません',
      status: 404,
      detail: null,
      instance: '/api/products/prd_x/pbis/pbi_missing',
      violations: null,
    };
    expect(isProblem(notFound)).toBe(true);
  });

  it('rejects values that lack the required RFC 9457 members', () => {
    expect(isProblem(null)).toBe(false);
    expect(isProblem('boom')).toBe(false);
    expect(isProblem({ title: 'x', status: 500 })).toBe(false); // type 欠落
    expect(isProblem({ type: 'x', title: 'y', status: '500' })).toBe(false); // status が文字列
  });
});

describe('hasViolation', () => {
  it('finds a specific invariant rule in violations', () => {
    // フロントは規則を再評価せず、サーバーが載せた規則 ID を参照するだけ（D-20）。
    expect(hasViolation(INVARIANT_PROBLEM, 'I-4')).toBe(true);
    expect(hasViolation(INVARIANT_PROBLEM, 'I-3')).toBe(false);
  });

  it('is safe when violations is null or absent', () => {
    const noViolations: Problem = {
      type: 'https://github.com/y-oga-819/scrum-board/errors/precondition-failed',
      title: '楽観排他に失敗しました',
      status: 412,
      detail: null,
      instance: null,
      violations: null,
    };
    expect(hasViolation(noViolations, 'I-4')).toBe(false);
  });
});
