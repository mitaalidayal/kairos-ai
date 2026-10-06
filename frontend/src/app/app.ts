import { Component, DestroyRef, effect, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { KairosApiService } from './core/kairos-api.service';
import { KairosStore, errText } from './core/kairos-store';
import { MemberProfile } from './core/models';
import { Greeting, SummaryTiles, ToastRegion, TopBar } from './ui/page-top';
import { AttentionQueue } from './ui/queue';
import { PersonDrawer } from './ui/person';
import { AuditTimeline, DecisionsTable } from './ui/lists';
import { HowKairosDecides } from './ui/how-kairos-decides';

/** The KairosApp page: top bar, then the queue, decisions, audit or "how it works" screen, and the person drawer. */
@Component({
  selector: 'app-root',
  imports: [AttentionQueue, AuditTimeline, DecisionsTable, Greeting, HowKairosDecides, PersonDrawer, SummaryTiles, ToastRegion, TopBar],
  templateUrl: './app.html',
})
export class App {
  protected readonly store = inject(KairosStore);
  private readonly api = inject(KairosApiService);

  protected readonly profile = signal<MemberProfile | null>(null);
  protected readonly profileLoading = signal(false);
  protected readonly profileError = signal<string | null>(null);
  private returnFocus: HTMLElement | null = null;

  constructor() {
    followSystemTheme(inject(DestroyRef));
    this.store.init();

    // Load the profile whenever a member is opened, or the viewer changes what they may read.
    effect(async () => {
      const id = this.store.openMemberId();
      const viewer = this.store.viewer();
      if (!id) return;
      this.profileLoading.set(true);
      this.profileError.set(null);
      try {
        const p = await firstValueFrom(this.api.getMember(id, viewer));
        if (this.store.openMemberId() === id) this.profile.set(p);
      } catch (e) {
        this.profileError.set(`Couldn’t open this profile. ${errText(e)}`);
      } finally {
        this.profileLoading.set(false);
      }
    });
  }

  protected openMember(memberId: string): void {
    this.returnFocus = document.activeElement as HTMLElement | null;
    this.profile.set(null);
    this.store.openMember(memberId);
  }

  protected closeMember(): void {
    this.store.closeMember();
    this.profile.set(null);
    this.returnFocus?.focus();
    this.returnFocus = null;
  }

  protected onScrimClick(e: MouseEvent): void {
    if (e.target === e.currentTarget) this.closeMember();
  }
}

/** tokens.css switches on [data-theme]; follow the system's light/dark preference. */
function followSystemTheme(destroyRef: DestroyRef): void {
  const mq = window.matchMedia?.('(prefers-color-scheme: dark)');
  if (!mq) return;
  const apply = () => document.documentElement.setAttribute('data-theme', mq.matches ? 'dark' : 'light');
  apply();
  mq.addEventListener('change', apply);
  destroyRef.onDestroy(() => mq.removeEventListener('change', apply));
}
