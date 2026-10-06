import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
  });

  it('renders the top bar and asks the API for the summary, staff and queue', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.kai-wordmark')?.textContent).toBe('Kairos');

    const http = TestBed.inject(HttpTestingController);
    expect(http.match('/api/summary').length).toBe(1);
    expect(http.match('/api/staff/load').length).toBe(1);
    expect(http.match((r) => r.url === '/api/queue').length).toBe(1);
  });
});
