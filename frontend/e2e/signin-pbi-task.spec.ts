import { expect, test } from '@playwright/test';

/**
 * 主要フロー 1/5: サインイン → PBI 作成 → タスク追加。
 *
 * 依存する画面: バックログ（B-17）・PBI 詳細（B-18）・タスク CRUD（B-20）。
 * それらが揃うまで fixme（受け皿）。有効化時に本体を埋める。
 */
test.fixme('サインインして PBI を作り、タスクを1件足せる', async ({ page }) => {
  await page.goto('/');
  // TODO(B-17/B-20): サインイン後、PBI を作成しタスクを追加する導線に置き換える。
  await page.getByRole('button', { name: 'PBI を追加' }).click();
  await page.getByLabel('タイトル').fill('最初の PBI');
  await page.getByRole('button', { name: '保存' }).click();

  await expect(page.getByText('最初の PBI')).toBeVisible();
});
