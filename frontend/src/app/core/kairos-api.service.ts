import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, map, throwError } from 'rxjs';
import {
  ApiError, AuditEntry, DecisionRow, MemberProfile, QueueItem, ReviewAction, Staff, Summary, ThankYouRefusal,
} from './models';
import { fmtDate } from './format';

/** The design's review choices → the backend's `resolution` values. */
const RESOLUTION: Record<ReviewAction, string> = { hold: 'keep_hold', care: 'escalate_care', release: 'release' };

export const REVIEW_MESSAGE: Record<ReviewAction, string> = {
  hold: 'Still holding. The message stays paused.',
  care: 'Now a care card for the person who knows them best',
  release: 'Released. The message will send as scheduled.',
};

/**
 * The single data layer (Kairos.data in the design bundle), against the FastAPI backend.
 * Every write needs `staff_id`: the named person taking the action.
 * Every failure is re-thrown as `ApiError {status, detail}`.
 */
@Injectable({ providedIn: 'root' })
export class KairosApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api';

  getSummary(): Observable<Summary> {
    return this.get<Summary>('/summary');
  }

  getStaffLoad(): Observable<Staff[]> {
    return this.get<Staff[]>('/staff/load');
  }

  getQueue(staffId: string | null): Observable<QueueItem[]> {
    const params = staffId ? new HttpParams().set('staff_id', staffId) : undefined;
    return this.get<QueueItem[]>('/queue', params).pipe(map((items) => items.map(normalizeQueueItem)));
  }

  getMember(memberId: string, viewer: string | null): Observable<MemberProfile> {
    const params = viewer ? new HttpParams().set('viewer', viewer) : undefined;
    return this.get<MemberProfile>(`/members/${encodeURIComponent(memberId)}`, params);
  }

  /** Every decision, routine ones included; the table filters on the client. */
  getDecisions(): Observable<DecisionRow[]> {
    return this.get<DecisionRow[]>('/decisions', new HttpParams().set('include_routine', true));
  }

  getAudit(limit = 200): Observable<AuditEntry[]> {
    return this.get<AuditEntry[]>('/audit', new HttpParams().set('limit', limit));
  }

  logContact(itemId: number, staffId: string, body: { note: string; channel: string; close: boolean })
    : Observable<{ reminder_due: string | null; message: string }> {
    return this.post<{ reminder: { due_date: string } | null }>(`/queue/${itemId}/contact`, {
      staff_id: staffId, note: body.note, channel: body.channel, close_care: body.close,
    }).pipe(map((r) => {
      const due = r.reminder?.due_date ?? null;
      return { reminder_due: due, message: due ? `Follow-up reminder set for ${fmtDate(due)}` : 'Care need closed' };
    }));
  }

  /** Rejects with `ThankYouRefusal` when the guardrail finds an ask in the note. */
  approveThankYou(itemId: number, staffId: string, text: string): Observable<{ ok: true }> {
    return this.post<{ ok: true }>(`/queue/${itemId}/approve`, { staff_id: staffId, draft: text }).pipe(
      catchError((e: ApiError) => throwError(() => asRefusal(e, text) ?? e)),
    );
  }

  reviewItem(itemId: number, staffId: string, action: ReviewAction, note: string): Observable<{ message: string }> {
    return this.post<{ action: string }>(`/queue/${itemId}/resolve`, {
      staff_id: staffId, resolution: RESOLUTION[action], note,
    }).pipe(map(() => ({ message: REVIEW_MESSAGE[action] })));
  }

  /** `staffId` is the person handing over: the current assignee, or a care lead. */
  handover(itemId: number, staffId: string, toStaffId: string, reason: string): Observable<{ to: string }> {
    return this.post<{ to: string }>(`/queue/${itemId}/reassign`, { staff_id: staffId, to_staff_id: toStaffId, note: reason });
  }

  /** Demo clock: "+14 days". Follow-up reminders that come due re-enter the queue. */
  advanceDays(days: number): Observable<{ sim_date: string }> {
    return this.post<{ sim_date: string }>('/clock/advance', { days });
  }

  /** Demo reset: "Re-run agents" over every scheduled message. */
  reset(): Observable<unknown> {
    return this.post('/run', {});
  }

  private get<T>(path: string, params?: HttpParams): Observable<T> {
    return this.http.get<T>(this.base + path, { params }).pipe(catchError(toApiError));
  }

  private post<T>(path: string, body: unknown): Observable<T> {
    return this.http.post<T>(this.base + path, body).pipe(catchError(toApiError));
  }
}

function toApiError(e: HttpErrorResponse): Observable<never> {
  const raw = e.error?.detail ?? e.error ?? e.message;
  const detail = typeof raw === 'string' ? raw
    : Array.isArray(raw) ? raw.map((x) => x?.msg ?? String(x)).join('; ')
    : e.status === 0 ? 'Kairos can’t reach the server. Is the backend running?' : JSON.stringify(raw);
  return throwError(() => ({ status: e.status, detail } satisfies ApiError));
}

/** The backend refuses with: a thank-you cannot contain an ask (found: "give again"). */
function asRefusal(e: ApiError, text: string): ThankYouRefusal | null {
  const m = /cannot contain an ask \(found: "(.+)"\)/i.exec(e.detail ?? '');
  if (!m) return null;
  const found = m[1].toLowerCase();
  const sentence = text.split(/(?<=[.?!])\s+|\n+/).find((s) => s.toLowerCase().includes(found));
  return { status: e.status, detail: 'This thank-you includes an ask.', offending: (sentence ?? m[1]).trim() };
}

/**
 * Fill in what the cards need but the backend only puts in prose.
 * REMINDER detail reads: Two weeks since your last contact on 2026-10-03: "Called Marcus…"
 */
export function normalizeQueueItem(item: QueueItem): QueueItem {
  if (item.kind !== 'REMINDER') return item;
  const m = /last contact on (\d{4}-\d{2}-\d{2}): "([\s\S]*)"$/.exec(item.detail ?? '');
  return m ? { ...item, contact_date: m[1], note: item.note ?? m[2] } : item;
}
