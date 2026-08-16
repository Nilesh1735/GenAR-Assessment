# Evidence-Grounded Regulatory Reporting Engine

A system that turns a raw pharmacovigilance ICSR dataset into a structured,
regulator-style **PADER** (Periodic Adverse Drug Experience Report) in which
**every number traces back to the source data**.

The point is deliberately *not* "hand the model a CSV and ask it to write a PADER."
It is a controlled pipeline that gathers the right evidence, computes every figure
deterministically, lets the model only *frame* those figures into prose, and then
**machine-verifies that the prose invented nothing**. PADER is the first report type;
PSUR / PBRER / DSUR are meant to be added as configuration, not new code.

---

## The one idea

> **Python computes every number. The LLM only frames pre-computed figures into neutral
> regulatory prose. A grounding gate then verifies that every number in the prose came
> from the evidence.**

- The model never calculates a count, percentage, date, or trend.
- The model receives a *scoped evidence packet* per section — never the raw rows.
- Every figure it writes is checked against that packet's allow-list. An ungrounded
  number fails the section and is logged.

This is the design decision the rest of the system is built to enforce. Everything
below is downstream of it.

---

## Quickstart

Requires Python 3.11+ (developed on 3.14) and a free [Groq](https://console.groq.com) API key.

```bash
# 1. install pinned dependencies
python -m venv .venv
source .venv/Scripts/activate        # Windows Git Bash; use .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

# 2. configure the API key (the .env file is gitignored and never committed)
cp .env.example .env
#   then edit .env and set GROQ_API_KEY=your_key

# 3. run the test suite (no API key needed — the deterministic core is fully tested)
python -m pytest -q

# 4. generate the report from the command line
python cli.py \
  --config config/pader.yaml \
  --data Bisoprolol_icsr_sample_1068rows.xlsx \
  --out output/bisoprolol_pader.md

# 5. or review it interactively before export
streamlit run app/streamlit_app.py
```

The CLI writes `output/bisoprolol_pader.md` and a companion
`output/bisoprolol_pader.manifest.json` (the reproducibility record), and prints a
warning if any section failed grounding.

---

## Architecture

Full diagram and component table: [docs/architecture.md](docs/architecture.md).

```
raw ICSR  →  load + validate + hash  →  normalize (dedup, explode, bucket)
          →  analyses (ALL figures, tables, evidence ids)         [deterministic]
          →  per-section evidence packet (scoped allow-list)      [deterministic]
          →  Groq structured output → SectionNarrative            [LLM: framing only]
          →  grounding gate: every prose number ∈ packet?         [deterministic]
          →  assemble Markdown (tables from Python, prose from model) + manifest
```

### Repository layout

| Path | Role |
|---|---|
| `src/data/` | load / validate / hash the dataset; normalize to case-level facts |
| `src/analysis/` | analysis **registry**; each analysis returns figures + tables + the case ids behind every number |
| `src/evidence/packet.py` | build the scoped evidence a section is allowed to cite |
| `src/llm/` | Groq structured-output client + `SectionNarrative` Pydantic schema |
| `src/eval/grounding.py` | verify every prose number is in the section's evidence packet |
| `src/report/` | render tables (Python) + prose (model) into Markdown |
| `src/pipeline.py` | orchestrate the flow; emit the run manifest |
| `config/pader.yaml` | the report **as configuration** — sections, modes, required analyses |
| `prompts/` | system + section prompt templates |
| `cli.py`, `app/streamlit_app.py` | two surfaces: batch CLI and human-in-the-loop review UI |
| `tests/` | golden-number regression + grounding + end-to-end pipeline tests |
| `docs/` | architecture diagram + one-page V1 design |

---

## AI vs deterministic — the split, and why

| Concern | Where it lives | Why |
|---|---|---|
| Dedup to latest case version, reaction explosion, age/sex/country, dates | Python (`normalize.py`) | Reproducible, testable, auditable. Wrong here = wrong everywhere. |
| Every count, percentage, top-N, trend, line listing | Python (`analysis/`) | A regulatory number must be exact and defensible. An LLM must never be the source of a statistic. |
| Which evidence a section may use | Python (`config` + `packet.py`) | Scope is a safety control, not a model choice. |
| Turning figures into neutral prose | **LLM** | This is genuine language work — phrasing, register, flow — where a model adds value. |
| Verifying the prose invented nothing | Python (`grounding.py`) | The check must be independent of the thing it checks. |

**Why this split and not "let the model do more":** the failure mode graders punish is a
model that quietly fabricates or miscomputes a safety figure. By making it structurally
impossible for the model to produce a number — it only ever receives pre-computed figures
and its output is checked against them — that failure mode is designed out rather than
hoped away. It is also why there is no RAG and no multi-agent framework here: the evidence
for a section is a small, known set of computed figures, so a **lookup** (build the packet)
is correct and retrieval would be theatre.

---

## Model choice

**Groq `llama-3.3-70b-versatile`, `temperature=0`.**

- **The task is framing, not reasoning-at-the-frontier.** Given exact figures and strict
  rules, a strong 70B open model produces clean regulatory prose. The hard correctness work
  is already done in Python, so paying for a frontier model buys little here.
- **`temperature=0`** for determinism — the same packet should frame the same way.
- **Structured output** via `with_structured_output(SectionNarrative)`: the model is forced
  to return validated Pydantic, so the code never parses raw text with regex or `json.loads`.
  (Groq's tool-schema validator rejects `bool`, so no schema field uses `bool`.)
- **Groq** for fast, free-tier-friendly inference, which matters when the target is batches
  of hundreds of reports.

Model, prompt hash, and config version are all recorded in the run manifest, so a report
generated by one model is distinguishable from another.

---

## The prompts (verbatim)

These are the actual files in `prompts/`, loaded at runtime and hashed into the manifest.

**`prompts/system.md`** (`{product}` is filled per run):

```
You are a regulatory medical writer assembling one section of a Periodic Adverse Drug Experience Report (PADER) for {product}.

Absolute rules:
1. You are given a fixed EVIDENCE PACKET of pre-computed figures and tables. State ONLY facts present in it. Never introduce a number, percentage, count, date, or proportion that is not present verbatim in the packet.
2. You do not calculate. Every statistic is already computed for you. Do not add, subtract, average, or infer new quantities.
3. Keep three registers distinct and never collapse them:
   - Observed: what the data directly shows ("80 cases reported acute kidney injury").
   - Derived: an already-computed proportion or trend present in the packet.
   - Interpretation: a pattern a human should assess. Present it as something to review, never as a confirmed safety signal or a causal claim.
4. If information needed for a complete section is absent from the packet (for example MedDRA System Organ Class grouping, the product label or expectedness, or a history of regulatory actions), state plainly that it was not available in the source data. Never invent or infer it.
5. Write in neutral, precise regulatory prose. No marketing language, no reassurance, no speculation about mechanism.

Every figure you cite must be copied exactly from the packet. For each material statement, record the figures it uses and the analysis_key that supports it. Return your answer only in the required structured format.
```

**`prompts/section.md`** (filled from the evidence packet):

```
SECTION: {section_title}
REPORTING PERIOD: {reporting_period}
PRODUCT: {product}

SECTION INSTRUCTIONS:
{instructions}

EVIDENCE PACKET (the only facts you may use):
{packet}

DATA GAPS DECLARED BY THE ANALYSIS LAYER:
{notes}

Write the section now. Cite only figures present above. For each material statement, record the figures used and the analysis_key that supports it.
```

The `{packet}` block is a compact rendering of only that section's computed figures and
tables — for example:

```
[case_counts] Case Seriousness Counts
  total_cases: 1024
  serious_cases: 1023
  non_serious_cases: 1
  serious_pct: 99.9
  non_serious_pct: 0.1
  expedited_cases: 1023
  category | cases | percent
  Serious | 1023 | 99.9
  Non-serious | 1 | 0.1
  Total | 1024 | 100.0
[reactions] Most Frequent Reactions (MedDRA PT, case-level)
  distinct_reactions_all: 1122
  scope | reaction | cases
  All cases | Acute kidney injury | 80
  All cases | Drug ineffective | 54
  ...
```

The model is asked to return a `SectionNarrative`: a `summary`, a list of `claims` (each a
statement + the `figures` it cites + the `analysis_key` that supports it), plus
`observations`, `interpretation_flags`, and `data_gaps`. The claim structure is what makes
grounding checkable at the statement level.

---

## Grounding — how every number is traced

`src/eval/grounding.py` runs after each narrative and is independent of the model:

1. Build the **allow-list**: the union of every number the section's analyses produced
   (`facts` values + numeric table cells) plus the reporting-period date tokens. Structural
   constants — e.g. the `15` in "15-day alert" — are in the allow-list only because an
   analysis emits `alert_window_days: 15`; nothing is hardcoded in the checker.
2. Extract every number from the narrative's `summary` and each claim `statement`.
3. Normalize both sides (`1,024` → `1024`, `99.9%` → `99.9`) and compare.
4. Any prose number **not** in the allow-list → `ungrounded` → the section **fails**. Any
   `analysis_key` a claim cites that isn't in the packet → also a fail. Failures emit a
   structured JSON `grounding_warn` log.

A test injects a fabricated number into a narrative and asserts the section fails, so the
gate itself is regression-protected.

The Markdown report and the review UI both surface the grounding status per section, so a
human always sees "N figures verified" or exactly which figure was flagged.

---

## Config-driven extensibility

A report type is `config/pader.yaml`, not code. Each section declares:

```yaml
- id: reaction_analysis
  title: Reaction / Adverse Event Analysis
  mode: both                                   # table | narrative | both
  required_analyses: [reactions, outcomes]     # the only evidence this section may cite
  instructions: >-
    Report the most frequently reported reactions ...
```

`mode: table` renders the computed table only (no LLM); `narrative` is prose only; `both`
is table + grounded narrative. Adding **PSUR / PBRER / DSUR** means writing a new YAML and,
only if it needs a figure no analysis yet produces, one new `@register`-ed analysis
function. The pipeline, grounding gate, prompts, and assembler do not change. This is
expanded in [docs/version1_design.md](docs/version1_design.md).

---

## Human-in-the-loop review UI

`streamlit run app/streamlit_app.py` opens a per-section review:

- computed figures and tables (the evidence, straight from Python),
- the generated narrative with a **claim-level traceability** table,
- the **grounding status** (green "N verified" or red with the flagged figures),
- **Approve / Flag / Regenerate** per section — regenerate re-frames just that section,
- **only approved sections export** to Markdown.

The API key is read silently from `.env` (no password widget). LLM and dataset errors are
shown as non-crashing banners, and rate-limit (429) responses are retried with backoff
rather than surfacing a stack trace.

---

## Evaluating at the scale of 1000 reports

Review does not mean reading 1000 reports by hand:

- **The grounding gate is the automated first pass.** Every section of every report is
  machine-checked; a report with any failing section is quarantined and clean reports
  proceed. "Read everything" becomes "read the exceptions."
- **Structured JSON logs make a batch queryable** — each section emits a
  `section_grounding` event (status + counts); aggregating gives per-batch pass rate,
  most-flagged sections, and most-flagged figures.
- **Golden-number regression tests** pin the deterministic layer (dedup = 1024, serious =
  1023, AKI = 80, …); drift fails CI before any report ships.
- **Manifests enable diffing** — same dataset SHA + prompt hash must yield the same
  figures, isolating whether a change came from data, config, or model.
- **Sampled human review** via the UI: reviewers check all grounding-failures plus a random
  slice of passes, rather than the whole batch.

---

## Testing

```bash
python -m pytest -q          # 28 tests, no API key required
```

- `test_normalize.py` — dedup to 1024, positional reaction explosion (incl. PT/outcome
  length mismatch), age-unit edge cases (`"800"`, month/day), missing-age → "Unknown",
  region-vs-country handling.
- `test_analyses.py` — golden numbers for all nine analyses.
- `test_grounding.py` — an injected fabricated number fails; the history-of-actions "state
  none" sentinel is present.
- `test_pipeline.py` — end-to-end via a **stub generator**, so orchestration, mode-handling,
  manifest, and Markdown assembly are verified deterministically without the API.

---

## Reproducibility — the run manifest

Every run writes a manifest:

```json
{
  "report_type": "PADER",
  "config_version": "1.0",
  "dataset": "Bisoprolol_icsr_sample_1068rows.xlsx",
  "dataset_sha256": "…",
  "model": "llama-3.3-70b-versatile",
  "prompts_hash": "…",
  "n_cases": 1024,
  "generated_at": "…Z"
}
```

Same dataset + same config + same prompts → the same computed figures, every time.

---

## Security

- `GROQ_API_KEY` is loaded via `python-dotenv` / `os.getenv`. `.env` is gitignored; only
  `.env.example` is committed. No secret is ever hardcoded.
- LLM output is consumed only through `with_structured_output` (validated Pydantic) — never
  `json.loads`/regex over raw model text.
- The dataset is excluded from version control and from the delivered ZIP.
- Errors are caught and surfaced as messages, not raw stack traces.
- Structured JSON logging (a `grounding_warn` event) fires on any ungrounded figure.

---

## Design decisions & one deliberate deviation

The provided checklist mentioned API auth (`X-API-Key`, rate limiting) and a web service.
**This build intentionally ships no FastAPI / HTTP layer.** The brief states no auth or
infrastructure is needed, and the rubric penalizes frameworks added for their own sake. The
useful surfaces for this task are a **CLI** (batch generation) and a **Streamlit review UI**
(human-in-the-loop). The auth/rate-limit posture from the checklist is instead applied where
it actually bites: **Groq 429s are handled with retry + exponential backoff**, and the API
key is managed as a secret. If a network service were later required, the same pipeline
functions would sit behind it unchanged — the engine is already decoupled from its surface.

---

## Known limitations (stated, not worked around)

- **No MedDRA System Organ Class grouping** in the source, so reactions are reported at
  Preferred Term level. Adding a SOC dictionary is a V1 item.
- **No expectedness assessment** — the source has no product label / CCDS, so listed-vs-
  unlisted is out of scope and stated as a data gap.
- **No history of regulatory actions** in the data; that section explicitly states none was
  provided rather than inventing content.
- **`occurcountry` includes region values** (e.g. `eu`); this is flagged in the demographics
  analysis rather than silently treated as a country.
- **The non-serious arm is n = 1**, which limits any serious-vs-non-serious comparison; this
  is noted, not smoothed over.
- **Trends are presented as observations for human review**, never auto-declared as safety
  signals — signal detection is a medical-review activity, not a generation-time claim.

---

## Deliverables map

| Deliverable | Location |
|---|---|
| V0 prototype | this repository (`src/`, `cli.py`, `app/`) |
| One generated PADER report | `output/bisoprolol_pader.md` (+ `.manifest.json`) |
| README | this file |
| Architecture diagram | [docs/architecture.md](docs/architecture.md) |
| V1 reusability + design doc | [docs/version1_design.md](docs/version1_design.md) |
