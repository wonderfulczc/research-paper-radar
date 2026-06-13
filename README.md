# Research Paper Radar / 文献雷达

> Conservative literature radar for breakdown-discharge-based wireless sensing.
>
> 面向“基于击穿放电的无线传感技术”的高保守文献雷达。

## 中文说明

### 目标

`research-paper-radar` 是一个 Codex skill 与 GitHub Actions 可运行包，用于检索、筛选和报告与以下方向相关的近年论文：

- 基于击穿放电、气体放电、摩擦诱导电磁波或瞬态电磁信号的无线传感
- 自供能、无电池、柔性、可穿戴无线传感中可迁移到该课题的机制和系统设计
- 顶刊、大子刊、强相关工程期刊和 IEEE Transactions 系列中的高价值候选文献

它不是通用 TENG 文献检索器，也不是长篇综述生成器。宁可少推，也不凑数。

### 当前能力

- OpenAlex 主检索，无需 API key
- Semantic Scholar API 按 DOI 补充摘要、引用和开放获取元数据
- Crossref DOI 元数据作为无 key 摘要兜底源
- Springer Nature Meta API 补充 Nature/Springer 旗下论文摘要
- Elsevier API 补充 ScienceDirect/Scopus 元数据与摘要
- DOI/title-hash 去重，只保存轻量 `doi`、`title_hash`、`feedback`
- 生成紧凑 HTML 表格报告和 JSON 运行结果
- GitHub Actions 支持手动运行和双月定时运行
- GitHub Actions 可选 SMTP 邮件发送；本地默认不发送邮件

### 仓库结构

```text
.
├── SKILL.md                         # Codex skill entrypoint
├── agents/                          # Skill metadata
├── references/                      # Scope, source strategy, rubric, report schema
├── work/                            # Runnable radar scripts
│   ├── three_year_top_scout.py       # Main 3-year scout
│   ├── openalex_radar.py             # Short-window OpenAlex radar
│   ├── *_enrich.py                   # API enrichment adapters
│   ├── radar_state.py                # Artifact/state paths and seen index
│   └── journal_quartiles.csv         # Optional CAS/JCR/Scopus table template
└── .github/workflows/
    └── research-paper-radar.yml      # Manual/scheduled GitHub Actions workflow
```

### 本地运行

Windows 本机默认产物目录：

```text
D:\PhD\10_vibe项目\research_paper_radar
```

非 Windows 或 GitHub Actions 默认产物目录：

```text
artifacts/research_paper_radar
```

运行：

```powershell
python -m py_compile work\*.py
python work\three_year_top_scout.py
```

本地运行默认不发送邮件，也不需要配置任何 `RADAR_EMAIL_*` 或 `SMTP_*` 变量。检索结果会直接写入产物目录，主要查看：

```text
reports/*.html
runs/*.json
state/seen_papers.json
```

小范围测试：

```powershell
$env:RADAR_QUERY_LIMIT="4"
$env:OPENALEX_PER_PAGE="8"
$env:SEMANTIC_SCHOLAR_ENRICH_LIMIT="5"
$env:SPRINGER_NATURE_ENRICH_LIMIT="5"
$env:ELSEVIER_ENRICH_LIMIT="5"
python work\three_year_top_scout.py
```

调试时显示已检索过的文献：

```powershell
$env:RADAR_SHOW_SEEN="1"
python work\three_year_top_scout.py
```

### API key 配置

脚本会从环境变量读取 API key。不要把 key 写入代码或提交到仓库。

| API | 推荐变量名 | 作用 |
| --- | --- | --- |
| Semantic Scholar | `SEMANTIC_SCHOLAR_API_KEY` | DOI 元数据、摘要、引用补全；推荐配置，可提高稳定性和限额 |
| Crossref | 不需要 | DOI 元数据与摘要兜底补全 |
| Springer Nature | `SPRINGER_NATURE_API_KEY` | Nature/Springer Meta API 摘要补全 |
| Elsevier | `ELSEVIER_API_KEY` | Scopus / ScienceDirect 元数据与摘要补全 |
| Elsevier optional | `ELSEVIER_INSTTOKEN` | 机构权限 token，可选 |

OpenAlex 是主检索源，不需要 key。Crossref 是 DOI 摘要兜底源，不需要 key。Semantic Scholar 支持无 key 公开调用；如需强制必须使用 key，可设置 `SEMANTIC_SCHOLAR_REQUIRE_KEY=1`。

### GitHub Actions 配置

GitHub Actions 有两种使用方式：

- 手动测试：在 Actions 页面点击 `research-paper-radar` -> `Run workflow`，可临时设置 `query_limit`、`show_seen`、`send_email`
- 定期检索：由 `.github/workflows/research-paper-radar.yml` 中的 `schedule` 自动触发，当前默认每两个月运行一次

在 GitHub 仓库中依次进入以下页面配置变量和密钥：

```text
Settings -> Secrets and variables -> Actions
```

#### 1. 文献 API 配置

添加文献 API 到 `Repository secrets`：

- `SEMANTIC_SCHOLAR_API_KEY`（推荐；支持无 key 公开兜底）
- `SPRINGER_NATURE_API_KEY`
- `ELSEVIER_API_KEY`
- `ELSEVIER_INSTTOKEN`（可选）

这些 key 只用于 GitHub Actions 运行时补全摘要、引用和出版商元数据。本地运行时也可以通过系统环境变量临时配置同名 key。

#### 2. 本地不发邮件配置

本地直接运行 `python work\three_year_top_scout.py` 时不会自动发邮件。若只在本地查看 HTML/JSON 结果，不需要配置下面这些变量：

```text
RADAR_EMAIL_TO
RADAR_EMAIL_FROM
SMTP_HOST
SMTP_USERNAME
SMTP_PASSWORD
```

#### 3. GitHub 只检索不发邮件

如果只希望 GitHub Actions 定期生成 artifact，不发送邮件：

Repository variables：

```text
RADAR_EMAIL_ENABLED=0
```

手动运行时也可以在 `Run workflow` 面板里把 `send_email` 填为 `0`。这种模式仍会上传：

```text
artifacts/research_paper_radar/
```

#### 4. GitHub 定期检索并发送邮件

邮件发送使用 SMTP。`RADAR_EMAIL_TO` 只是收件邮箱；GitHub Actions 还必须有一个发件 SMTP 通道，才能真正把报告发出去。

建议把非敏感配置放在 `Repository variables`：

- `RADAR_EMAIL_TO`：收件人，多个邮箱用英文逗号或分号分隔；可以是 163、QQ、Gmail 等任意接收邮箱
- `RADAR_EMAIL_CC`：抄送，可选
- `RADAR_EMAIL_BCC`：密送，可选
- `RADAR_EMAIL_FROM`：发件人地址；不填时默认使用 `SMTP_USERNAME`
- `RADAR_EMAIL_ENABLED`：`auto`、`1` 或 `0`；定时运行默认 `auto`
- `RADAR_EMAIL_SUBJECT_PREFIX`：邮件标题前缀，默认 `Research Paper Radar`
- `RADAR_EMAIL_ATTACH_JSON`：是否附带 JSON，默认 `1`
- `SMTP_PROVIDER`：发件服务预设，可选 `qq`、`163`、`gmail`、`outlook`
- `SMTP_HOST`：发件 SMTP 服务器地址；也可放在 secrets
- `SMTP_USERNAME`：发件 SMTP 登录账号；也可放在 secrets
- `SMTP_PORT`：默认 `587`
- `SMTP_USE_TLS`：默认 `1`
- `SMTP_USE_SSL`：默认 `0`；如使用 465 端口通常设为 `1`

把敏感配置放在 `Repository secrets`：

- `SMTP_PASSWORD`：发件 SMTP 密码、token 或授权码

若变量误放到 `Repository secrets`，当前 workflow 也会读取大多数邮件字段的 secret 版本；但推荐把非敏感项放在 variables，便于后续排查。

#### 5. 常见收发邮箱配置

如果你的 163 邮箱只是接收邮箱，只需要把它填到 `RADAR_EMAIL_TO`。但如果要发送邮件，还需要额外配置发件 SMTP。

Foxmail/QQ 发件到 163 收件箱，已测试通过的配置：

Repository variables：

```text
RADAR_EMAIL_TO=你的163收件邮箱@163.com
RADAR_EMAIL_FROM=你的Foxmail邮箱@foxmail.com
RADAR_EMAIL_ENABLED=auto
SMTP_PROVIDER=qq
SMTP_HOST=smtp.qq.com
SMTP_USERNAME=你的Foxmail邮箱@foxmail.com
SMTP_PORT=465
SMTP_USE_TLS=0
SMTP_USE_SSL=1
```

Repository secrets：

```text
SMTP_PASSWORD=QQ/Foxmail邮箱SMTP授权码
```

其中 `SMTP_PROVIDER=qq` 可以自动补齐 QQ/Foxmail 的默认 SMTP 设置；仍建议显式保留 `SMTP_HOST=smtp.qq.com`，便于排查配置。`SMTP_USERNAME` 必须是完整发件邮箱地址，例如 `name@foxmail.com`；`SMTP_PASSWORD` 必须是开启 SMTP/IMAP 后生成的授权码，不是网页登录密码。若 QQ/Foxmail 拒绝发件，优先确认 `RADAR_EMAIL_FROM` 与 `SMTP_USERNAME` 完全一致。

163 发件到任意收件箱：

Repository variables：

```text
RADAR_EMAIL_TO=你的收件邮箱
RADAR_EMAIL_FROM=你的163发件邮箱@163.com
RADAR_EMAIL_ENABLED=auto
SMTP_PROVIDER=163
SMTP_HOST=smtp.163.com
SMTP_USERNAME=你的163发件邮箱@163.com
SMTP_PORT=465
SMTP_USE_SSL=1
SMTP_USE_TLS=0
```

Repository secrets：

```text
SMTP_PASSWORD=163邮箱客户端授权码
```

使用其他发件服务时，保持同一逻辑：`RADAR_EMAIL_TO` 是收件人，`RADAR_EMAIL_FROM` 和 `SMTP_USERNAME` 是发件账号，`SMTP_PASSWORD` 是发件服务提供的 SMTP 密码或授权码。

#### 6. 开启和测试定期检索

1. 在 `Settings -> Secrets and variables -> Actions` 配好 API key 和邮件变量。
2. 进入 `Actions -> research-paper-radar`。
3. 如果页面提示 workflow 未启用，点击启用。
4. 点击 `Run workflow` 做一次手动测试：
   - `query_limit=4` 可用于快速测试
   - `show_seen=0` 保持默认即可
   - `send_email=1` 强制测试邮件发送
5. 手动测试通过后，保留 `schedule` 配置即可自动定期运行。

当前定期检索周期写在 `.github/workflows/research-paper-radar.yml`：

```yaml
schedule:
  - cron: "0 1 1 */2 *"
```

该 cron 使用 UTC 时间，当前表示每两个月的 1 日 01:00 UTC 运行一次。常见修改：

```yaml
# 每月 1 日 01:00 UTC
- cron: "0 1 1 * *"

# 每两个月 1 日 01:00 UTC
- cron: "0 1 1 */2 *"

# 每周一 01:00 UTC
- cron: "0 1 * * 1"
```

工作流支持：

- `workflow_dispatch`：手动运行，可设置 `query_limit`、`show_seen` 和 `send_email`
- `schedule`：默认每两个月运行一次；配好收件邮箱和发件 SMTP 通道后会发送邮件

GitHub 运行产物会被上传为 artifact：

```text
artifacts/research_paper_radar/
├── state/seen_papers.json
├── runs/*.json
├── reports/*.html
└── cache/*.json
```

#### 7. 邮件故障排查

发送邮件前，日志会输出脱敏诊断信息，例如：

```text
Email config: recipient_configured=True, from_configured=True, username_configured=True, password_configured=True, sender_domain=foxmail.com, provider=qq, host=smtp.qq.com, port=465, use_ssl=True, use_tls=False
```

如果邮件失败，优先检查：

- `password_configured=True` 是否出现；若为 `False`，说明 `SMTP_PASSWORD` secret 没配置或名字不对
- `sender_domain` 是否是预期发件域名，例如 `foxmail.com`
- `host`、`port`、`use_ssl`、`use_tls` 是否匹配发件服务
- Foxmail/QQ 发件时，`RADAR_EMAIL_FROM` 与 `SMTP_USERNAME` 是否完全一致
- `SMTP_PASSWORD` 是否为 SMTP/IMAP 授权码，而不是网页登录密码

#### 8. 维护和提交约定

每次修改 GitHub Actions、邮件发送、定期检索或 CI 相关逻辑后，`git commit` 信息需要写清楚本次 CI 变化原因。推荐格式：

```text
<scope>: <what changed>

CI reason: <why the workflow/config/test behavior changed>
```

示例：

```text
docs: clarify scheduled radar email setup

CI reason: document the tested Foxmail-to-163 workflow and cron configuration so future Actions runs are reproducible.
```

### 反馈说明

HTML 中的反馈按钮可以展示选择状态；自动持久反馈需要额外的 feedback receiver。当前仓库已保留 `feedback` 字段和相关架构说明，但不会把静态 HTML 的点击自动写回 JSON。

### 边界

- 不下载付费全文
- 不绕过出版商访问限制
- 不把摘要层面判断当作正式全文阅读结论
- 不推荐纯 TENG、纯材料、普通 ML 预测或泛高压工程文章，除非它们明确服务于击穿放电无线传感链条

## English

### Purpose

`research-paper-radar` is both a Codex skill package and a runnable GitHub Actions workflow for conservative paper discovery around:

- wireless sensing based on breakdown discharge, gas discharge, friction-induced electromagnetic waves, or transient electromagnetic signals;
- self-powered, battery-free, flexible, or wearable wireless sensing mechanisms transferable to this topic;
- high-value candidates from major journals, strong engineering venues, and IEEE Transactions venues.

It is not a generic TENG search tool and not a long-form literature review generator. Precision is preferred over volume.

### What It Does

- Uses OpenAlex as the main discovery source; no API key required
- Enriches DOI records with Semantic Scholar metadata, abstracts, and citation counts
- Uses Crossref DOI metadata as a no-key abstract fallback
- Enriches Nature/Springer records with Springer Nature Meta API
- Enriches Elsevier/ScienceDirect/Scopus records with Elsevier APIs
- Deduplicates by DOI and normalized-title hash
- Stores only lightweight seen-state fields: `doi`, `title_hash`, and `feedback`
- Produces compact HTML reports and machine-readable JSON
- Runs locally or through GitHub Actions
- Can send scheduled GitHub reports by configurable SMTP email; local runs skip email by default

### Local Usage

Compile and run:

```bash
python -m py_compile work/*.py
python work/three_year_top_scout.py
```

Quick test:

```bash
RADAR_QUERY_LIMIT=4 \
OPENALEX_PER_PAGE=8 \
SEMANTIC_SCHOLAR_ENRICH_LIMIT=5 \
SPRINGER_NATURE_ENRICH_LIMIT=5 \
ELSEVIER_ENRICH_LIMIT=5 \
python work/three_year_top_scout.py
```

Show already-seen papers for debugging:

```bash
RADAR_SHOW_SEEN=1 python work/three_year_top_scout.py
```

Local runs do not send email by default and do not require any `RADAR_EMAIL_*` or `SMTP_*` variables. Results are written to the artifact directory, especially `reports/*.html`, `runs/*.json`, and `state/seen_papers.json`.

### GitHub Actions Setup

The GitHub workflow supports two modes:

- Manual test: open `Actions -> research-paper-radar -> Run workflow`, then set `query_limit`, `show_seen`, and `send_email`.
- Scheduled radar: `.github/workflows/research-paper-radar.yml` runs automatically on the configured cron schedule.

Configure repository secrets and variables under:

```text
Settings -> Secrets and variables -> Actions
```

#### 1. Literature API Secrets

Recommended repository secrets:

- `SEMANTIC_SCHOLAR_API_KEY`
- `SPRINGER_NATURE_API_KEY`
- `ELSEVIER_API_KEY`
- `ELSEVIER_INSTTOKEN` optional

These keys are used for abstract, citation, and publisher metadata enrichment in GitHub Actions. Local runs can use the same names as environment variables.

#### 2. Local Runs Without Email

Local usage does not need email settings. You can run:

```bash
python work/three_year_top_scout.py
```

and open the generated HTML report directly from the artifact directory.

#### 3. GitHub Runs Without Email

To let GitHub Actions generate artifacts without sending email, set:

Repository variables:

```text
RADAR_EMAIL_ENABLED=0
```

For manual `Run workflow` tests, set `send_email=0`.

#### 4. Scheduled GitHub Runs With Email

Email delivery is optional and SMTP-based. `RADAR_EMAIL_TO` is only the recipient address; GitHub Actions also needs a sender SMTP channel to actually deliver email.

Store non-sensitive values as repository variables:

- `RADAR_EMAIL_TO` recipient address; any inbox provider is fine, including 163 Mail
- `RADAR_EMAIL_CC` optional
- `RADAR_EMAIL_BCC` optional
- `RADAR_EMAIL_FROM` sender address, optional when `SMTP_USERNAME` is also the sender address
- `RADAR_EMAIL_ENABLED` optional, `auto`, `1`, or `0`
- `RADAR_EMAIL_SUBJECT_PREFIX` optional
- `RADAR_EMAIL_ATTACH_JSON` optional, defaults to `1`
- `SMTP_PROVIDER` optional sender preset: `qq`, `163`, `gmail`, or `outlook`
- `SMTP_HOST` sender SMTP host, optional here or as a secret
- `SMTP_USERNAME` sender SMTP login, optional here or as a secret
- `SMTP_PORT` optional, defaults to `587`
- `SMTP_USE_TLS` optional, defaults to `1`
- `SMTP_USE_SSL` optional, defaults to `0`

Store sender SMTP credentials as repository secrets:

- `SMTP_PASSWORD`

If a non-sensitive value is accidentally stored as a repository secret instead of a variable, the workflow can read most email fields from either source. Variables are still recommended for non-sensitive values because they are easier to inspect.

#### 5. Common Sender/Recipient Examples

Foxmail/QQ sender to a 163 recipient, tested configuration:

Repository variables:

```text
RADAR_EMAIL_TO=recipient@163.com
RADAR_EMAIL_FROM=sender@foxmail.com
RADAR_EMAIL_ENABLED=auto
SMTP_PROVIDER=qq
SMTP_HOST=smtp.qq.com
SMTP_USERNAME=sender@foxmail.com
SMTP_PORT=465
SMTP_USE_SSL=1
SMTP_USE_TLS=0
```

Repository secrets:

```text
SMTP_PASSWORD=QQ/Foxmail SMTP authorization code
```

Keep `RADAR_EMAIL_FROM` identical to `SMTP_USERNAME` unless the provider explicitly allows a sender alias. Use the SMTP/IMAP authorization code, not the web login password.

163 sender to any recipient:

Repository variables:

```text
RADAR_EMAIL_TO=recipient@example.com
RADAR_EMAIL_FROM=sender@163.com
RADAR_EMAIL_ENABLED=auto
SMTP_PROVIDER=163
SMTP_HOST=smtp.163.com
SMTP_USERNAME=sender@163.com
SMTP_PORT=465
SMTP_USE_SSL=1
SMTP_USE_TLS=0
```

Repository secrets:

```text
SMTP_PASSWORD=163 SMTP authorization code
```

For any other provider, use the same rule: `RADAR_EMAIL_TO` is the recipient, `RADAR_EMAIL_FROM` and `SMTP_USERNAME` are the sender account, and `SMTP_PASSWORD` is the sender provider's SMTP password or authorization token.

#### 6. Enabling and Changing the Schedule

1. Configure API keys and email variables under `Settings -> Secrets and variables -> Actions`.
2. Open `Actions -> research-paper-radar`.
3. Enable the workflow if GitHub shows an enable button.
4. Run a manual test with `Run workflow`:
   - `query_limit=4` for a quick test
   - `show_seen=0` for normal behavior
   - `send_email=1` to force email delivery testing
5. After a successful manual run, keep the `schedule` entry enabled for unattended runs.

The current schedule lives in `.github/workflows/research-paper-radar.yml`:

```yaml
schedule:
  - cron: "0 1 1 */2 *"
```

GitHub cron uses UTC. The current value means 01:00 UTC on the first day of every two months. Common alternatives:

```yaml
# Monthly, day 1, 01:00 UTC
- cron: "0 1 1 * *"

# Every two months, day 1, 01:00 UTC
- cron: "0 1 1 */2 *"

# Every Monday, 01:00 UTC
- cron: "0 1 * * 1"
```

The workflow stores outputs under `artifacts/research_paper_radar` and uploads them as a GitHub Actions artifact.

#### 7. Email Troubleshooting

Before sending, the script prints a sanitized diagnostic line:

```text
Email config: recipient_configured=True, from_configured=True, username_configured=True, password_configured=True, sender_domain=foxmail.com, provider=qq, host=smtp.qq.com, port=465, use_ssl=True, use_tls=False
```

Check:

- `password_configured=True`; otherwise `SMTP_PASSWORD` is missing or misnamed
- `sender_domain` is the expected sender domain
- `host`, `port`, `use_ssl`, and `use_tls` match the sender provider
- for Foxmail/QQ, `RADAR_EMAIL_FROM` exactly matches `SMTP_USERNAME`
- `SMTP_PASSWORD` is the SMTP/IMAP authorization code, not the web login password

#### 8. Maintenance And Commit Convention

Whenever a commit changes GitHub Actions, scheduled runs, email delivery, or CI behavior, include the CI reason in the commit message:

```text
<scope>: <what changed>

CI reason: <why the workflow/config/test behavior changed>
```

Example:

```text
docs: clarify scheduled radar email setup

CI reason: document the tested Foxmail-to-163 workflow and cron configuration so future Actions runs are reproducible.
```

### Installing as a Codex Skill

For local Codex use, install the repository root as a skill directory named:

```text
research-paper-radar
```

The root `SKILL.md` is the skill entrypoint, and `references/` contains the detailed topic profile, source strategy, screening rubric, report schema, and feedback architecture.

### Evidence Boundary

The radar uses metadata, abstracts, DOI pages, and publisher metadata. It does not download paid full text, bypass access restrictions, or treat abstract-level screening as final paper reading.
