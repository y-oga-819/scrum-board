import { expect, test } from '@playwright/test';

/**
 * 主要フロー 5/5: スプリントから外したチームタスクが「未割当」に現れる。
 *
 * 提案書が **唯一許容できない失敗**と呼ぶ「どこにも表示されない状態」（D-16）の
 * 回帰テスト。チームタスクをスプリントから外すとバックログ画面の未割当に現れ、
 * **消えない**こと。依存: 未割当チームタスク（B-29）。それまで fixme。
 */
test.fixme('スプリントから外したチームタスクが未割当に現れ、消えない', async ({ page }) => {
  await page.goto('/');
  // TODO(B-29): チームタスクをスプリントから外す導線に置き換える。
  await page.getByRole('button', { name: 'スプリントから外す' }).click();

  // D-16: 外した先が「未割当」に必ず現れる（どこにも無い状態を作らない）。
  await page.goto('/backlog');
  await expect(page.getByRole('region', { name: '未割当' })).toContainText('チームタスク');
});
