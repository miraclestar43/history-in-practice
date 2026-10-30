# 给 Claude Opus：按最终评审结论分阶段实施

这是实施阶段的 prompt。**只有 Fable 评审和 ChatGPT 再评审已完成、用户已要求进入实施时才执行。** 当前仓库初始化并不等于要求立即部署或发送邮件。

仓库：https://github.com/miraclestar43/history-in-practice

先读 `README.md`、`docs/PLAN.md`、`docs/EDITORIAL_BRIEF.md`、`docs/reviews/` 中实际存在的评审文件，以及对应 PR 的讨论。若最终评审存在尚未落到代码仓库的决策，先整理出实现所依据的版本。不要把缺失评审文件假装成已通过。

## 最终目标

树莓派长期运行，使用已配置的 Hermes CLI / Xiaomi MiMo 生成有史料依据、叙事有趣、与现实判断相关的每日双语历史文章。邮件发给 Star 和阿范，中文全文在前、英文全文在后；StarHub 新子页面默认中文、英文 tab 切换。正式内容和派生 Markdown 在 GitHub 归档，网页和邮件与归档使用同一期次和版本。

每天新故事，四类轮换。历史事件级去重，不能通过改标题或改语言重发；长期扩充来源与题库，提前生成审核，维持约 14 天合格库存并在低于 7 天时告警。不要以硬性不断更为理由跳过证据要求。

文章包含：具体故事、必要背景、解释、简短现实应用、适用边界、开放问题、示例解答、本篇依据和带说明的延伸阅读。示例是可讨论的参考思路，不是标准答案。形成自己的语言，不套用历史博主的标志性表达。

## 先核实环境，再决定细节

- news-intel：https://github.com/miraclestar43/news-intel 。只作调用与运维习惯参考；本项目不修改 news-intel、gateway 或全局 Hermes 配置。
- **Hermes 不用 `hermes -z`**。2026-10-30 在 Pi 已安装版本（v0.14.0，revision `a6d87153e`）上核实：`-z … -t "" --ignore-rules` 会启用 29 个配置工具并自动批准，且注入 SOUL、memory 与 cwd 的 AGENTS.md；模型报错时退出码 0、stdout 为空。使用项目级隔离调用器（验证版 `validation/hermes_isolated.py` + `validation/run_hermes.py`），上线前与每次 Hermes 升级后重跑 `validation/hermes_probe.py`，确认 0 工具、无 canary。
- 调用预算以 `samples/model_timings.json` 的实测为初值，可配置；运行中强制输出上限与进程组超时；批量补稿按分篇 + 整批截止设计。
- 网站：https://github.com/miraclestar43/website_test ，域名 https://starhub.vip/ 。线上对任何路径返回 200 + 首页 HTML，`*.html` 308 跳转。发布核对用 `data/history/*.json` 的 `edition_id`、`revision` 与 `content_sha256`，首次上线再用无头浏览器验证两种语言深链；链接统一 `/history/?story=<id>&lang=zh|en`；`articles.html` 是口令保护的私人库，新栏目与它完全隔离。确认实际 Cloudflare 资源、生产分支和发布配置，不改 DNS。
- 邮件授权、准确收件人和发送时间从用户确认或明确配置取得；不能根据人名猜地址。默认排期建议 20:00 America/Los_Angeles 准备、07:30 发送。缺失输入（`docs/PLAN.md` §2.6）只阻塞实际发信，不阻塞 dry run。
- 史料来源：按“适配器 + 具体文档”记录状态（`docs/PLAN.md` §2.4、`validation/fetch_results.json`）；zh.wikisource 必须用渲染文本或模板感知解析（原始 wikitext 会吞掉人名）。

## 分阶段执行

1. **读者反馈**：四篇样稿（`samples/`）先给两位读者读并计时；按反馈调整篇幅、语气与栏目，再扩展。
2. **自动供稿流水线**：来源适配器与证据缓存、episode 注册表（`docs/PLAN.md` §4.4，参考 `validation/dedup_check.py`）、自动准入与待处理队列（§4.2）、隔离调用器、结构化内容、确定性检查（参考 `validation/check_article.py`）、同源渲染（参考 `validation/render.py`）、SQLite 状态与 CLI。验收：连续两轮四类 dry run（八篇）无人工点击进入合格队列，异常进入待处理而不阻塞其他稿，报告每篇人工介入时间与原因及每次调用的真实耗时与字节数；关键故障测试见 §12。
3. **归档与发布**：同一正式内容生成 JSON、中英文 Markdown、索引、邮件和网页。网站导出限制为允许路径。跟踪两个 repo 提交与线上 revision 和 `content_sha256`，确保发布中断能恢复。
4. **接入邮件和网站**：配置具备授权的发信账号、分别跟踪两位收件人。网站确认正式内容可读后再发邮件。
5. **Pi 运行与七天观察**：独立 systemd 配置，错开 news-intel，准备库存，验证恢复、夏令时和各渠道状态。

## 实施约束

- 历史依据必须来自取得正文的材料或可追溯缓存。搜索摘要和模型自评不构成充分事实证明。关键事实、引语和数字有 source 映射，冲突与不确定性写清楚。
- 不把私人聊天和真实组内纠纷发布到公开网站；用一般化的现代情境。现代例子须与史事分开。
- 叙事质量不能只用词数和 JSON 合法性验收；展示四篇真实样稿，让人能读出差异。
- 去重覆盖已发布、已排期、已准备和已预留的稿件；SQLite 可从已发布 Git 内容重建；若本地状态丢失，不因此重发历史文章。
- 人物动机与“考虑过的选项”只有材料写了才能写；作者提出的替代选择只放在分析或开放问题里并标明。
- 收件人、凭据、原始私密数据不进公开仓库或 LLM prompt。模型不生成可执行 HTML/JS。CLI 用 argv、`shell=False` 和明确时间/大小预算。
- SMTP accepted 不等于读者收件箱已收到；结果未知时不能盲重发。发信、部署分别重试，失败不重新生成正文。
- 不 force push、不丢弃他人更改、不自动清除生产工作目录。开发短期分支、draft PR；Pi 生产使用干净的 main，避免堆积多个分支目录。
- 不把模拟结果说成生产成功。分别报告 mock 测试、真实 Hermes、Cloudflare 部署、线上双语内容、SMTP 接受和实际收到邮件的证据。
- 不为样式和简单文字改动堆机械测试；测试事实门槛、去重、状态恢复、部署旧版本和部分投递失败等关键行为。

## 交付

提交可运行代码、样稿与证据、预览、测试结果、配置示例、Pi 安装和恢复步骤、网站集成 PR，以及剩余未验证项。记录具体 commit 和运行命令。内容与发布尚未接通时明确说明，不能用“已实现接口”代替最终可用性。
