import { execFileSync } from 'node:child_process';
import * as path from 'node:path';

const repoRoot = path.resolve(__dirname, '..', '..');

/**
 * E2E の隔離パーティションを物理削除して後片付けする（EX-1・D-22）。
 *
 * `scripts/e2e_teardown.py` を回し、`prd_test_<E2E_RUN_ID>` を物理削除する。
 * テストの成否に関わらず Playwright が必ず呼ぶ（`E2E_RUN_ID` は globalSetup と同じ値）。
 */
export default function globalTeardown(): void {
  execFileSync('make', ['-C', repoRoot, 'e2e-teardown'], { stdio: 'inherit' });
}
