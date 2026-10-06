// The two record screens: DecisionsTable (every scheduled message) and AuditTimeline.
import { Component, computed, input, output, signal } from '@angular/core';
import { AuditEntry, DecisionLabel, DecisionRow, Staff } from '../core/models';
import { SEND_STATUS, decisionOf, initials } from '../core/format';
import { KaiDatePipe, KaiDateTimePipe } from '../core/format.pipes';
import { nextId } from '../core/ids';
import { DecisionTag } from './atoms';

type Filter = 'ALL' | DecisionLabel;

@Component({
  selector: 'kai-decisions-table',
  imports: [DecisionTag, KaiDateTimePipe],
  template: `
    <div class="kai-dtable__bar">
      <div class="kai-filter" role="group" aria-label="Filter by decision">
        @for (f of filters; track f) {
          <button type="button" class="kai-filter__chip" [attr.aria-pressed]="filter() === f" (click)="filter.set(f)">
            @if (f === 'ALL') { All } @else { <kai-decision-tag [decision]="f" /> }
          </button>
        }
      </div>
      <div class="kai-check">
        <input type="checkbox" [id]="routineId" [checked]="includeRoutine()" (change)="includeRoutine.set(checked($event))" />
        <label [for]="routineId">Include routine messages</label>
      </div>
    </div>
    <p class="kai-dtable__count" aria-live="polite">{{ visible().length }} of {{ scoped().length }} scheduled messages</p>
    <div class="kai-dtable__scroll">
      @if (!visible().length) {
        <p class="kai-muted kai-dtable__empty">Nothing matches this filter.</p>
      } @else {
        <table class="kai-table">
          <thead>
            <tr>
              @for (c of cols; track c) { <th scope="col">{{ c }}</th> }
            </tr>
          </thead>
          <tbody>
            @for (r of visible(); track r.automation_id) {
              <tr>
                <td data-label="Person">
                  <button type="button" class="kai-person-link kai-person-link--sm" (click)="openMember.emit(r.member_id)">
                    {{ r.first_name }} {{ r.last_name }}
                  </button>
                </td>
                <td data-label="Message">{{ r.workflow_name }}</td>
                <td data-label="Scheduled">{{ r.scheduled_send_at | kaiDateTime }}</td>
                <td data-label="Decision"><kai-decision-tag [decision]="label(r)" /></td>
                <td data-label="Action"><code>{{ r.automation_action }}</code></td>
                <td data-label="Trigger">
                  @if (r.guardrail_trigger) { <code>{{ r.guardrail_trigger }}</code> } @else { <span class="kai-muted">—</span> }
                </td>
                <td data-label="Why">{{ r.reason }}</td>
                <td data-label="Status"><span [class]="'kai-status kai-status--' + r.send_status">{{ status(r) }}</span></td>
              </tr>
            }
          </tbody>
        </table>
      }
    </div>
  `,
  host: { class: 'kai-dtable', role: 'region', 'aria-label': 'All decisions' },
})
export class DecisionsTable {
  readonly rows = input<DecisionRow[]>([]);
  readonly openMember = output<string>();

  protected readonly filters: Filter[] = ['ALL', 'CARE', 'THANK', 'WAIT', 'WAIT·REVIEW', 'ASK'];
  protected readonly cols = ['Person', 'Message', 'Scheduled', 'Decision', 'Action', 'Trigger', 'Why', 'Status'];
  protected readonly routineId = nextId('rt');
  protected readonly filter = signal<Filter>('ALL');
  protected readonly includeRoutine = signal(false);

  protected readonly scoped = computed(() => this.rows().filter((r) => this.includeRoutine() || !+r.routine));
  protected readonly visible = computed(() =>
    this.scoped().filter((r) => this.filter() === 'ALL' || decisionOf(r) === this.filter()),
  );

  protected label = decisionOf;
  protected status(r: DecisionRow): string {
    return SEND_STATUS[r.send_status] ?? r.send_status;
  }
  protected checked(e: Event): boolean {
    return (e.target as HTMLInputElement).checked;
  }
}

/** Every agent decision and human action, newest first. People are named, never staff ids. */
@Component({
  selector: 'ol[kai-audit-timeline]',
  imports: [DecisionTag, KaiDatePipe],
  template: `
    @for (e of view(); track e.audit_id) {
      <li [class]="'kai-audit__item kai-audit__item--' + e.who">
        <span class="kai-audit__avatar" aria-hidden="true">{{ e.avatar }}</span>
        <div class="kai-audit__main">
          <p class="kai-audit__line">
            <span class="kai-audit__actor">{{ e.actorName }}</span>
            <span class="kai-audit__role"> ({{ e.who }})</span>
            <span>{{ e.what }}</span>
            @if (e.first_name && e.member_id) {
              ·
              <button type="button" class="kai-person-link kai-person-link--sm" (click)="openMember.emit(e.member_id)">
                {{ e.first_name }}
              </button>
            }
            @if (e.decision) {
              <kai-decision-tag [decision]="e.decision" />
            }
          </p>
          @if (e.scheduled) {
            <p class="kai-audit__sched"><span class="kai-eyebrow">Scheduled </span>{{ e.scheduled }}</p>
          }
          @if (e.reason) {
            <p class="kai-audit__reason">{{ e.reason }}</p>
          }
          <p class="kai-audit__meta">
            <time [attr.datetime]="e.ts">Demo date {{ e.sim_date | kaiDate: true }}</time>
            @if (e.routed_to) { · routed to {{ e.routed_to }} }
            @if (e.details?.rule) { · rule <code>{{ e.details!.rule }}</code> }
            @if (e.automation_id) { · <code>{{ e.automation_id }}</code> }
          </p>
        </div>
      </li>
    }
  `,
  host: { class: 'kai-audit', 'aria-label': 'Audit log' },
})
export class AuditTimeline {
  readonly entries = input<AuditEntry[]>([]);
  readonly staffById = input<Map<string, Staff>>(new Map());
  readonly openMember = output<string>();

  protected readonly view = computed(() =>
    this.entries().map((e) => {
      const who = e.actor_type === 'person' || e.actor_type === 'human' ? 'person' : e.actor_type === 'system' ? 'system' : 'agent';
      const actorName = this.staffById().get(e.actor)?.name ?? (e.actor === 'demo' ? 'Demo clock' : e.actor);
      const d = e.details ?? {};
      const what = e.event === 'run_finished'
        ? 'finished a run' + (d.decisions ? ` · ${d.decisions} decisions` : '')
        : e.event === 'run_started' ? 'started a run' : (e.action_taken || e.event);
      return { ...e, who, actorName, what, avatar: who === 'person' ? initials(actorName) : who === 'system' ? '∙' : 'K' };
    }),
  );
}
