# CI とブランチ保護（B-11）

CI は毎 PR で lint・型チェック・テストを走らせる（[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)）。
ただし **「失敗でマージがブロックされる」は CI 側では完結しない** — GitHub の
**ブランチ保護ルール**で「特定のチェックを必須にする」設定が要る（D-19 の CI 方針）。
ここはリポジトリ管理者が一度だけ行う。

## 何を必須チェックにするか

`main` へのマージ条件として、次のジョブを **Required status checks** に指定する。

| ジョブ | いつ走る | 必須にするか |
|:---|:---|:---|
| `Backend (ruff / mypy / pytest)` | 毎 PR | ✅ 必須 |
| `Frontend (eslint / tsc / vitest)` | 毎 PR | ✅ 必須 |
| `Backend Cosmos contract (層3 / emulator)` | 毎 PR | ⚠️ 下記参照 |
| `E2E (Playwright)` | main への push | ✅ 必須（別ワークフロー [`e2e.yml`](../../.github/workflows/e2e.yml)。main でのみ走る） |

- **層3（Cosmos 契約）**: エミュレータ起動を伴い、実行時間と安定性の当たりが
  読めない。**まずは非必須で回して緑の安定を確認し、安定したら必須へ昇格**する。
  D-19 は「毎 PR で回す」としているが、必須化はフレークが無いことを見てから。
- **E2E** は毎 PR には載せず main で走る設計（層4は分単位）。現時点では主要フロー
  5本が `test.fixme`（対象画面が M4/M5 で実装されるまで skip）なので、実質的な
  ゲートになるのは画面が揃ってから。

## 設定手順（管理者・一度だけ）

GitHub の **Settings → Branches → Branch protection rules** で `main` に対し:

1. **Require a pull request before merging** を有効化。
2. **Require status checks to pass before merging** を有効化し、上表の必須ジョブを選ぶ
   （チェック名は一度 CI が走った後に選択肢へ出る）。
3. **Require branches to be up to date before merging** を有効化（古い base での
   すり抜けを防ぐ）。

CLI で入れる場合（`gh` が使える環境）:

```bash
gh api -X PUT repos/y-oga-819/scrum-board/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f 'required_status_checks[strict]=true' \
  -f 'required_status_checks[checks][][context]=Backend (ruff / mypy / pytest)' \
  -f 'required_status_checks[checks][][context]=Frontend (eslint / tsc / vitest)' \
  -F 'enforce_admins=true' \
  -F 'required_pull_request_reviews=null' \
  -F 'restrictions=null'
```

> チェックの `context` は CI ジョブの `name:` と一致させる。ジョブ名を変えたら
> ここも更新する（さもないと「存在しないチェック待ち」でマージできなくなる）。
