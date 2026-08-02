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
 *
 * 型（`AppEnvironment`）と `ENTRA_PLACEHOLDER` は `environment.model.ts` にあり、e2e ビルドの
 * `fileReplacements` 対象外。ここは実体（`environment` 定数）だけを持つ（EX-1・D-22）。
 */
import { AppEnvironment } from './environment.model';

export const environment: AppEnvironment = {
  production: true,
  e2e: false,
  auth: {
    // B-02 で発行した実値（単一アプリ登録を localhost と本番で共有）。公開値。
    clientId: 'dd05674f-075b-4468-be25-83e890670078',
    tenantId: '075f0018-3389-43f4-9bae-fe99eb51040a',
  },
};
