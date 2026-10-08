// The person profile: PersonDrawer with AttendanceStrip, SignalList, ReadText, RelationshipBar,
// PersonDecision + AgentTrace, and History.
import { Component, ElementRef, afterNextRender, computed, input, output, viewChild } from '@angular/core';
import {
  AuditEntry, MemberDecision, MemberProfile, MemberText, Signals, Staff, TraceLabel, TraceStep,
} from '../core/models';
import { SEND_STATUS, decisionOf, fmtDate, humanize } from '../core/format';
import { HumanizePipe, KaiDatePipe, KaiDateTimePipe } from '../core/format.pipes';
import { nextId } from '../core/ids';
import { DecisionTag, RelationshipBar } from './atoms';

@Component({
  selector: 'kai-attendance-strip',
  imports: [KaiDatePipe],
  template: `
    <div class="kai-att__halves">
      @for (half of halves(); track half.label) {
        <div class="kai-att__half" [class.kai-att__half--recent]="half.recent">
          <p class="kai-att__k">{{ half.label }}<strong> {{ half.count }}/8</strong></p>
          <ol class="kai-att__row">
            @for (w of half.weeks; track w.date) {
              <li class="kai-att__cell" [class.is-in]="w.attended" [class.is-out]="!w.attended"
                [title]="(w.date | kaiDate) + (w.attended ? ': attended' : ': missed')">
                <span class="kai-sr">{{ w.date | kaiDate }}, {{ w.attended ? 'attended' : 'missed' }}</span>
              </li>
            }
          </ol>
        </div>
      }
    </div>
    <figcaption class="kai-att__cap">
      <span class="kai-att__key kai-att__key--in">Attended</span>
      <span class="kai-att__key kai-att__key--out">Missed</span>
      @if (signals()?.weeks_since_last_attended) {
        <span>Last here {{ signals()!.weeks_since_last_attended }} weeks ago</span>
      }
    </figcaption>
  `,
  host: { class: 'kai-att', role: 'figure' },
})
export class AttendanceStrip {
  readonly weeks = input<{ date: string; attended: boolean }[]>([]);
  readonly signals = input<Signals | undefined>();

  protected readonly halves = computed(() => {
    const w = this.weeks();
    const half = Math.floor(w.length / 2);
    const prior = w.slice(0, half);
    const recent = w.slice(half);
    const s = this.signals();
    const count = (arr: typeof w) => arr.filter((x) => x.attended).length;
    return [
      { label: 'Earlier 8 weeks', weeks: prior, count: s?.attended_prior_8w ?? count(prior), recent: false },
      { label: 'Last 8 weeks', weeks: recent, count: s?.attended_last_8w ?? count(recent), recent: true },
    ];
  });
}

@Component({
  selector: 'kai-signal-list',
  template: `
    <dl class="kai-signals">
      @for (r of rows(); track r.k) {
        <div class="kai-signals__row" [class.is-notable]="r.notable"><dt>{{ r.k }}</dt><dd>{{ r.v }}</dd></div>
      }
    </dl>
  `,
})
export class SignalList {
  readonly profile = input.required<MemberProfile>();

  protected readonly rows = computed(() => {
    const p = this.profile();
    const s = p.signals ?? {};
    const plan = p.giving?.plan?.[0];
    const rows: { k: string; v: string; notable: boolean }[] = [];
    if (s.attendance_trend) {
      const trend = ({ down: 'Dropping', sharp_down: 'Dropping sharply', up: 'Rising', flat: 'Steady' } as Record<string, string>)[s.attendance_trend];
      rows.push({ k: 'Attendance', v: trend ?? s.attendance_trend, notable: /down/.test(s.attendance_trend) });
    }
    if (plan) {
      rows.push({
        k: 'Giving',
        v: `$${Math.round(+plan.amount)} ${String(plan.frequency).toLowerCase()} plan · ${plan.status}` +
          (plan.paused_or_canceled_at ? ` since ${fmtDate(plan.paused_or_canceled_at)}` : ''),
        notable: plan.status !== 'Active',
      });
    } else if (s.giving_status) {
      rows.push({ k: 'Giving', v: s.giving_status, notable: /pause|lapse|cancel/i.test(s.giving_status) });
    }
    for (const x of p.volunteering ?? []) {
      rows.push({
        k: 'Serving',
        v: `${x.team} · ${x.status}${x.last_served_date ? ', last served ' + fmtDate(x.last_served_date) : ''}`,
        notable: x.status !== 'Active',
      });
    }
    if ('days_since_human_contact' in s) {
      const d = s.days_since_human_contact;
      rows.push({ k: 'Last personal contact', v: d == null ? 'None logged' : `${d} days ago`, notable: d == null || d > 30 });
    }
    if (s.open_prayer_requests) {
      rows.push({
        k: 'Prayer requests',
        v: `${s.open_prayer_requests} open · latest ${s.days_since_last_prayer} days ago`,
        notable: true,
      });
    }
    if (s.tenure_months) rows.push({ k: 'With the church', v: `${Math.floor(s.tenure_months / 12)} years`, notable: false });
    return rows;
  });
}

/** One prayer request or pastoral note. Privacy decides what shows: the words, the label only, or nothing. */
@Component({
  selector: 'kai-read-text',
  imports: [HumanizePipe, KaiDatePipe],
  template: `
    @let t = text();
    <header class="kai-read__head">
      <span class="kai-read__kind">{{ t.kind }}</span>
      <span class="kai-read__date">{{ t.date | kaiDate: true }}</span>
      @if (t.status) {
        <span class="kai-read__status">{{ t.status }}</span>
      }
    </header>
    @if (!t.restricted && t.label) {
      <div class="kai-read__labels">
        <span class="kai-label-chip"><span class="kai-sr">Kairos read it as: </span>{{ t.label.sacred_type || t.label.category | humanize }}</span>
        @if (t.label.category && t.label.sacred_type) {
          <span class="kai-label-chip kai-label-chip--quiet">{{ t.label.category | humanize }}</span>
        }
        @if (t.label.injection_attempt) {
          <span class="kai-label-chip kai-label-chip--guard"
            title="The text contained an instruction aimed at the AI. It was treated as text, and the decision did not change.">
            Instruction in text ignored
          </span>
        }
      </div>
    }
    @if (t.restricted) {
      <p class="kai-read__locked kai-read__locked--consent">
        <span class="kai-lock-note__icon" aria-hidden="true"></span>
        Kairos never read this. A person will. (They didn’t consent to AI reading their requests.)
      </p>
    } @else if (!canRead() || t.text == null) {
      <p class="kai-read__locked">
        <span class="kai-lock-note__icon" aria-hidden="true"></span>
        Full {{ t.kind.startsWith('Pastoral') ? 'note' : 'request' }} is in the care record (care team only).
      </p>
    } @else {
      <blockquote class="kai-read__text">{{ t.text }}</blockquote>
    }
  `,
  host: { class: 'kai-read', role: 'article' },
})
export class ReadText {
  readonly text = input.required<MemberText>();
  readonly canRead = input(false);
}

const TRACE_STEPS: [string, string][] = [
  ['signal', 'Signal'], ['SacredMomentDetector', 'Sacred Moment Detector'], ['DecisionAgent', 'Decision'],
  ['RoutingAgent', 'Routing'], ['DraftAgent', 'Draft'], ['GuardrailAgent', 'Guardrail'],
];

interface TraceView {
  title: string;
  skipped: boolean;
  lines: string[];
  decision?: { rule: string; decision: string; action: string };
  checks?: { check: string; result: string }[];
  final?: string;
}

/** Signal → Detector → Decision → Routing → Draft → Guardrail, as a readable pipeline. */
@Component({
  selector: 'ol[kai-agent-trace]',
  imports: [DecisionTag, HumanizePipe],
  template: `
    @for (s of steps(); track s.title) {
      <li class="kai-trace__step" [class.is-skipped]="s.skipped">
        <span class="kai-trace__node" aria-hidden="true"></span>
        <div>
          <p class="kai-trace__title">{{ s.title }}</p>
          <div class="kai-trace__body">
            @if (s.skipped) {
              <span class="kai-trace__skip">{{ s.lines[0] }}</span>
            } @else {
              @for (l of s.lines; track $index) {
                <span>{{ l }}</span>
              }
              @if (s.decision) {
                <span class="kai-trace__decision">
                  <code>{{ s.decision.rule }}</code> <kai-decision-tag [decision]="s.decision.decision" />
                  <code>{{ s.decision.action }}</code>
                </span>
              }
              @for (c of s.checks; track c.check) {
                <span>{{ c.check | humanize }}: <code>{{ c.result }}</code></span>
              }
              @if (s.final) {
                <span>Final: <code>{{ s.final }}</code></span>
              }
            }
          </div>
        </div>
      </li>
    }
  `,
  host: { class: 'kai-trace', 'aria-label': 'Agent trace' },
})
export class AgentTrace {
  readonly trace = input<TraceStep[]>([]);

  protected readonly steps = computed<TraceView[]>(() => {
    const byAgent = new Map(this.trace().map((t) => [t.agent, t]));
    const labels: TraceLabel[] = byAgent.get('SacredMomentDetector')?.labels ?? [];
    return TRACE_STEPS.map(([key, title]) => {
      if (key === 'signal') {
        if (!labels.length) return { title, skipped: true, lines: ['No recent notes or requests'] };
        return {
          title, skipped: false,
          lines: labels.map((l) => {
            const kind = l.kind === 'prayer' ? 'Prayer request' : l.kind === 'note' ? 'Pastoral note' : l.kind;
            return `${kind} ${l.id}, ${fmtDate(l.on)} (${l.days_ago} days ago)${l.consent === false ? ' · no AI consent' : ''}`;
          }),
        };
      }
      const t = byAgent.get(key);
      if (!t) return { title, skipped: true, lines: ['Not needed'] };
      switch (key) {
        case 'SacredMomentDetector':
          return {
            title, skipped: false,
            lines: labels.length
              ? labels.map((l) => humanize(l.label?.sacred_type || l.label?.category || (l.consent ? 'unlabelled' : 'not read')) +
                  (l.label?.injection_attempt ? ' · instruction in text ignored' : ''))
              : ['Nothing to read'],
          };
        case 'DecisionAgent':
          return { title, skipped: false, lines: [], decision: { rule: t.rule ?? '', decision: t.decision ?? '', action: t.action ?? '' } };
        case 'RoutingAgent':
          return { title, skipped: false, lines: [t.why || t.staff_id || ''] };
        case 'DraftAgent':
          return {
            title, skipped: false,
            lines: [t.drafted === 'CARE' ? 'Private brief for the person routed' : t.drafted === 'THANK' ? 'Thank-you with no ask' : String(t.drafted)],
          };
        default:
          return { title, skipped: false, lines: [], checks: t.checks ?? [], final: t.final?.join(' · ') };
      }
    });
  });
}

@Component({
  selector: 'kai-person-decision',
  imports: [AgentTrace, DecisionTag, KaiDateTimePipe],
  template: `
    @let d = decision();
    <div class="kai-pdec__top">
      <kai-decision-tag [decision]="label()" />
      <span class="kai-pdec__status">{{ status() }}</span>
    </div>
    <p class="kai-pdec__wf">
      {{ d.workflow_name }}<span class="kai-muted"> · {{ d.scheduled_channel }}, {{ d.scheduled_send_at | kaiDateTime }}</span>
    </p>
    <p class="kai-pdec__reason">{{ d.reason }}</p>
    @if (d.injection_flag) {
      <span class="kai-label-chip kai-label-chip--guard">Instruction in text ignored · decision unchanged</span>
    }
    @if (d.trace.length) {
      <details class="kai-why">
        <summary>Agent trace · rule {{ d.rule }}</summary>
        <ol kai-agent-trace [trace]="d.trace"></ol>
      </details>
    }
  `,
  host: { class: 'kai-pdec', role: 'article' },
})
export class PersonDecision {
  readonly decision = input.required<MemberDecision>();
  protected readonly label = computed(() => decisionOf(this.decision()));
  protected readonly status = computed(() => SEND_STATUS[this.decision().send_status] ?? this.decision().send_status);
}

interface HistoryRow { when: string; text: string; kind: 'contact' | 'reminder' | 'audit' }

@Component({
  selector: 'kai-person-drawer',
  imports: [AttendanceStrip, KaiDatePipe, PersonDecision, ReadText, RelationshipBar, SignalList],
  template: `
    <aside class="kai-drawer" role="dialog" aria-modal="true" [attr.aria-labelledby]="titleId" (keydown.escape)="close.emit()">
      <header class="kai-drawer__head">
        <div>
          @if (profile(); as p) {
            <h2 class="kai-drawer__name" [id]="titleId">{{ p.member.first_name }} {{ p.member.last_name }}</h2>
            <p class="kai-drawer__meta">{{ meta() }}</p>
            @if (optins().length) {
              <p class="kai-optins">
                @for (o of optins(); track o.k) {
                  <span class="kai-optin" [class.is-on]="o.on">{{ o.k }} {{ o.on ? 'on' : 'off' }}</span>
                }
              </p>
            }
          } @else {
            <h2 class="kai-drawer__name" [id]="titleId">{{ loading() ? 'Opening profile…' : 'Profile' }}</h2>
          }
        </div>
        <button #closeBtn type="button" class="kai-icon-btn" aria-label="Close profile" (click)="close.emit()">×</button>
      </header>
      <div class="kai-drawer__body">
        @if (loading()) {
          <div class="kai-skeleton" aria-busy="true" aria-label="Loading"><span></span><span></span></div>
        } @else if (error()) {
          <p class="kai-form-error" role="alert">{{ error() }}</p>
        } @else if (profile(); as p) {
          @if (p.attendance_weeks?.length) {
            <section class="kai-drawer__sec">
              <h3 class="kai-drawer__h">Attendance</h3>
              <kai-attendance-strip [weeks]="p.attendance_weeks!" [signals]="p.signals" />
            </section>
          }
          @if (p.signals) {
            <section class="kai-drawer__sec">
              <h3 class="kai-drawer__h">Signals</h3>
              <kai-signal-list [profile]="p" />
            </section>
          }
          @if (p.texts?.length) {
            <section class="kai-drawer__sec">
              <h3 class="kai-drawer__h">What Kairos read</h3>
              <p class="kai-drawer__note">
                {{ p.viewer_can_read_text ? 'You can read these because you’re on the care team.'
                  : 'You see the label Kairos gave, not the words. Prayer requests stay with the care team.' }}
              </p>
              @for (t of p.texts; track $index) {
                <kai-read-text [text]="t" [canRead]="!!p.viewer_can_read_text" />
              }
            </section>
          }
          @if (relationships().length) {
            <section class="kai-drawer__sec">
              <h3 class="kai-drawer__h">Who knows {{ p.member.first_name || 'them' }}</h3>
              @if (relationships().length > 1) {
                <p class="kai-drawer__note">The person who knows them best gets the card, not the pastor by default.</p>
              }
              @for (r of relationships(); track r.staff_id; let first = $first) {
                <kai-relationship-bar [name]="r.name" [role]="r.role" [strengthPct]="r.strength_pct" [top]="first" />
              }
            </section>
          }
          @if (p.decisions?.length) {
            <section class="kai-drawer__sec">
              <h3 class="kai-drawer__h">Decisions</h3>
              @for (d of p.decisions; track d.automation_id) {
                <kai-person-decision [decision]="d" />
              }
            </section>
          }
          @if (history().length) {
            <section class="kai-drawer__sec">
              <h3 class="kai-drawer__h">History</h3>
              <ol class="kai-hist-list">
                @for (h of history(); track $index) {
                  <li class="kai-hist" [class.kai-hist--contact]="h.kind === 'contact'" [class.kai-hist--reminder]="h.kind === 'reminder'">
                    <span class="kai-hist__when">{{ h.when | kaiDate }}</span><span>{{ h.text }}</span>
                  </li>
                }
              </ol>
            </section>
          }
        }
      </div>
    </aside>
  `,
  host: { style: 'display: contents' },
})
export class PersonDrawer {
  readonly profile = input<MemberProfile | null>(null);
  readonly loading = input(false);
  readonly error = input<string | null>(null);
  readonly staffById = input<Map<string, Staff>>(new Map());
  readonly close = output<void>();

  protected readonly titleId = nextId('dt');
  private readonly closeBtn = viewChild.required<ElementRef<HTMLButtonElement>>('closeBtn');

  constructor() {
    afterNextRender(() => this.closeBtn().nativeElement.focus());
  }

  protected readonly meta = computed(() => {
    const m = this.profile()?.member;
    if (!m) return '';
    return [m.membership_status, m.member_since ? 'since ' + fmtDate(m.member_since, true) : null,
      m.preferred_channel ? 'prefers ' + m.preferred_channel : null].filter(Boolean).join(' · ');
  });

  protected readonly optins = computed(() => {
    const m = this.profile()?.member;
    if (!m) return [];
    return ([['Email', m.email_opt_in], ['Text', m.sms_opt_in], ['Appeals', m.appeals_opt_in]] as const)
      .filter(([, v]) => v)
      .map(([k, v]) => ({ k, on: v === 'Yes' }));
  });

  protected readonly relationships = computed(() =>
    [...(this.profile()?.relationships ?? [])].sort((a, b) => b.strength_pct - a.strength_pct),
  );

  protected readonly history = computed<HistoryRow[]>(() => {
    const p = this.profile();
    if (!p) return [];
    const name = (sid: string) => this.staffById().get(sid)?.name ?? sid;
    return [
      ...(p.contacts ?? []).map((c) => ({
        when: c.contact_date, kind: 'contact' as const,
        text: `${name(c.staff_id)} · ${c.channel}${c.note ? ': “' + c.note + '”' : ''}`,
      })),
      ...(p.reminders ?? []).map((r) => ({
        when: r.due_date, kind: 'reminder' as const,
        text: `Check-in reminder for ${name(r.staff_id)} · ${r.status}`,
      })),
      ...(p.audit ?? []).map((a: AuditEntry) => ({
        when: a.sim_date, kind: 'audit' as const,
        text: `${a.actor_type === 'human' ? name(a.actor) : a.actor}: ${a.action_taken || a.event}`,
      })),
    ];
  });
}
