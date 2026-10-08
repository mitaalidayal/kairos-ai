// Small presentational pieces: DecisionTag, UrgencyPill, Button, EmptyState, CapacityBanner/Line,
// RelationshipBar, LoadMeter. The host element carries the design's kai-* class, so no extra wrapper.
import { Component, computed, input } from '@angular/core';
import { DecisionLabel, UrgencyLevel } from '../core/models';

const DECISION_LABEL: Record<string, string> = {
  CARE: 'Care', THANK: 'Thank', WAIT: 'Wait', ASK: 'Ask', REVIEW: 'Review', REMINDER: 'Check-in',
  'WAIT·REVIEW': 'Wait · Review',
};

/** Colour + glyph + word. Never colour alone. */
@Component({
  selector: 'kai-decision-tag',
  template: `<span class="kai-tag__glyph" aria-hidden="true"></span>{{ text() }}`,
  host: { '[class]': 'cls()' },
})
export class DecisionTag {
  readonly decision = input.required<DecisionLabel | string>();
  readonly size = input<'md' | 'lg'>('md');
  readonly label = input<string>();

  protected readonly text = computed(() => {
    const d = String(this.decision()).toUpperCase();
    return this.label() ?? DECISION_LABEL[d] ?? d;
  });
  protected readonly cls = computed(() => {
    const d = String(this.decision()).toUpperCase();
    const key = d === 'REVIEW' || d === 'WAIT·REVIEW' || d === 'WAIT-REVIEW' ? 'review' : d.toLowerCase();
    return `kai-tag kai-tag--${key}${this.size() === 'lg' ? ' kai-tag--lg' : ''}`;
  });
}

/** Gentle urgency words: urgent → Today, high → Soon, normal → When you can. */
@Component({
  selector: 'kai-urgency-pill',
  template: `
    <span class="kai-urgency__dot" aria-hidden="true"></span>
    <span class="kai-urgency__word">{{ word() }}</span>
    @if (reason()) {
      <span class="kai-urgency__reason"> · {{ reason() }}</span>
    }
  `,
  host: { '[class]': '"kai-urgency kai-urgency--" + level()' },
})
export class UrgencyPill {
  readonly level = input<UrgencyLevel>('normal');
  readonly reason = input<string>('');
  protected readonly word = computed(
    () => ({ urgent: 'Today', high: 'Soon', normal: 'When you can' })[this.level()] ?? this.level(),
  );
}

/** <button kai-button variant="primary">Label</button> */
@Component({
  selector: 'button[kai-button]',
  template: `<ng-content />`,
  host: {
    '[class]': '"kai-btn kai-btn--" + variant() + (size() === "sm" ? " kai-btn--sm" : "")',
    '[attr.type]': 'type()',
  },
})
export class Button {
  readonly variant = input<'primary' | 'secondary' | 'quiet'>('secondary');
  readonly size = input<'md' | 'sm'>('md');
  readonly type = input<'button' | 'submit'>('button');
}

@Component({
  selector: 'kai-empty-state',
  template: `
    <div class="kai-empty__art" aria-hidden="true"><span></span><span></span><span></span><i></i></div>
    <h2 class="kai-empty__title">{{ title() }}</h2>
    <p class="kai-empty__sub">{{ message() }}</p>
  `,
  host: { class: 'kai-empty' },
})
export class EmptyState {
  readonly title = input('No one needs you right now.');
  readonly message = input(
    'Kairos is watching the automations. When someone needs a person, they’ll appear here.',
  );
}

@Component({
  selector: 'kai-capacity-banner',
  template: `
    <p class="kai-capacity__line">
      <strong>{{ count() }} people need care from you this week.</strong> Your capacity is {{ capacity() }}.
    </p>
    <p class="kai-capacity__sub">
      Kairos doesn’t decide who is too busy. It shows the load so you can share it — use “Hand to…” on any
      card below the line.
    </p>
  `,
  host: { class: 'kai-capacity', role: 'note' },
})
export class CapacityBanner {
  readonly count = input.required<number>();
  readonly capacity = input.required<number>();
}

@Component({
  selector: 'kai-capacity-line',
  template: `<span class="kai-capline__label">Your week runs out here · {{ capacity() }} of {{ capacity() }}</span>`,
  host: { class: 'kai-capline', role: 'separator', 'aria-label': 'Your week runs out here' },
})
export class CapacityLine {
  readonly capacity = input.required<number>();
}

/** How well someone knows the member. The top relationship stands out. */
@Component({
  selector: 'kai-relationship-bar',
  template: `
    <div class="kai-rel__who">
      <span class="kai-rel__name">{{ name() }}</span>
      @if (role()) {
        <span class="kai-rel__role">{{ role() }}</span>
      }
      @if (top()) {
        <span class="kai-rel__badge">Knows them best</span>
      }
    </div>
    <div class="kai-rel__track" role="meter" aria-valuemin="0" aria-valuemax="100"
      [attr.aria-valuenow]="strengthPct() ?? 0" [attr.aria-label]="'How well ' + name() + ' knows them'">
      <span class="kai-rel__fill" [style.width.%]="strengthPct() ?? 0"></span>
    </div>
    <span class="kai-rel__pct">{{ strengthPct() != null ? strengthPct() + '%' : 'Not yet' }}</span>
  `,
  host: { '[class]': 'cls()' },
})
export class RelationshipBar {
  readonly name = input.required<string>();
  readonly role = input<string>('');
  readonly strengthPct = input<number | null>(null);
  readonly top = input(false);
  readonly compact = input(false);
  protected readonly cls = computed(
    () => 'kai-rel' + (this.top() ? ' kai-rel--top' : '') + (this.compact() ? ' kai-rel--compact' : ''),
  );
}

/** "3 of 4 this week", as cells. Over capacity shows in ochre: busy isn't an emergency. */
@Component({
  selector: 'kai-load-meter',
  template: `
    <span class="kai-load__cells" aria-hidden="true">
      @for (c of cells(); track $index) {
        <span class="kai-load__cell" [class.is-used]="c.used" [class.is-over]="c.over"></span>
      }
    </span>
    <span class="kai-load__text">{{ load() }} of {{ capacity() }} this week{{ hasRoom() === false ? ' · full' : '' }}</span>
  `,
  host: { '[class]': '"kai-load" + (hasRoom() === false ? " kai-load--full" : "")' },
})
export class LoadMeter {
  readonly load = input(0);
  readonly capacity = input(0);
  readonly hasRoom = input<boolean | null>(null);
  protected readonly cells = computed(() =>
    Array.from({ length: Math.max(this.capacity(), this.load()) }, (_, i) => ({
      used: i < this.load(),
      over: i >= this.capacity(),
    })),
  );
}
