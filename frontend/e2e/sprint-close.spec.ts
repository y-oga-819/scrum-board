import { expect, test, type Page } from '@playwright/test';

/**
 * 「スプリントを作成」を押し、作成された新スプリントの id を **`POST /sprints` の応答本文から
 * 直接**取り出す。UI のセレクタ更新は非同期で、押した直後に値を読むと更新前を拾う（前回
 * s1===s2 で落ちた原因）。応答から取れば描画タイミングに依存せず確実。
 */
async function createSprintAndCaptureId(page: Page): Promise<string> {
  const [response] = await Promise.all([
    page.waitForResponse(
      (r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/sprints'),
    ),
    page.getByRole('button', { name: 'スプリントを作成' }).click(),
  ]);
  const body = (await response.json()) as { id: string };
  return body.id;
}

/**
 * 主要フロー 4/5: スプリント終了処理（B-25）。
 *
 * **完了タスクは動かさず、未完了だけを次スプリントへ持ち越す**（不変条件 I-5）。持ち越し
 * 対象はプレビューしてから確定する（D-20。強制も警告もせず事実だけ見せる — P-1）。
 *
 * サインインは EX-1・D-22 の実行方式（フロントは e2e ビルドで MSAL 無効・バックエンドは env
 * ゲートの resolver）。既知の初期状態は `globalSetup` が `prd_test_<runId>` に seeding する。
 * スプリントはこのフロー内でプランニング右ペインから作る（seeding には積まない）。他フローと
 * 同じ partition を共有するため、タイトルはこのフロー固有にする（EX-1/D-22）。
 *
 * 各操作は状態を変えるたびに集約 GET を引き直す（D-24）。ボードの再描画レースを避けるため、
 * **次の操作へ進む前に `expect(...)` で描画が落ち着くのを待つ**（フロー③ board.spec と同じ流儀）。
 */
test('スプリント終了で未完了だけが持ち越され、完了タスクは動かない', async ({ page }) => {
  await page.goto('/backlog');

  // タスクを2件持つ PBI を1件作る（1件は完了・1件は未完了にして I-5 を確かめる）。
  const pbiTitle = 'フロー4の PBI';
  await page.getByRole('button', { name: 'PBI を追加' }).click();
  await page.getByLabel('タイトル').fill(pbiTitle);
  await page.getByRole('button', { name: '保存' }).click();
  await expect(page.getByText(pbiTitle)).toBeVisible();

  // 以降の操作はこの PBI の行にスコープする（他フローの同名ボタンと衝突させない）。
  const row = page.locator('.pbi-row').filter({ hasText: pbiTitle });
  const doneTitle = 'フロー4の完了タスク';
  const keepTitle = 'フロー4の未完了タスク';
  for (const taskTitle of [doneTitle, keepTitle]) {
    await row.getByRole('button', { name: 'タスクを追加' }).click();
    await row.getByLabel('タスク名').fill(taskTitle);
    await row.getByRole('button', { name: '追加', exact: true }).click();
    await expect(row.getByText(taskTitle)).toBeVisible();
  }

  // プランニング右ペインで締める対象 S1 と持ち越し先 S2 を作る。作成は非同期でセレクタを
  // 更新するので、**オプションが1件増えるのを待ってから**選択中の id（＝作成された新スプリント）を
  // 控える（作成直後に読むと更新前の値を拾う — 前回 s1===s2 で落ちた原因）。partition には他
  // フローのスプリントも残るため id で扱う（EX-1/D-22）。
  await page.getByRole('button', { name: 'プランニング' }).click();
  const planningSelect = page.locator('.planning-pane .sprint-select select');
  const s1 = await createSprintAndCaptureId(page);
  const s2 = await createSprintAndCaptureId(page);
  expect(s1).not.toBe(s2);

  // 取り込み先を S1 に戻し（作成直後は S2 が選択中）、PBI を取り込む。配下の未完了2タスクに
  // S1 の sprintId が付く（B-22）。取り込みの確定はチェック状態＝配下タスクの sprintId からの
  // 導出（D-08）が S1 で true になるのを待って確かめる。
  await planningSelect.selectOption(s1);
  const pbiCheckbox = page.getByRole('checkbox', { name: pbiTitle });
  await pbiCheckbox.check();
  await expect(pbiCheckbox).toBeChecked();

  // ボードへ移り S1 を選ぶ。取り込んだ2タスクが未着手に並ぶまで待つ（取り込みの確定＝
  // ボードのロード完了。ここを待たずに操作すると再描画レースになる — フロー③と同じ）。
  await page.goto('/board');
  await page.locator('.sprint-select select').selectOption(s1);
  const todoColumn = page.getByRole('list', { name: '未着手' });
  await expect(todoColumn).toContainText(doneTitle);
  await expect(todoColumn).toContainText(keepTitle);

  // planned なので開始（active）してから終了できる（M5 の1周）。開始はボードを引き直すので、
  // 「スプリントを終了」が出る＝ active への遷移とロード完了を待ってから次へ進む。
  await page.getByRole('button', { name: 'スプリントを開始' }).click();
  await expect(page.getByRole('button', { name: 'スプリントを終了' })).toBeVisible();

  // 完了タスクを done にする（このスプリントに凍結され、持ち越されないことを後で確かめる）。
  const doneColumn = page.getByRole('list', { name: '完了' });
  await page.getByRole('listitem', { name: doneTitle }).dragTo(doneColumn);
  await expect(doneColumn).toContainText(doneTitle);

  // スプリントを終了 → 持ち越しプレビュー。未完了だけが並び、完了タスクは出ない（I-5）。
  await page.getByRole('button', { name: 'スプリントを終了' }).click();
  const dialog = page.getByRole('dialog', { name: '持ち越しプレビュー' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(keepTitle)).toBeVisible();
  await expect(dialog.getByText(doneTitle)).toHaveCount(0);

  // 持ち越し先に S2 を選んで確定する（候補は締める対象・終了済みを除く）。
  await dialog.locator('.next-select select').selectOption(s2);
  await dialog.getByRole('button', { name: '確定' }).click();

  // 確定後は持ち越し先 S2 が表示スプリントになる。未完了タスクは S2 の未着手にいて、
  // 完了タスクは持ち越されていない（S1 に凍結・S2 には現れない — I-5）。
  await expect(page.getByRole('list', { name: '未着手' })).toContainText(keepTitle);
  await expect(page.getByRole('listitem', { name: doneTitle })).toHaveCount(0);
});
