import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
  provideZoneChangeDetection,
} from '@angular/core';
import { provideRouter } from '@angular/router';
import {
  HTTP_INTERCEPTORS,
  provideHttpClient,
  withInterceptorsFromDi,
} from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import {
  MSAL_GUARD_CONFIG,
  MSAL_INSTANCE,
  MSAL_INTERCEPTOR_CONFIG,
  MsalBroadcastService,
  MsalGuard,
  MsalInterceptor,
  MsalService,
} from '@azure/msal-angular';

import { routes } from './app.routes';
import {
  msalGuardConfigFactory,
  msalInstanceFactory,
  msalInterceptorConfigFactory,
} from './auth/auth.config';
import { environment } from '../environments/environment';

// E2E ビルドでは MSAL を一切配線しない（EX-1・D-22）。実 Entra への対話サインインは
// ヘッドレスで通せないため、ガード・インターセプタ・initialize() を外し、認証は
// バックエンドの env ゲート resolver に委ねる。本番／通常ビルドでは environment.e2e が
// 静的に false なので、この配列は空になり MSAL 無効化コードはバンドルに残らない。
const msalProviders = environment.e2e
  ? []
  : [
      { provide: MSAL_INSTANCE, useFactory: msalInstanceFactory },
      { provide: MSAL_GUARD_CONFIG, useFactory: msalGuardConfigFactory },
      { provide: MSAL_INTERCEPTOR_CONFIG, useFactory: msalInterceptorConfigFactory },
      MsalService,
      MsalGuard,
      MsalBroadcastService,
      // /api/* への発信に Bearer アクセストークンを付ける（→ B-04）。
      { provide: HTTP_INTERCEPTORS, useClass: MsalInterceptor, multi: true },
      // MSAL v3+ は利用前に initialize() の完了が必要。ブートストラップを
      // ここで待たせ、ガードやインターセプタが確実に初期化済みのインスタンスを使う。
      provideAppInitializer(() => firstValueFrom(inject(MsalService).initialize())),
    ];

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    // MsalInterceptor は DI 経由で登録するため withInterceptorsFromDi() が要る。
    provideHttpClient(withInterceptorsFromDi()),

    // --- MSAL（認証）配線。E2E ビルドでは空（上記コメント参照） ---
    ...msalProviders,
  ],
};
