import { expect, test } from '@playwright/test';

/**
 * 主要フロー 2/5: プランニング（右ペイン。B-22）。
 *
 * PBI をスプリントへ取り込むと配下の未完了タスクに `sprintId` が付く。**タスク0件の PBI を
 * チェックすると「タスク分解」タスクが1件生成される**（D-15）——タスクの無い PBI をスプリント
 * に置けるようにし、「どこにも表示されない状態」を作らない。
 *
 * サインインは EX-1・D-22 の実行方式（フロントは e2e ビルドで MSAL 無効・バックエンドは env
 * ゲートの resolver）。既知の初期状態は `globalSetup` が `prd_test_<runId>` に seeding する。
 * スプリントはこのフロー内でプランニング右ペインから作る（seeding には積まない）。
 */
test('タスク0件の PBI をスプリントに入れると「タスク分解」タスクが生成される', async ({
  page,
}) => {
  await page.goto('/backlog');

  // タスクを持たない PBI を1件作る（B-17）。
  await page.getByRole('button', { name: 'PBI を追加' }).click();
  await page.getByLabel('タイトル').fill('タスク未分解の PBI');
  await page.getByRole('button', { name: '保存' }).click();
  await expect(page.getByText('タスク未分解の PBI')).toBeVisible();

  // プランニング右ペインを開き、取り込み先のスプリントを作る（B-21 のスプリント CRUD）。
  await page.getByRole('button', { name: 'プランニング' }).click();
  await page.getByRole('button', { name: 'スプリントを作成' }).click();

  // その PBI をスプリントへ取り込む（チェックのアクセシブル名は PBI のタイトル）。
  await page.getByRole('checkbox', { name: 'タスク未分解の PBI' }).check();

  // D-15: どこにも表示されない状態を作らないため、空 PBI には受け皿タスクを1件生成する。
  await expect(page.getByText('タスク分解')).toBeVisible();
});
