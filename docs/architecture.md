# Architecture

## Design principle

One hard split runs through the whole system:

- **Python computes every number, table, percentage, date, and trend.**
- **The LLM only frames pre-computed figures into neutral regulatory prose. It never calculates.**

A grounding gate sits between the LLM and the report: every number that appears in the
narrative must trace back to a figure the analysis layer produced, or the section fails.

## End-to-end flow

```mermaid
flowchart TD
    subgraph inputs[Inputs]
        DS[(ICSR dataset<br/>xlsx / csv)]
        CFG[report config<br/>config/pader.yaml]
        PR[prompts<br/>system.md · section.md]
    end

    subgraph deterministic[Deterministic zone — every figure originates here]
        LD[loader<br/>load · validate · sha256]
        NM[normalize<br/>dedup → 1024 cases<br/>explode reactions positionally<br/>bucket age · pick country · parse dates]
        CD[CaseData<br/>cases + reactions]
        AN[analysis registry<br/>run required analyses]
        AR[AnalysisResult per key<br/>facts · table · evidence ids · notes]
        PK[build_packet<br/>scoped evidence per section]
        EP[EvidencePacket<br/>allowed_numbers set]
    end

    subgraph llm[LLM zone — framing only, no arithmetic]
        GEN[Groq structured output<br/>llama-3.3-70b-versatile]
        SN[SectionNarrative<br/>summary + claims + gaps]
    end

    subgraph gate[Grounding gate]
        GC{every prose number<br/>in allowed_numbers?}
        GR[GroundingReport<br/>pass / fail + flagged figures]
    end

    subgraph outputs[Outputs]
        ASM[assemble Markdown<br/>tables from Python<br/>prose from approved narrative]
        MAN[run manifest<br/>dataset sha · config ver · model · prompt hash]
        MD[[report.md + manifest.json]]
    end

    DS --> LD --> NM --> CD --> AN --> AR
    CFG --> AN
    AR --> PK --> EP --> GEN
    PR --> GEN --> SN --> GC
    EP --> GC
    GC -- pass --> GR
    GC -- fail --> GR
    GR --> ASM
    AR --> ASM
    ASM --> MD
    MAN --> MD

    CLI[cli.py] -.drives.-> LD
    UI[streamlit review UI] -.drives.-> LD
```

## Why the pieces exist

| Component | Responsibility | AI or deterministic |
|---|---|---|
| `src/data/loader.py` | load xlsx/csv, validate shape, hash for the manifest | deterministic |
| `src/data/normalize.py` | dedup to latest case version, positional reaction explode, age buckets, country, dates | deterministic |
| `src/analysis/` | registry of analyses; each returns figures + tables + the case ids behind every number | deterministic |
| `src/evidence/packet.py` | assemble the scoped evidence a section is allowed to cite | deterministic |
| `src/llm/` | Groq structured-output wrapper + `SectionNarrative` schema; frames figures into prose | AI |
| `src/eval/grounding.py` | verify every prose number is in the packet's allow-list | deterministic |
| `src/report/` | render tables from Python + prose from the approved narrative into Markdown | deterministic |
| `src/pipeline.py` | orchestrate the flow, emit the reproducibility manifest | deterministic |
| `config/pader.yaml` | declares the report: sections, modes, required analyses | config |

## Config-driven extensibility

A report type is a YAML file, not code. Each section declares a `mode`
(`table` = computed table only, `narrative` = prose only, `both`) and the
`required_analyses` it may cite.

```mermaid
flowchart LR
    subgraph configs[report configs]
        P[pader.yaml]
        S[psur.yaml · new]
        D[dsur.yaml · new]
    end
    subgraph engine[unchanged engine]
        E[pipeline + analysis registry + grounding]
    end
    P --> E
    S --> E
    D --> E
    E --> OUT[[grounded report]]
```

Adding PSUR/PBRER/DSUR means writing a new YAML (and, only if it needs a figure
no analysis yet produces, a new `@register`-ed analysis function). The pipeline,
grounding gate, and assembler do not change.
