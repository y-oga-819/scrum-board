import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { HomePage } from './home';

describe('HomePage', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HomePage],
      providers: [provideHttpClient(), provideHttpClientTesting()],
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

  it('shows the API health status', () => {
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    httpMock.expectOne('/api/health').flush({ status: 'ok', service: 'scrum-board' });
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.status dd')?.textContent).toContain('ok');
  });
});
