# HTML Report Schema

## Report Contract

The formal radar output is a single HTML file suitable for email attachment and browser review.

The email body should not duplicate paper summaries. It may contain only a short note that the report is attached.

If user feedback must work without manual saving, exporting, or maintaining extra files, the HTML must not rely on local-only checkboxes. It must include ordinary links or buttons that submit feedback to a configured feedback receiver.

## Main Table Fields

Required columns:

1. `序号`
2. `推荐等级`
3. `文献类型`
4. `标题`
5. `摘要`
6. `期刊/会议`
7. `年份`
8. `DOI`
9. `证据级别`
10. `相关性评分`
11. `创新性评分`
12. `综合判断`
13. `创新点判断`
14. `可借鉴点`
15. `用户反馈`

`摘要` should include the visible abstract text from the metadata/source when available. If no abstract is available, state `未获取到摘要`.

`综合判断` should combine the screening reason and the relationship to the user's topic, such as why the paper entered the radar, whether it is core-chain, transferable, reference-only, or out-of-scope-adjacent, and the evidence boundary. Do not keep separate `为什么相关`, `排除/风险提示`, or `建议动作` columns in the main table.

Do not include a separate `是否顶刊` column. Venue quality is visible through `期刊/会议`, and novelty is judged separately.

## Paper Types

Use one of:

- `击穿放电无线传感`
- `击穿放电机理支撑`
- `柔性无线传感借鉴`
- `自供能/无电池无线传感借鉴`
- `预印本观察`
- `近似但排除`

## Feedback Controls

The HTML should include convenient one-click controls for:

- `极其相关`
- `相关`
- `可参考`
- `无关`
- `已下载`
- `已精读`
- `误判`
- `重点跟进`
- `下次少推此类`

Feedback controls must not move the reader away from the current table position. Avoid `href="#"`, hash anchors, or full-page navigation that resets horizontal scroll. Prefer buttons or non-navigating controls that submit feedback in the background when a feedback endpoint is configured.

After feedback, the selected option must be visually marked in place: keep the selected button in a clear colored active state, turn all other feedback options for the same paper black, and show a short current-feedback status. Users may change feedback repeatedly; every click should update the result and button colors.

The relevance feedback group is the primary learning signal:

- `极其相关`: direct core-chain match.
- `相关`: strong transfer path.
- `可参考`: indirect inspiration only.
- `无关`: negative example.

When persistence is required, submit to a configured feedback receiver without jumping away from the report. Use `fetch(..., {keepalive: true})`, a background form target, or another non-navigating mechanism. Provide a normal endpoint URL as fallback only when the user accepts leaving the page.

Recommended endpoint payload shape:

```html
https://<feedback-endpoint>/record?report_id=<REPORT_ID>&paper_id=<PAPER_ID>&action=useful&token=<TOKEN>
```

The endpoint should record:

- report ID
- paper ID
- DOI or arXiv ID
- action
- timestamp
- optional user token

After a click, the report should update the row status in place, such as `当前反馈：有用，更新时间 HH:MM:SS`. If the endpoint returns a response, handle it without resetting scroll. The user should not need to download, edit, save, upload any local feedback file, or return from a success page.

If no feedback receiver has been configured, the report may include non-persistent visual controls for review convenience, but it must clearly state that automatic feedback capture is not active. Do not present checkbox-only controls as working persistent feedback.

## Summary Section

Keep the summary short:

- run date
- search window
- sources searched
- number of candidates screened
- number included
- strongest 3 papers
- any important source limitations

Do not write a long literature review.

## Exclusion Section

After the user's 2026-06-11 feedback, do not show non-recommended examples in the normal report. If the recommendation table is empty, state that strict screening found no recommendable papers. Only produce exclusion samples when the user explicitly asks for algorithm diagnosis or debugging.

Never let exclusion rows look like recommendations. Do not show `暂不读` as a recommendation grade in the main table; excluded rows should be explicitly labeled as non-recommendation/剔除样例 if the user explicitly asks to see them.

## History Expectations

Future automation may maintain:

- `history.json`: DOI/arXiv/title fingerprints already recommended
- `feedback.json`, GitHub issue comments, GitHub artifact data, a form backend, or another configured feedback store: user decisions

The user should primarily interact with the HTML report. Supporting files are implementation details.

## Feedback Receiver Options

For a GitHub-hosted automation, acceptable feedback receiver patterns include:

- a lightweight serverless endpoint that writes feedback to the repository
- a preconfigured form endpoint, such as a private form backend, that exports machine-readable feedback
- a GitHub issue or discussion URL prefilled by each feedback button, if the user accepts the extra confirmation step

Prefer the first two options when the user requires no extra action beyond clicking a feedback control. Avoid solutions that require the user to manually save the HTML, edit CSV files, or upload feedback files.
