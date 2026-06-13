---
name: research-paper-radar
description: Use when monitoring, searching, screening, or reporting recent research papers for the user's PhD topic on breakdown-discharge-based wireless sensing and transferable flexible wireless sensing technologies. This skill produces a conservative literature radar, usually as an HTML table report, with relevance and novelty judgments, DOI-only download pointers, and feedback-aware filtering. Do not use for long literature reviews, automatic paid full-text downloads, generic TENG paper searches, or broad PRISMA-style systematic reviews.
---

# Research Paper Radar

## Purpose

Create a high-precision literature radar for the user's PhD topic: breakdown-discharge-based wireless sensing, plus flexible, passive, self-powered, or battery-free wireless sensing ideas that can transfer into that topic.

This skill is for discovery and triage. It does not write long reviews, download paid papers, bypass access limits, or treat abstract-level evidence as full-text reading.

## Core Boundaries

- Prioritize relevance and field novelty over quantity. Return fewer papers when candidates are weak.
- Search the most recent three years by default.
- Use a two-month cadence for scheduled radar runs unless the user requests another window.
- Prefer English literature.
- Provide DOI only as the download pointer. Include arXiv IDs only for preprints.
- Include preprints only when they are strongly relevant or unusually novel, and label them clearly.
- Closed-source papers may be judged from visible title, abstract, graphical abstract, metadata, and publisher page text; state the evidence level.
- Do not recommend pure TENG, pure triboelectric material, pure material synthesis, pure ML prediction, or ordinary plasma/high-voltage engineering papers unless they directly support wireless sensing through discharge-triggered signals, modulation, device design, modeling, or experimental method.

## Reference Files

Read only the files needed for the task:

- `references/research_profile.md`: topic scope, positive/negative keyword families, and paper classes.
- `references/source_strategy.md`: sources, journal/venue priorities, high-impact heuristics, and scheduling assumptions.
- `references/screening_rubric.md`: two-gate screening, relevance score, novelty score, recommendation levels, and exclusion rules.
- `references/html_report_schema.md`: required HTML report fields, feedback controls, history expectations, and email-output contract.
- `references/automation_feedback_architecture.md`: GitHub Actions scheduling, email delivery, and no-save feedback receiver design.

## Standard Workflow

1. Clarify the run mode if unclear:
   - `manual radar`: screen recent papers for a requested time window.
   - `scheduled radar design`: create or update a GitHub Actions/email workflow.
   - `feedback update`: incorporate the user's HTML feedback into future criteria.
2. Load `research_profile.md` and `screening_rubric.md`.
3. For live searches, use current web/API sources and verify dates, venues, DOI/arXiv IDs, and abstracts from source pages or scholarly metadata.
4. Candidate generation:
   - Build queries for both tracks: breakdown-discharge wireless sensing and transferable flexible wireless sensing.
   - Keep source provenance for every candidate.
   - Deduplicate by DOI, arXiv ID, and normalized title.
5. Screening:
   - Apply Gate 1 to decide whether the paper belongs in scope.
   - Apply Gate 2 to score topic relevance and novelty.
   - Exclude weak candidates instead of filling the table.
6. Reporting:
   - Load `html_report_schema.md`.
   - Produce a compact HTML table report when creating a deliverable.
   - Include short reasons, not long review prose.
   - Include a small exclusion note section only for important near-misses.
7. Feedback:
   - For no-save/no-export feedback, use endpoint-backed feedback links or buttons from the HTML report.
   - Do not claim local checkbox-only feedback is persistent.
   - If no feedback endpoint is configured, ask the user to choose or provide one before promising automatic feedback capture.
   - Treat user feedback as rule and weight updates, not model training.
   - If the user marks papers as useful, strengthen the matching concepts and venues.
   - If the user marks papers as irrelevant, add or adjust exclusion cues.

## Borrowed Design Patterns

Use these as inspiration, not as dependencies:

- `paper-search-pro`: multi-source literature discovery and single-file HTML report.
- `ai-skill-arxiv`: watchlist and seen-ID monitoring.
- `ai-skill-scholar`: OpenAlex-oriented discovery and two-pass screening.
- `paperradar-agent`: scheduled digest, journal watchlist, and relevance scoring.
- Academic research skill collections: workflow boundaries and research-task categorization.

## Output Style

For chat summaries, answer in Chinese unless the user asks otherwise.

For HTML reports, keep the table dense and practical. Do not generate a long narrative literature review. Each included paper must have a concrete reason tied to breakdown-discharge wireless sensing or transferable flexible wireless sensing.
