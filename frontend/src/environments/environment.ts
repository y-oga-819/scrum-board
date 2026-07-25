/**
 * アプリケーション設定（フロントエンド）。
 *
 * Entra ID のアプリ登録で発行される値をここに置く。**同一のアプリ登録**を
 * ローカル（`localhost:4200`）と本番（`*.azurewebsites.net`）で共有するため、
 * `clientId` / `tenantId` は環境で分かれない。環境ごとに変わるのはリダイレクト
 * URI だが、それは実行時に `window.location.origin` から導く（`auth.config.ts`）
 * ので、この1ファイルで足りる（提案書 08章のリダイレクトURI 3種のうち、
 * 本番SPA と localhost の2つがこれで自動的に切り替わる）。
 *
 * ⚠️ 下の `clientId` / `tenantId` は **B-02（Entra ID にアプリを登録する）が発行する
 * 実値に差し替える**。差し替えるまではサインインは実際には通らない（PoC の
 * 端から端までの疎通確認は B-02 完了後）。それまでも本 PBI の実装（MSAL 配線・
 * ルートガード・トークン付与）はビルド・単体テストで検証できる。
 */
export interface AppEnvironment {
  readonly production: boolean;
  readonly auth: {
    /** Entra ID アプリ登録の「アプリケーション (クライアント) ID」。B-02 で発行。 */
    readonly clientId: string;
    /** Entra ID の「ディレクトリ (テナント) ID」。単一テナントで登録する。B-02 で発行。 */
    readonly tenantId: string;
  };
}

/** B-02 の実値に差し替えるまでのプレースホルダ。 */
export const ENTRA_PLACEHOLDER = 'REPLACE_WITH_ENTRA_VALUE_FROM_B-02';

export const environment: AppEnvironment = {
  production: true,
  auth: {
    clientId: ENTRA_PLACEHOLDER,
    tenantId: ENTRA_PLACEHOLDER,
  },
};
