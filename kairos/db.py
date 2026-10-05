"""SQLite store. Source tables are loaded verbatim from data/*.csv; app tables hold decisions, the Human Attention
Queue, human contacts, reminders and the append-only audit log."""
import csv, json, sqlite3
from datetime import datetime, timezone
from .config import DATA_DIR, DB_PATH

SOURCE_TABLES = ["members", "member_signal_snapshot", "attendance", "giving", "recurring_plans", "volunteer_roles",
                 "volunteer_shifts", "prayer_requests", "pastoral_notes", "communications_log", "scheduled_automation",
                 "relationship_strength", "staff"]

APP_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS decisions (
  automation_id TEXT PRIMARY KEY, member_id TEXT, run_id TEXT, decision TEXT, automation_action TEXT,
  sacred_detected TEXT, sacred_type TEXT, guardrail_result TEXT, guardrail_trigger TEXT, requires_human_review TEXT,
  human_staff_id TEXT, human_role TEXT, human_reason TEXT, channel TEXT, follow_up_days INTEGER, reason TEXT,
  rule TEXT, routine INTEGER, injection_flag INTEGER, draft TEXT, trace TEXT,
  send_status TEXT,            -- sent_mock | blocked | held | replaced_pending | replaced_sent | released_sent
  created_at TEXT);
CREATE TABLE IF NOT EXISTS queue (
  item_id INTEGER PRIMARY KEY AUTOINCREMENT, member_id TEXT, kind TEXT,  -- CARE | THANK | REVIEW | REMINDER
  staff_id TEXT, automation_ids TEXT, headline TEXT, detail TEXT, draft TEXT, trigger TEXT,
  status TEXT,                  -- open | done | dismissed
  due_date TEXT, created_at TEXT, resolved_at TEXT, resolved_by TEXT, resolution TEXT, note TEXT,
  urgency INTEGER DEFAULT 0, urgency_level TEXT DEFAULT 'normal', urgency_reason TEXT DEFAULT '', reassigned_from TEXT DEFAULT '', summary TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS contacts (
  contact_id INTEGER PRIMARY KEY AUTOINCREMENT, member_id TEXT, staff_id TEXT, contact_date TEXT, channel TEXT,
  note TEXT, queue_item_id INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS reminders (
  reminder_id INTEGER PRIMARY KEY AUTOINCREMENT, member_id TEXT, staff_id TEXT, due_date TEXT, reason TEXT,
  from_contact_id INTEGER, queue_item_id INTEGER, status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS audit_log (
  audit_id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, sim_date TEXT, actor TEXT, actor_type TEXT,  -- agent | human | system
  event TEXT, member_id TEXT, automation_id TEXT, scheduled TEXT, action_taken TEXT, decision TEXT,
  reason TEXT, routed_to TEXT, details TEXT);
"""


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path=DB_PATH):
    con = sqlite3.connect(path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def load_sources(con, force=False):
    for t in SOURCE_TABLES:
        exists = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone()
        if exists and not force:
            continue
        with open(DATA_DIR / f"{t}.csv", newline="") as f:
            rows = list(csv.DictReader(f))
        cols = list(rows[0].keys())
        con.execute(f"DROP TABLE IF EXISTS {t}")
        coldefs = ", ".join('"' + c + '" TEXT' for c in cols)
        con.execute(f"CREATE TABLE {t} ({coldefs})")
        con.executemany(f"INSERT INTO {t} VALUES ({', '.join('?' * len(cols))})", [tuple(r[c] for c in cols) for r in rows])
    for idx in ["attendance(member_id)", "giving(member_id)", "prayer_requests(member_id)", "pastoral_notes(member_id)",
                "relationship_strength(member_id)", "scheduled_automation(member_id)", "communications_log(member_id)"]:
        con.execute(f"CREATE INDEX IF NOT EXISTS ix_{idx.split('(')[0]} ON {idx}")
    con.executescript(APP_SCHEMA)
    # Lightweight migration for databases created before urgency/reassign existed.
    have = {r[1] for r in con.execute("PRAGMA table_info(queue)")}
    for col, ddl in [("urgency", "INTEGER DEFAULT 0"), ("urgency_level", "TEXT DEFAULT 'normal'"),
                     ("urgency_reason", "TEXT DEFAULT ''"), ("reassigned_from", "TEXT DEFAULT ''"), ("summary", "TEXT DEFAULT ''")]:
        if col not in have:
            con.execute(f"ALTER TABLE queue ADD COLUMN {col} {ddl}")
    con.commit()


def reset_app(con):
    # The audit log is append-only and survives resets; each run is bracketed by run_started/run_finished rows.
    for t in ["decisions", "queue", "contacts", "reminders", "app_state"]:
        con.execute(f"DELETE FROM {t}")
    con.commit()


def audit(con, *, actor, actor_type, event, member_id=None, automation_id=None, scheduled=None, action_taken=None,
          decision=None, reason=None, routed_to=None, details=None, sim_date=None):
    con.execute("""INSERT INTO audit_log (ts, sim_date, actor, actor_type, event, member_id, automation_id, scheduled,
                   action_taken, decision, reason, routed_to, details) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (now_iso(), sim_date, actor, actor_type, event, member_id, automation_id, scheduled, action_taken,
                 decision, reason, routed_to, json.dumps(details) if details is not None else None))
