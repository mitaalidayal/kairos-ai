"""Label every distinct prayer request / pastoral note with the LLM once and save to kairos/detector_cache.json.
After this, every mode (including offline keyword mode) uses the cached LLM labels.
Requires ANTHROPIC_API_KEY (or another credential the anthropic SDK resolves).
Usage: python scripts/warm_cache.py [--workers 8]"""
import argparse, csv, json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kairos.agents.detector import SacredMomentDetector

ap = argparse.ArgumentParser(); ap.add_argument("--workers", type=int, default=8)
args = ap.parse_args()

texts = set()
for p in csv.DictReader(open(ROOT / "data/prayer_requests.csv")):
    if p["consent_for_ai_read"] == "Yes":
        texts.add(("prayer", "", p["request_text"]))
for n in csv.DictReader(open(ROOT / "data/pastoral_notes.csv")):
    texts.add(("note", n["note_type"], n["note_text"]))
for f in ["test_cases.json", "test_cases_reworded.json"]:
    path = ROOT / "data" / f
    if path.exists():
        for c in json.load(open(path))["cases"]:
            for p in c["input"]["prayer_requests"]:
                if p["consent_for_ai_read"] == "Yes":
                    texts.add(("prayer", "", p["request_text"]))
            for n in c["input"]["pastoral_notes"]:
                texts.add(("note", n.get("note_type", ""), n["note_text"]))

det = SacredMomentDetector(mode="llm")
print(f"{len(texts)} distinct texts")
with ThreadPoolExecutor(args.workers) as ex:
    labels = list(ex.map(lambda t: (t, det.label(t[0], t[2], t[1])), sorted(texts)))
det.save_cache()
for (kind, nt, text), lab in labels:
    print(f"{lab.source:8} {lab.category:17} {lab.sacred_type or '':18} inj={int(lab.injection_attempt)}  {kind}: {text[:70]}")
print(det.stats)
if det.stats["error"]:
    print("WARNING: some calls failed and fell back to keywords (not cached). Check credentials / network.")
