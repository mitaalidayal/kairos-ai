// Types for the Kairos FastAPI responses. Field names match the backend exactly.

export type Decision = 'CARE' | 'THANK' | 'WAIT' | 'ASK';
/** Decision as shown in the UI: WAIT that needs a person reads as WAIT·REVIEW; queue kinds have tags too. */
export type DecisionLabel = Decision | 'WAIT·REVIEW' | 'REVIEW' | 'REMINDER';
export type QueueKind = 'CARE' | 'THANK' | 'REVIEW' | 'REMINDER';
export type UrgencyLevel = 'urgent' | 'high' | 'normal';
export type Screen = 'queue' | 'decisions' | 'audit' | 'how';

export interface Summary {
  sim_date: string;
  as_of: string;
  counts: Record<Decision, number>;
  automations_total: number;
  routine_passed: number;
  messages_held: number;
  asks_sent: number;
  asks_replaced: number;
  care_needs_routed: number;
  care_contacts_logged: number;
  queue_open: number;
  reminders_upcoming: number;
  needs_review: number;
  injection_flags: number;
  detector_mode: string | null;
}

export interface Staff {
  staff_id: string;
  name: string;
  role: string;
  is_staff: string;
  weekly_care_capacity: string;
  small_group_id: string;
  load: number;
}

export interface Automation {
  automation_id: string;
  workflow_name: string;
  channel: string;
  scheduled_send_at: string;
  draft_summary: string;
}

export interface HandoverOption {
  staff_id: string;
  name: string;
  role: string;
  strength_pct: number | null;
  load: number;
  capacity: number;
  has_room: boolean;
}

export interface RoutingWhy {
  strength_pct: number | null;
  last_contact: string;
  is_top: boolean;
  assignee_first: string;
  handed_from_first: string;
}

export interface QueueItem {
  item_id: number;
  member_id: string;
  kind: QueueKind;
  staff_id: string;
  automation_ids: string[];
  headline: string;
  detail: string;
  draft: string;
  trigger: string;
  status: string;
  due_date: string;
  created_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution: string | null;
  note: string | null;
  urgency: number;
  urgency_level: UrgencyLevel;
  urgency_reason: string;
  reassigned_from: string;
  summary: string;
  first_name: string;
  last_name: string;
  staff_label: string;
  reassigned_from_label: string;
  automations: Automation[];
  handover_options: HandoverOption[];
  why: RoutingWhy;
  /** REMINDER only: the date of the contact being followed up (parsed from `detail`). */
  contact_date?: string;
}

export interface TextLabel {
  category: string | null;
  sacred_type: string | null;
  injection_attempt: boolean;
  source: string | null;
}

export interface MemberText {
  kind: string;
  date: string;
  status?: string;
  label: TextLabel | null;
  restricted: boolean;
  text: string | null;
  author?: string;
}

export interface TraceLabel {
  kind: string;
  id: string;
  on: string;
  days_ago: number;
  consent: boolean;
  label: TextLabel | null;
}

export interface TraceStep {
  agent: string;
  labels?: TraceLabel[];
  rule?: string;
  decision?: Decision;
  action?: string;
  staff_id?: string;
  why?: string;
  drafted?: string;
  checks?: { check: string; result: string }[];
  final?: string[];
  error?: string;
}

export interface MemberDecision {
  automation_id: string;
  member_id: string;
  decision: Decision;
  automation_action: string;
  sacred_detected: string;
  sacred_type: string | null;
  guardrail_result: string;
  guardrail_trigger: string;
  requires_human_review: string;
  human_staff_id: string;
  human_role: string;
  human_reason: string;
  channel: string;
  follow_up_days: number | null;
  reason: string;
  rule: string;
  routine: number;
  injection_flag: number;
  draft: string;
  trace: TraceStep[];
  send_status: string;
  workflow_name: string;
  message_type: string;
  scheduled_channel: string;
  scheduled_send_at: string;
  draft_summary: string;
}

export interface Relationship {
  staff_id: string;
  role: string;
  strength_pct: number;
  name: string;
}

export interface Contact {
  contact_id: number;
  member_id: string;
  staff_id: string;
  contact_date: string;
  channel: string;
  note: string;
}

export interface Reminder {
  reminder_id: number;
  member_id: string;
  staff_id: string;
  due_date: string;
  status: string;
  reason: string;
}

export interface AuditEntry {
  audit_id: number;
  ts: string;
  sim_date: string;
  actor: string;
  actor_type: 'agent' | 'system' | 'human' | 'person';
  event: string;
  member_id: string | null;
  automation_id: string | null;
  scheduled: string | null;
  action_taken: string | null;
  decision: Decision | null;
  reason: string | null;
  routed_to: string | null;
  details: { rule?: string; decisions?: number; [k: string]: unknown } | null;
  first_name: string | null;
}

export interface Signals {
  tenure_months?: number;
  attended_last_8w?: number;
  attended_prior_8w?: number;
  weeks_since_last_attended?: number;
  attendance_trend?: string;
  giving_status?: string;
  days_since_human_contact?: number | null;
  open_prayer_requests?: number;
  days_since_last_prayer?: number | null;
  [k: string]: unknown;
}

export interface GivingPlan {
  amount: string;
  frequency: string;
  status: string;
  paused_or_canceled_at?: string;
}

export interface Volunteering {
  team: string;
  status: string;
  last_served_date?: string;
}

export interface MemberProfile {
  member: {
    member_id: string;
    first_name: string;
    last_name: string;
    membership_status?: string;
    member_since?: string;
    preferred_channel?: string;
    email_opt_in?: string;
    sms_opt_in?: string;
    appeals_opt_in?: string;
  };
  signals?: Signals;
  attendance_weeks?: { date: string; attended: boolean }[];
  giving?: { plan: GivingPlan[]; recent_gifts: unknown[] };
  volunteering?: Volunteering[];
  relationships?: Relationship[];
  decisions?: MemberDecision[];
  texts?: MemberText[];
  viewer_can_read_text?: boolean;
  contacts?: Contact[];
  reminders?: Reminder[];
  audit?: AuditEntry[];
}

export interface DecisionRow {
  automation_id: string;
  member_id: string;
  first_name: string;
  last_name: string;
  workflow_name: string;
  message_type: string;
  scheduled_send_at: string;
  decision: Decision;
  automation_action: string;
  guardrail_trigger: string;
  requires_human_review: string;
  human_staff_id: string;
  reason: string;
  send_status: string;
  routine: number;
}

/** Every failed call rejects with this shape (`detail` is the backend's message). */
export interface ApiError {
  status: number;
  detail: string;
}

/** The thank-you guardrail refused the note because it contains an ask. */
export interface ThankYouRefusal extends ApiError {
  offending: string;
}

export type ReviewAction = 'hold' | 'care' | 'release';
