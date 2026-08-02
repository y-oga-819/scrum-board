import { defineConfig, devices } from '@playwright/test';

/**
 * E2E（D-19 の層4）。主要フローを網羅する受け皿。対象画面（M4/M5）が未実装のフローは
 * `test.fixme` で置き、フロー本体はそれぞれの PBI で埋める。フロー①はサインイン経路・
 * seeding・webServer が揃ったので有効（EX-1・D-22）。
 *
 * CI では **毎 PR（マージ前ゲート）**で回す（`e2e.yml` の PR トリガー。main への push で
 * デプロイするため、マージ後 E2E ではゲートにならない — D-19 改定 / ci-branch-protection.md）。
 *
 * 実行方式（EX-1・D-22）:
 * - **サインイン**: 実 Entra への対話サインインはヘッドレスで通せないため、フロントは
 *   e2e ビルドで MSAL を無効化し、バックエンドは env ゲートの resolver に差し替える
 *   （`webServer` が `E2E_AUTH_BYPASS=1` で app を起動する）。
 * - **既知の初期状態**: `globalSetup` が `prd_test_<runId>` を seeding し、`globalTeardown`
 *   が物理削除する（D-21）。Cosmos エミュレータに対して回す。
 * - Chromium はこの環境でプリインストール済み（PLAYWRIGHT_BROWSERS_PATH）。バージョン差が
 *   あれば launchOptions.executablePath で明示する。
 */

// seeding（globalSetup）・app（webServer）・teardown（globalTeardown）で **同じ oid / runId**
// を使う必要がある。ここで一度だけ既定値を正規化して process.env に載せ、後続の子プロセス
// （make e2e-seed / run-e2e / e2e-teardown）すべてに同じ値が渡るようにする。CI が明示的に
// 設定していればそれを優先する。
process.env.E2E_AUTH_OID ??= 'oid-e2e';
process.env.E2E_RUN_ID ??= 'local';
// E2E は誰も Cosmos DB を作らないため、app（webServer）と seeding が自前で
// create_database_if_not_exists する（本番は infra 前提で既定 OFF — EX-1）。globalSetup と
// webServer のどちらが先に起動しても冪等に DB を用意でき、起動順に依存しない。
process.env.COSMOS_CREATE_DATABASE ??= '1';

const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:8000';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // e2e ビルドの SPA を実 FastAPI が配信し、認証は env ゲートでバイパスする（EX-1・D-22）。
  // COSMOS_* は呼び出し側（CI / ローカル）が渡す。E2E_AUTH_BYPASS はここで固定し、通常の
  // プロセス env に混ぜない（誤有効化を避ける）。
  webServer: {
    command: 'make -C .. run-e2e',
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: {
      ...process.env,
      E2E_AUTH_BYPASS: '1',
    },
  },
});
