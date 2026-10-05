"""Build data/test_cases_reworded.json: clones of existing cases with the prayer text reworded so that the
keyword lists do not fire (or fire wrongly). Expected labels are inherited from the source case.
Usage: python scripts/make_reworded_cases.py"""
import copy, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = {c["case_id"]: c for c in json.load(open(ROOT / "data/test_cases.json"))["cases"]}

# (source case, new text, sacred_type expected, why keywords struggle)
REWORDED = [
    ("TC-001", "The scans came back and it is not good news. They want to operate before Thanksgiving. I am trying to be brave.", "serious_illness", "no illness keyword"),
    ("TC-002", "Our little girl has been really sick and the specialists finally gave us a name for it. We are terrified.", "serious_illness", "diagnosis implied, not stated"),
    ("TC-005", "My husband's first round of infusions wiped him out this week. Please hold us up.", "serious_illness", "'infusions' instead of chemo"),
    ("TC-010", "My wife collapsed on Saturday and still can't speak or move her right side. The doctors are watching her closely.", "serious_illness", "stroke described, not named"),
    ("TC-013", "Forty years together and now I set one plate at the table. I don't know how to do this without him.", "grief", "death never mentioned"),
    ("TC-011", "We buried my best friend on Saturday. I keep reaching for my phone to text her.", "grief", "'buried' not a keyword"),
    ("TC-087", "Dad went home to be with the Lord on Tuesday. The service is Saturday.", "grief", "church euphemism for death"),
    ("TC-015", "Most mornings I can't get out of bed and I don't see the point anymore. Please pray.", "mental_health", "depression described, not named"),
    ("TC-017", "I've been crying every night and I have nobody to talk to.", "mental_health", "isolation without 'alone'"),
    ("TC-019", "We are two months late on everything and I skipped meals this week so the kids could eat.", "financial_hardship", "no rent/bill keyword"),
    ("TC-020", "We had to leave the apartment last week and the kids and I sleep at a different place each night.", "homelessness_risk", "no car/motel/evict keyword"),
    ("TC-022", "After twelve years my position was eliminated on Tuesday. I have no idea what comes next for our family.", "job_loss", "'position eliminated' not 'laid off'"),
    ("TC-023", "Our 15-year-old didn't come home last night and isn't answering his phone. The police are involved.", "family_crisis", "runaway described, not named"),
    ("TC-024", "My wife moved out and took the kids to her mother's. I'm lost.", "family_crisis", "separation described, not named"),
    ("TC-090", "The biopsy confirmed it's malignant. I start radiation Monday.", "serious_illness", "'malignant'/'radiation' not keywords"),
    # Keyword false positives / false holds
    ("TC-092", "Our son is out of surgery and the doctors say it went perfectly! Thank you all.", None, "praise, but 'surgery' fires the sacred list"),
    ("TC-091", "Six weeks after the transplant she walked into church on her own. God is good!", None, "praise with no praise keyword"),
    ("TC-098", "My manager at work had a stroke yesterday. Please pray for him and his family.", None, "someone else's crisis, 'stroke' fires sacred"),
    ("TC-045", "Praying that the new building project brings our whole neighborhood together.", None, "routine prayer; unknown text fails closed"),
]


def main():
    out = []
    for i, (cid, text, st, why) in enumerate(REWORDED, 1):
        c = copy.deepcopy(src[cid])
        c["case_id"] = f"RW-{i:03d}"
        c["reworded_from"] = cid
        c["reword_note"] = why
        c["description"] = f"Reworded from {cid}: {why}"
        prs = c["input"]["prayer_requests"]
        if prs:
            prs[0]["request_text"] = text
        else:
            prs.append({"request_id": f"PRX{i:03d}", "submitted_at": "2026-09-28T10:00:00.000", "request_text": text,
                        "consent_for_ai_read": "Yes", "status": "Open"})
            c["input"]["signals"]["open_prayer_requests"] = 1
            c["input"]["signals"]["days_since_last_prayer"] = 5.0
        if st:
            assert c["expected"]["sacred_moment"]["type"] == st, (cid, st)
        out.append(c)
    json.dump({"as_of": "2026-10-03", "cases": out}, open(ROOT / "data/test_cases_reworded.json", "w"), indent=1)
    print(f"wrote {len(out)} reworded cases to data/test_cases_reworded.json")


if __name__ == "__main__":
    main()
