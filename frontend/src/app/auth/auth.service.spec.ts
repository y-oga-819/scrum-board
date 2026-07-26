import { TestBed } from '@angular/core/testing';
import { MsalBroadcastService, MsalService } from '@azure/msal-angular';
import {
  AccountInfo,
  AuthenticationResult,
  InteractionRequiredAuthError,
} from '@azure/msal-browser';
import { Observable, Subject, of, throwError } from 'rxjs';

import { AuthService } from './auth.service';

const account = {
  homeAccountId: 'hid',
  localAccountId: 'lid',
  environment: 'login.microsoftonline.com',
  tenantId: 'tid',
  username: 'user@example.com',
  name: 'テスト ユーザー',
} as AccountInfo;

interface SetupOptions {
  /** 初期のアクティブアカウント（キャッシュ済み）。 */
  activeAccount?: AccountInfo | null;
  /** getAllAccounts() が返すアカウント一覧。 */
  allAccounts?: AccountInfo[];
  /** ssoSilent の応答（成功なら結果、失敗なら throwError）。 */
  ssoSilent$?: Observable<AuthenticationResult>;
}

function setup(options: SetupOptions = {}) {
  const { activeAccount = null, allAccounts = [], ssoSilent$ = of(null as never) } = options;

  // setActiveAccount が getActiveAccount に反映される状態付きフェイク。
  let active: AccountInfo | null = activeAccount;
  const instance = {
    getActiveAccount: () => active,
    getAllAccounts: () => allAccounts,
    setActiveAccount: vi.fn((a: AccountInfo) => {
      active = a;
    }),
  };
  const msal = {
    instance,
    handleRedirectObservable: vi.fn(() => of(null)),
    ssoSilent: vi.fn(() => ssoSilent$),
    logoutRedirect: vi.fn(),
  };
  const broadcast = {
    msalSubject$: new Subject(),
    inProgress$: new Subject(),
  };

  TestBed.configureTestingModule({
    providers: [
      { provide: MsalService, useValue: msal },
      { provide: MsalBroadcastService, useValue: broadcast },
    ],
  });

  return { service: TestBed.inject(AuthService), msal, instance };
}

describe('AuthService', () => {
  it('reports not authenticated when there is no account', () => {
    const { service } = setup();
    service.handleRedirect().subscribe();
    expect(service.isAuthenticated()).toBe(false);
    expect(service.displayName()).toBe('');
  });

  it('adopts the only cached account and exposes its display name', () => {
    const { service, instance } = setup({ allAccounts: [account] });
    service.handleRedirect().subscribe();
    expect(service.isAuthenticated()).toBe(true);
    expect(service.displayName()).toBe('テスト ユーザー');
    // アクティブ未設定でも1件あれば採用してアクティブ化する。
    expect(instance.setActiveAccount).toHaveBeenCalledWith(account);
  });

  it('delegates sign-out to MSAL logoutRedirect', () => {
    const { service, msal } = setup({ activeAccount: account, allAccounts: [account] });
    service.handleRedirect().subscribe();
    service.logout();
    expect(msal.logoutRedirect).toHaveBeenCalledWith({ account });
  });

  describe('restoreSession', () => {
    it('restores an existing account without calling ssoSilent', () => {
      const { service, msal, instance } = setup({ allAccounts: [account] });
      service.restoreSession();
      expect(msal.ssoSilent).not.toHaveBeenCalled();
      expect(instance.setActiveAccount).toHaveBeenCalledWith(account);
      expect(service.isAuthenticated()).toBe(true);
    });

    it('signs in silently when no account is cached', () => {
      const { service, msal, instance } = setup({
        allAccounts: [],
        ssoSilent$: of({ account } as AuthenticationResult),
      });
      service.restoreSession();
      expect(msal.ssoSilent).toHaveBeenCalled();
      expect(instance.setActiveAccount).toHaveBeenCalledWith(account);
      expect(service.isAuthenticated()).toBe(true);
      expect(service.displayName()).toBe('テスト ユーザー');
    });

    it('stays signed out when ssoSilent needs interaction (no error thrown)', () => {
      // vi.spyOn は既定で本物を呼ぶため、テスト中の console.error は握りつぶす（jasmine の spyOn 相当）。
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {
        /* 出力を抑止するだけ */
      });
      const { service } = setup({
        allAccounts: [],
        ssoSilent$: throwError(
          () => new InteractionRequiredAuthError('interaction_required', 'test-correlation-id'),
        ),
      });
      expect(() => service.restoreSession()).not.toThrow();
      expect(service.isAuthenticated()).toBe(false);
      // 対話が必要なだけなので、これはエラーログを出さずに握りつぶす。
      expect(consoleError).not.toHaveBeenCalled();
    });
  });
});
