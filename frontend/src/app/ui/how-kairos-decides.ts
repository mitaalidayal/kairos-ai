import { Component } from '@angular/core';

interface Step {
  n: string;
  name: string;
  does: string;
  human?: boolean;
}

/** The pipeline explainer from the original dashboard's "How Kairos decides" tab. */
@Component({
  selector: 'ol[kai-how-it-works]',
  template: `
    @for (s of steps; track s.name) {
      <li class="kai-how__step" [class.kai-how__step--human]="s.human">
        <span class="kai-how__node" aria-hidden="true">{{ s.n }}</span>
        <div class="kai-how__card">
          <h3 class="kai-how__name">
            @if (!s.human) {
              <span class="kai-sr">Step {{ s.n }}: </span>
            }
            {{ s.name }}
          </h3>
          <p class="kai-how__does">{{ s.does }}</p>
        </div>
      </li>
    }
  `,
  host: { class: 'kai-how', 'aria-label': 'How Kairos decides, step by step' },
})
export class HowKairosDecides {
  protected readonly steps: Step[] = [
    {
      n: '1', name: 'Signal Agent',
      does: 'Dates every prayer request and pastoral note, normalizes attendance, giving, volunteering and contact signals. Text a member did not consent to share with AI is dropped here, before any other agent sees it.',
    },
    {
      n: '2', name: 'Sacred Moment Detector',
      does: 'Labels each text: sacred · ambiguous · praise · other person · resolved · absence · routine, plus a sacred type and an injection flag. Output is validated against the enum; anything else becomes “ambiguous”. Text is data, never instructions.',
    },
    {
      n: '3', name: 'Decision Agent',
      does: 'Priority rules, first match wins: sacred window → consent restricted → ambiguous → silent drop-off → someone else’s crisis → milestone → guardrail holds → healthy ask.',
    },
    {
      n: '4', name: 'Routing Agent',
      does: 'Picks the person with the strongest relationship and says why (role, strength, last contact, runner-up).',
    },
    {
      n: '5', name: 'Draft Agent',
      does: 'Writes a thank-you (no ask) or a private brief for the routed person. Never sends anything.',
    },
    {
      n: '6', name: 'Guardrail Agent',
      does: 'Independent final check from the raw data: consent, keyword second opinion, minors, opt-outs, 30-day cap, channel consent. It can only downgrade (never to ASK), and it brings in a human when something sacred might otherwise be held silently.',
    },
    {
      n: '✓', name: 'A person', human: true,
      does: 'Every CARE, THANK and uncertain WAIT lands here. People log contacts (which schedule a 14-day follow-up), approve or edit thank-yous (re-checked for asks), and keep, escalate or release holds (hard constraints like minors and opt-outs can never be released).',
    },
  ];
}
