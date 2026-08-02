/**
 * E2E ビルド用の設定（EX-1・D-22）。`ng build --configuration e2e` のとき
 * `fileReplacements` で `environment.ts` の代わりに使われる。
 *
 * `e2e: true` により MSAL（ガード・インターセプタ・initialize）を配線しない。
 * E2E は実サーバ + 実ブラウザで回り、実 Entra への対話サインインをヘッドレスで
 * 通せないため、認証はバックエンドの env ゲート resolver（`E2E_AUTH_BYPASS`）に委ねる。
 * `auth` はビルドを通すために形だけ残す（MSAL を配線しないので参照されない）。
 */
import { AppEnvironment } from './environment.model';

export const environment: AppEnvironment = {
  production: false,
  e2e: true,
  auth: {
    clientId: 'e2e-unused',
    tenantId: 'e2e-unused',
  },
};
