import { expect, test } from '@playwright/test';

/**
 * 主要フロー 1/5: サインイン → PBI 作成 → タスク追加。
 *
 * 依存する画面: バックログ（B-17・完了）・タスク CRUD（B-20・完了）。PBI 作成
 * （`PBI を追加`／`タイトル`／`保存`）は B-17、PBI 配下のタスク追加（`タスクを追加`／
 * `タスク名`／`追加`）は B-20 で用意済み。
 *
 * サインインは EX-1・D-22 の実行方式で通す: フロントは e2e ビルドで MSAL を無効化し、
 * バックエンドは env ゲートの resolver で固定 E2E ユーザーに解決する。既知の初期状態は
 * `globalSetup` が `prd_test_<runId>` に seeding する（このフローが操作するプロダクト）。
 * そのため `/backlog` に直接遷移した時点で認証済み・所属あり、と扱える。
 */
test('サインインして PBI を作り、タスクを1件足せる', async ({ page }) => {
  await page.goto('/backlog');

  // PBI を 1 件作る（B-17）。
  await page.getByRole('button', { name: 'PBI を追加' }).click();
  await page.getByLabel('タイトル').fill('最初の PBI');
  await page.getByRole('button', { name: '保存' }).click();
  await expect(page.getByText('最初の PBI')).toBeVisible();

  // その PBI 配下にタスクを 1 件足す（B-20）。
  await page.getByRole('button', { name: 'タスクを追加' }).click();
  await page.getByLabel('タスク名').fill('実装する');
  await page.getByRole('button', { name: '追加' }).click();
  await expect(page.getByText('実装する')).toBeVisible();
});
