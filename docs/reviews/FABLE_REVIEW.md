# Fable 评审：History in Practice｜每日一鉴 计划 v2

评审日期：2026-10-30（America/Los_Angeles）  
评审对象：`README.md`、`docs/PLAN.md`（v2，2026-10-29）、`docs/EDITORIAL_BRIEF.md`、`prompts/01_FABLE_REVIEW.md`、`prompts/02_OPUS_IMPLEMENT.md`，commit `bd522ae`。  
评审方式：通读文档；克隆 `news-intel` 与 `website_test` 对照代码；对 starhub.vip 线上做只读 HTTP 探测；在 raspberrypi51 本机做只读环境检查（不读取、不输出任何凭据）；对 Hermes 做了一次无敏感内容的计时调用。  
本文件配套的文档修订已直接写入 `docs/PLAN.md`（v2.1）、`docs/EDITORIAL_BRIEF.md`、`README.md`、`prompts/02_OPUS_IMPLEMENT.md`。

## 1. 总体结论

计划可以进入 ChatGPT 再评审；核心目标（有依据、好读、双语、每日、事件级去重、GitHub 归档）成立，证据规则与可靠性章节比同类个人项目严谨得多。但有四处会在实施时直接出问题，必须先改：

1. **史料供给没有主体和机制。** Hermes 关闭工具不能检索，ctext.org 对脚本返回 JS 验证页（已实测），计划只写了"从预选 URL 建立证据包"，没有说明每周 7 篇、每篇 ≥2 份可取回正文的材料由谁、用什么流程产生。这是长期每日供稿是否现实的决定性问题。本评审给出"程序侦察 + 每周一次人工批准 + 白名单语料库"的方案，并明确每周人工成本。
2. **模型调用预算量级错了。** 实测 Hermes（mimo-v2.6-pro）一次性生成 404 个汉字耗时 78 秒。news-intel 的 20 秒超时、20,000 字符上限不能沿用；每篇文章的模型时间约 10–20 分钟，必须前一晚准备。
3. **十分钟的篇幅分配不对。** 现行 1,000–1,300 字 / 550–700 词双语合计约 6–7 分钟，且九个栏目把故事本体压到 500–650 字，难以容纳"2–4 个场景 + 一个可核实细节"，容易退化成履历摘要。建议上调篇幅并把"为什么会这样"并入故事。
4. **线上部署行为已核实，与计划假设不同。** starhub.vip 对任何不存在的路径都返回 HTTP 200 并送回首页 HTML（含 `/history/` 和 `/data/history/index.json`），`*.html` 会 308 跳转到无扩展名 URL，HTML 页面被 Cloudflare 注入脚本。"URL 返回 200"不能作为发布成功信号；必须以 JSON 数据文件中的 `edition_id` + `revision` 核对。

其余为中等或低优先级问题，见第 3 节。第 4 节是已直接修订的内容，第 5 节是仍未验证、需 Opus 在实施时核实的项目，第 6 节是建议实施顺序，第 7 节给出四篇样稿提纲（仅检验设计，事实尚待核实）。

## 2. 本轮核实结果（2026-10-30）

### 2.1 已核实为真（计划中的陈述）

| 计划陈述 | 核实方式 | 结果 |
|---|---|---|
| `LLM_PROVIDER=hermes_cli` 选用 `HermesCliProvider` | 读取 `news-intel/src/news_intel/llm/provider.py` | 一致 |
| argv 为 `[hermes_bin, "-z", prompt, "-t", "", "--ignore-rules"]`，`shell=False` | 读取 `hermes_cli.py` | 一致 |
| `compose_daily` / `compose_weekly` / `explain_event` 未实现 | 同上 | 一致，三者直接抛 `LLMUnavailableError` |
| 默认 timeout 20 秒，prompt/output 各 20,000 字符 | 同上 | 一致 |
| `website_test` 根目录为 `index.html`、`articles.html`、`css/`、`data/`、`media/`，无 Wrangler/Workers 配置 | 克隆仓库 | 一致；另有两张 PNG 和模板 README；无 `.github/`、`_headers`、`_redirects` |
| `articles.html` 有中英按钮与 JSON 索引思路 | 读取源码 | 一致，但见 2.3 第 6 条 |

### 2.2 本机（raspberrypi51）只读检查

| 项目 | 结果 |
|---|---|
| Hermes 可执行文件 | `/home/star/.local/bin/hermes` 存在，为 shell 包装脚本；`Hermes Agent v0.14.0 (2026.5.16)`，Python 3.11.2 |
| 配置的模型 | `model.default: mimo-v2.6-pro`，`provider: xiaomi`（仅读取模型名，未读取密钥） |
| `-z` 的语义（来自 `hermes --help`） | "Tools, memory, rules, and AGENTS.md **in the CWD** are loaded as normal" —— 因此 `-t ""` 与 `--ignore-rules` 必须同时给，且子进程 **cwd 必须是空目录**，否则会把当前目录的 AGENTS.md 等注入上下文 |
| 其他可用参数 | `-m MODEL`、`--provider` 可按次覆盖模型，不改 config.yaml；也可用环境变量 `HERMES_INFERENCE_MODEL` |
| 计时调用 | prompt：要求约 400 汉字、三段、无标题的中性说明文（河道弯曲成因）。结果：rc=0，**wall 78.3 s**，输出 404 字 / 1,194 字节，stderr 为空 |
| 调用副作用 | 调用后 6 分钟内仅 `~/.hermes/logs/agent.log` 与 `gateway.log` 被修改；`sessions/`、`state.db`、`memories/` 未变 |
| 系统时区 | **America/Chicago**（不是计划默认的 America/Los_Angeles）；NTP 同步正常 |
| `systemd-analyze calendar "*-*-* 07:30:00 America/Los_Angeles"` | 可解析，下一次为 `09:30 CDT`，证明 OnCalendar 时区后缀在本机可用 |
| 共享 Hermes 的其他消费者 | `hermes-gateway.service` 常驻运行；`pi-news-daily.timer`（22:00 LA，单元内写死 `05:00 UTC`，不随夏令时）；`pi-news-daily-zh.timer`（07:00 LA，周一至周六）；`pi-news-collect.timer`（每 5 分钟，采集）；`poly-daily-metrics-dedicated.timer`（00:30 LA）；polymarket 另有 Hermes cron 小时任务 |
| 单个 argv 上限 | 本机内核页 16 KB，`MAX_ARG_STRLEN` = 512 KB；4 KB 页内核为 128 KB。prompt 作为单个 argv 传入，必须留足余量 |
| 磁盘 / 内存 | 根分区 58 G 已用 78%（剩 13 G）；内存 7.9 G |
| 本机仓库 | `/home/star/pi-news-intel`、`/home/star/polymarket-optimizer` 存在；`website_test` 与 `history-in-practice` 本机没有工作副本 |

### 2.3 线上网站（只读 HTTP）

1. `https://starhub.vip/` 由 Cloudflare 提供（`server: cloudflare`，`cf-cache-status: DYNAMIC`）。
2. `data/articles/index.json` 线上与 git `main` **字节一致**；`index.html`、`articles.html` 跟随 308 跳转后与 git 的唯一差别是 `</body>` 前被注入的 Cloudflare challenge 脚本。结论：**线上内容与 main 一致**，与"Git 连接自动部署"相容，但不能证明是自动部署而非手工发布。
3. `articles.html` → 308 → `/articles`；`index.html` → 308 → `/`。因此计划里的 `history/index.html?story=` 链接会先跳一次，应直接用 `/history/?story=<id>&lang=zh`。
4. `/history/`、`/history/index.html`、`/data/history/index.json`、`/nonexistent-zz` **全部返回 200**，正文都是首页 HTML（`<title>StarHub | Command Center</title>`）。这是单页应用式回退（Workers Static Assets `not_found_handling: single-page-application` 或 Pages 的等价行为）。影响：JSON 请求可能拿到 HTML；状态码无意义。
5. JSON 文件未被注入脚本，适合作为发布核对对象。
6. `articles.html` 是一个**客户端口令保护的私人文章库**，口令哈希与明文注释都在页面源码里，内容为付费 newsletter 的归档副本。新栏目不得与它共享索引、脚本或导航入口，发布器不得写入 `data/articles/`。这与计划 §8 一致，这里补充的是已核实的事实依据。

### 2.4 史料站点从 Pi 的可达性（脚本 UA，8 秒超时）

| 站点 | 结果 | 结论 |
|---|---|---|
| `ctext.org`（《礼记·大学》《史记·陈丞相世家》） | 200，但正文为 2.7 KB 的 "Checking the security of your connection..." JS 验证页 | **不能作为程序化取证来源**；只能人工阅读或走其 API/授权 |
| `zh.wikisource.org/wiki/史記/卷056` | 200，139 KB，含"陳平"25 处 | 可用 |
| `zh.wikipedia.org` 页面与 `api.wikimedia.org` REST | 200 | 可用于导航、找原始出处（不作为证据本身） |
| `wikidata.org` EntityData JSON | 200 | 可用作人物/事件稳定 ID |
| `loc.gov` 资源页 | 403 | 对脚本封锁；需换 Founders Online 等（未测） |
| `en.wikisource` Livy、marxists.org 毛泽东中文库 | 404（我猜的 URL 不对） | **未验证**，不是不可达 |
| `penelope.uchicago.edu`（LacusCurtius） | 连接失败 | **未验证** |

## 3. Findings

格式：位置 → 影响 → 最小修复 → 验收方式。

### P0

**P0-1 史料供给没有机制和主体**  
位置：`docs/PLAN.md` §4 "先建立 40 个候选选题"、§6 "MVP 从预选 URL、可靠原典和机构材料建立证据包"。  
影响：按规则每篇需 ≥2 份不同来源、已取回正文、已映射到段落的材料。Hermes 不能检索，ctext.org 封锁脚本。没有"谁来找 URL、怎么取正文、怎么批准"的流程，长期每日供稿在第 3–5 周就会断。隐含的"全自动历史研究"是不现实的，也不应该追求。  
最小修复：
- 建立 `config/sources.yaml` **语料库白名单**，每个语料库一个取回适配器（第一批：zh/en Wikisource、Wikipedia REST、Wikidata；人工阅读来源如 ctext.org、纸书只能以"人工摘录 + 页码"形式进入证据包并如此标注）。
- 增加**选题侦察任务**（纯 Python，不用模型联网）：从 Wikipedia 条目的参考文献与 Wikisource 搜索为候选选题拼出初步证据包，附取回状态。
- 增加**每周一次人工批准**：维护者在 20–40 分钟内批准/否决候选（题目、事件 ID、来源），批准后才进入写作队列。把这件事写成产品成本，而不是省掉。
- 候选→可用通过率、每题人工分钟数作为运行指标记录。
验收：Phase 1 的四个证据包只用白名单来源建成并记录人工分钟数；Phase 2 侦察任务对任一类别产出 ≥10 个带可取回来源的候选；Phase 4 七天内库存不低于告警线。

**P0-2 模型调用预算与调用方式**  
位置：`docs/PLAN.md` §2 "默认 timeout 20 秒"、§6 流程第 4 步 "每篇约 3–4 次调用"。  
影响：实测约 5 字/秒（含进程启动）。1,600 字初稿约 5 分钟，审稿 1–2 分钟，英文翻译 3–5 分钟，一篇合计 10–20 分钟模型时间；任何按秒计的超时都会让每天失败。`-z` 会加载 cwd 的 AGENTS.md；argv 单参数有上限；输出上限 20k 字符装不下双语 JSON。  
最小修复（已写入 PLAN §6）：每次调用超时 900 s、整篇总预算 45 分钟；prompt ≤ 120 KB（兼容 4 KB 页内核）、证据摘录预算约 25,000 汉字；输出上限 ≥ 80,000 字符；子进程 cwd 指向空目录；记录每次 wall time；准备工作放在前一晚。  
验收：Phase 2 dry run 报告每次调用的真实耗时与字节数；超限 prompt 被拒绝而不是截断；在 cwd 放一个诱饵 AGENTS.md 验证它不会被注入。

**P0-3 部署核对方式**  
位置：`docs/PLAN.md` §6 第 7 步、§7 链接形式、§12 故障测试"部署返回旧页面"。  
影响：线上对任何路径都返回 200 + 首页，HTML 还会被注入脚本；按 200 或整页哈希核对会误判成功，页面 JS 取 JSON 可能收到 HTML 而静默失败。  
最小修复（已写入 PLAN）：发布核对只取 `data/history/index.json` 与当日 JSON，解析后比较 `edition_id`、`revision`、两种语言的 `title`；页面 JS 校验 `Content-Type` 与 JSON 可解析并显示明确错误；邮件与站内链接统一为 `/history/?story=<id>&lang=zh|en`。  
验收：故障测试里"旧页面"用 revision 不一致触发；手工把 index.json 改坏后页面显示错误而非首页。

### P1

**P1-1 篇幅与十分钟**  
位置：`docs/PLAN.md` §3。  
估算（中文 350 字/分，英文 220 词/分，陌生题材的仔细阅读）：

| 方案 | 中文 | 英文 | 双语合计阅读 | 含问题停顿 |
|---|---|---|---|---|
| v2 | 1,000–1,300 字 | 550–700 词 | 约 6–7 分钟 | 约 7–8 分钟 |
| v2.1 建议 | 1,400–1,800 字 | 800–1,000 词 | 约 8–9.5 分钟 | 约 10 分钟 |

影响：双语十分钟是现实的，但 v2 规格偏短约 30%，更重要的是九个栏目让故事只剩 500–650 字。  
最小修复（已写入）：上调篇幅；"为什么会这样"并入故事正文作为"转折与解释"；故事 + 解释 ≥ 55%；"本篇依据 / 想再读一点"不计入阅读时间预算。只读一种语言的读者约 5 分钟，可以接受。前七天用真实时间校准的要求保留。  
验收：Phase 1 四篇样稿字数在区间内，两位读者各记录两次真实阅读时间。

**P1-2 去重依赖模型自拟的事件 ID**  
位置：`docs/PLAN.md` §4、§7；`docs/EDITORIAL_BRIEF.md` "每日新内容与长期可持续性"。  
影响：若 `event_id` 由模型起名，同一事件换个 slug 就绕过去重；语义比较成本高且不稳定。  
最小修复（已写入）：事件 ID 在每周人工批准时确定；内容对象增加 `wikidata.persons[]`、`wikidata.event`（有则填）；规则：事件 QID 相同 = 重复；主角 QID 90 天内再现 = 告警并要求不同事件；SQLite FTS5 对双语标题、摘要、人物、地点做召回，语义比较只在 top-k 候选上做。Wikidata 从 Pi 可达（已测）。  
验收：用改标题、改语言、改类别的三种同事件稿件测试，均被拒。

**P1-3 时区与排期窗口**  
位置：`docs/PLAN.md` §2 默认 07:30、§6 "与 news-intel 错峰"、§10 "明确 IANA 时区"。  
影响：Pi 系统时区是 Chicago；现有 LLM 重任务在 22:00 LA（写死 UTC，不随夏令时）与 07:00 LA；若按系统时区写 OnCalendar 会差两小时，若与 22:00 撞车会争抢 MiMo 额度。  
最小修复（已写入）：`OnCalendar=*-*-* 20:00:00 America/Los_Angeles` 准备、`07:30:00 America/Los_Angeles` 发送，`Persistent=true`；文档列出共享 Hermes 的全部任务；并发 1。  
验收：`systemd-analyze calendar` 在 2026-11-01 夏令时结束前后各给出正确时刻；七天试运行日志无与 22:00 LA 任务重叠。

**P1-4 故事"有趣"缺少提纲阶段的硬门槛**  
位置：`docs/PLAN.md` §5 "文章审核"、`docs/EDITORIAL_BRIEF.md` "一篇好故事的最低要求"。  
影响：现有要求都在成稿后检查；但题目本身没有"真实决策点"的（过程史、制度史）写出来必然是摘要，返工成本在成稿后最高。  
最小修复（已写入 EDITORIAL_BRIEF）：提纲必须填写**故事骨架**五项：主角想要什么、受什么约束、在哪个时刻面对 ≥2 个真实选项、选了什么与后果、一个可核实的记得住的细节（带来源）。缺任一项不进入写作。  
验收：Phase 1 四篇提纲各附骨架；至少否决一个候选并记录原因。

**P1-5 开放问题会趋同**  
位置：`docs/EDITORIAL_BRIEF.md` "开放问题与示例解答"。  
影响：模型默认会反复产出"利益分配/信任"类问题，示例解答也会收敛到同一处事策略。  
最小修复（已写入）：问题类型标签轮换（不确定下决策、分配与归属、何时离开、相信谁、如何纠错、何时等待、如何授权、如何传达坏消息），连续 7 期不重复类型；示例解答必须含"另一种合理选择"。  
验收：归档索引可按 `reflection.type` 统计；七天内无重复。

**P1-6 缺失输入未集中列出**  
位置：`docs/PLAN.md` §2 分散叙述。  
最小修复（已写入 §2 "缺失输入清单"表）：SMTP 账号与授权方式、两位读者邮箱、发送时间确认、Cloudflare 部署方式与生产分支、维护者告警渠道。实施前由用户一次性提供。

**P1-7 新栏目与私人文章库的边界**  
位置：`docs/PLAN.md` §8。  
影响：`articles.html` 是口令保护的付费内容归档，口令可从源码恢复；新公开栏目若复用其脚本或索引，会把两者的问题互相传染。  
最小修复（已写入）：独立 `history/` 页面与 `data/history/`，不 import `articles.html` 的 JS，不在新页面链接 vault；发布器写路径白名单只含 `history/`、`data/history/`。  
验收：PR 评审检查 diff 不触及 `articles.html` 与 `data/articles/`。

### P2

- **P2-1 目录树与实际文件名不一致**：§7 列 `docs/EDITORIAL_POLICY.md`，实际是 `docs/EDITORIAL_BRIEF.md`。已改。
- **P2-2 邮件体积预算**：按 v2.1 篇幅，table + inline CSS 的 HTML 约 30–60 KB，低于 Gmail 约 102 KB 的裁剪阈值，但应在门槛中写死上限（建议 90 KB）并在 Phase 3 用真实客户端验证；页脚不要每天逐字相同，否则 Gmail 会折叠为"已修剪内容"。已写入 §9。
- **P2-3 来源许可**：Wikisource / Wikipedia 文本为公有领域或 CC BY-SA；引用其译文或条目文字须注明。已写入 §5 证据规则。
- **P2-4 Hermes 日志增长**：每次 `-z` 调用写 `~/.hermes/logs/agent.log`，证据文本会落在日志里（无密钥，但有体量）。Opus 核实轮转策略。已写入 §10。
- **P2-5 资源上限**：根分区 78% 已用；系统单元加 `MemoryMax=1G`、`Nice=10`，证据缓存设上限（建议 2 GB）并清理；此前本机曾有无界任务拖垮采集器两天。已写入 §10。
- **P2-6 1840 年前后与"世界史"边界**：无需改；建议把 1840 写成"约"，避免为鸦片战争前后题材争边界。已微调。
- **P2-7 Telegram**：维持不作为首版渠道。无需改。

## 4. 已直接修订的文档

- `docs/PLAN.md` → v2.1：§2 改写为"已核实 / 未验证 / 缺失输入"三表；§3 篇幅与阅读时间表；§4 语料库白名单、侦察任务、每周人工批准、Wikidata 去重、问题类型轮换；§6 实测调用预算、cwd、argv 上限、排期窗口与时区；§7 目录树与链接形式、`wikidata` 与 `reflection.type` 字段；§8/§6 发布核对改为 JSON revision 比对；§9 邮件体积预算；§10 资源上限与日志；§13 记录本评审。
- `docs/EDITORIAL_BRIEF.md`：新增"故事骨架（提纲门槛）"、"问题类型轮换"；篇幅与预算说明与 PLAN 一致。
- `README.md`：加入本评审链接与 v2.1 状态。
- `prompts/02_OPUS_IMPLEMENT.md`：加入实测约束、必须核实项与每周人工批准步骤。

## 5. 仍未验证（交 Opus 实施时核实）

1. Cloudflare 资源类型（Pages 还是 Workers Static Assets）、连接的仓库与生产分支、是否 push 即部署。线上 = main 只是相容证据。现阶段不改 Cloudflare 或 DNS。
2. SMTP 账号、授权方式、两位读者邮箱、发送时间：待用户提供。
3. `hermes -z` 在模型报错、额度耗尽、fallback 链触发时的退出码与 stdout 内容；MiMo 的并发/速率限制；与 `hermes-gateway` 和 polymarket cron 同时调用时的行为。
4. Hermes 日志轮转；`sessions/` 在长期一次性调用下是否增长（本次单次调用未增长）。
5. 可达性未定的史料站点：marxists.org 中文毛泽东文库、Founders Online、Perseus/LacusCurtius、Gutenberg；以及 Wikisource 对脚本的速率要求。
6. 英文 Wikisource 的 Livy 卷 3 正确 URL。
7. 实际邮件客户端（Gmail Web/iOS、Apple Mail）对双语长邮件的呈现与裁剪。
8. `-m` 覆盖到更便宜/更快模型做审稿或翻译是否可行与可接受。

## 6. 建议实施顺序（对 PLAN §11 的调整）

Phase 0（本轮）→ ChatGPT 再评审 → 用户确认后：

1. **Phase 1 先做证据包与提纲，再写稿**：四个候选先过"故事骨架"门槛并建成白名单证据包，记录人工分钟数；再写四篇样稿、邮件/网页预览。两位读者计时阅读。
2. **Phase 2 dry run 必须报真实耗时**：含一次故意超限、一次 AGENTS.md 诱饵、一次重复事件被拒。
3. **Phase 3 网站 PR 最小化**：只加 `history/`、`data/history/`、首页一个入口；用 JSON revision 核对部署。
4. **Phase 4 七天试运行**：从 20:00 LA 准备、07:30 LA 发送开始；每周一次人工批准会固定下来，作为长期运行的一部分而不是启动期的临时安排。

## 7. 四篇样稿提纲（仅检验设计，事实尚待核实）

每条列出：骨架、候选来源、核实要点、问题类型。**所有史实均未在本轮完成正文核实**，不得视为可发布稿。

**A. 中国古代｜刘邦给陈平四万斤金，不问去向**  
骨架：汉王在楚汉相持、屡败之际，要用离间计瓦解项羽阵营；约束是钱从哪来、人能不能信（陈平是降将，有"盗嫂受金"的指控）；决策点是把巨额黄金交给一个被告发的人且"不问其出入"；后果是楚营内部生疑、范增离去。记得住的细节：四万斤金，不问去向。  
候选来源：《史记》卷五十六陈丞相世家（zh.wikisource 可达，已见"陳平"25 处）；《汉书》卷四十（与《史记》同源，需披露）；一份现代研究或点校本导读作解读。  
核实要点：原文是否确为"出黄金四万斤……不问其出入"；范增离去的因果在史料中如何表述，是否只是时间先后；"盗嫂受金"指控的出处与陈平回应原文。  
问题类型：如何授权——什么时候可以把资源交给一个你不完全信任、但只有他能做成事的人。边界：现代组织里"不问去向"的授权通常违反基本的财务控制。

**B. 世界史｜沙克尔顿决定弃船后往哪里走（1915–1916）**  
骨架：坚忍号被浮冰压毁，28 人在冰上；约束是补给、拖行雪橇船的速度、冰的漂移；决策点先是"向陆地强行跋涉"还是"扎营等冰漂"，后是"谁留在象岛、谁坐小船去南乔治亚"；后果全员生还。记得住的细节：待核实（候选：被迫射杀拖船犬；允许带的个人物品重量限制）。  
候选来源：Shackleton, *South*（1919，公有领域，Gutenberg/Internet Archive）；Frank Worsley 的航海记述；一份现代研究做制衡。  
核实要点：弃船与两次跋涉的日期；小船航程天数；*South* 中关于个人物品限制的原文；避免把 Lansing（1959，受版权保护）的叙事细节当作一手材料。  
问题类型：何时等待——团队在信息不足时，是"做点什么"还是"保存体力等窗口"。

**C. 中国近现代｜毛泽东在寻乌做调查（1930 年 5 月）**  
骨架：红四军进驻寻乌，上级与本地对"怎么分土地、怎么对待商业"有争论；约束是时间（约 20 天）、材料来源（主要靠座谈对象）；决策点是写文件还是先去问清一个县的商店、物价、土地占有；产出《寻乌调查》与同期《反对本本主义》。记得住的细节：待核实（候选：报告中对寻乌城各类店铺与商品的逐项记录）。  
候选来源：《寻乌调查》《反对本本主义》原文（《毛泽东选集》/《毛泽东农村调查文集》；marxists.org 中文库或人民网文本，可达性待核实）；一份关于寻乌调查史料来源与局限的研究。  
核实要点：《反对本本主义》原题与发表史（1930 年 5 月写成，1961 年前长期未公开）；寻乌调查的座谈对象与其局限；文章须说明该文本后来的编辑与版本差异。  
问题类型：相信谁——当文件与你亲眼所见不一致时，先补信息还是先执行。边界：调查方法本身有选择偏差；后续历史不能被这一次调查简化解释。

**D. 美国史｜华盛顿在纽堡面对军官的不满（1783 年 3 月 15 日）**  
骨架：战争将结束，军官欠薪与养老金没有保障，匿名信号召施压国会甚至拒绝解散；约束是军队对国会的从属与华盛顿自己的威望；决策点是不出席、派人去，还是亲自到场；后果是军官们投票表忠于国会。记得住的细节：戴眼镜读信的一句话——但这句话出自在场者 Samuel Shaw 的记述，不在演讲正式文本里，必须按"目击者转述"标注。  
候选来源：Washington 1783-03-15 讲稿文本（Founders Online / 国家档案，可达性待核实；loc.gov 对脚本 403）；Samuel Shaw 的信件/日记；一份现代研究。  
核实要点：讲稿正式文本与眼镜一句的出处分离；匿名信（Newburgh addresses）作者的归属争议；国会随后的实际决议。  
问题类型：如何传达坏消息——下属要去对上施压时，领导站在他们前面还是后面。边界：这是一个威望极高的领导者的个案，不等于任何人到场就能平息。

四篇覆盖：授权、等待、信息核实、传达坏消息四种问题类型，没有重复"识人、分钱、用人"。
