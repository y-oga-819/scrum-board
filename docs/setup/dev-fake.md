# dev-fake — サインイン・Cosmos なしで API を叩く

`make dev-fake` は、**Entra のサインインも Cosmos 接続も無しで API をローカルに立てる
開発専用ハーネス**。「PR をマージ前に軽く動作確認したい」ときの受け皿として用意した
（[`scripts/dev_server.py`](../../scripts/dev_server.py)）。

```bash
make dev-fake                       # http://127.0.0.1:8000
DEV_FAKE_OID=oid-x PORT=9000 make dev-fake
```

起動すると開発ユーザー（既定 `oid-dev-local`）が `prd_sandbox` / `prd_scrum_board`
両方の **admin** として member 済みになっているので、そのまま叩ける:

```bash
# PBI を作る → 取得する（ETag が返る）
curl -X POST localhost:8000/api/products/prd_sandbox/pbis \
  -H 'Content-Type: application/json' -d '{"title":"ためし"}'
curl localhost:8000/api/products/prd_sandbox/pbis/<返ってきた id>

# 自分の所属を見る
curl localhost:8000/api/me
```

## 仕組み

本番の入口 [`app/main.py`](../../backend/app/main.py)（`make run` / `make dev`）と
**同じ組み立てブロック**（ルータ・エラーハンドラ・OpenAPI）でアプリを組む。実物と違うのは
2点だけ:

| 層 | 本番 | dev-fake |
|:---|:---|:---|
| データ | Cosmos（`CosmosRepository`） | **`InMemoryRepository`**（プロセス内・**非永続**） |
| 認証 | Entra トークン検証（`current_user`） | 固定 oid を返すスタブ（`dependency_overrides`） |

起動時に実マイグレーション（`run_migrations`）を流すので、プロダクトは本番と同じ
`prd_sandbox` / `prd_scrum_board` になる。ハンドラ・認可・problem+json の挙動は実物を
そのまま通る。

## 制約・注意

- **データは消える。** メモリ上なので、サーバーを止めるとリセットされる。
- **これは B-14（ゲストログイン）ではない。** B-14 は本番アプリ内の env で制御される
  resolver 実装（既定 OFF・実データ経路）で、正式な「毎回サインインしない」仕組み。
  dev-fake は `dependency_overrides` に頼る**開発機だけの近道**で、本番の入口には一切
  影響しない。永続確認や本番同等の検証が要るときは B-14 ＋ Cosmos エミュレータで行う。
- **本番では絶対に使わない。** 認証を素通しするため、公開してはならない。

ハーネス自身の退行は [`backend/tests/test_dev_server.py`](../../backend/tests/test_dev_server.py)
が守る（本番の部品で組めていること・member 済みユーザーとして CRUD が通ること）。
