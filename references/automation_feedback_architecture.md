# Automation and Feedback Architecture

## Goal

Run the literature radar every two months, email a single HTML report attachment, and let the user submit feedback by clicking controls in the report without saving, exporting, editing, or uploading any file.

## Recommended Architecture

Use a GitHub repository with three moving parts:

1. `scheduled radar action`
   - Runs every two months with GitHub Actions.
   - Searches scholarly sources.
   - Deduplicates candidates against history.
   - Scores and filters papers with the skill rubric.
   - Generates a single HTML report.
   - Sends the HTML report as an email attachment.

2. `static report`
   - The emailed HTML report is readable offline as a static document.
   - Feedback controls are ordinary links, not local-only checkboxes.
   - Each feedback link contains `report_id`, `paper_id`, `doi`, `action`, and a lightweight token.

3. `feedback receiver`
   - A small HTTPS endpoint records feedback clicks.
   - The user sees a success page after clicking, such as `反馈已记录`.
   - The next scheduled radar run reads the feedback store and adjusts rules or weights.

This is the only architecture class that satisfies the user's requirement: no extra saving or file maintenance after clicking feedback.

## Feedback Link Contract

Each feedback action should be a normal hyperlink so it works from an email attachment or a browser:

```html
<a href="https://<feedback-endpoint>/record?report_id=2026-06&paper_id=p012&doi=10.xxxx/yyyy&action=useful&token=<TOKEN>">有用</a>
```

Required fields:

- `report_id`: identifies the radar cycle.
- `paper_id`: stable ID generated for the report.
- `doi`: DOI when available.
- `arxiv_id`: arXiv ID when DOI is unavailable.
- `action`: one of the accepted feedback labels.
- `token`: lightweight anti-spam or user-identification token.

Accepted actions:

- `downloaded`
- `read`
- `useful`
- `irrelevant`
- `wrong_match`
- `follow_up`
- `less_like_this`

The receiver should store timestamp, request IP if appropriate, and user agent only when needed for debugging or abuse prevention.

## Preferred Feedback Receiver Options

### Option A: Serverless Endpoint

Best fit for the requirement.

Use a lightweight endpoint that accepts feedback links and writes to a machine-readable store. The store can be a JSON file, database table, spreadsheet, or repository artifact depending on the implementation.

Pros:

- one-click user feedback
- works from static HTML attachments
- easy for the next scheduled run to ingest
- cleanest long-term automation

Cons:

- requires one small hosted endpoint
- requires a token or other simple abuse-control strategy

### Option B: Form Backend With Direct Submit Links

Acceptable if the form backend supports direct link submission or prefilled links that do not require the user to manually edit or upload files.

Pros:

- less custom backend code
- may be easier to maintain

Cons:

- some form services require an extra confirmation page
- export format and API access may be less convenient

### Option C: GitHub Issue/Discussion Links

Use prefilled GitHub issue or discussion URLs for feedback.

Pros:

- no separate backend
- feedback stays in the repository

Cons:

- usually requires the user to confirm submission in GitHub
- does not fully satisfy the no-extra-action requirement

Use only as a fallback if the user accepts the extra confirmation step.

## Not Acceptable for Persistent Feedback

Do not use these as the only feedback mechanism when persistence is required:

- local-only checkboxes in an HTML attachment
- JavaScript that stores feedback only in browser local storage
- requiring the user to save the modified HTML file
- requiring the user to edit or upload CSV/JSON feedback files
- email replies that must be manually parsed, unless the user explicitly chooses that workflow

These can be used only as visual conveniences, not as reliable feedback capture.

## Repository State Files

The automation may maintain these files internally:

- `data/history.json`: DOI/arXiv/title fingerprints already recommended
- `data/feedback.jsonl`: feedback events from the receiver
- `data/profile_weights.json`: adjusted keyword, venue, and exclusion weights
- `reports/<report_id>.html`: generated reports

The user should not need to edit these files during normal use.

## Feedback Learning Policy

Feedback changes rules and weights, not the fundamental research topic.

Examples:

- `useful`: increase weight for the paper's mechanism, venue, and query terms
- `irrelevant`: add negative cues or lower similar query terms
- `wrong_match`: review Gate 1 scope wording and exclusion rules
- `follow_up`: keep the DOI/topic in future related-work searches
- `less_like_this`: reduce similar paper classes without banning the whole venue

For major topic-boundary changes, summarize the proposed rule update and ask for user approval before applying it permanently.

## Email Delivery Contract

Email should include:

- a short subject with report ID and date range
- a concise body saying the radar HTML is attached and listing the main run counts
- the HTML report attachment
- the JSON run result attachment when configured

Email delivery must be optional and configuration-driven:

- local/manual runs skip email unless SMTP and recipient environment variables are provided
- GitHub scheduled runs can send email when repository variables/secrets are configured
- recipient addresses and SMTP credentials must never be hardcoded in source files
- SMTP passwords and usernames belong in repository secrets, not variables

The sender should tolerate missing email configuration by skipping delivery unless email is explicitly required.

## Security and Privacy Notes

- Tokens should prevent accidental or public spam submissions.
- Do not place secret API keys in the HTML report.
- DOI, title, action, and report ID are usually safe to include in feedback links.
- If the report repository is public, avoid storing private notes directly in publicly visible files.
