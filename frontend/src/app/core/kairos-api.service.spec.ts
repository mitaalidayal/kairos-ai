import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { firstValueFrom } from 'rxjs';
import { KairosApiService, normalizeQueueItem } from './kairos-api.service';
import { QueueItem, ThankYouRefusal } from './models';

describe('KairosApiService', () => {
  let api: KairosApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(KairosApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('logs contact with the backend field names and reports the reminder date', async () => {
    const result = firstValueFrom(api.logContact(6, 'ST13', { note: 'Called Marcus.', channel: 'Call', close: false }));
    const req = http.expectOne('/api/queue/6/contact');
    expect(req.request.body).toEqual({ staff_id: 'ST13', note: 'Called Marcus.', channel: 'Call', close_care: false });
    req.flush({ contact_id: 1, reminder: { reminder_id: 1, due_date: '2026-10-17' } });
    expect(await result).toEqual({ reminder_due: '2026-10-17', message: 'Follow-up reminder set for Oct 17' });
  });

  it('maps review choices to backend resolutions', async () => {
    const result = firstValueFrom(api.reviewItem(3, 'ST02', 'care', 'Read it. Needs a call.'));
    const req = http.expectOne('/api/queue/3/resolve');
    expect(req.request.body).toEqual({ staff_id: 'ST02', resolution: 'escalate_care', note: 'Read it. Needs a call.' });
    req.flush({ ok: true, action: 'Escalated to CARE' });
    await result;
  });

  it('turns the no-ask guardrail refusal into the offending sentence', async () => {
    const text = 'Ray, thank you for sharing your news. Would you consider giving again?';
    const result = firstValueFrom(api.approveThankYou(58, 'ST13', text));
    http.expectOne('/api/queue/58/approve').flush(
      { detail: 'a thank-you cannot contain an ask (found: "giving again")' },
      { status: 400, statusText: 'Bad Request' },
    );
    const err = (await result.catch((e) => e)) as ThankYouRefusal;
    expect(err.status).toBe(400);
    expect(err.offending).toBe('Would you consider giving again?');
  });

  it('passes other errors through as {status, detail}', async () => {
    const result = firstValueFrom(api.handover(6, 'ST09', 'ST05', ''));
    http.expectOne('/api/queue/6/reassign').flush(
      { detail: 'only the person it is assigned to, or a care lead, can hand it over' },
      { status: 400, statusText: 'Bad Request' },
    );
    expect(await result.catch((e) => e)).toEqual({
      status: 400, detail: 'only the person it is assigned to, or a care lead, can hand it over',
    });
  });

  it('reads the quoted note and contact date out of a REMINDER card', () => {
    const item = {
      kind: 'REMINDER', note: null,
      detail: 'Two weeks since your last contact on 2026-10-03: "Called Marcus. Meals Thursday."',
    } as unknown as QueueItem;
    expect(normalizeQueueItem(item)).toMatchObject({ note: 'Called Marcus. Meals Thursday.', contact_date: '2026-10-03' });
  });
});
