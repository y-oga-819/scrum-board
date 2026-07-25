import { TestBed } from '@angular/core/testing';
import { MsalBroadcastService, MsalService } from '@azure/msal-angular';
import { AccountInfo } from '@azure/msal-browser';
import { Subject, of } from 'rxjs';

import { AuthService } from './auth.service';

const account = {
  homeAccountId: 'hid',
  localAccountId: 'lid',
  environment: 'login.microsoftonline.com',
  tenantId: 'tid',
  username: 'user@example.com',
  name: 'テスト ユーザー',
} as AccountInfo;

function setup(activeAccount: AccountInfo | null, allAccounts: AccountInfo[]) {
  const instance = {
    getActiveAccount: jasmine.createSpy('getActiveAccount').and.returnValue(activeAccount),
    getAllAccounts: jasmine.createSpy('getAllAccounts').and.returnValue(allAccounts),
    setActiveAccount: jasmine.createSpy('setActiveAccount'),
  };
  const msal = {
    instance,
    handleRedirectObservable: jasmine
      .createSpy('handleRedirectObservable')
      .and.returnValue(of(null)),
    logoutRedirect: jasmine.createSpy('logoutRedirect'),
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
    const { service } = setup(null, []);
    service.handleRedirect();
    expect(service.isAuthenticated()).toBeFalse();
    expect(service.displayName()).toBe('');
  });

  it('adopts the only cached account and exposes its display name', () => {
    const { service, instance } = setup(null, [account]);
    service.handleRedirect();
    expect(service.isAuthenticated()).toBeTrue();
    expect(service.displayName()).toBe('テスト ユーザー');
    // アクティブ未設定でも1件あれば採用してアクティブ化する。
    expect(instance.setActiveAccount).toHaveBeenCalledWith(account);
  });

  it('delegates sign-out to MSAL logoutRedirect', () => {
    const { service, msal } = setup(account, [account]);
    service.handleRedirect();
    service.logout();
    expect(msal.logoutRedirect).toHaveBeenCalledWith({ account });
  });
});
