import { expect, test } from '@playwright/test';

/**
 * 主要フロー 2/5: プランニング（右ペイン）。
 *
 * PBI をスプリントへ入れると配下の未完了タスクに sprintId が付く。**タスク0件の
 * PBI をチェックすると「タスク分解」タスクが1件生成される**（D-15）。
 * 依存: プランニングモード（B-22）。それまで fixme。
 */
test.fixme('タスク0件の PBI をスプリントに入れると「タスク分解」タスクが生成される', async ({
  page,
}) => {
  await page.goto('/');
  // TODO(B-22): プランニング右ペインで PBI をチェックする導線に置き換える。
  await page.getByRole('checkbox', { name: 'タスク未分解の PBI' }).check();

  // D-15: どこにも表示されない状態を作らないため、空 PBI には受け皿タスクを1件生成する。
  await expect(page.getByText('タスク分解')).toBeVisible();
});
