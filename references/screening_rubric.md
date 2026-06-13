# Screening Rubric

## Gate 1: Scope Fit

A paper enters scoring only if it satisfies at least one of these:

1. It directly studies breakdown-discharge-based wireless sensing.
2. It studies breakdown discharge, spark/corona/microplasma, or microgap gas breakdown and provides clear support for wireless sensing through EM emission, waveform, frequency, spectrum, device design, modeling, or experimental method.
3. It studies flexible, passive, self-powered, or battery-free wireless sensing with a transferable mechanism for the user's topic.
4. It is a high-impact methods, device, or modeling paper that can plausibly change the user's research design.

If the only match is a generic keyword such as TENG, discharge, flexible sensor, or wireless sensor, exclude it.

Do not treat scope fit as a small fixed keyword list. Judge the visible title, abstract, and page text as a mechanism chain. A paper can be relevant even if it does not use the exact anchor phrase, when the abstract shows:

- an energy or excitation source such as self-powered, friction-induced, triboelectric effect, contact electrification, electrostatic generation, or mechanical motion;
- a signal-generation step such as friction-induced electromagnetic waves, gas breakdown discharge, breakdown discharge, discharge-induced displacement current, EM/RF emission, or wireless electromagnetic waves;
- a sensing/readout/system step such as wearable sensing, wireless communication, wireless readout, information encoding, long-distance transmission, HMI, haptic feedback, or sensor monitoring.

If all three parts are present, treat the paper as a strong candidate even when the title lacks words such as `breakdown-discharge wireless sensing`. If two parts are present in a high-impact venue and the missing part is plausibly supplied by the abstract or figures, keep it as `可参考` pending source-page review.

After the 2026-06-11 user feedback, apply a stricter topic boundary:

- Pure TENG, TENG-based harvesting/sensing, and triboelectric material/device enhancement are `可参考` at most unless they explicitly connect to breakdown-discharge-triggered wireless signals, EM/RF emission, or a directly transferable wireless readout architecture.
- Partial-discharge prediction, diagnosis, cable/transformer monitoring, high-voltage insulation, and sensor-fusion papers are usually `无关` or `可参考`; include only when the paper provides transferable EM waveform, RF/UHF reception, antenna, discharge-source localization, or experimental method value for the user's discharge-wireless-sensing chain.
- Pure ML prediction/classification, ordinary condition monitoring, or local discharge fault diagnosis should not enter the main recommendation table unless the device/readout mechanism is the central contribution.
- MDPI-family papers should be down-ranked by default and usually placed in near-misses unless they are unusually direct and technically useful.

After the user's completed feedback on the 2026-06-11 test report, treat broad transferable categories as negative for main-table inclusion:

- Generic passive wireless sensors, SAW sensors, chipless/RFID/backscatter systems, battery-free wearables, implantable communication systems, microwave/metamaterial sensors, and ordinary self-powered systems are `无关` for this radar unless the abstract/title/page text explicitly connects to the user's mechanism chain.
- TENG/self-powered papers are `无关` by default, not `可参考`, unless the abstract/page text explicitly involves triboelectric-discharge effect, gas breakdown discharge, friction-induced electromagnetic waves, discharge-triggered EM/RF emission, spark/corona/breakdown, or a wireless readout/communication mechanism that is directly analogous to the user's system.
- Top venue is not a substitute for topic fit. A top-venue paper that only matches generic wireless/passive/TENG terms should be excluded or placed in near-misses, not the main table.
- The main table should prefer being empty or very short over filling with generic transfer candidates.

## Gate 2: Conservative Scoring

Score only papers that pass Gate 1.

### Relevance Score, 0-10

- 9-10: Directly matches breakdown-discharge wireless sensing or strongly supports its core chain.
- 7-8: Strongly transferable wireless sensing mechanism, device architecture, or modeling method.
- 5-6: Some useful mechanism or system idea, but indirect.
- 3-4: Keyword-adjacent with weak transfer value.
- 0-2: Out of scope.

### Novelty Score, 0-10

- 9-10: New sensing principle, new wireless readout mechanism, unusually strong system integration, or high-impact conceptual advance.
- 7-8: Meaningful device/system innovation with clear transfer value.
- 5-6: Incremental but useful method, parameter study, or implementation detail.
- 3-4: Mostly routine adaptation.
- 0-2: Low novelty or unclear contribution.

### Recommendation Levels

- `必读`: relevance >= 8 and novelty >= 7, or direct core-chain paper.
- `建议读`: relevance >= 7 or novelty >= 8 with clear transfer path.
- `可参考`: useful but indirect; only recommend when the paper has real reference value for the topic.
- `暂不读`: near-miss, weak transfer, or insufficient evidence.

Map user feedback to the internal standard:

- `极其相关`: directly advances breakdown-discharge wireless sensing or a core signal-generation/readout mechanism; strengthen these concepts heavily.
- `相关`: strong transferable mechanism, system architecture, or experimental method; keep similar candidates but do not over-promote adjacent keywords.
- `可参考`: only indirect inspiration; keep as low-priority/top-venue-observation material, not a main recommendation pattern.
- `无关`: negative example; extract exclusion cues and reduce similar future recommendations.

Do not include `暂不读` in the recommendation table. If an important near-miss must be shown for algorithm diagnosis, put it in a clearly labeled non-recommendation/exclusion section, not in the recommended-paper table.

## Innovation Judgment

Judge novelty by:

- whether it introduces a new signal generation or modulation path
- whether it improves wireless readout, distance, stability, anti-interference, or multi-parameter decoupling
- whether it adds a flexible, wearable, MEMS, or packaging approach that can transfer to discharge sensing
- whether it provides a model or experiment that helps explain discharge-triggered EM signals
- whether it appears in a high-impact venue with a nontrivial technical contribution

## Exclusion Rules

Exclude by default:

- pure TENG material/contact electrification papers
- ordinary TENG-based sensing/energy-harvesting papers without breakdown-discharge or wireless readout transfer
- pure flexible material or electrode papers without wireless readout
- pure ML sensor classification papers
- pure partial-discharge prediction, high-voltage insulation, cable/transformer monitoring, or fault-diagnosis papers with no transferable EM-signal/device/readout path
- pure plasma/high-voltage breakdown papers with no sensor or EM-signal path
- biomedical wearable demos without transferable wireless mechanism
- broad review papers unless they are unusually useful as a map of wireless sensing mechanisms

When excluding a seemingly relevant paper, give one concise reason such as:

- `pure TENG, no wireless/discharge readout`
- `breakdown mechanism but no EM-sensing transfer path`
- `partial discharge monitoring/prediction, weak transfer to user's wireless sensing chain`
- `wireless sensor but no flexible/passive/self-powered insight`
- `materials-only contribution`
- `MDPI/low-priority venue and only keyword-adjacent`

## Feedback Learning

Feedback updates rules and weights:

- Papers marked `极其相关` strongly reinforce their topic terms, venues, mechanisms, and methods.
- Papers marked `相关` reinforce the mechanism and venue moderately.
- Papers marked `可参考` are retained as indirect inspiration only; do not promote similar papers to `必读`.
- Papers marked `无关` or `误判` become negative examples; extract exclusion cues.
- Papers marked `已精读` should not repeat unless a formal version, correction, or major follow-up appears.
- Do not silently change the topic boundary; summarize proposed criterion changes for user approval when substantial.
