// Top of the page: TopBar, Greeting, SummaryTile(s), and the toast region.
import { Component, computed, inject, input, output } from '@angular/core';
import { Screen, Staff, Summary } from '../core/models';
import { KaiDatePipe, KaiLongDatePipe } from '../core/format.pipes';
import { nextId } from '../core/ids';
import { ToastService } from '../core/toast.service';
import { Button, DecisionTag } from './atoms';

@Component({
  selector: 'kai-top-bar',
  imports: [Button, KaiDatePipe],
  template: `
    <div class="kai-topbar__brand">
      <span class="kai-wordmark">Kairos</span>
      <span class="kai-topbar__sub">{{ subtitle() }}</span>
    </div>
    <div class="kai-topbar__viewer">
      <label class="kai-eyebrow" [for]="selectId">Viewing as</label>
      <select class="kai-select" [id]="selectId" (change)="viewerChange.emit(asStaffId($event))">
        <option value="" [selected]="!viewer()">All staff</option>
        @for (s of staff(); track s.staff_id) {
          <option [value]="s.staff_id" [selected]="s.staff_id === viewer()">{{ s.name }} — {{ s.role }}</option>
        }
      </select>
    </div>
    <div class="kai-topbar__demo" role="group" aria-label="Demo controls">
      <span class="kai-clock" title="Simulated date for the demo">
        <span class="kai-clock__k">Demo date</span> {{ simDate() | kaiDate: true }}
      </span>
      <button kai-button variant="quiet" size="sm" (click)="advance.emit(14)">+14 days</button>
      <button kai-button variant="quiet" size="sm" (click)="rerun.emit()">Re-run agents</button>
    </div>
    <nav class="kai-tabs" aria-label="Sections">
      @for (t of tabs; track t.id) {
        <button type="button" class="kai-tabs__tab" [attr.aria-current]="screen() === t.id ? 'page' : null"
          (click)="navigate.emit(t.id)">{{ t.label }}</button>
      }
    </nav>
  `,
  host: { class: 'kai-topbar', role: 'banner' },
})
export class TopBar {
  readonly staff = input<Staff[]>([]);
  readonly viewer = input<string | null>(null);
  readonly simDate = input<string | null>(null);
  readonly screen = input<Screen>('queue');
  readonly subtitle = input('Who needs a human today?');

  readonly viewerChange = output<string | null>();
  readonly advance = output<number>();
  readonly rerun = output<void>();
  readonly navigate = output<Screen>();

  protected readonly selectId = nextId('viewer');
  protected readonly tabs: { id: Screen; label: string }[] = [
    { id: 'queue', label: 'Who needs you' },
    { id: 'decisions', label: 'All decisions' },
    { id: 'audit', label: 'Audit log' },
    { id: 'how', label: 'How Kairos decides' },
  ];

  protected asStaffId(e: Event): string | null {
    return (e.target as HTMLSelectElement).value || null;
  }
}

@Component({
  selector: 'kai-greeting',
  imports: [KaiLongDatePipe],
  template: `
    <p class="kai-eyebrow">{{ simDate() | kaiLongDate }}</p>
    <h1 class="kai-greeting__line">{{ line() }}</h1>
    @if (count()) {
      <p class="kai-greeting__sub">{{ sub() }}</p>
    }
  `,
  host: { class: 'kai-greeting' },
})
export class Greeting {
  readonly staff = input<Staff | null>(null);
  readonly count = input(0);
  readonly simDate = input<string | null>(null);

  protected readonly line = computed(() => {
    const s = this.staff();
    if (!s) return 'Here’s who needs a person today.';
    const first = s.name.split(' ')[0];
    return this.count() ? `${first}, here’s who needs you today.` : `${first}, no one needs you right now.`;
  });
  protected readonly sub = computed(() =>
    this.count() === 1
      ? 'One person. Kairos has paused their automated messages until you’ve been in touch.'
      : `${this.count()} people. Kairos has paused their automated messages until someone has been in touch.`,
  );
}

@Component({
  selector: 'kai-summary-tile',
  imports: [DecisionTag],
  template: `
    @if (decision()) {
      <kai-decision-tag [decision]="decision()!" />
    } @else {
      <span class="kai-eyebrow">{{ label() }}</span>
    }
    <span class="kai-tile__value">{{ value() }}</span>
    @if (caption()) {
      <span class="kai-tile__caption">{{ caption() }}</span>
    }
  `,
  host: { '[class]': '"kai-tile" + (emphasis() ? " kai-tile--" + emphasis() : "")' },
})
export class SummaryTile {
  readonly label = input<string>('');
  readonly decision = input<string | null>(null);
  readonly value = input<number | string>(0);
  readonly caption = input<string>('');
  readonly emphasis = input<'care' | 'quiet' | null>(null);
}

@Component({
  selector: 'kai-summary-tiles',
  imports: [SummaryTile],
  template: `
    <div class="kai-tiles__story">
      <kai-summary-tile label="Scheduled" [value]="summary().automations_total" caption="automated messages reviewed" />
      <kai-summary-tile label="Held" [value]="summary().messages_held" caption="stopped or paused before sending" />
      <kai-summary-tile label="Routed to a person" [value]="summary().care_needs_routed"
        caption="care needs sent to someone who knows them" emphasis="care" />
      <kai-summary-tile label="Passed through" [value]="summary().routine_passed"
        caption="routine messages sent untouched" emphasis="quiet" />
    </div>
    <div class="kai-tiles__decisions">
      @for (d of decisions; track d.key) {
        <kai-summary-tile [decision]="d.key" [value]="summary().counts[d.key] ?? 0" [caption]="d.caption" />
      }
    </div>
  `,
  host: {
    class: 'kai-tiles',
    role: 'region',
    '[attr.aria-label]': '"What Kairos did with " + summary().automations_total + " scheduled messages"',
  },
})
export class SummaryTiles {
  readonly summary = input.required<Summary>();
  protected readonly decisions = [
    { key: 'CARE', caption: 'blocked, a person reaches out' },
    { key: 'THANK', caption: 'ask replaced with thanks' },
    { key: 'WAIT', caption: 'held for timing or review' },
    { key: 'ASK', caption: 'sent as normal' },
  ] as const;
}

@Component({
  selector: 'kai-toast-region',
  template: `
    @for (t of toasts.toasts(); track t.id) {
      <div [class]="'kai-toast kai-toast--' + t.tone" role="status" aria-live="polite">
        <span class="kai-toast__mark" aria-hidden="true"></span>
        <div class="kai-toast__text">
          <p class="kai-toast__msg">{{ t.message }}</p>
          @if (t.detail) {
            <p class="kai-toast__detail">{{ t.detail }}</p>
          }
        </div>
        <button class="kai-icon-btn" type="button" aria-label="Dismiss" (click)="toasts.dismiss(t.id)">×</button>
      </div>
    }
  `,
  host: { class: 'kai-toast-region' },
})
export class ToastRegion {
  protected readonly toasts = inject(ToastService);
}
