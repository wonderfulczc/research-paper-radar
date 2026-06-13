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

在 GitHub 仓库中依次进入：

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

添加文献 API secrets：

- `SEMANTIC_SCHOLAR_API_KEY`（推荐；支持无 key 公开兜底）
- `SPRINGER_NATURE_API_KEY`
- `ELSEVIER_API_KEY`
- `ELSEVIER_INSTTOKEN`（可选）

邮件发送使用 SMTP，默认本地运行不发送。GitHub 定时运行时，若仓库同时配置了收件人和发件 SMTP 通道，则自动发送最新 HTML 报告和 JSON 结果；只配置收件邮箱时会跳过邮件，仍上传 artifact。

建议把非敏感配置放在 repository variables：

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

把敏感配置放在 repository secrets：

- `SMTP_PASSWORD`：发件 SMTP 密码、token 或授权码

如果你的 163 邮箱只是接收邮箱，只需要把它填到 `RADAR_EMAIL_TO`，例如：

Repository variables：

```text
RADAR_EMAIL_TO=你的163收件邮箱@163.com
RADAR_EMAIL_ENABLED=auto
```

但 GitHub Actions 不能凭空发邮件。若需要定时邮件通知，还必须额外配置一个发件 SMTP 通道，可以是 QQ/Foxmail 发件邮箱、163 发件邮箱，也可以是其他专门的发件邮箱或 SMTP 服务。例如用 Foxmail 发件邮箱发送到 163 收件邮箱：

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

如果也想用 163 作为发件通道，通常是 `SMTP_HOST=smtp.163.com`、`SMTP_PORT=465`、`SMTP_USE_SSL=1`、`SMTP_USE_TLS=0`，并且 `SMTP_PASSWORD` 应使用 163 邮箱的“客户端授权码/SMTP 授权码”，通常不是网页登录密码。需要在 163 邮箱设置中开启 POP3/SMTP/IMAP 服务并生成授权码。

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

### GitHub Actions Secrets

Configure repository secrets under:

```text
Settings -> Secrets and variables -> Actions
```

Recommended secrets:

- `SEMANTIC_SCHOLAR_API_KEY`
- `SPRINGER_NATURE_API_KEY`
- `ELSEVIER_API_KEY`
- `ELSEVIER_INSTTOKEN` optional

Email delivery is optional and SMTP-based. A recipient address only tells the workflow where to send the report; GitHub Actions still needs a sender SMTP channel to actually deliver email. Store non-sensitive values as repository variables:

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

If 163 Mail is only the recipient inbox, set only `RADAR_EMAIL_TO=<your 163 address>` for that part. To receive scheduled email reports, also configure a sender SMTP provider. For QQ/Foxmail sender to a 163 recipient, use `SMTP_PROVIDER=qq`, `SMTP_HOST=smtp.qq.com`, `SMTP_PORT=465`, `SMTP_USE_SSL=1`, `SMTP_USE_TLS=0`, `SMTP_USERNAME=<your full QQ/Foxmail email>`, and use the QQ/Foxmail SMTP authorization code as `SMTP_PASSWORD`. Keep `RADAR_EMAIL_FROM` identical to `SMTP_USERNAME` unless the sender alias is allowed. If 163 Mail is used as the sender provider, use `SMTP_HOST=smtp.163.com`, `SMTP_PORT=465`, `SMTP_USE_SSL=1`, `SMTP_USE_TLS=0`, and use the 163 SMTP authorization code as `SMTP_PASSWORD`.

The workflow stores outputs under `artifacts/research_paper_radar` and uploads them as a GitHub Actions artifact.

### Installing as a Codex Skill

For local Codex use, install the repository root as a skill directory named:

```text
research-paper-radar
```

The root `SKILL.md` is the skill entrypoint, and `references/` contains the detailed topic profile, source strategy, screening rubric, report schema, and feedback architecture.

### Evidence Boundary

The radar uses metadata, abstracts, DOI pages, and publisher metadata. It does not download paid full text, bypass access restrictions, or treat abstract-level screening as final paper reading.
