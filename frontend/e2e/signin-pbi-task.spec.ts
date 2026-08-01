import { expect, test } from '@playwright/test';

/**
 * 主要フロー 1/5: サインイン → PBI 作成 → タスク追加。
 *
 * 依存する画面: バックログ（B-17・完了）・タスク CRUD（B-20・未）。
 * **PBI 作成の導線（`PBI を追加`／`タイトル`／`保存`）は B-17 で用意済み。** 緑化に残るのは
 * (1) タスク追加UI（B-20）と (2) ヘッドレスで通すサインイン経路（playwright.config の宿題）。
 * 両方が揃う B-20 の時点で `test.fixme` を外して本体を仕上げる（B-17 の完了条件が明示的に
 * この繰り延べを許している）。
 */
test.fixme('サインインして PBI を作り、タスクを1件足せる', async ({ page }) => {
  // B-17 で用意済みのバックログ画面。サインイン経路が通ればここまでは動く。
  await page.goto('/backlog');
  await page.getByRole('button', { name: 'PBI を追加' }).click();
  await page.getByLabel('タイトル').fill('最初の PBI');
  await page.getByRole('button', { name: '保存' }).click();
  await expect(page.getByText('最初の PBI')).toBeVisible();

  // TODO(B-20): PBI 配下にタスクを1件追加する導線に差し替え、フローを緑化する。
});
