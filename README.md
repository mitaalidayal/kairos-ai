# Kairos: Human Handoff Agent for Ministry (hackathon MVP)

Kairos sits on top of a church's (mocked) tools. For every scheduled automated message it decides **ASK** (let it send), **CARE** (block it, assign a person), **THANK** (replace it with a personal thank-you) or **WAIT** (hold it). Anything sensitive goes to a human. Synthetic data only; nothing is really sent.

## Run

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/) (uv will fetch Python 3.12 if needed).

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env                              # optional: add ANTHROPIC_API_KEY (labels are cached, so it runs without one)
.venv/bin/uvicorn server.app:app --port 8765      # http://localhost:8765
```
On first start the server loads `data/*.csv` into `kairos.db` (SQLite) and runs the agents over all 249 scheduled automations. To start from scratch, delete `kairos.db` (or click **Re-run agents**).

Demo deep link: `http://localhost:8765/?as=ST13#M0010` (Isabella's queue, Marcus open). Rehearse the whole flow: `.venv/bin/python scripts/demo_flow.py`.

## Evaluate

```bash
.venv/bin/python scripts/predict.py && .venv/bin/python evaluate.py predictions.csv data/test_cases.json
.venv/bin/python scripts/check_contract.py          # stricter: trigger, review, channel, follow-up
.venv/bin/python scripts/test_safety.py             # adversarial: fooled detector, crashes, injection, consent
.venv/bin/python scripts/test_service.py            # human-in-the-loop: urgency, handover, follow-up loop
.venv/bin/python scripts/make_reworded_cases.py      # 19 reworded prayer requests (where keywords fail)
.venv/bin/python scripts/predict.py --cases data/test_cases_reworded.json --out rw.csv && .venv/bin/python evaluate.py rw.csv data/test_cases_reworded.json
```

## LLM detector

The Sacred Moment Detector uses Claude (`claude-opus-5-5`) when credentials are available, and the keyword fallback otherwise. To turn it on:
```bash
export ANTHROPIC_API_KEY=...
.venv/bin/python scripts/warm_cache.py              # labels every distinct text once -> kairos/detector_cache.json
KAIROS_DETECTOR=llm .venv/bin/uvicorn server.app:app --port 8765
```
Once the cache is warm, every mode (offline included) uses the cached LLM labels.

## Layout
```
kairos/agents/     signals · detector (+keywords) · decision · routing · drafter · guardrail
kairos/orchestrator.py   runs the agents per automation, fails closed
kairos/service.py  run, queue, human actions (contact, approve, keep/escalate/release), clock
server/app.py      FastAPI endpoints + serves server/static/index.html (dashboard)
docs/DEMO.md       demo walkthrough
```
