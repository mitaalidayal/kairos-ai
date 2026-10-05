"""Thresholds and constants. All day windows are measured against the dataset as-of date, not the wall clock."""
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path):
    """Minimal .env loader (KEY=value lines, # comments). Real environment variables always win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")
DATA_DIR = ROOT / "data"
CACHE_PATH = ROOT / "kairos" / "detector_cache.json"
DB_PATH = ROOT / "kairos.db"

AS_OF = date(2026, 10, 3)

SACRED_WINDOW_DAYS = 45        # R1
UNCERTAIN_TEXT_DAYS = 21       # R2, R3
SACRED_ADJACENT_HOLD_DAYS = 14 # R5
MILESTONE_DAYS = 14            # R6
ASK_CAP_DAYS = 30              # R7 RECENT_ASK (signal asks_last_30d)
JUST_GAVE_DAYS = 14            # R7 JUST_GAVE
HUMAN_CONTACT_DAYS = 7         # R7 RECENT_HUMAN_CONTACT
RESOLVED_SOFTEN_DAYS = 90      # R10 modifier
DROPOFF_MIN_TENURE_MONTHS = 60 # R4
HEALTHY_ATTENDANCE_OF_8 = 5    # R8
NEWER_ATTENDER_MONTHS = 12     # R8 participation invites
CARE_FOLLOW_UP_DAYS = 14

DETECTOR_MODEL = "claude-opus-5-5"
