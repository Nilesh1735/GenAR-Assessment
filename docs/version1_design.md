# V1 Design — Reusable Regulatory Reporting Engine

## What V0 already proves

V0 is a working PADER generator, but the parts that matter for V1 are deliberately
general:

- **A report type is a config, not code.** `config/pader.yaml` declares sections,
  each section's `mode` (`table` / `narrative` / `both`), and the `required_analyses`
  it may cite. The pipeline reads the config; it has no PADER-specific branches.
- **Analyses are a registry.** Each analysis self-registers with `@register(key)` and
  returns a uniform `AnalysisResult` (figures, table, the case ids behind every number,
  caveats). New figures are new functions, not engine edits.
- **Grounding is report-type-agnostic.** The gate checks "is every prose number in this
  section's evidence packet?" — that holds for any report type.
- **Every run emits a manifest** (dataset SHA-256, config version, model, prompt hash,
  case count, timestamp) so any report is reproducible and auditable.

## Extending to PSUR / PBRER / DSUR

Because the split above is fixed, a new report type is:

1. A new YAML (`psur.yaml`): its section list, modes, and required analyses.
2. Only if it needs a figure no analysis yet produces: one new `@register`-ed function
   returning an `AnalysisResult`.

No change to the pipeline, grounding gate, prompts loader, or assembler. Shared
analyses (case counts, reactions, demographics, seriousness) are reused verbatim across
report types; the differences (cumulative vs interval data, benefit-risk sections,
line listings) are new configs and, where genuinely new, new analyses.

## Extending to other products

Product is a config field, not a code assumption. The same engine runs on any ICSR
export with the E2B/FAERS-style columns declared in `src/data/schema.py`. A different
product is a different `--data` file plus `product:` in the config. Where a product
needs a different source schema, the change is localized to `schema.py` +
`normalize.py`; everything downstream consumes the normalized `CaseData`.

## Evaluating at the scale of 1000 reports

The design assumes review does **not** scale by reading 1000 reports by hand:

- **The grounding gate is the automated first pass.** Every section of every report is
  machine-checked: no ungrounded number, no unknown analysis key. A report with any
  failing section is quarantined for human review; clean reports proceed. This turns
  "read everything" into "read the exceptions."
- **Structured logs make the batch queryable.** Each section emits a JSON event
  (`section_grounding` with status and counts). Aggregating the log gives a per-batch
  dashboard: pass rate, most-flagged sections, most-flagged figures.
- **Golden-number regression tests** pin the deterministic layer (dedup = 1024, AKI =
  80, …). If normalization or an analysis drifts, tests fail before any report ships.
- **Manifests enable diffing.** Two runs with the same dataset SHA and prompt hash must
  produce the same figures; a diff isolates whether a change came from data, config, or
  model.
- **Sampled human review** stays in the loop via the Streamlit UI: reviewers spot-check
  a stratified sample (all grounding-failures + a random slice of passes), approve or
  flag per section, and only approved sections export.

## Built now vs designed for later

| Capability | State |
|---|---|
| Report-type-as-config, registered analyses, run manifest, evidence tracing | **Built in V0** |
| Grounding gate + structured WARN logging | **Built in V0** |
| CLI + human-in-the-loop review UI | **Built in V0** |
| Batch runner over many products/periods writing a per-batch grounding summary | V1 — thin loop over the existing pipeline |
| MedDRA SOC dictionary → System Organ Class grouping (removes the "PT-level only" gap) | V1 — new normalize step + analysis |
| Product label / CCDS config → expectedness (listed vs unlisted) | V1 — new config + analysis |
| Persisted review/audit trail (who approved which section, when) | V1 — persist the UI's approval state alongside the manifest |

Each V1 item is additive: a new config, a new registered analysis, or a loop around the
existing pipeline. None require reworking the V0 core, which is the point of the split.
