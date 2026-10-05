"""Kairos API + dashboard. Run: .venv/bin/uvicorn server.app:app --reload
Set KAIROS_DETECTOR=llm to use the LLM detector (cached labels are used in every mode)."""
import os, threading
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from kairos.db import connect, load_sources
from kairos import service as S

MODE = os.environ.get("KAIROS_DETECTOR", "keyword")
con = connect()
lock = threading.Lock()  # one writer at a time; SQLite connection is shared


@asynccontextmanager
async def lifespan(app):
    with lock:
        load_sources(con)
        if not con.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]:
            S.run_all(con, MODE)
    yield


app = FastAPI(title="Kairos", lifespan=lifespan)
STATIC = Path(__file__).parent / "static"


def guarded(fn, *a, **kw):
    with lock:
        try:
            return fn(con, *a, **kw)
        except S.HumanActionError as e:
            raise HTTPException(400, str(e))


class RunReq(BaseModel):
    mode: str | None = None

class ContactReq(BaseModel):
    staff_id: str
    note: str
    channel: str = "Call"
    close_care: bool = False

class ApproveReq(BaseModel):
    staff_id: str
    draft: str

class ResolveReq(BaseModel):
    staff_id: str
    resolution: str
    note: str

class ReassignReq(BaseModel):
    staff_id: str          # who is doing the handover
    to_staff_id: str
    note: str = ""

class ClockReq(BaseModel):
    days: int = 14


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/api/run")
def run(req: RunReq | None = None):
    """Run every agent over every scheduled automation. Resets queue/contacts/reminders (demo reset); audit log is kept."""
    return guarded(S.run_all, (req.mode if req and req.mode else MODE))


@app.get("/api/summary")
def summary():
    return guarded(S.summary)


@app.get("/api/queue")
def queue(staff_id: str | None = None, include_done: bool = False):
    return guarded(S.queue, staff_id, include_done)


@app.post("/api/queue/{item_id}/contact")
def contact(item_id: int, req: ContactReq):
    return guarded(S.log_contact, item_id, req.staff_id, req.note, req.channel, req.close_care)


@app.post("/api/queue/{item_id}/approve")
def approve(item_id: int, req: ApproveReq):
    return guarded(S.approve_thank, item_id, req.staff_id, req.draft)


@app.post("/api/queue/{item_id}/resolve")
def resolve(item_id: int, req: ResolveReq):
    return guarded(S.resolve_review, item_id, req.staff_id, req.resolution, req.note)


@app.post("/api/queue/{item_id}/reassign")
def reassign(item_id: int, req: ReassignReq):
    return guarded(S.reassign, item_id, req.staff_id, req.to_staff_id, req.note)


@app.get("/api/staff/load")
def staff_load():
    with lock:
        load = S.care_load(con)
        return [{**dict(r), "load": load.get(r["staff_id"], 0)} for r in con.execute("SELECT * FROM staff ORDER BY staff_id")]


@app.get("/api/members/{member_id}")
def member(member_id: str, viewer: str | None = None):
    try:
        return guarded(S.person, member_id, viewer)
    except IndexError:
        raise HTTPException(404, "member not found")


@app.get("/api/decisions")
def decisions(decision: str | None = None, include_routine: bool = False):
    sql = ("SELECT d.automation_id, d.member_id, m.first_name, m.last_name, a.workflow_name, a.message_type, a.scheduled_send_at, "
           "d.decision, d.automation_action, d.guardrail_trigger, d.requires_human_review, d.human_staff_id, d.reason, d.send_status, d.routine "
           "FROM decisions d JOIN members m USING(member_id) JOIN scheduled_automation a USING(automation_id) WHERE 1=1")
    args = []
    if decision:
        sql += " AND d.decision=?"; args.append(decision)
    if not include_routine:
        sql += " AND d.routine=0"
    with lock:
        return [dict(r) for r in con.execute(sql + " ORDER BY a.scheduled_send_at", args)]


@app.get("/api/audit")
def audit(member_id: str | None = None, event: str | None = None, limit: int = Query(300, le=2000), all_runs: bool = False):
    return guarded(S.audit_log, member_id, limit, event, all_runs)


@app.get("/api/reminders")
def reminders():
    with lock:
        return [dict(r) for r in con.execute(
            "SELECT r.*, m.first_name FROM reminders r JOIN members m USING(member_id) ORDER BY due_date")]


@app.get("/api/staff")
def staff():
    with lock:
        return [dict(r) for r in con.execute("SELECT * FROM staff ORDER BY staff_id")]


@app.post("/api/clock/advance")
def clock(req: ClockReq):
    """Demo only: move the simulated date forward so due reminders re-enter the queue."""
    return guarded(S.advance_clock, req.days)
