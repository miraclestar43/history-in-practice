# History in Practice｜每日一鉴

版本：v2.3（用户阅读目标澄清），2026-10-30（America/Los_Angeles）  
状态：ChatGPT 再评审的必要修订已落实；四篇样稿、证据映射、邮件/网页本地预览与技术验证已完成（见 `samples/` 与 `docs/reviews/OPUS_VALIDATION.md`）。未部署、未启用定时任务、未发送邮件。用户已要求 overnight 继续实施；最新范围见 `prompts/03_OVERNIGHT_OPUS.md`，不因等待读者反馈或邮件账号停下独立工作。

修订记录：

- v2：长期每日供稿、事件级去重与 GitHub 可读归档、叙事质量、开放问题与示例解答、带说明的延伸阅读。
- v2.1（Fable 评审）：实测调用耗时、线上部署行为、Pi 时区、来源可达性、篇幅调整、问题类型轮换、缺失输入清单。
- v2.2（ChatGPT 再评审 + Opus 验证）：
  - 取消固定每周人工批准，改为默认自动准入、异常进入待处理、可选人工策划。
  - Hermes 隔离：在已安装版本上核实 `-z -t "" --ignore-rules` **并不隔离**，改用项目级隔离调用器。
  - 去重改为不可变 episode 注册表 + 规范出处位置 + 别名/繁简/QID 重定向 + 中文二字召回。
  - 来源按具体文档记录状态。
  - 叙事规则改为“有记录的矛盾、约束、行动与后果”，不要求人物二选一。
  - 篇幅是试稿区间；调用预算来自样稿实测；部署核对覆盖正文哈希。

配套规范见 `docs/EDITORIAL_BRIEF.md`。

## 1. 产品目标与命名

中文约十分钟、英文也约十分钟，通过一个有史料依据、好读的中英双语故事，积累历史知识，练习对现实问题的判断。历史范围包括中国古代、中国近现代（含毛泽东相关历史）、世界史、美国史，也可纳入有文献依据的现代组织、科学和商业事件。

repository：`history-in-practice`。中文栏目：**每日一鉴**；英文栏目：**History in Practice**。description：`A daily bilingual history story, grounded in sources and connected to everyday decisions. Delivered by email and published on StarHub.`

核心体验：**一个好读的故事 → 为什么会这样 → 两点可用启发 → 一条适用边界 → 一个开放问题与示例思路 → 出处与延伸阅读。** 不把成功者说过的话一概当真，不把一次成败总结成普遍定律。

长期目标是机器人每日产出新内容。默认流程不要求维护者每周固定编辑；只有异常需要人处理，并记录实际介入时间。不承诺“完全无人维护”，以试运行实测为准。

## 2. 核实结果、未验证项与缺失输入

“已核实”指读到了代码、命令输出或 HTTP 响应。日期为核实日期；Pi 指 raspberrypi51。

### 2.1 已核实：news-intel Hermes adapter（2026-10-29/30）

- `news-intel` 是 Python / SQLite / systemd 项目；`LLM_PROVIDER=hermes_cli` 选用 `HermesCliProvider`，argv 为 `[hermes_bin, "-z", prompt, "-t", "", "--ignore-rules"]`，`shell=False`，默认 timeout 20 秒，prompt / output 各 20,000 字符。`compose_*` 未实现。
- 该 adapter 的注释认为 `-t ""` 关闭工具、`--ignore-rules` 跳过规则与记忆。**在 Pi 已安装的 Hermes 上两者都不成立**，见 2.2。

### 2.2 已核实：Pi 上 Hermes 的实际行为（2026-10-30）

- Hermes Agent v0.14.0（2026.5.16），源码 revision `a6d87153e`（本地分支 `cst-telegram-integration-20260531-1010`）；配置模型 `mimo-v2.6-pro`，provider `xiaomi`；无 fallback 链。只读取了模型名，未读取凭据。
- **源码检查**（`hermes_cli/oneshot.py`、`hermes_cli/main.py`）：
  - `-t ""` 经 `_normalize_toolsets` 变成“未指定”，于是启用配置里的全部 CLI 工具集；同时设置 `HERMES_YOLO_MODE=1` 自动批准。
  - `-z` 的分派发生在设置 `HERMES_IGNORE_RULES` 之前，`AIAgent` 以 `skip_context_files=False`、`skip_memory=False` 构造。
  - 这与上游 [issue #26633](https://github.com/NousResearch/hermes-agent/issues/26633) 描述一致。
- **加载器探针**（真实 `hermes` 入口，`AIAgent.chat` 被替换为输出摘要，不调用模型；只打印名称与布尔值）：

  | 调用方式 | 工具数 | 含 terminal / write_file / send_message | cwd AGENTS.md canary | SOUL.md | memory |
  |---|---|---|---|---|---|
  | `hermes -z … -t "" --ignore-rules`（news-intel 方式） | 29 | 是，且 YOLO=1 | 注入 | 注入 | 注入 |
  | 项目级隔离调用器（`AIAgent(enabled_toolsets=[], skip_context_files=True, skip_memory=True, session_db=None)`） | 0 | 否 | 无 | 无 | 无 |

- 模型报错时 `hermes -z` **退出码 0、stdout 为空**（用不存在的模型名实测）。调用方必须把空输出当失败。
- 隔离调用器实测：最短调用 11.4 秒；调用前后 `~/.hermes` 内文件无变化。prompt 经 stdin 传入，不再受单个 argv 上限约束。
- 系统时区 America/Chicago；`systemd-analyze calendar "*-*-* 07:30:00 America/Los_Angeles"` 可解析。共享同一 Hermes / MiMo 的任务：`hermes-gateway.service` 常驻；`pi-news-daily.timer` 22:00 LA（写死 05:00 UTC）；`pi-news-daily-zh.timer` 07:00 LA 周一至周六；`pi-news-collect.timer` 每 5 分钟；polymarket 的 Hermes cron。
- 根分区已用 78%；内存 7.9 G。

**现有生产影响（不在本项目范围内修改）**：Pi 上 news-intel 的 `.env` 使用 `LLM_PROVIDER=hermes_cli`，因此它把外部新闻文本送进了一个带 29 个工具、自动批准的 agent，并注入了个人 SOUL / memory。是否、何时修复由用户决定；本项目不改 news-intel、gateway 或全局 Hermes 配置，也不升级生产 Hermes。

### 2.3 已核实：starhub.vip 线上行为（2026-10-30，只读 HTTP）

- 线上 `data/articles/index.json` 与 git `main` 字节一致；HTML 页面只多出 Cloudflare 注入脚本。与 Git 自动部署相容，但未证明是自动部署。
- `*.html` 308 跳转到无扩展名路径；**任意不存在的路径都返回 200 并送回首页 HTML**（含 `/data/history/index.json`）；JSON 文件原样提供。
- `articles.html` 是客户端口令保护的私人付费内容库，新栏目必须与它完全隔离。

### 2.4 已核实：史料来源（2026-10-30，按具体文档，不按域名）

状态阶梯：`unverified → reachable → extractable → evidence_usable`；失败类：`challenge_page`、`wrong_url`、`http_error`、`site_fallback`、`no_relevant_content`（可取回但缺少预期内容）。`evidence_usable` 要求正文中出现预先声明的标记文字（含人名），并在缓存中记录取回时间与 SHA-256。

| 类别 | 文档（适配器） | 状态 | 来源基础 |
|---|---|---|---|
| 中国古代 | 《史记·项羽本纪》《陈丞相世家》（zh.wikisource 渲染文本） | evidence_usable | 司马迁 |
| 中国古代 | 《汉书·张陈王周传》（zh.wikisource） | evidence_usable | 据《史记》改写（同源） |
| 世界史 | Snow, *On the Mode of Communication of Cholera*, 1855（archive.org OCR） | evidence_usable | Snow |
| 世界史 | Cholera Inquiry Committee, *Report…St. James, Westminster*, 1855（archive.org OCR） | evidence_usable | 教区委员会 / Whitehead |
| 中国近现代 | Yung Wing, *My Life in China and America*, 1909, ch. 17, 19（en.wikisource 渲染） | evidence_usable | 容闳（当事人） |
| 中国近现代 | 《清史纪事本末》卷五十八（zh.wikisource） | evidence_usable | 清官方系统史书 |
| 中国近现代 | 《游美同学录》（1917）詹天佑条（zh.wikisource） | evidence_usable | 清华校友录 |
| 中国近现代 | 《清史稿》卷一百七 | no_relevant_content（页面可取，未涉及此事） | — |
| 美国史 | Washington, Newburgh address（en.wikisource） | evidence_usable | Washington |
| 美国史 | *Journals of Major Samuel Shaw*, 1847（archive.org OCR） | evidence_usable | 在场者 Shaw |
| 美国史 | *Journals of the Continental Congress*, vol. 24（archive.org OCR） | evidence_usable | 国会记录 |
| 对照 | ctext.org / Founders Online / loc.gov | challenge_page（200 JS 验证 / 202 空 / 403） | — |
| 对照 | starhub.vip `/data/history/index.json` | site_fallback | — |

验证中发现一个提取缺陷：zh.wikisource 原始 wikitext 用 `{{ProperNoun|陳平}}` 包住人名，简单清洗会把人名整体删掉，而不含人名的标记仍能命中。已改为使用渲染文本，并把人名加入必现标记。来源适配器上线前须有同类抽检。

### 2.5 尚待实施时确认

- Cloudflare 资源类型、生产分支、是否 push 即部署；首次部署后正式链接是否可用。现阶段不改 Cloudflare 或 DNS。
- MiMo 速率限制、与 gateway / polymarket cron 并发时的行为；隔离调用器在 Hermes 升级后是否仍成立（升级后须重跑加载器探针）。
- 更多来源适配器（Gutenberg 直连在 Pi 上超时；marxists.org 中文文库可达但未做文档级验证）。
- 真实邮件客户端呈现与真实读者阅读时间。

### 2.6 缺失输入清单（只影响实际发信与上线，不阻塞样稿与 dry run）

| 输入 | 用途 | 状态 |
|---|---|---|
| 发信账号与授权方式 | 发信 | 建议 Resend + history@read.starhub.vip；账号、域验证及 key 待配置 |
| 两位读者的准确邮箱 | 收件人配置（本地私密文件） | 用户已在私密会话提供；只放 repo 外私密配置，不公开列出 |
| 发送时间确认 | 排期 | 建议 07:30 America/Los_Angeles |
| Cloudflare 部署方式与生产分支 | 网站发布器 | 未知 |
| 维护者告警渠道 | 失败与待处理通知 | 建议沿用现有 Telegram bot，未确认 |

## 3. 阅读长度与栏目设计

**用户最新澄清：中文完整阅读约十分钟，英文完整阅读也约十分钟；不是双语合计十分钟。** 每个版本包含故事、分析、应用、边界、开放问题与示例解答，延伸点开外部来源的时间不计入。

初稿可暂以中文约 **2,800–3,600 字**、英文约 **1,800–2,200 words** 为松参考。这不是硬性下限；以两位读者各语言真实阅读体验校准，不凑字数，也不按固定词数字数比例强迫翻译。两版事实、数字、判断、保留条件与来源一致，英文应自然地道，可重组句法和解释文化背景，不逐字硬译或添加无依据细节。

已有四篇短样稿与实测见 `samples/README.md`，属于旧的双语合计时长目标。保留其证据和运行记录作为基线；今夜在其基础上补充有依据的背景、过程与解释，重做长篇阅读目标与译文质量检验，不能把旧样稿直接视为新长度目标已达标。两种语言分别给出阅读时间估算，随后据真实读速调整。

| 栏目（section id） | 要求 |
|---|---|
| 引子 `hook` | 具体矛盾或处境；不编造人物内心、私密对话或惊险细节 |
| 时间、地点、人物 `context` | 读懂故事必需的背景；日期精度与证据一致 |
| 故事 `story` | 历史本体占最大篇幅；有记录的矛盾、约束、行动、转折与后果 |
| 为什么会这样 `analysis` | 解释利益、信息、信任、制度或约束；区分史料记载与作者推断 |
| 今天可以怎么用 `today` | 两个具体启发，各配一个现代小场景；可与开放问题衔接，不重复说教 |
| 别照搬的地方 `limits` | 至少一条边界、代价、反例或替代解释 |
| 开放问题与示例 `reflection` | 有真实权衡、允许不同合理答案；示例含假设、步骤、另一种合理选择 |
| 出处与不确定性 | 支撑正文的来源与争议；不计入阅读时间 |
| 想再读一点 | 1–3 个说明“点开能读到什么”的链接；不计入阅读时间 |

同一份双语结构化内容生成邮件、网页及 GitHub Markdown，禁止为各渠道分别自由改写。

用户喜欢小约翰可汗的历史内容带来的兴趣：落实为具体矛盾、必要背景、有约束的人物与制度、可核实细节与自然推进的叙事，形成自己的栏目语言，不复制创作者的标志性表达。

## 4. 选题、供稿与去重

### 4.1 轮换与库存

连续四期轮换（中国古代 → 世界史 → 中国近现代 → 美国史），不按固定星期分配。

| 类别 | 边界 |
|---|---|
| 中国古代 | 约 1840 年前；不局限于帝王和战争，纳入改革、科技、商贸、家庭与普通人 |
| 世界史 | 排除中国和美国，覆盖欧洲、亚洲其他地区、非洲、拉美等 |
| 中国近现代 | 约 1840 年起；含晚清、民国、毛泽东相关史事及后续有可靠文献的事件 |
| 美国史 | 独立建国、社会运动、科学、组织与企业等 |

跨国事件选一个主类别。目标库存约 14 天已通过检查、尚未发布的成稿，四类均有储备，低于 7 天告警；库存按已分配排期计算。

### 4.2 供稿运行方式（v2.2）

默认自动进行：候选生成 → 证据取回与分级 → 去重 → 提纲 → 起草 → 规则检查 → 进入库存。维护者不承担固定的每周审批。

1. **候选生成**：模型可以提出候选事件、检索词和候选 URL；这些只是线索。Python fetcher 按来源政策取回正文、分级并缓存。现有写作调用保持无工具；是否另设允许检索工具的“研究调用”，作为可选实验单独测量，不影响写作调用的隔离。
2. **自动准入**（全部满足才进入写作队列，并记录每条通过/拒绝原因）：
   - 来源适配器已在来源政策中；
   - 每条关键事实有 `evidence_usable` 文档中的逐字摘录支撑；
   - 至少两个不同来源基础，或已明确披露共同源头且符合 §5 规则；
   - 去重结论为 `distinct`；
   - 模型自评分数不能代替证据。
3. **待处理队列**（不阻塞其他合格候选，先改用其他候选或备用稿）：新来源类型、材料互相冲突、人物或事件身份不确定、核心细节缺乏支撑、去重结论为 `review`、规则检查 BLOCK。
4. **可选人工策划**：维护者可随时抽查、加题或否决，不是默认流程的必经步骤。试运行若证明某类题材必须人工校核，报告实测劳动量与可靠性限制，再由用户调整服务承诺。
5. 记录每篇的人工介入时间与原因；样稿阶段的编辑介入见 `samples/README.md`。

### 4.3 来源政策

- 记录到“适配器 + 具体文档”级别，不以域名作笼统保证；状态与失败类见 §2.4。
- 同一文本的不同镜像或转载不算独立来源；同一作者的不同篇章（如《史记》两篇）是同一来源基础；经他人书籍转载的文件（如容闳书中所录美国教育者抗议信）须注明转载链。
- 允许逐步扩展可靠机构与研究材料；白名单不是“永远只用少数站点”。依赖缺失时不得用模型记忆补齐。
- ctext.org、Founders Online、loc.gov 对脚本封锁；需要时只能人工阅读后以“摘录 + 位置”进入证据包，并如此标注。

### 4.4 去重（v2.2）

- **episode 注册表**：每个具体片段/决策一条记录，由持久注册表分配不可变的顺序 ID（`ep-000123`）；编号不承担“已查重”的语义。`parent_event` 记录宏观事件（战争、远征、运动），同一宏观事件下可有多篇不同片段。Wikidata QID 为可选外部关联，查询前做重定向规范化。
- **重复判定**（依次）：
  1. 规范 QID 相同 → 重复。
  2. 引用了相同的规范出处位置（作品 + 卷/章 + 段落区间），且至少一个相同人物 → 重复。
     - 译本和其他版本必须映射到原作的卷/段编号；字符偏移不能跨版本比较。
  3. 人物、地点、时间相同且行为描述相近 → `review`（进入待处理，由检查调用或人判断）。
  4. 人物、地点、时间相同但出处与行为不同 → `distinct`。
- **规范化**：繁简（OpenCC t2s）、人名别名表（中/英/称号，例如 陈平 = 陳平 = Chen Ping，亚父 = 范增）、地名。
- **检索**：SQLite FTS5 默认 unicode61 与 trigram 都无法用 MATCH 找到二字人名“陈平”（Pi 上 SQLite 3.40.1 复现）。改为“CJK 二字切分列 + `instr` 子串 + 结构化实体”召回，FTS 只作候选召回，最终以出处位置与实体判定。
- **范围与并发**：查重覆盖 `reserved / prepared / scheduled / published` 全部活动状态；预留在单个 `BEGIN IMMEDIATE` 事务中检查并插入，另以“核心出处位置”唯一索引防止并发双份。
- **重建**：索引可从 Git 中已发布的结构化内容重建，结论与原库一致。
- **验证**：`validation/dedup_check.py`，13/13 通过，结果见 `validation/dedup_check.out.txt`。
- **已知残余风险**：同一片段改用另一部作品转述、且无 QID、行为措辞差异大时，只能落到 `review` 或漏判，须靠检查调用或抽查兜底。

### 4.5 问题类型轮换

`reflection.type` 取自：不确定下决策、分配与归属、何时离开、相信谁、如何纠错、何时等待、如何授权、如何传达坏消息（可扩展）。连续 7 期不重复同一类型。四篇样稿分别为：何时离开、如何纠错、不确定下决策、如何传达坏消息。

## 5. 史料与写作质量

### 证据规则

1. 默认每篇至少两个不同来源基础；优先一份接近原始记录的材料，加一份不同立场或机构的材料。互相转载不是独立证据。
2. “原始记录”不等于客观真相。史书、回忆录、官方材料都有立场和记忆局限，需说明。古代事件如无独立史源，不强造第二证据，须披露共同源头及局限，必要时换题。
3. 关键事实、引语、动机解释都关联到证据 ID 与逐字摘录；模型补出的 URL、书名或凭记忆的段落不可作为证据。
4. 网页必须实际取回正文（或可追溯缓存）；搜索摘要、状态码 200、域名可信都不能证明结论得到支持。
5. 保存短证据片段、获取时间、正文 hash 和出处位置；公开页以原创转述和必要短引为主。
6. 引号只用于原文有据的话。间接引语保持间接（例如肖对华盛顿戴眼镜一幕的记述是转述，不能改写成直接引语）。
7. 人物动机、想法、“考虑过的选项”只有材料写了才能写，并标明出处；作者提出的替代选择、反事实与现代讨论放在分析或开放问题中并明确标记。
8. 毛泽东及其他重要政治人物采用相同标准：交代具体时期、材料来源和分歧，允许讨论成功、错误、代价及其他人的作用。
9. 遵守来源许可；受版权保护的现代著作只做短引与转述并给出页码。

### 文章审核

先检查“读完具体知道发生过什么”，再检查“能否练习一个判断”。程序检查（`validation/check_article.py`）能核对：

- 证据 ID 是否存在；
- 古文引语（繁简转换后）与英文引语（逐字）是否出现在所引摘录中；
- 中英数字是否一致；
- 栏目结构与篇幅是否合规。

它不能证明历史叙述为真。LLM 审稿只是辅助，不能宣称为独立史学审查。

门槛：关键事实没有材料支撑、核心引语归属错、材料冲突未说明、中英文结论漂移、拿现代场景当历史事实，任一出现即不发布，进入待处理；改用合格备用稿，没有则跳过并告警，绝不退回纯模型记忆。

## 6. 架构

### 6.1 部件

第一版：Python + SQLite + systemd + Hermes（经项目级隔离调用器）+ SMTP + 静态 HTML/JSON。独立 repo，不并入 news-intel。

| 部件 | 职责 |
|---|---|
| 候选与队列 | 四期轮换、自动准入、待处理队列、备用稿 |
| 来源适配器与证据缓存 | 取回、分级、提取摘录、hash 与时间戳 |
| episode 注册表 | 去重、预留、从 Git 重建 |
| Hermes 隔离调用器 | 无工具、无规则/记忆注入的写作、审稿、翻译调用；不处理发信或 Git 凭据 |
| 确定性检查 | Schema、引语、证据 ID、数字、长度、跨语言字段 |
| Renderer | 同一内容对象 → 邮件 HTML/纯文本、网页数据、GitHub Markdown |
| Publisher | 归档、导出网站文件、提交、线上核对、按收件人发信 |
| 状态与调度 | 状态机、重试、锁、统计与告警 |

### 6.2 Hermes 调用方式

不使用 `hermes -z`。项目级调用器（验证版见 `validation/hermes_isolated.py` 与 `validation/run_hermes.py`）的约束如下：

- 用 Hermes 自己的 venv 解释器运行，直接构造 `AIAgent(enabled_toolsets=[], skip_context_files=True, skip_memory=True, session_db=None)`。
- 调用前断言工具数为 0、上下文文件与记忆未加载，否则退出码 5。
- prompt 走 stdin，上限 200 KB；工作目录必须为空。
- 空输出视为失败（退出码 3）。
- 调用方用独立进程组，超时先 SIGTERM 后 SIGKILL。
- stdout/stderr 在运行中按上限截断并终止，而不是结束后再检查。
- 不改动用户 SOUL、memory、全局配置，不升级生产 Hermes。Hermes 升级后必须重跑 `validation/hermes_probe.py`。

### 6.3 每日流程与调用预算

1. 前一晚 20:00 America/Los_Angeles 从库存取当日类别的稿件；库存不足时补稿。
2. 每篇三次调用：中文稿（结构化 JSON）→ 按证据审稿 → 英文版；程序检查后冻结版本。
3. 生成邮件、网页数据与 Markdown；归档；导出网站并提交；线上核对（§8）；发信。

预算是可配置初值，来自四篇样稿的实测（见下表与 `samples/model_timings.json`）。单次调用超时与输出上限取实测最大值的约 2 倍；库存补充按“分篇截止 + 整批截止”设计，systemd `TimeoutStartSec` 不能设成单篇预算，否则批量补稿会在第一篇后被杀。

2026-10-30 在 Pi 上用隔离调用器实测（mimo-v2.6-pro，串行，共 12 次调用，0 次重试，全部一次返回合法 JSON）：

| 调用 | wall time（4 篇） | 输入 | 输出 | 建议初值（可配置） |
|---|---|---|---|---|
| 中文稿 | 163–362 s（均值 231 s） | 8.9–13.5 KB | 10.0–10.5 KB（约 4,600–4,900 字符） | 单次超时 720 s |
| 按证据审稿 | 129–271 s（均值 209 s） | 14.9–19.4 KB | 3.7–9.4 KB | 600 s |
| 英文版 | 100–119 s（均值 111 s） | 15.3–19.8 KB | 13.2–14.4 KB（约 13,200–14,400 字符） | 480 s |
| 每篇合计 | 447–602 s | | | 分篇截止 25 分钟 |

- 输出上限设 64 KB。最大一次输出约 14,400 字符，news-intel 的 20,000 字符上限勉强够用但余量小。
- 整批补稿的截止时间按“篇数 × 25 分钟 + 余量”计算。
- 这只是一次运行 12 个样本，provider 波动未测；试运行中继续记录，再调整。

### 6.4 调度与并发

`OnCalendar=*-*-* 20:00:00 America/Los_Angeles`（准备）与 `*-*-* 07:30:00 America/Los_Angeles`（发送），`Persistent=true`；Pi 系统时区是 Chicago，不能依赖它。准备窗口避开 22:00 LA 与 07:00 LA 的 news-intel 任务；本项目 Hermes 并发为 1。全局锁只有在所有参与任务共同采用时才有效。资源上限：`MemoryMax=1G`、`Nice=10`；证据缓存上限约 2 GB 并清理。

## 7. 内容对象与文件组织

公开内容对象（样稿实例见 `samples/*/article.json`）：

- 标识与版本：`schema_version`、`edition_id`、`episode_id`、`edition_date`、`category`、`revision`。
- 双语正文：`title.zh/en`、`dek.zh/en`、`sections[]`（稳定 id，每段 `zh/en/kind/ev[]`）。
- 开放问题：`reflection`（`type`、`scenario`、`question`，以及 `example.assumptions/steps/alternative`）。
- 来源与延伸：`uncertainty_note`、`sources[]`（含来源基础、URL、取回时间、文本 hash）、`further_reading[]`（含说明与访问限制）。
- 篇幅与校验：`length`、`reading_minutes`（标注估算口径）、`content_sha256`（覆盖双语正文、问题、示例与来源字段）、`correction_note`。

内部审核记录另存：证据摘录、模型原始输出、审稿意见、编辑修改记录。收件人、密钥、投递日志、私人反馈和原始抓取全文不进入公开 JSON。

```text
README.md
docs/PLAN.md  docs/EDITORIAL_BRIEF.md  docs/reviews/
config/rotation.yaml  config/sources.yaml  config/delivery.example.yaml
prompts/
src/history_in_practice/{sources,registry,llm,editorial,render,publish,jobs}/
templates/
content/YYYY/MM/DD-<edition>.json  .zh.md  .en.md
deploy/systemd/
tests/
samples/      # 本阶段样稿与证据（非正式期次）
validation/   # 本阶段技术验证脚本（非生产代码）
```

本地 `data/`（SQLite、日志、抓取缓存、待处理稿）和私密配置不提交。

网站新增 `history/index.html`、`data/history/index.json`、`data/history/YYYY/MM/DD-<edition>.json`；链接统一 `/history/?story=<id>&lang=zh|en`。

## 8. 网站阅读体验与部署

默认中文；顶部 `中文 / English` tab（键盘可操作），切换时按 section id 保持阅读位置；记住语言偏好；URL 可指定语言。列表按日期倒序、四类筛选。示例思路可折叠；来源与延伸阅读分区。正文宽约 720 px、字号 17.5 px、行距 1.8，支持明暗主题。页面只用 `textContent` 渲染数据；取 JSON 时校验 `Content-Type` 与可解析性，取到首页回退时显示明确错误。本地预览见 `samples/preview/`。

`website_test` 只新增 `history/`、`data/history/` 与首页一个入口；不触及 `articles.html` 与 `data/articles/`。

**发布核对**：

1. 取回线上 `index.json` 与当日 JSON。
2. 比较 `edition_id`、`revision` 与 `content_sha256`，三者都要与本地冻结版本一致；`content_sha256` 覆盖双语正文、问题、示例与来源。
3. 首次上线与改版时，用无头浏览器打开两种语言的深链，确认正文渲染（本阶段已在本地预览上这样验证）。

JSON 取回成功不等于阅读页面已验证。

Git 约定：开发用短期分支和 PR；Pi 生产各 repo 保留干净 main。发布器只能修改允许路径；冲突立即停下，不 force push。

## 9. 邮件：中文完整篇在前，英文完整篇在后

首版使用已有、可授权的 SMTP 账号，TLS，HTML + text/plain。顺序：栏目信息 → 中文全文、问题与参考思路、出处与延伸阅读 → “在网页阅读 / Read in English”按钮与分隔线 → 英文全文 → 页脚（期次、链接、反馈与暂停方法）。table 布局 + inline CSS，约 640 px，不依赖 JS、外部字体或背景图。

HTML 上限 90 KB 作为工程初值（样稿实测字节数见 `samples/README.md`）；真实客户端的呈现与裁剪以实测为准，不作“不截断/不折叠”的保证。

分别发给两位读者、分别记录状态；不能依据昵称猜地址。

## 10. 可靠性、重试与恢复

- 状态：`prepared → checked → archived → site_committed → site_live → email_pending → complete`；每收件人 `pending / sending / accepted / unknown / failed`。SMTP accepted 不等于读者已收到。
- 正文冻结后不因网络失败重新生成；已成功渠道不重复投递；发送后结果不明标记 `unknown`，禁止盲目自动重发。
- 网站提交、部署和发信分别重试，有上限、退避和总截止时间；重启不补发积压多天邮件。
- 轮换按已发布期次推进；故障补发使用原期次。
- 更正保留 revision 与说明；实质错误发送简短更正。
- 没有合格稿就停发并告警，不发送占位内容。
- 正文与史料中的指令视为数据；Git 与发信密钥不进入任何模型调用。
- 记录模型名、prompt 版本、材料 hash、耗时、字节数、调用次数与失败原因；token 与费用拿不到就记 unknown。

## 10.5 实施状态（2026-10-30 overnight）

详见 `docs/OVERNIGHT_REPORT.md`。简表：

| 部分 | 状态 |
|---|---|
| 来源取回与分级、证据摘录、去重注册表、隔离 Hermes 调用、校验、同源渲染 | 已实现，并在真实取回与真实模型调用中使用 |
| 自动供稿流水线（候选 → 证据 → 准入 → 去重 → Hermes 三步 → 检查 → 库存或待处理） | 已实现；两个候选题真实运行 |
| SQLite 状态、崩溃恢复、逐收件人发信状态、SMTP 发送 | 已实现；本地 SMTPS 测试，未真实发信（发信账号待配置） |
| 网站导出与上线核对 | 已实现；本地 fixture 验证；`website_test` 改动为本地分支补丁，未推送 |
| systemd 模板 | 已写，未安装、未启用 |
| 库存 | 远低于 14 天目标；四篇样稿 + 自动候选，详见报告 |

## 11. 阶段

- **Phase 0 评审**：完成（Fable → ChatGPT → 本轮修订）。
- **Phase 1 证明值得读**：四篇样稿、证据映射、预览与真实耗时已交付（`samples/`）。待两位读者阅读、计时并反馈；若反馈认为空泛或过长，先改样稿再扩展。
- **Phase 2 自动供稿 dry run**：实现来源适配器、episode 注册表、自动准入与待处理队列、隔离调用器、检查与渲染、SQLite 状态机和 CLI（`doctor / prepare / preview / publish --dry-run / status / retry`）。验收：
  - 自动完成至少连续两轮四类供稿 dry run（共八篇），无人工点击也能进入合格写作队列；
  - 异常进入待处理而不停止其他合格稿；
  - 报告每篇实际人工介入时间与原因；
  - 这八篇不等于证明全年无需维护。
- **Phase 3 集成网站与邮件**：核实 Cloudflare 配置，网站小范围 PR，按 §8 核对；确认发信授权与收件人后发测试信。
- **Phase 4 Pi 七天试运行**：独立 systemd 单元，观察阅读时长、空泛程度、模型耗时、投递与部署问题，再按确定配置持续运行。

分别报告：本地预览、真实 Hermes 调用、Cloudflare 部署、线上双语可读、SMTP accepted、读者实际收到。

## 12. 验收清单

- 四类各有一篇样稿，故事具体、证据可追溯、中英结论一致；叙事与编辑解释逐段标注（`kind`）。
- 引语与日期经证据对照；间接引语未被改成直接引语；替代选项不写成人物的真实想法。
- 每篇两个具体应用、一条边界、一个有真实权衡的开放问题，示例含假设、步骤与另一种选择。
- 两位读者至少数篇真实阅读用时。
- 自动准入、待处理、去重（含繁简、别名、英文、类别、QID 缺失/重定向、预备中重复、并发）与从 Git 重建均有测试。
- 隔离调用器的加载器探针为 0 工具、无 canary；模型报错不被当作成功。
- 网站与邮件来自同一期次与 revision，`content_sha256` 一致；网站未上线时不发坏链接。
- 私人聊天、收件人和凭据不出现在公开内容或提交中。
- 关键故障测试：Hermes 超时/空输出/非法 JSON、证据缺失、错误引语、翻译数字漂移、Git 冲突、部署旧版本、部分投递失败、发送结果未知、Pi 重启、SQLite 丢失后重建。

## 13. 评审与验证记录

- `docs/reviews/FABLE_REVIEW.md`（v2 → v2.1；其中“-t '' 关闭工具、空 cwd 即可隔离”的结论已被本轮核实推翻，保留原文作为记录）。
- `docs/reviews/CHATGPT_REVIEW.md`（v2.1 再评审）。
- `docs/reviews/OPUS_VALIDATION.md`（本轮：修订落实情况、技术验证、样稿与耗时）。
- 当前阶段不安装定时任务、不部署网站、不发送邮件。

## 14. 核实来源

- news-intel：[README](https://github.com/miraclestar43/news-intel/blob/main/README.md)、[provider.py](https://github.com/miraclestar43/news-intel/blob/main/src/news_intel/llm/provider.py)、[hermes_cli.py](https://github.com/miraclestar43/news-intel/blob/main/src/news_intel/llm/hermes_cli.py)
- Hermes 上游：[issue #26633](https://github.com/NousResearch/hermes-agent/issues/26633)；Pi 已安装源码 `~/.hermes/hermes-agent`（`hermes_cli/oneshot.py`、`hermes_cli/main.py`、`run_agent.py`）
- [website_test](https://github.com/miraclestar43/website_test)、[articles.html](https://github.com/miraclestar43/website_test/blob/main/articles.html)
- [Cloudflare Workers Git integration](https://developers.cloudflare.com/workers/ci-cd/builds/git-integration/)
- [SQLite FTS5](https://www.sqlite.org/fts5.html)、[Wikidata redirects](https://www.wikidata.org/wiki/Help:Redirects)
- 史料文档与取回记录：`validation/fetch_results.json`

## 最新用户要求与 overnight 入口

`docs/USER_REQUIREMENTS_20261030.md` 优先于旧篇幅和阶段描述；执行 `prompts/03_OVERNIGHT_OPUS.md`。新增长稿需重测调用预算，旧短稿实测仅为基线。邮件建议见 `docs/EMAIL_SETUP.md`。任务文件推送不代表 Pi Claude 已自动启动。
