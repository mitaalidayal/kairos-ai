import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { KairosApiService } from './kairos-api.service';
import { ToastService } from './toast.service';
import { firstName, fmtDate } from './format';
import { ApiError, AuditEntry, DecisionRow, QueueItem, ReviewAction, Screen, Staff, Summary } from './models';

const LEAVE_MS = 260;

/** Deep links: ?as=ST13 selects the viewer, #M0010 opens that member. */
export function readDeepLink(loc: Location = window.location): { as: string | null; member_id: string | null } {
  const as = new URLSearchParams(loc.search).get('as');
  const hash = (loc.hash || '').replace(/^#/, '');
  return { as: as || null, member_id: /^M\d+$/.test(hash) ? hash : null };
}

/**
 * App state and the wiring the design's prototype page did by hand (wireDemo): load data, run
 * the human actions against the API, toast the result, slide the card out, refresh.
 */
@Injectable({ providedIn: 'root' })
export class KairosStore {
  private readonly api = inject(KairosApiService);
  private readonly toast = inject(ToastService);

  readonly viewer = signal<string | null>(null);
  readonly screen = signal<Screen>('queue');
  readonly summary = signal<Summary | null>(null);
  readonly staff = signal<Staff[]>([]);
  readonly queue = signal<QueueItem[]>([]);
  readonly queueLoading = signal(true);
  readonly queueError = signal<string | null>(null);
  readonly decisions = signal<DecisionRow[] | null>(null);
  readonly audit = signal<AuditEntry[] | null>(null);
  readonly listError = signal<string | null>(null);
  /** Cards sliding out after an action. */
  readonly leaving = signal<ReadonlySet<number>>(new Set());
  readonly openMemberId = signal<string | null>(null);

  readonly me = computed(() => this.staff().find((s) => s.staff_id === this.viewer()) ?? null);
  readonly staffById = computed(() => new Map(this.staff().map((s) => [s.staff_id, s])));

  init(): void {
    const link = readDeepLink();
    this.viewer.set(link.as);
    if (link.member_id) this.openMemberId.set(link.member_id);
    void this.refresh();
  }

  async refresh(): Promise<void> {
    const viewer = this.viewer();
    try {
      const [summary, staff, queue] = await Promise.all([
        firstValueFrom(this.api.getSummary()),
        firstValueFrom(this.api.getStaffLoad()),
        firstValueFrom(this.api.getQueue(viewer)),
      ]);
      if (viewer !== this.viewer()) return; // the viewer changed while loading
      this.summary.set(summary);
      this.staff.set(staff);
      this.queue.set(queue);
      this.queueError.set(null);
    } catch (e) {
      this.queueError.set(errText(e));
    } finally {
      this.queueLoading.set(false);
    }
    if (this.screen() !== 'queue') void this.loadScreen(this.screen());
  }

  setViewer(staffId: string | null): void {
    this.viewer.set(staffId);
    this.screen.set('queue');
    this.queueLoading.set(true);
    try {
      const u = new URL(window.location.href);
      if (staffId) u.searchParams.set('as', staffId);
      else u.searchParams.delete('as');
      history.replaceState(null, '', u);
    } catch { /* URL updates are a convenience */ }
    void this.refresh();
  }

  navigate(screen: Screen): void {
    this.screen.set(screen);
    if (screen !== 'queue') void this.loadScreen(screen);
  }

  private async loadScreen(screen: Screen): Promise<void> {
    try {
      this.listError.set(null);
      if (screen === 'decisions') this.decisions.set(await firstValueFrom(this.api.getDecisions()));
      if (screen === 'audit') this.audit.set(await firstValueFrom(this.api.getAudit()));
    } catch (e) {
      this.listError.set(errText(e));
    }
  }

  openMember(memberId: string): void {
    this.openMemberId.set(memberId);
    history.replaceState(null, '', `${location.pathname}${location.search}#${memberId}`);
  }

  closeMember(): void {
    this.openMemberId.set(null);
    history.replaceState(null, '', `${location.pathname}${location.search}`);
  }

  /** The named person acting: the viewer, or the card's owner when viewing as All staff. */
  actorFor(item: QueueItem): string {
    return this.viewer() ?? item.staff_id;
  }

  // ── human actions. Each resolves on success and rejects with ApiError so forms can show it. ──

  async logContact(item: QueueItem, body: { note: string; channel: string; close: boolean }): Promise<void> {
    const r = await firstValueFrom(this.api.logContact(item.item_id, this.actorFor(item), body));
    this.done(item, r.message, body.note ? `“${body.note}”` : null);
  }

  async approveThankYou(item: QueueItem, text: string): Promise<void> {
    await firstValueFrom(this.api.approveThankYou(item.item_id, this.actorFor(item), text));
    this.done(item, `Thank-you approved for ${item.first_name}`);
  }

  async review(item: QueueItem, action: ReviewAction, note: string): Promise<void> {
    const r = await firstValueFrom(this.api.reviewItem(item.item_id, this.actorFor(item), action, note));
    this.done(item, r.message);
  }

  async handover(item: QueueItem, toStaffId: string, reason: string): Promise<void> {
    await firstValueFrom(this.api.handover(item.item_id, this.actorFor(item), toStaffId, reason));
    const to = this.staffById().get(toStaffId);
    this.done(item, `${item.first_name} is now with ${firstName(to?.name)}`, 'They’ll see it in their queue.');
  }

  async advanceDays(days: number): Promise<void> {
    try {
      const r = await firstValueFrom(this.api.advanceDays(days));
      this.toast.show(`Moved the demo clock to ${fmtDate(r.sim_date)}`, 'Any follow-ups that came due are now at the top.');
      await this.refresh();
    } catch (e) {
      this.toast.error('Couldn’t move the demo clock', errText(e));
    }
  }

  async rerun(): Promise<void> {
    try {
      this.queueLoading.set(true);
      await firstValueFrom(this.api.reset());
      this.decisions.set(null);
      this.audit.set(null);
      this.toast.show('Agents re-ran. The demo is reset.');
      await this.refresh();
    } catch (e) {
      this.queueLoading.set(false);
      this.toast.error('Couldn’t re-run the agents', errText(e));
    }
  }

  private done(item: QueueItem, message: string, detail: string | null = null): void {
    this.toast.show(message, detail);
    this.leaving.update((s) => new Set(s).add(item.item_id));
    setTimeout(async () => {
      await this.refresh();
      this.leaving.update((s) => {
        const n = new Set(s);
        n.delete(item.item_id);
        return n;
      });
    }, LEAVE_MS);
  }
}

export function errText(e: unknown): string {
  const d = (e as ApiError)?.detail;
  return typeof d === 'string' ? sentence(d) : 'Something went wrong.';
}

/** Backend messages are lower-case fragments ("a short note is required"); show them as sentences. */
function sentence(s: string): string {
  const t = s.trim();
  return t.charAt(0).toUpperCase() + t.slice(1) + (/[.!?]$/.test(t) ? '' : '.');
}
