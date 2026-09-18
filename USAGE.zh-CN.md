# 文献雷达简明使用与配置说明

本文用于完成仓库首次配置、手动测试、定期检索发信和反馈导入。敏感信息放在 GitHub `Repository secrets`，普通开关和参数放在 `Repository variables`：

```text
仓库 Settings -> Secrets and variables -> Actions
```

## 1. 必要与可选密钥

在 `Repository secrets` 中配置：

| 名称 | 必要性 | 含义 |
| --- | --- | --- |
| `SEMANTIC_SCHOLAR_API_KEY` | 推荐 | 补全摘要、引用和开放获取信息 |
| `SPRINGER_NATURE_API_KEY` | 推荐 | 补全 Nature/Springer 论文摘要 |
| `ELSEVIER_API_KEY` | 推荐 | 补全 Elsevier/ScienceDirect 论文摘要与元数据 |
| `ELSEVIER_INSTTOKEN` | 可选 | Elsevier 机构权限令牌 |
| `DEEPL_API_KEY` | 可选 | 把最终入选论文的摘要翻译为简体中文 |
| `SMTP_PASSWORD` | 发邮件时必要 | 发件邮箱的 SMTP 授权码，不是网页登录密码 |
| `RADAR_FEEDBACK_WRITE_TOKEN` | 自动反馈时可选 | 向反馈接收端写入事件的令牌 |
| `RADAR_FEEDBACK_READ_TOKEN` | 自动反馈时可选 | 从反馈接收端读取事件的令牌 |

OpenAlex 和 Crossref 不需要密钥。未配置某个补全 API 时，雷达仍会运行，但对应出版商论文可能缺少摘要或引用信息。

## 2. 推荐的普通变量

在 `Repository variables` 中配置：

| 名称 | 推荐值 | 含义 |
| --- | --- | --- |
| `RADAR_SCHEDULE_ENABLED` | `1` | `1` 启用自动检索，`0` 暂停 |
| `RADAR_INTERVAL_DAYS` | `7` | 两次成功自动检索之间的天数 |
| `RADAR_LOOKBACK_DAYS` | `30` | 每次向前检索多少天；`0` 表示默认近 3 年 |
| `RADAR_MAX_RECOMMENDATIONS` | `10` | 每期 HTML 和邮件最多推荐多少篇 |
| `RADAR_SCHEDULE_INITIAL_LAST_RUN` | 最近一次成功测试日期 | 首次建立定时状态时使用，格式 `YYYY-MM-DD` |
| `RADAR_KEEPALIVE_DAYS` | `45` | 公共仓库定时任务保活阈值 |
| `RADAR_EMAIL_ENABLED` | `auto` | 定时运行在邮件参数完整时自动发信 |
| `RADAR_TRANSLATE_ABSTRACTS` | `1` 或 `0` | 是否使用 DeepL 翻译最终入选摘要 |

每 7 天运行时建议使用 `RADAR_LOOKBACK_DAYS=30`，而不是只查 7 天。较长回溯可以覆盖数据库收录延迟；已经推送的论文会通过 DOI 或标题 hash 排除，不会因为 30 天窗口重复发送。

## 3. 邮件配置

通用变量：

| 名称 | 含义 |
| --- | --- |
| `RADAR_EMAIL_TO` | 收件邮箱；多个地址用英文逗号或分号分隔 |
| `RADAR_EMAIL_FROM` | 发件邮箱，通常与 `SMTP_USERNAME` 相同 |
| `SMTP_PROVIDER` | 发件服务预设：`qq`、`163`、`gmail` 或 `outlook` |
| `SMTP_HOST` | SMTP 服务器地址 |
| `SMTP_USERNAME` | 完整发件邮箱地址 |
| `SMTP_PORT` | SSL 常用 `465`，STARTTLS 常用 `587` |
| `SMTP_USE_SSL` | 465 端口通常为 `1` |
| `SMTP_USE_TLS` | 465 端口通常为 `0` |
| `RADAR_EMAIL_ATTACH_JSON` | `1` 表示随邮件附带 JSON |

163 发件、QQ/Foxmail 收件示例：

```text
RADAR_EMAIL_TO=你的QQ或Foxmail收件邮箱
RADAR_EMAIL_FROM=你的163发件邮箱@163.com
RADAR_EMAIL_ENABLED=auto
SMTP_PROVIDER=163
SMTP_HOST=smtp.163.com
SMTP_USERNAME=你的163发件邮箱@163.com
SMTP_PORT=465
SMTP_USE_SSL=1
SMTP_USE_TLS=0
```

并在 `Repository secrets` 配置：

```text
SMTP_PASSWORD=163邮箱客户端授权码
```

只在本地生成报告、不发邮件时，无需配置任何 `RADAR_EMAIL_*` 或 `SMTP_*` 参数。

## 4. DeepL 中文摘要

启用中文摘要：

```text
# Repository variable
RADAR_TRANSLATE_ABSTRACTS=1

# Repository secret
DEEPL_API_KEY=你的 DeepL API key
```

只翻译最终入选论文，不翻译全部候选。翻译失败不会中断检索，HTML 会回退显示英文；JSON 的 `abstract` 保留英文原文，`abstract_zh` 保存中文译文。

## 5. 手动测试

进入：

```text
仓库 Actions -> research-paper-radar -> Run workflow
```

输入项：

| 输入项 | 快速测试值 | 含义 |
| --- | --- | --- |
| `show_seen` | `0` | `1` 会显示已经进入去重索引的论文，仅用于排查 |
| `query_limit` | `4` | 限制 OpenAlex 查询数量；`0` 表示完整查询 |
| `send_email` | `0` 或 `1` | `0` 不发邮件；`1` 强制测试邮件配置 |
| `lookback_days` | `30` | 本次临时覆盖检索范围；`0` 使用仓库变量 |
| `max_recommendations` | `3` 或 `10` | 本次临时覆盖推荐数量；`0` 使用仓库变量 |

建议分两步测试：

1. 首次用 `0 / 4 / 0 / 30 / 3`，确认检索与 artifact 正常。
2. 再用 `0 / 4 / 1 / 30 / 3`，确认邮件能够收到。

手动点击 `Run workflow` 会立即运行，因为手动任务会绕过自动周期门控；它不会重置或推进下一次自动检索日期。

## 6. 开启自动检索

1. 配好文献 API、SMTP 和上面的 Repository variables。
2. 完成一次手动检索测试和一次发信测试。
3. 将 `RADAR_SCHEDULE_INITIAL_LAST_RUN` 设置为测试成功当天，例如 `2026-09-18`。
4. 确认 `RADAR_SCHEDULE_ENABLED=1`、`RADAR_EMAIL_ENABLED=auto`。
5. 在 Actions 页面确认 `research-paper-radar` workflow 已启用。

GitHub 每天约北京时间 09:17 唤醒一次，只做是否到期的轻量检查。达到 `RADAR_INTERVAL_DAYS` 后才执行真实检索并发信。若初始日期为空、失效或早于一个完整周期，启用后下一次每日检查会立即执行一次，这是正常行为。

每 7 天发送、查近 30 天、最多 10 篇的完整核心配置为：

```text
RADAR_SCHEDULE_ENABLED=1
RADAR_INTERVAL_DAYS=7
RADAR_LOOKBACK_DAYS=30
RADAR_MAX_RECOMMENDATIONS=10
RADAR_SCHEDULE_INITIAL_LAST_RUN=最近一次成功测试日期
RADAR_EMAIL_ENABLED=auto
```

若没有符合严格门槛的论文，系统不会凑数，会发送“本期暂无合适文献”的邮件。

## 7. 去重与项目记忆

每次实际进入 HTML/邮件的论文会写入轻量状态文件：

```text
artifacts/research_paper_radar/state/seen_papers.json
```

有 DOI 时按 DOI 去重；没有 DOI 时按标准化标题 hash 去重。只记录实际推送的论文，候选池中因数量上限未展示的论文不会提前标记为已推送。GitHub Actions 通过缓存恢复该状态。

本地默认产物目录为：

```text
D:\PhD\10_vibe项目\research_paper_radar\
```

GitHub 运行结果在当次 run 的 `Artifacts` 中下载。

## 8. 用户反馈

HTML 支持四级相关性反馈：极其相关、相关、可参考、无关，并支持下载/精读等行为标记。

### 简单方式：导出反馈

1. 在 HTML 中完成反馈选择。
2. 点击“导出本期反馈 JSON”。
3. 把 JSON 交给 Codex，或在本地导入：

```powershell
$env:RADAR_FEEDBACK_SOURCE_URL="C:\path\to\radar_feedback.json"
python work\sync_feedback.py
```

建议积累 2 至 3 轮后统一校准规则，避免根据单次偶然反馈过拟合。

### 自动方式：反馈接收端

配置：

```text
RADAR_FEEDBACK_ENDPOINT=https://你的接收端/record
RADAR_FEEDBACK_SOURCE_URL=https://你的接收端/events
```

需要鉴权时，把写入和读取令牌分别放入 `RADAR_FEEDBACK_WRITE_TOKEN`、`RADAR_FEEDBACK_READ_TOKEN` secrets。下一次检索前，工作流会导入反馈，对已经通过课题硬门槛的候选论文按机制、期刊和题名线索加权或降权。

该功能是透明的规则和权重调整，不是训练新的机器学习模型。未配置反馈接收端时，HTML 按钮状态只保存在当前浏览器，必须导出 JSON 才能进入后续检索。

## 9. 常见操作

- 暂停自动检索：`RADAR_SCHEDULE_ENABLED=0`
- 恢复自动检索：`RADAR_SCHEDULE_ENABLED=1`
- 改为每 30 天：`RADAR_INTERVAL_DAYS=30`
- 暂停邮件但继续生成结果：`RADAR_EMAIL_ENABLED=0`
- 关闭摘要翻译：`RADAR_TRANSLATE_ABSTRACTS=0`
- 完整手动检索：`query_limit=0`，其他临时覆盖项填 `0`

