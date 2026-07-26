import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { App } from './app';
import { routes } from './app.routes';
import { AuthService } from './auth/auth.service';

/** MSAL に触れずに App を検証するためのスタブ。 */
class AuthServiceStub {
  handleRedirect = vi.fn(() => of(null));
  restoreSession = vi.fn();
  displayName = () => 'テスト ユーザー';
  logout = vi.fn();
}

describe('App', () => {
  let authStub: AuthServiceStub;

  beforeEach(async () => {
    authStub = new AuthServiceStub();
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideRouter(routes),
        { provide: AuthService, useValue: authStub },
      ],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('processes the sign-in redirect on init', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    expect(authStub.handleRedirect).toHaveBeenCalled();
  });

  it('attempts a silent session restore after the redirect completes', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    // handleRedirect() の完了後に無音復元が走る（スタブは of(null) で即完了）。
    expect(authStub.restoreSession).toHaveBeenCalled();
  });
});
