import { expect, test } from '@playwright/test';

/**
 * 主要フロー 1/5: サインイン → PBI 作成 → タスク追加。
 *
 * 依存する画面: バックログ（B-17・完了）・タスク CRUD（B-20・完了）。
 * **画面の導線はすべて揃った** — PBI 作成（`PBI を追加`／`タイトル`／`保存`）は B-17、
 * PBI 配下のタスク追加（`タスクを追加`／`タスク名`／`追加`）は B-20 で用意済み。フロー本体は
 * 下のとおり完成しているが、`test.fixme` を外して**緑にできるのは残り 1 点**——ヘッドレスで
 * 通すサインイン経路（`playwright.config.ts` の宿題。実 Entra の対話サインインは CI では
 * 通せないため、テスト用トークン注入か開発用サインイン省略経路 B-14 のどちらかを決める）が
 * 決まってから。この 1 点は方針判断が要るため、B-20 では意図的に繰り延べている。
 */
test.fixme('サインインして PBI を作り、タスクを1件足せる', async ({ page }) => {
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
