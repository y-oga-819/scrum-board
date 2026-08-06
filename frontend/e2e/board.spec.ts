import { expect, test } from '@playwright/test';

/**
 * 主要フロー 3/5: ボード操作（todo → doing → done）。
 *
 * スプリント画面のボード（B-23）でカードをカラム間にドラッグして状態を移せることを、
 * サインイン → PBI 作成 → プランニングでスプリントへ取り込み → ボードで移動、まで端から
 * 端まで確かめる。取り込み先スプリントは runId 共有の partition で他フローと混ざらないよう、
 * プランニングで作った直後にその id を控え、ボードで明示的に選ぶ（EX-1/D-22）。
 *
 * サインインは EX-1・D-22 の実行方式（フロントは e2e ビルドで MSAL 無効・バックエンドは env
 * ゲートの resolver）。既知の初期状態は `globalSetup` が `prd_test_<runId>` に seeding する。
 */
test('タスクを todo → doing → done へ動かせる', async ({ page }) => {
  await page.goto('/backlog');

  // タスクを持たない PBI を1件作る（B-17）。プランニングで取り込むと、タスク0件の PBI には
  // 「タスク分解」タスクが1件生成され、そのスプリントに割り当てられる（D-15）。これをボードで動かす。
  const pbiTitle = 'ボード操作フローの PBI';
  await page.getByRole('button', { name: 'PBI を追加' }).click();
  await page.getByLabel('タイトル').fill(pbiTitle);
  await page.getByRole('button', { name: '保存' }).click();
  await expect(page.getByText(pbiTitle)).toBeVisible();

  // プランニング右ペインを開いて取り込み先スプリントを作り、その id を控える（他フローの
  // スプリントと混ざらないよう、ボードでこの id を選ぶ）。
  await page.getByRole('button', { name: 'プランニング' }).click();
  await page.getByRole('button', { name: 'スプリントを作成' }).click();
  const sprintId = await page.locator('.planning-pane .sprint-select select').inputValue();
  expect(sprintId).not.toBe('');

  // その PBI をスプリントへ取り込む（タスク0件なので「タスク分解」が生成・割り当てされる）。
  await page.getByRole('checkbox', { name: pbiTitle }).check();
  const row = page.locator('.pbi-row').filter({ hasText: pbiTitle });
  await expect(row.getByText('タスク分解')).toBeVisible();

  // ボードへ移り、控えたスプリントを選ぶ。生成された「タスク分解」カードが todo にいる。
  await page.goto('/board');
  await page.locator('.sprint-select select').selectOption(sprintId);
  const card = page.getByRole('listitem', { name: 'タスク分解' });
  await expect(page.getByRole('list', { name: '未着手' })).toContainText('タスク分解');

  // todo → doing → done とカラム間をドラッグで移す。各移動後にボードは引き直される（D-24）。
  await card.dragTo(page.getByRole('list', { name: '進行中' }));
  await expect(page.getByRole('list', { name: '進行中' })).toContainText('タスク分解');

  await card.dragTo(page.getByRole('list', { name: '完了' }));
  await expect(page.getByRole('list', { name: '完了' })).toContainText('タスク分解');
});
