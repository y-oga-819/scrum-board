import { expect, test } from '@playwright/test';

/**
 * 主要フロー 3/5: ボード操作（todo → doing → done）。
 *
 * 依存: スプリント画面のボード（B-23）。ドラッグ移動と、2人同時操作でも
 * 片方の更新が消えない楽観排他（412）が要点。それまで fixme。
 */
test.fixme('タスクを todo → doing → done へ動かせる', async ({ page }) => {
  await page.goto('/');
  // TODO(B-23): ボードのカラム間ドラッグ（または移動操作）に置き換える。
  const card = page.getByRole('listitem', { name: 'サンプルタスク' });
  await card.dragTo(page.getByRole('list', { name: 'doing' }));
  await card.dragTo(page.getByRole('list', { name: 'done' }));

  await expect(page.getByRole('list', { name: 'done' })).toContainText('サンプルタスク');
});
