# History in Practice｜每日一鉴

每天约十分钟：一个有依据、值得读的历史故事，一个与生活有关的判断问题。

A daily bilingual history story, grounded in sources and connected to everyday decisions.

## 计划中的阅读体验

- 中国古代 → 世界史 → 中国近现代 → 美国史，连续四期轮换。
- 中文与英文对应，邮件中文全文在前、英文全文在后；StarHub 子页面以 tab 切换语言。
- 有具体人物、约束、选择和细节的叙事；简短现实应用、适用边界、开放问题及示例解答。
- 可追溯出处与带说明的延伸阅读，让感兴趣的人继续读。
- 长期每日更新、事件级去重、GitHub 永久归档；提前准备合格库存，内容质量优先。

## 当前状态：计划评审阶段

本仓库目前只有规划与评审任务，尚未实现或部署自动化服务，也未发送邮件。

1. [完整方案 v2.1](docs/PLAN.md)
2. [内容体验与长期编辑要求](docs/EDITORIAL_BRIEF.md)
3. [Claude Fable：评审与修订任务](prompts/01_FABLE_REVIEW.md)
4. [Claude Opus：最终评审后分阶段实施](prompts/02_OPUS_IMPLEMENT.md)
5. [Fable 评审结果（2026-10-30）](docs/reviews/FABLE_REVIEW.md)

工作顺序：Fable 评审并提交修订（已完成）→ ChatGPT 再评审 → 用户要求进入实施 → Opus 实施。

运行环境计划采用 Raspberry Pi、Hermes CLI（现有 MiMo 配置）、Python、SQLite、systemd、SMTP，以及 [StarHub](https://starhub.vip/) 现有静态网站结构。

参考已有项目：[news-intel](https://github.com/miraclestar43/news-intel)。Hermes 调用方式、实测耗时、Pi 时区与线上部署行为已在 2026-10-30 核实并记录于 `docs/PLAN.md` §2；发信账号、收件人、Cloudflare 配置等仍待实施阶段确认。
