# Source Strategy

## Default Search Window

Search the current date minus three years through the current date unless the user specifies another window.

The scheduled radar cadence is every two months.

For scheduled operation, the recommended architecture is:

1. GitHub Actions runs the literature search on schedule.
2. The action generates a report ID and stable paper IDs.
3. The action writes history data for deduplication.
4. The action creates an HTML report with feedback links connected to a configured receiver.
5. The action emails the HTML report as an attachment.
6. Feedback clicks are recorded by the receiver without requiring the user to save or upload files.

Do not promise persistent HTML feedback from a static attachment alone. Persistent feedback needs a receiver endpoint or another external store.

## Preferred Sources

Use source pages and metadata APIs when available:

- OpenAlex for broad scholarly metadata, DOI, venue, publication date, concepts, and open-access links
- CrossRef for DOI, publisher metadata, and journal information
- Semantic Scholar for abstracts, citation signals, and influential references when available
- arXiv for recent preprints, used as a supplement rather than the main source
- Publisher pages for visible abstracts, graphical abstracts, and article metadata

Do not claim full-text reading unless the full text was actually accessible and read.

When OpenAlex/CrossRef lacks an abstract, check the DOI publisher page or other source page before excluding a top-venue or mechanism-adjacent candidate. If the source page is accessible in the interactive review but blocked in the automated script, store a short mechanism-evidence note for that DOI and mark the evidence level as page-text/manual-evidence rather than treating the paper as metadata-only.

## Journal and Venue Priority

Use journal/venue quality as a soft priority, not a sufficient inclusion criterion.

After the 2026-06-11 user feedback, every radar run must include a separate `top-venue scouting` lane. The target is at least three papers from top journals, major sub-journals, or strong IEEE Transactions-style specialist venues, but they must still pass the strict topic gate. Do not fill the main table with generic passive wireless, TENG, wearable, SAW, RFID/backscatter, or microwave/metamaterial papers merely to satisfy the top-venue target. If fewer than three top/strong-venue papers pass the gate, state the shortfall explicitly. Do not list non-recommended near-miss samples unless the user explicitly asks for algorithm diagnosis.

High-priority families:

- Nature and Nature Portfolio journals
- Science and AAAS journals
- Advanced Materials, Advanced Functional Materials, Advanced Science, Advanced Energy Materials, Advanced Intelligent Systems, and related Wiley Advanced journals
- Energy & Environmental Science
- ACS Nano, Nano Letters, ACS Sensors, ACS Applied Materials & Interfaces when strongly relevant
- Nano Energy
- Matter, Joule, Device, Cell Reports Physical Science when relevant
- IEEE Transactions series, especially sensors, electron devices, industrial electronics, instrumentation, antennas, microwave, circuits, IoT, biomedical circuits, and related device/system venues
- High-level conferences in sensors, MEMS, electron devices, circuits, antennas, HCI/wearables, and wireless systems when relevant

Impact factor greater than 15 is a soft heuristic. If exact current impact factor is unavailable or unstable, rely on venue family, publisher metadata, field reputation, and article relevance.

Low-priority venue rule:

- Reduce recommendations from MDPI journals by default, including Sensors, Micromachines, Energies, Electronics, Materials, Nanomaterials, Polymers, Applied Sciences, and related MDPI titles.
- MDPI papers may appear only as important near-misses or low-priority `可参考` items unless they are unusually direct for breakdown-discharge wireless sensing.
- Avoid filling the report with MDPI papers when top-venue or stronger specialist-venue papers are available.

## Query Families

Generate separate query families for:

1. Core breakdown-discharge wireless sensing:
   - breakdown discharge wireless sensing
   - triboelectric discharge wireless sensing
   - spark discharge electromagnetic signal sensor
   - microgap discharge wireless sensor
   - corona discharge electromagnetic sensing
   - RLC frequency modulation wireless sensor discharge
2. Mechanism support:
   - microgap gas breakdown electromagnetic emission
   - Paschen deviation microgap discharge sensor
   - discharge current waveform electromagnetic pulse
   - surface charge space charge breakdown microgap
3. Transferable wireless sensing:
   - flexible passive wireless sensor LC resonator
   - flexible RFID sensor wearable
   - chipless RFID flexible sensor
   - chip-less self-powered electronic patch
   - self-powered electronic patch wireless sensing
   - SAW flexible wireless sensor
   - backscatter wearable sensor
   - battery-free wireless flexible sensor
   - self-powered electrotactile textile haptic glove
   - electrotactile textile haptic human-machine interface
4. Self-powered wireless sensing:
   - self-powered wireless sensor energy harvesting
   - triboelectric wireless sensor battery-free
   - high voltage self-powered wireless sensing
5. Top-venue scouting:
   - Nature flexible wireless sensor battery-free
   - Nature Sensors self-powered sensor
   - Nature Sensors electronic patch
   - Nature Portfolio wireless passive sensor
   - Science Advances self-powered textile haptic
   - Advanced Materials flexible wireless sensor
   - ACS Nano wireless sensor battery-free
   - Nano Energy self-powered wireless sensor
   - IEEE Transactions partial discharge UHF sensor
   - IEEE Transactions wireless passive sensor
   - IEEE Transactions antennas microwave sensor

Refine query terms with user feedback after each radar cycle.

## Evidence Level Labels

Use one of:

- `metadata only`: title/venue/date/DOI only
- `abstract visible`: abstract or equivalent publisher summary read
- `page text visible`: publisher page, figures, or extended page text read
- `full text read`: full paper or open-access full text read
- `preprint`: arXiv or other preprint source

Closed-source papers should usually be `abstract visible` or `page text visible`.
