from __future__ import annotations

from pydantic import BaseModel, Field


class Claim(BaseModel):
    statement: str = Field(description="One factual sentence grounded entirely in the evidence packet.")
    figures: list[str] = Field(
        default_factory=list,
        description="Exact numeric figures cited in this statement, copied verbatim from the packet, e.g. '1024', '80', '99.9%'.",
    )
    analysis_key: str = Field(description="Key of the packet analysis that supports this statement, e.g. 'case_counts'.")


class SectionNarrative(BaseModel):
    summary: str = Field(
        description="Neutral regulatory prose for this section, framing only the figures provided in the packet. Introduce no new numbers."
    )
    claims: list[Claim] = Field(
        description="Each material statement in the summary, decomposed with the figures it cites and the supporting analysis_key."
    )
    observations: list[str] = Field(
        default_factory=list,
        description="Observed data points stated only as observations, without medical conclusions.",
    )
    interpretation_flags: list[str] = Field(
        default_factory=list,
        description="Patterns a human reviewer should assess; never asserted as a confirmed safety signal or causal claim.",
    )
    data_gaps: list[str] = Field(
        default_factory=list,
        description="Relevant information absent from the evidence, e.g. MedDRA SOC grouping, product label, or history of actions.",
    )
