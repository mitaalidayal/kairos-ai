// The forms that open inside a queue card: LogContactForm, ThankYouEditor, ReviewActions, HandoverPicker.
// Each is presentational: it emits what the person chose; the card runs the action and passes back
// `submitting` and `error`.
import { Component, computed, input, linkedSignal, output, signal } from '@angular/core';
import { QueueItem, ReviewAction } from '../core/models';
import { nextId } from '../core/ids';
import { Button, LoadMeter, RelationshipBar } from './atoms';

const MIN_NOTE = 3; // the backend requires a short note for every human action

@Component({
  selector: 'kai-log-contact-form',
  imports: [Button],
  template: `
    <form class="kai-form" [attr.aria-label]="'Log what happened with ' + first()" (submit)="submit($event)">
      <div class="kai-field">
        <label class="kai-field__label" [for]="ids.note">What happened?</label>
        <textarea class="kai-input" rows="3" [id]="ids.note" [attr.aria-describedby]="ids.hint"
          [placeholder]="'Called ' + first() + '. '" [value]="note()" (input)="note.set(value($event))"></textarea>
        <p class="kai-field__hint" [id]="ids.hint">
          A sentence is enough. It stays in the care record, and Kairos will quote it back to you when it’s time
          to check in.
        </p>
      </div>
      <fieldset class="kai-field">
        <legend class="kai-field__label">How you connected</legend>
        <div class="kai-chips" role="radiogroup" aria-label="How you connected">
          @for (c of channels; track c) {
            <span class="kai-chip">
              <input type="radio" [name]="ids.group" [id]="ids.group + '-' + c" [value]="c"
                [checked]="channel() === c" (change)="channel.set(c)" />
              <label [for]="ids.group + '-' + c">{{ c }}</label>
            </span>
          }
        </div>
      </fieldset>
      <div class="kai-check">
        <input type="checkbox" [id]="ids.close" [checked]="close()" (change)="close.set(checked($event))" />
        <label [for]="ids.close">Close this care need. No follow-up reminder.</label>
      </div>
      @if (shownError()) {
        <p class="kai-form-error" role="alert">{{ shownError() }}</p>
      }
      <div class="kai-form__actions">
        <button kai-button variant="primary" type="submit" [disabled]="submitting()">
          {{ submitting() ? 'Saving…' : 'Save note' }}
        </button>
        <button kai-button variant="quiet" (click)="cancel.emit()">Cancel</button>
      </div>
    </form>
  `,
})
export class LogContactForm {
  readonly item = input.required<QueueItem>();
  readonly submitting = input(false);
  readonly error = input<string | null>(null);
  readonly logContact = output<{ item_id: number; note: string; channel: string; close: boolean }>();
  readonly cancel = output<void>();

  protected readonly channels = ['Call', 'Visit', 'Text', 'Coffee', 'Card', 'Other'];
  protected readonly ids = { note: nextId('note'), hint: nextId('hint'), group: nextId('ch'), close: nextId('close') };
  protected readonly note = signal('');
  protected readonly channel = signal('Call');
  protected readonly close = signal(false);
  private readonly localError = signal<string | null>(null);
  protected readonly shownError = computed(() => this.localError() ?? this.error());
  protected readonly first = computed(() => this.item().first_name || 'them');

  protected submit(e: Event): void {
    e.preventDefault();
    const note = this.note().trim();
    if (note.length < MIN_NOTE) {
      this.localError.set('Add a short note about what happened. A sentence is enough.');
      return;
    }
    this.localError.set(null);
    this.logContact.emit({ item_id: this.item().item_id, note, channel: this.channel(), close: this.close() });
  }

  protected value = value;
  protected checked = checked;
}

@Component({
  selector: 'kai-thank-you-editor',
  imports: [Button],
  template: `
    <form class="kai-form" [attr.aria-label]="'Thank-you note to ' + item().first_name" (submit)="submit($event)">
      <div class="kai-field">
        <label class="kai-field__label" [for]="ids.text">Thank-you note</label>
        <textarea class="kai-input kai-input--letter" rows="6" [id]="ids.text" [attr.aria-describedby]="ids.hint"
          [attr.aria-invalid]="error() ? 'true' : null" [value]="text()" (input)="text.set(value($event))"></textarea>
        <p class="kai-field__hint" [id]="ids.hint">
          Kairos replaced the scheduled ask with this note. Edit it in your own words. It sends only when you approve.
        </p>
      </div>
      @if (error()) {
        <div class="kai-refusal" role="alert" tabindex="-1">
          <p class="kai-refusal__title">Kairos held this note back</p>
          <p>{{ error() }}</p>
          @if (offending()) {
            <p class="kai-refusal__quote">“{{ offending() }}”</p>
            <p class="kai-refusal__help">A thank-you can’t ask for anything. Remove that line and approve again.</p>
          }
        </div>
      }
      <div class="kai-form__actions">
        <button kai-button variant="primary" type="submit" [disabled]="submitting()">
          {{ submitting() ? 'Approving…' : 'Approve and send' }}
        </button>
        <button kai-button variant="quiet" (click)="cancel.emit()">Cancel</button>
      </div>
    </form>
  `,
})
export class ThankYouEditor {
  readonly item = input.required<QueueItem>();
  readonly submitting = input(false);
  readonly error = input<string | null>(null);
  readonly offending = input<string | null>(null);
  readonly approveThanks = output<{ item_id: number; text: string }>();
  readonly cancel = output<void>();

  protected readonly ids = { text: nextId('ty'), hint: nextId('hint') };
  protected readonly text = linkedSignal(() => this.item().draft || '');

  protected submit(e: Event): void {
    e.preventDefault();
    this.approveThanks.emit({ item_id: this.item().item_id, text: this.text() });
  }

  protected value = value;
}

/** Triggers whose hold can never be released from the dashboard. The backend enforces this too. */
export const LOCKED_HOLDS: Record<string, string> = {
  MINOR: 'Messages to minors are never automated. A parent or youth leader reaches out instead.',
  OPT_OUT: 'This person opted out of these messages. Kairos will not release them.',
};

@Component({
  selector: 'kai-review-actions',
  imports: [Button],
  template: `
    <form class="kai-form" [attr.aria-label]="'Review the hold on ' + item().first_name" (submit)="submit($event)">
      <div class="kai-options" role="radiogroup" aria-label="What should happen">
        @for (o of options; track o.id) {
          <div class="kai-option" [class.is-disabled]="o.id === 'release' && lockReason()">
            <input type="radio" [name]="ids.group" [id]="ids.group + '-' + o.id" [value]="o.id"
              [checked]="action() === o.id" [disabled]="o.id === 'release' && !!lockReason()"
              [attr.aria-describedby]="o.id === 'release' && lockReason() ? ids.lock : null"
              (change)="action.set(o.id)" />
            <label [for]="ids.group + '-' + o.id">
              <span class="kai-option__title">{{ o.title }}</span>
              <span class="kai-option__desc">{{ o.desc }}</span>
            </label>
          </div>
        }
      </div>
      @if (lockReason()) {
        <p class="kai-lock-note" [id]="ids.lock">
          <span class="kai-lock-note__icon" aria-hidden="true"></span>
          <span><strong>Release isn’t available. </strong>{{ lockReason() }}</span>
        </p>
      }
      <div class="kai-field">
        <label class="kai-field__label" [for]="ids.note">Note</label>
        <textarea class="kai-input" rows="2" [id]="ids.note" [attr.aria-describedby]="ids.hint"
          [value]="note()" (input)="note.set(value($event))"></textarea>
        <p class="kai-field__hint" [id]="ids.hint">A sentence for the record: what you read and why you chose this.</p>
      </div>
      @if (shownError()) {
        <p class="kai-form-error" role="alert">{{ shownError() }}</p>
      }
      <div class="kai-form__actions">
        <button kai-button variant="primary" type="submit" [disabled]="submitting()">
          {{ submitting() ? 'Saving…' : 'Save decision' }}
        </button>
        <button kai-button variant="quiet" (click)="cancel.emit()">Cancel</button>
      </div>
    </form>
  `,
})
export class ReviewActions {
  readonly item = input.required<QueueItem>();
  readonly lockedReason = input<string | null>(null);
  readonly submitting = input(false);
  readonly error = input<string | null>(null);
  readonly review = output<{ item_id: number; action: ReviewAction; note: string }>();
  readonly cancel = output<void>();

  protected readonly options: { id: ReviewAction; title: string; desc: string }[] = [
    { id: 'hold', title: 'Keep holding', desc: 'Leave the message paused.' },
    { id: 'care', title: 'Needs care', desc: 'Something is going on. Turn this into a care card for the person who knows them.' },
    { id: 'release', title: 'Release', desc: 'Nothing sensitive. Let the scheduled message send.' },
  ];
  protected readonly ids = { group: nextId('rv'), lock: nextId('lock'), note: nextId('rn'), hint: nextId('hint') };
  protected readonly action = signal<ReviewAction>('hold');
  protected readonly note = signal('');
  private readonly localError = signal<string | null>(null);
  protected readonly shownError = computed(() => this.localError() ?? this.error());
  protected readonly lockReason = computed(() => this.lockedReason() ?? LOCKED_HOLDS[this.item().trigger] ?? null);

  protected submit(e: Event): void {
    e.preventDefault();
    const note = this.note().trim();
    if (note.length < MIN_NOTE) {
      this.localError.set('Add a short note for the record. A sentence is enough.');
      return;
    }
    this.localError.set(null);
    this.review.emit({ item_id: this.item().item_id, action: this.action(), note });
  }

  protected value = value;
}

@Component({
  selector: 'kai-handover-picker',
  imports: [Button, LoadMeter, RelationshipBar],
  template: `
    <form class="kai-form kai-handover" [attr.aria-label]="'Hand ' + (item().first_name || 'this') + ' to someone else'"
      (submit)="submit($event)">
      <p class="kai-form__intro">
        Sorted by how well they know {{ item().first_name || 'this person' }}. Kairos shows how full each week is; you decide.
      </p>
      @if (item().handover_options.length) {
        <div class="kai-handover__list" role="radiogroup" aria-label="Who should take this">
          @for (o of item().handover_options; track o.staff_id) {
            <div class="kai-handover__opt">
              <input type="radio" [name]="ids.group" [id]="ids.group + '-' + o.staff_id" [value]="o.staff_id"
                (change)="chosen.set(o.staff_id)" />
              <label [for]="ids.group + '-' + o.staff_id">
                <kai-relationship-bar [name]="o.name" [role]="o.role" [strengthPct]="o.strength_pct" [compact]="true" />
                <kai-load-meter [load]="o.load" [capacity]="o.capacity" [hasRoom]="o.has_room" />
              </label>
            </div>
          }
        </div>
      } @else {
        <p class="kai-muted">No one else has a relationship with {{ item().first_name || 'this person' }} yet.</p>
      }
      <div class="kai-field">
        <label class="kai-field__label" [for]="ids.reason">Reason (optional)</label>
        <textarea class="kai-input" rows="2" [id]="ids.reason" placeholder="e.g. I’m away this week"
          [value]="reason()" (input)="reason.set(value($event))"></textarea>
      </div>
      @if (error()) {
        <p class="kai-form-error" role="alert">{{ error() }}</p>
      }
      <div class="kai-form__actions">
        <button kai-button variant="primary" type="submit" [disabled]="!chosen() || submitting()">
          {{ submitting() ? 'Handing over…' : chosenFirst() ? 'Hand to ' + chosenFirst() : 'Hand over' }}
        </button>
        <button kai-button variant="quiet" (click)="cancel.emit()">Cancel</button>
      </div>
    </form>
  `,
})
export class HandoverPicker {
  readonly item = input.required<QueueItem>();
  readonly submitting = input(false);
  readonly error = input<string | null>(null);
  readonly handover = output<{ item_id: number; to_staff_id: string; reason: string }>();
  readonly cancel = output<void>();

  protected readonly ids = { group: nextId('ho'), reason: nextId('hr') };
  protected readonly chosen = signal<string | null>(null);
  protected readonly reason = signal('');
  protected readonly chosenFirst = computed(
    () => this.item().handover_options.find((o) => o.staff_id === this.chosen())?.name.split(' ')[0] ?? null,
  );

  protected submit(e: Event): void {
    e.preventDefault();
    const to = this.chosen();
    if (to) this.handover.emit({ item_id: this.item().item_id, to_staff_id: to, reason: this.reason().trim() });
  }

  protected value = value;
}

function value(e: Event): string {
  return (e.target as HTMLInputElement | HTMLTextAreaElement).value;
}

function checked(e: Event): boolean {
  return (e.target as HTMLInputElement).checked;
}
