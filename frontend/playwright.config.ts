import { defineConfig, devices } from '@playwright/test';

/**
 * E2E（D-19 の層4）。主要フローを網羅する受け皿。対象画面（M4/M5）が実装される
 * まで各フローは `test.fixme` で置き、フロー本体はそれぞれの PBI で埋める。
 * CI では **毎 PR（マージ前ゲート）**で回す（`e2e.yml` の PR トリガー。main への push で
 * デプロイするため、マージ後 E2E ではゲートにならない — D-19 改定 / ci-branch-protection.md）。
 *
 * フロー有効化時の宿題（フローを fixme から外す前に決めること）:
 * - **サインインの通し方**。実 Entra への対話サインインは CI ヘッドレスでは通せない。
 *   テスト用トークン注入か、開発用のサインイン省略経路（B-14）を使う。
 * - **既知の初期状態**。E2E は seeding のたびに初期状態を作り直す前提（D-19）。
 * - この環境では Chromium がプリインストール済み（PLAYWRIGHT_BROWSERS_PATH）。
 *   バージョン差があれば launchOptions.executablePath で明示する。
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8000',
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // フロー有効化時に app を起動する導線（今は全フロー fixme なので無効のまま）:
  // webServer: {
  //   command: 'make -C .. run',
  //   url: 'http://localhost:8000',
  //   reuseExistingServer: !process.env.CI,
  //   timeout: 120_000,
  // },
});
