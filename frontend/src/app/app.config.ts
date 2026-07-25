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
  API_SCOPE,
  msalGuardConfigFactory,
  msalInstanceFactory,
  msalInterceptorConfigFactory,
} from './auth/auth.config';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    // MsalInterceptor は DI 経由で登録するため withInterceptorsFromDi() が要る。
    provideHttpClient(withInterceptorsFromDi()),

    // --- MSAL（認証）配線 ---
    { provide: MSAL_INSTANCE, useFactory: msalInstanceFactory },
    {
      provide: MSAL_GUARD_CONFIG,
      useFactory: msalGuardConfigFactory,
      deps: [API_SCOPE],
    },
    {
      provide: MSAL_INTERCEPTOR_CONFIG,
      useFactory: msalInterceptorConfigFactory,
      deps: [API_SCOPE],
    },
    MsalService,
    MsalGuard,
    MsalBroadcastService,
    // /api/* への発信に Bearer アクセストークンを付ける（→ B-04）。
    { provide: HTTP_INTERCEPTORS, useClass: MsalInterceptor, multi: true },

    // MSAL v3+ は利用前に initialize() の完了が必要。ブートストラップを
    // ここで待たせ、ガードやインターセプタが確実に初期化済みのインスタンスを使う。
    provideAppInitializer(() => firstValueFrom(inject(MsalService).initialize())),
  ],
};
