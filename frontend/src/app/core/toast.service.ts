import { Injectable, signal } from '@angular/core';

export interface ToastMessage {
  id: number;
  message: string;
  detail?: string | null;
  tone: 'done' | 'error';
}

/** showToast() from the design bundle: a fixed region, auto-dismissed after a few seconds. */
@Injectable({ providedIn: 'root' })
export class ToastService {
  readonly toasts = signal<ToastMessage[]>([]);
  private nextId = 0;

  show(message: string, detail?: string | null, tone: 'done' | 'error' = 'done', ms = 5000): void {
    const id = ++this.nextId;
    this.toasts.update((t) => [...t, { id, message, detail, tone }]);
    setTimeout(() => this.dismiss(id), ms);
  }

  error(message: string, detail?: string | null): void {
    this.show(message, detail, 'error', 7000);
  }

  dismiss(id: number): void {
    this.toasts.update((t) => t.filter((x) => x.id !== id));
  }
}
