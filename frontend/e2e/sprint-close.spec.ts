import { expect, test } from '@playwright/test';

/**
 * 主要フロー 4/5: スプリント終了処理。
 *
 * **完了タスクは動かさず、未完了だけ次スプリントへ持ち越す**（不変条件 I-5）。
 * 持ち越し対象はプレビューしてから確定する（B-25・D-20）。それまで fixme。
 */
test.fixme('スプリント終了で未完了だけが持ち越され、完了タスクは動かない', async ({ page }) => {
  await page.goto('/');
  // TODO(B-25): 「スプリントを終了」→ 持ち越しプレビュー → 確定 の導線に置き換える。
  await page.getByRole('button', { name: 'スプリントを終了' }).click();
  await expect(page.getByRole('dialog', { name: '持ち越しプレビュー' })).toBeVisible();
  await page.getByRole('button', { name: '確定' }).click();

  // I-5: 完了タスクは次スプリントに現れない（sprintId を変えない）。
  await expect(page.getByText('未完了タスク')).toBeVisible();
  await expect(page.getByText('完了タスク')).toHaveCount(0);
});
