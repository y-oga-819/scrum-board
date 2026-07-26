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
 * `clientId` / `tenantId` には **B-02（Entra ID にアプリを登録する）が発行した実値**が
 * 入っている。これらは秘密情報ではない — MSAL の仕組み上 SPA バンドルに埋め込まれ、
 * ブラウザから見える公開値である（アクセスを守るのは署名・aud・iss・scp の検証であって
 * この ID の秘匿ではない）。そのためリポジトリに直接置いてよい。
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

/** 未設定検知（ログ用途）のためのプレースホルダ。実値が入った今は一致しない。 */
export const ENTRA_PLACEHOLDER = 'REPLACE_WITH_ENTRA_VALUE_FROM_B-02';

export const environment: AppEnvironment = {
  production: true,
  auth: {
    // B-02 で発行した実値（単一アプリ登録を localhost と本番で共有）。公開値。
    clientId: 'dd05674f-075b-4468-be25-83e890670078',
    tenantId: '075f0018-3389-43f4-9bae-fe99eb51040a',
  },
};
