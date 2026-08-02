/**
 * 環境設定の型と定数（フロントエンド）。
 *
 * ここは **`fileReplacements` の対象にしない**共有モジュール。`environment.ts` と
 * `environment.e2e.ts` の両方がこの型を import するため、実体（`environment` 定数）を
 * 差し替えても型定義は 1 か所に保てる（e2e ビルドで型の自己参照が起きない — EX-1）。
 */

export interface AppEnvironment {
  readonly production: boolean;
  /**
   * E2E ビルドの旗（EX-1・D-22）。真のとき MSAL（ガード・インターセプタ・initialize）を
   * 配線しない。E2E は実サーバ + 実ブラウザで回り、実 Entra への対話サインインを
   * ヘッドレスで通せないため、認証はバックエンドの env ゲート resolver に委ねる。
   * 本番／通常ビルドでは常に `false` で、この分岐は静的に落ちて MSAL 無効化コードが
   * バンドルに残らない（`fileReplacements` で `environment.e2e.ts` に差し替える）。
   */
  readonly e2e: boolean;
  readonly auth: {
    /** Entra ID アプリ登録の「アプリケーション (クライアント) ID」。B-02 で発行。 */
    readonly clientId: string;
    /** Entra ID の「ディレクトリ (テナント) ID」。単一テナントで登録する。B-02 で発行。 */
    readonly tenantId: string;
  };
}

/** 未設定検知（ログ用途）のためのプレースホルダ。実値が入った今は一致しない。 */
export const ENTRA_PLACEHOLDER = 'REPLACE_WITH_ENTRA_VALUE_FROM_B-02';
