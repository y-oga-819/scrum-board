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

  it('renders the app title', () => {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    httpMock.expectOne('/api/health').flush({ status: 'ok', service: 'scrum-board' });
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('Scrum Board');
  });

  it('shows the signed-in user', () => {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    httpMock.expectOne('/api/health').flush({ status: 'ok', service: 'scrum-board' });
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.signed-in')?.textContent).toContain('テスト ユーザー');
  });

  it('shows the API health status', () => {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    httpMock.expectOne('/api/health').flush({ status: 'ok', service: 'scrum-board' });
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.status dd')?.textContent).toContain('ok');
  });

  it('signs out via AuthService', () => {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    httpMock.expectOne('/api/health').flush({ status: 'ok', service: 'scrum-board' });
    const button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('.signout');
    button?.click();
    expect(authStub.logout).toHaveBeenCalled();
  });
});
