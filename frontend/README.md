# Kairos frontend (Angular)

The Kairos dashboard in Angular + TypeScript, built from the Claude Design system
(Kairos "quiet notebook" design: tokens, 26 components, the KairosApp prototype).
The original single-file dashboard in `server/static/index.html` is unchanged, for comparison.

## Run it

Needs Node 22, 24 or 26+ (Angular 22 does not support odd-numbered Node versions like 25).

```bash
# terminal 1 — backend, from the repo root
.venv/bin/uvicorn server.app:app --port 8765

# terminal 2 — frontend, from frontend/
npm install
npx ng serve            # http://localhost:4200  (/api is proxied to :8765, see proxy.conf.json)
```

Deep links work as in the old dashboard: `http://localhost:4200/?as=ST13#M0010` opens Isabella's
queue with Marcus's profile. The theme follows the system light/dark setting.

```bash
npx ng test --watch=false   # unit tests (Vitest)
npx ng build                # production build → dist/kairos-frontend
```

## Layout

```
src/styles.css                 tokens + one partial per component (src/styles/components/*.css)
src/styles/tokens.css          design tokens, copied verbatim from the design system
src/app/core/
  models.ts                    types for every API response (backend field names, unchanged)
  kairos-api.service.ts        the data layer (Kairos.data in the design) against FastAPI
  kairos-store.ts              app state (signals) + human actions → toast → refresh
  format.ts / format.pipes.ts  dates and labels, read as plain strings (no timezone shifts)
src/app/ui/
  atoms.ts       DecisionTag, UrgencyPill, Button, EmptyState, CapacityBanner/Line, RelationshipBar, LoadMeter
  page-top.ts    TopBar, Greeting, SummaryTile(s), ToastRegion
  queue.ts       AttentionQueue, QueueCard, BlockedMessage, PrivateBrief
  card-forms.ts  LogContactForm, ThankYouEditor, ReviewActions, HandoverPicker
  person.ts      PersonDrawer, AttendanceStrip, SignalList, ReadText, AgentTrace, PersonDecision
  lists.ts       DecisionsTable, AuditTimeline
src/app/app.ts / app.html      the page: top bar, the three screens, the person drawer
```

Component styles are global partials rather than Angular component styles: the design
namespaces every class as `kai-*`, and form/link classes are shared across components.

## Where the design and the backend differ

The design was made from read-only sample data, so it guessed the write endpoints.
`KairosApiService` maps the design's calls onto the real API; the backend is unchanged.

| Design | Backend |
|---|---|
| `logContact {note, channel, close}` | `POST /api/queue/{id}/contact {staff_id, note, channel, close_care}` |
| `approveThankYou` → 422 `{offending}` | `POST /api/queue/{id}/approve {staff_id, draft}` → 400 `a thank-you cannot contain an ask (found: "…")` |
| `reviewItem` hold / care / release | `POST /api/queue/{id}/resolve {staff_id, resolution: keep_hold / escalate_care / release, note}` |
| `handover {reason}` | `POST /api/queue/{id}/reassign {staff_id, to_staff_id, note}` |
| `advanceDays`, `reset` | `POST /api/clock/advance {days}`, `POST /api/run` |

- Every action needs a named person (`staff_id`): the viewer, or the card's owner when viewing as All staff.
- The backend requires a short note (3+ characters) to log contact or review a hold, so those notes are required in the UI.
- REMINDER cards carry the earlier note only inside `detail`; the service parses it out for the quote.

## Open items

- **Fonts load from Google Fonts** (Fraunces, Atkinson Hyperlegible, IBM Plex Mono), so they need internet.
  Self-host them before the demo.
- Serving the built app from FastAPI needs a small backend change (static mount for `dist/`); until then, use `ng serve`.
