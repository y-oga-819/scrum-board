import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { HomePage } from './home';
import { AuthService } from '../auth/auth.service';
import { ProductSummary } from '../products/product.service';

/** MSAL に触れずに HomePage を検証するためのスタブ。 */
class AuthServiceStub {
  handleRedirect = jasmine.createSpy('handleRedirect');
  displayName = () => 'テスト ユーザー';
  logout = jasmine.createSpy('logout');
}

interface MeBody {
  oid: string;
  displayName: string | null;
  isGuest: boolean;
  products: ProductSummary[];
}

const SANDBOX: ProductSummary = { productId: 'prd_sandbox', name: 'サンドボックス', role: 'member' };
const SCRUM: ProductSummary = { productId: 'prd_scrum_board', name: 'スクラムボード', role: 'admin' };

describe('HomePage', () => {
  let httpMock: HttpTestingController;
  let authStub: AuthServiceStub;

  beforeEach(async () => {
    sessionStorage.clear();
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

  afterEach(() => {
    httpMock.verify();
    sessionStorage.clear();
  });

  const defaultMe: MeBody = {
    oid: 'oid-from-api',
    displayName: 'テスト ユーザー',
    isGuest: false,
    products: [SANDBOX],
  };

  /** ngOnInit が投げる 2 本（/api/health と /api/me）に既定の応答を返す。 */
  function flushInitRequests(me: MeBody = defaultMe): void {
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
    flushInitRequests({ ...defaultMe, oid: 'verified-oid-123' });
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.status .oid')?.textContent).toContain('verified-oid-123');
  });

  it('lists the products returned by /api/me (no hardcoded productId)', () => {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    flushInitRequests({ ...defaultMe, products: [SANDBOX, SCRUM] });
    fixture.detectChanges();
    const options = (fixture.nativeElement as HTMLElement).querySelectorAll(
      '.product-selector option',
    );
    expect(options.length).toBe(2);
    expect(options[0].textContent).toContain('サンドボックス');
    expect(options[1].textContent).toContain('スクラムボード');
  });

  it('defaults the selected product to the first one', () => {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    flushInitRequests({ ...defaultMe, products: [SANDBOX, SCRUM] });
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.selected-product')?.textContent).toContain('prd_sandbox');
  });

  it('switches the selected product via the selector', () => {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    flushInitRequests({ ...defaultMe, products: [SANDBOX, SCRUM] });
    fixture.detectChanges();
    const select = (fixture.nativeElement as HTMLElement).querySelector<HTMLSelectElement>(
      '.product-selector select',
    )!;
    select.value = 'prd_scrum_board';
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.selected-product')?.textContent,
    ).toContain('prd_scrum_board');
  });

  it('shows an invitation note when the user has no products', () => {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    flushInitRequests({ ...defaultMe, products: [] });
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.product-selector')).toBeNull();
    expect(compiled.querySelector('.no-products')?.textContent).toContain('属していません');
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
