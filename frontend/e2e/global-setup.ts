import { execFileSync } from 'node:child_process';
import * as path from 'node:path';

const repoRoot = path.resolve(__dirname, '..', '..');

/**
 * E2E の既知の初期状態を作る（EX-1・D-22）。
 *
 * `scripts/e2e_seed.py` を回し、このランだけの隔離パーティション
 * `prd_test_<E2E_RUN_ID>` にプロダクトと E2E ユーザーの admin member を投入する。
 * Cosmos 接続（`COSMOS_*`）と `E2E_RUN_ID` / `E2E_AUTH_OID` は環境変数から渡る
 * （`playwright.config.ts` が既定値を正規化して process.env に載せている）。
 */
export default function globalSetup(): void {
  execFileSync('make', ['-C', repoRoot, 'e2e-seed'], { stdio: 'inherit' });
}
