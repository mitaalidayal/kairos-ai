// Date and label formatting, ported from the design system's reference bundle.
// Dates from the API are plain strings ("2026-10-04" or "2026-10-04 15:00:00") and are read as-is,
// never through the browser's timezone, so the demo clock shows the same day everywhere.
import { DecisionLabel, MemberDecision, DecisionRow } from './models';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
  'September', 'October', 'November', 'December'];
const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

interface DateParts { y: number; mo: number; d: number; hh: number | null; mm: number | null }

function parseDate(s: string | null | undefined): DateParts | null {
  if (!s) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(s);
  if (!m) return null;
  return { y: +m[1], mo: +m[2] - 1, d: +m[3], hh: m[4] != null ? +m[4] : null, mm: m[5] != null ? +m[5] : null };
}

export function fmtDate(s: string | null | undefined, withYear = false): string {
  const p = parseDate(s);
  if (!p) return s ?? '';
  return `${MONTHS[p.mo]} ${p.d}${withYear ? ', ' + p.y : ''}`;
}

export function fmtLongDate(s: string | null | undefined): string {
  const p = parseDate(s);
  if (!p) return s ?? '';
  const dt = new Date(Date.UTC(p.y, p.mo, p.d));
  return `${DAYS[dt.getUTCDay()]}, ${MONTHS_LONG[p.mo]} ${p.d}`;
}

export function fmtTime(s: string | null | undefined): string {
  const p = parseDate(s);
  if (!p || p.hh == null) return '';
  const ap = p.hh >= 12 ? 'PM' : 'AM';
  const hr = p.hh % 12 || 12;
  return `${hr}:${String(p.mm).padStart(2, '0')} ${ap}`;
}

export function fmtDateTime(s: string | null | undefined): string {
  const t = fmtTime(s);
  return fmtDate(s) + (t ? ', ' + t : '');
}

const HUMANIZE: Record<string, string> = {
  serious_illness: 'Serious health concern', grief: 'Grief or loss', family_crisis: 'Family crisis',
  job_loss: 'Job loss', housing_crisis: 'Housing crisis', homelessness_risk: 'Possible loss of housing',
  financial_hardship: 'Financial hardship', mental_health: 'Mental health struggle', sacred: 'Sacred',
  praise: 'Praise report', ambiguous: 'Unclear', routine: 'Routine', other_person: 'Someone else’s crisis',
  resolved_followup: 'Resolved', absence: 'Away',
};

export function humanize(s: string | null | undefined): string {
  if (!s) return '';
  if (HUMANIZE[s]) return HUMANIZE[s];
  const t = String(s).replace(/_/g, ' ').toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export function initials(name: string | null | undefined): string {
  return (name || '?').split(/\s+/).map((w) => w.charAt(0)).slice(0, 2).join('').toUpperCase();
}

/** "Isabella Parker (Small Group Leader)" → "Isabella Parker" */
export function staffName(label: string | null | undefined): string {
  return (label || '').replace(/\s*\(.*\)\s*$/, '');
}

export function firstName(name: string | null | undefined): string {
  return (name || '').split(' ')[0];
}

/** WAIT that needs a person reads as WAIT·REVIEW everywhere in the UI. */
export function decisionOf(r: Pick<DecisionRow | MemberDecision, 'decision' | 'requires_human_review'>): DecisionLabel {
  return r.decision === 'WAIT' && r.requires_human_review === 'Yes' ? 'WAIT·REVIEW' : r.decision;
}

export const SEND_STATUS: Record<string, string> = {
  blocked: 'Blocked', held: 'Held', replaced_pending: 'Replaced · awaiting approval', sent_mock: 'Sent',
  sent: 'Sent', released: 'Released', released_sent: 'Released · sent', replaced_sent: 'Thank-you sent',
};
