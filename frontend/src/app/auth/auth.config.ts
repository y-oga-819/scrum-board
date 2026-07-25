/**
 * MSAL（Microsoft Authentication Library）の構成。
 *
 * 提案書 08章・D-10 の方針をそのまま配線する。
 *  - App Service の Easy Auth は使わない。MSAL でサインインし、API 側で JWT を検証する。
 *  - ローカルでも本番と同じ経路を通す（リダイレクト URI は origin から導出）。
 *  - PKCE のためクライアントシークレットは持たない（SPA として登録）。
 */
import {
  BrowserCacheLocation,
  IPublicClientApplication,
  InteractionType,
  LogLevel,
  PublicClientApplication,
} from '@azure/msal-browser';
import {
  MsalGuardConfiguration,
  MsalInterceptorConfiguration,
} from '@azure/msal-angular';

import { ENTRA_PLACEHOLDER, environment } from '../../environments/environment';

/**
 * 自作 API（FastAPI）を呼ぶためのアクセストークンが要求するスコープ。
 * B-04 のトークン検証（V-4: `scp` に `access_as_user` が含まれる）と対になる。
 * Graph 用の `User.Read` では自作 API を通せない（提案書 08章）。
 */
export const API_SCOPE = `api://${environment.auth.clientId}/access_as_user`;

/**
 * サインイン時・無音復元時に共通で要求するスコープ。
 *
 * ガード（{@link msalGuardConfigFactory}）と、起動時の無音復元
 * （{@link AuthService.restoreSession}）が **この単一定義を参照**する。
 * 2 箇所にスコープが散ると片方だけ増減して同意ダイアログが再発するため、
 * 定義はここ 1 つに寄せる。
 */
export const LOGIN_SCOPES: readonly string[] = ['openid', 'profile', 'email', API_SCOPE];

/** Entra 登録が未反映（B-02 前）かどうか。ログ用途。 */
function isUnconfigured(): boolean {
  return (
    environment.auth.clientId === ENTRA_PLACEHOLDER ||
    environment.auth.tenantId === ENTRA_PLACEHOLDER
  );
}

/**
 * MSAL の `PublicClientApplication` を生成する。
 * `redirectUri` は origin から導くので、localhost と本番で同じ設定が使える。
 */
export function msalInstanceFactory(): IPublicClientApplication {
  if (isUnconfigured()) {
    // B-02 の実値に差し替えるまではサインインは通らない。原因が「設定漏れ」だと
    // すぐ分かるように、黙って 401 で詰まらせず明示的に警告する（提案書 08章）。
    console.warn(
      '[auth] Entra ID のクライアント/テナント ID が未設定です。' +
        'src/environments/environment.ts を B-02 の実値に差し替えてください。',
    );
  }

  return new PublicClientApplication({
    auth: {
      clientId: environment.auth.clientId,
      // 単一テナント（提案書 08章「外部テナントのユーザーを到達させない」）。
      authority: `https://login.microsoftonline.com/${environment.auth.tenantId}`,
      // 本番 SPA と localhost:4200 のどちらでも、いま開いている origin に戻す。
      redirectUri: window.location.origin,
      postLogoutRedirectUri: window.location.origin,
    },
    cache: {
      // トークンは永続化せずタブのセッションに限定する（XSS で盗まれる窓を狭める）。
      // タブを開き直したときの復元は localStorage ではなく、Entra 側のブラウザ
      // セッションを使った無音復元（ssoSilent）で行う（AuthService.restoreSession）。
      cacheLocation: BrowserCacheLocation.SessionStorage,
    },
    system: {
      loggerOptions: {
        logLevel: environment.production ? LogLevel.Error : LogLevel.Warning,
        piiLoggingEnabled: false,
        loggerCallback: (level, message) => {
          if (level === LogLevel.Error) {
            console.error(message);
          } else if (level === LogLevel.Warning) {
            console.warn(message);
          }
        },
      },
    },
  });
}

/**
 * ルートガードの構成。未認証ユーザーをリダイレクト方式でサインインへ送る。
 * サインイン時に API スコープへの同意も得ておく（以後 API 呼び出しが無音で通る）。
 */
export function msalGuardConfigFactory(): MsalGuardConfiguration {
  return {
    interactionType: InteractionType.Redirect,
    authRequest: {
      scopes: [...LOGIN_SCOPES],
    },
  };
}

/**
 * インターセプタの構成。`/api/*` への発信に Bearer アクセストークンを付ける。
 * これで B-04（API のトークン検証）まで端から端まで繋がる。
 */
export function msalInterceptorConfigFactory(): MsalInterceptorConfiguration {
  const protectedResourceMap = new Map<string, string[] | null>([
    // 相対パス（同一オリジン）。ヘルスチェックを含む全 /api にトークンを付ける。
    ['/api', [API_SCOPE]],
  ]);

  return {
    interactionType: InteractionType.Redirect,
    protectedResourceMap,
  };
}
