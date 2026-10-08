// The Human Attention Queue: AttentionQueue → QueueCard (CARE · THANK · REVIEW · REMINDER),
// with BlockedMessage and PrivateBrief inside each card.
import { Component, ElementRef, computed, inject, input, linkedSignal, output, signal, viewChild } from '@angular/core';
import { Automation, QueueItem, QueueKind, Staff, ThankYouRefusal } from '../core/models';
import { KaiDatePipe, KaiDateTimePipe } from '../core/format.pipes';
import { staffName } from '../core/format';
import { KairosStore, errText } from '../core/kairos-store';
import { Button, CapacityBanner, CapacityLine, DecisionTag, EmptyState, UrgencyPill } from './atoms';
import { HandoverPicker, LogContactForm, ReviewActions, ThankYouEditor } from './card-forms';

/** One stopped automated message: struck through in the card's colour, with a rotated stamp. */
@Component({
  selector: 'li[kai-blocked-message]',
  imports: [KaiDateTimePipe],
  template: `
    <div class="kai-blocked__meta">
      <span class="kai-blocked__wf">{{ automation().workflow_name }}</span>
      <span class="kai-blocked__when">
        {{ automation().channel ? automation().channel + ' · ' : '' }}was set for {{ automation().scheduled_send_at | kaiDateTime }}
      </span>
    </div>
    <p class="kai-blocked__body"><s><span class="kai-sr">Would have said: </span>{{ automation().draft_summary }}</s></p>
    <span class="kai-blocked__stamp">{{ verb() }}</span>
  `,
  host: { '[class]': '"kai-blocked kai-blocked--" + tone()' },
})
export class BlockedMessage {
  readonly automation = input.required<Automation>({ alias: 'kai-blocked-message' });
  readonly verb = input('Stopped');
  readonly tone = input('stopped');
}

@Component({
  selector: 'kai-private-brief',
  template: `
    <details class="kai-brief">
      <summary><span>Private brief</span><span class="kai-brief__hint">only for you</span></summary>
      <div class="kai-brief__body">
        @if (head()) {
          <p class="kai-brief__head">{{ head() }}</p>
        }
        @for (l of lines(); track $index) {
          <p>{{ l }}</p>
        }
      </div>
    </details>
  `,
})
export class PrivateBrief {
  readonly draft = input('');
  private readonly all = computed(() => this.draft().split('\n'));
  protected readonly head = computed(() => (/^PRIVATE BRIEF/i.test(this.all()[0] ?? '') ? this.all()[0] : null));
  protected readonly lines = computed(() => this.all().slice(this.head() ? 1 : 0).filter(Boolean));
}

const KIND_COPY = {
  CARE: { stopped: 'Kairos stopped', verb: 'Stopped', primary: 'Log what happened' },
  THANK: { stopped: 'Kairos replaced', verb: 'Replaced', primary: 'Review thank-you' },
  REVIEW: { stopped: 'Kairos is holding', verb: 'Held', primary: 'Review' },
  REMINDER: { stopped: 'Still paused', verb: 'Paused', primary: 'Log check-in' },
} as const;

/**
 * One card in the queue. It opens its forms in place and runs the action through KairosStore,
 * so it can show `submitting` and the backend's refusal right inside the form.
 */
@Component({
  selector: 'kai-queue-card',
  imports: [
    BlockedMessage, Button, DecisionTag, HandoverPicker, KaiDatePipe, LogContactForm, PrivateBrief, ReviewActions,
    ThankYouEditor, UrgencyPill,
  ],
  template: `
    @let it = item();
    <article [class]="'kai-card kai-card--' + kindClass()" [class.is-leaving]="leaving()"
      [attr.aria-labelledby]="'kai-h-' + it.item_id">
      <div class="kai-card__top">
        <kai-decision-tag [decision]="it.kind" />
        <kai-urgency-pill [level]="it.urgency_level" [reason]="it.urgency_reason" />
      </div>
      <h3 class="kai-card__headline" [id]="'kai-h-' + it.item_id">{{ it.headline }}</h3>
      <button type="button" class="kai-person-link" (click)="openMember.emit(it.member_id)">
        {{ it.first_name }} {{ it.last_name }}<span class="kai-sr">, open profile</span>
      </button>
      <p class="kai-card__summary">{{ it.summary }}</p>
      @if (it.reassigned_from_label) {
        <p class="kai-card__handed">Handed over from {{ it.reassigned_from_label }}</p>
      }
      @if (it.kind === 'REMINDER' && it.note) {
        <blockquote class="kai-card__quote">
          <p>{{ it.note }}</p>
          <footer>Your note, {{ it.contact_date || it.created_at | kaiDate }}</footer>
        </blockquote>
      }
      @if (it.automations.length) {
        <section class="kai-card__stopped" [attr.aria-label]="stoppedLabel()">
          <p class="kai-eyebrow">{{ stoppedLabel() }}</p>
          <ul class="kai-blocked-list">
            @for (a of it.automations; track a.automation_id) {
              <li [kai-blocked-message]="a" [verb]="copy().verb" [tone]="kindClass()"></li>
            }
          </ul>
        </section>
      }
      @if (it.kind === 'CARE' && it.draft) {
        <kai-private-brief [draft]="it.draft" />
      }
      <div class="kai-card__route">
        <p>
          <span class="kai-card__route-k">For </span>{{ assignee() || 'Unassigned' }}
          @if (it.why.strength_pct != null) {
            <span class="kai-card__route-why">
              · {{ it.why.is_top ? 'knows ' + (it.first_name || 'them') + ' best, ' : '' }}{{ it.why.strength_pct }}%{{
                it.why.last_contact ? ' · last in touch ' + it.why.last_contact : '' }}
            </span>
          }
        </p>
        @if (it.detail) {
          <details class="kai-why"><summary>Why Kairos did this</summary><p>{{ it.detail }}</p></details>
        }
      </div>
      <div class="kai-card__actions">
        <button #primaryBtn kai-button variant="primary" [attr.aria-expanded]="open() === 'primary'"
          (click)="toggle('primary')">{{ copy().primary }}</button>
        <button kai-button variant="secondary" [attr.aria-expanded]="open() === 'hand'" (click)="toggle('hand')">
          Hand to…
        </button>
      </div>
      <div #panel class="kai-card__panel">
        @switch (open()) {
          @case ('primary') {
            @switch (it.kind) {
              @case ('THANK') {
                <kai-thank-you-editor [item]="it" [submitting]="submitting()" [error]="error()" [offending]="offending()"
                  (approveThanks)="run(store.approveThankYou(it, $event.text))" (cancel)="close()" />
              }
              @case ('REVIEW') {
                <kai-review-actions [item]="it" [submitting]="submitting()" [error]="error()"
                  (review)="run(store.review(it, $event.action, $event.note))" (cancel)="close()" />
              }
              @default {
                <kai-log-contact-form [item]="it" [submitting]="submitting()" [error]="error()"
                  (logContact)="run(store.logContact(it, $event))" (cancel)="close()" />
              }
            }
          }
          @case ('hand') {
            <kai-handover-picker [item]="it" [submitting]="submitting()" [error]="error()"
              (handover)="run(store.handover(it, $event.to_staff_id, $event.reason))" (cancel)="close()" />
          }
        }
      </div>
    </article>
  `,
  host: { style: 'display: block' },
})
export class QueueCard {
  protected readonly store = inject(KairosStore);
  readonly item = input.required<QueueItem>();
  readonly leaving = input(false);
  readonly openMember = output<string>();

  protected readonly open = signal<'primary' | 'hand' | null>(null);
  protected readonly submitting = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly offending = signal<string | null>(null);
  private readonly panel = viewChild.required<ElementRef<HTMLElement>>('panel');
  private readonly primaryBtn = viewChild.required<Button, ElementRef<HTMLButtonElement>>('primaryBtn', {
    read: ElementRef,
  });

  protected readonly kindClass = computed(() => this.item().kind.toLowerCase());
  protected readonly copy = computed(() => KIND_COPY[this.item().kind] ?? KIND_COPY.CARE);
  protected readonly assignee = computed(() => staffName(this.item().staff_label));
  protected readonly stoppedLabel = computed(() => {
    const n = this.item().automations.length;
    return `${this.copy().stopped} ${n === 1 ? 'one automated message' : n + ' automated messages'}`;
  });

  protected toggle(which: 'primary' | 'hand'): void {
    this.error.set(null);
    this.offending.set(null);
    this.open.update((o) => (o === which ? null : which));
    if (this.open()) {
      setTimeout(() => this.panel().nativeElement.querySelector<HTMLElement>('textarea, input')?.focus());
    }
  }

  protected close(): void {
    this.open.set(null);
    this.primaryBtn().nativeElement.focus();
  }

  protected async run(action: Promise<void>): Promise<void> {
    this.submitting.set(true);
    this.error.set(null);
    this.offending.set(null);
    try {
      await action;
      this.open.set(null);
    } catch (e) {
      const refusal = e as ThankYouRefusal;
      this.error.set(refusal.offending ? refusal.detail : errText(e));
      this.offending.set(refusal.offending ?? null);
      setTimeout(() => this.panel().nativeElement.querySelector<HTMLElement>('[role=alert]')?.focus());
    } finally {
      this.submitting.set(false);
    }
  }
}

const KIND_ORDER: QueueKind[] = ['CARE', 'REMINDER', 'REVIEW', 'THANK'];
const KIND_LABEL: Record<QueueKind, string> = { CARE: 'Care', REMINDER: 'Check-in', REVIEW: 'Review', THANK: 'Thank' };

/**
 * The queue, in the backend's order (care and due follow-ups first, most urgent first).
 * Filter chips narrow it by kind; only kinds in the queue get a chip. When the viewer has more
 * care cards than their weekly capacity, a banner and a dashed line show where their week runs out.
 */
@Component({
  selector: 'kai-attention-queue',
  imports: [CapacityBanner, CapacityLine, DecisionTag, EmptyState, QueueCard],
  template: `
    @if (loading()) {
      <div class="kai-skeleton" aria-busy="true" aria-label="Loading"><span></span><span></span><span></span></div>
    } @else if (error()) {
      <p class="kai-form-error" role="alert">{{ error() }}</p>
    } @else if (!items().length) {
      <kai-empty-state />
    } @else {
      @if (kinds().length > 1) {
        <div class="kai-filter" role="group" aria-label="Show only">
          <button type="button" class="kai-filter__chip" [attr.aria-pressed]="active() === 'ALL'" (click)="filter.set('ALL')">
            All · {{ items().length }}
          </button>
          @for (k of kinds(); track k.kind) {
            <button type="button" class="kai-filter__chip" [attr.aria-pressed]="active() === k.kind" (click)="filter.set(k.kind)">
              <kai-decision-tag [decision]="k.kind" [label]="k.label + ' · ' + k.count" />
            </button>
          }
        </div>
      }
      @if (over()) {
        <kai-capacity-banner [count]="careCount()" [capacity]="capacity()!" />
      }
      <ol class="kai-queue__list">
        @for (it of visible(); track it.item_id; let i = $index) {
          <li><kai-queue-card [item]="it" [leaving]="leaving().has(it.item_id)" (openMember)="openMember.emit($event)" /></li>
          @if (over() && i === capIndex()) {
            <li class="kai-queue__cap"><kai-capacity-line [capacity]="capacity()!" /></li>
          }
        }
      </ol>
    }
  `,
  host: { class: 'kai-queue', role: 'region', 'aria-label': 'Human attention queue' },
})
export class AttentionQueue {
  readonly items = input<QueueItem[]>([]);
  readonly viewer = input<Staff | null>(null);
  readonly loading = input(false);
  readonly error = input<string | null>(null);
  readonly leaving = input<ReadonlySet<number>>(new Set());
  readonly openMember = output<string>();

  /** Back to All whenever the viewer changes. */
  protected readonly filter = linkedSignal<Staff | null, 'ALL' | QueueKind>({ source: this.viewer, computation: () => 'ALL' });
  protected readonly kinds = computed(() =>
    KIND_ORDER.map((kind) => ({ kind, label: KIND_LABEL[kind], count: this.items().filter((i) => i.kind === kind).length }))
      .filter((k) => k.count > 0),
  );
  /** If the last card of the chosen kind is done, fall back to All. */
  protected readonly active = computed(() => {
    const f = this.filter();
    return f === 'ALL' || this.kinds().some((k) => k.kind === f) ? f : 'ALL';
  });
  protected readonly visible = computed(() =>
    this.active() === 'ALL' ? this.items() : this.items().filter((i) => i.kind === this.active()),
  );

  protected readonly capacity = computed(() => {
    const v = this.viewer();
    return v ? Number(v.weekly_care_capacity) || null : null;
  });
  /** Capacity counts care work (CARE + due check-ins), like the backend's load, whatever the filter. */
  protected readonly careCount = computed(() => this.items().filter(isCare).length);
  protected readonly over = computed(() => this.capacity() != null && this.careCount() > this.capacity()!);
  /** Where the line goes in the visible list: after the capacity-th care card. */
  protected readonly capIndex = computed(() => {
    const idx = this.visible().flatMap((it, i) => (isCare(it) ? [i] : []));
    return idx[(this.capacity() ?? 0) - 1] ?? -1;
  });
}

function isCare(it: QueueItem): boolean {
  return it.kind === 'CARE' || it.kind === 'REMINDER';
}
