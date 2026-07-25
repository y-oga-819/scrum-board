import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { HomePage } from './home';
import { AuthService } from '../auth/auth.service';

/** MSAL に触れずに HomePage を検証するためのスタブ。 */
class AuthServiceStub {
  handleRedirect = jasmine.createSpy('handleRedirect');
  displayName = () => 'テスト ユーザー';
  logout = jasmine.createSpy('logout');
}

describe('HomePage', () => {
  let httpMock: HttpTestingController;
  let authStub: AuthServiceStub;

  beforeEach(async () => {
    authStub = new AuthServiceStub();
    await TestBed.configureTestingModule({
      imports: [HomePage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: authStub },
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  /** ngOnInit が投げる 2 本（/api/health と /api/me）に既定の応答を返す。 */
  function flushInitRequests(
    me: { oid: string; displayName: string | null } = {
      oid: 'oid-from-api',
      displayName: 'テスト ユーザー',
    },
  ): void {
    httpMock.expectOne('/api/health').flush({ status: 'ok', service: 'scrum-board' });
    httpMock.expectOne('/api/me').flush(me);
  }

  it('renders the app title', () => {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    flushInitRequests();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('Scrum Board');
  });

  it('shows the signed-in user', () => {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    flushInitRequests();
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.signed-in')?.textContent).toContain('テスト ユーザー');
  });

  it('shows the API health status', () => {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    flushInitRequests();
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.status dd')?.textContent).toContain('ok');
  });

  it('shows the oid the API verified from the token (B-04 end-to-end)', () => {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    flushInitRequests({ oid: 'verified-oid-123', displayName: 'テスト ユーザー' });
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.status .oid')?.textContent).toContain('verified-oid-123');
  });

  it('signs out via AuthService', () => {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    flushInitRequests();
    const button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('.signout');
    button?.click();
    expect(authStub.logout).toHaveBeenCalled();
  });
});
