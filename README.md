# History in Practice｜每日一鉴

每天约十分钟：一个有依据、值得读的历史故事，一个与生活有关的判断问题。

A daily bilingual history story, grounded in sources and connected to everyday decisions.

## 计划中的阅读体验

- 中国古代 → 世界史 → 中国近现代 → 美国史，连续四期轮换。
- 中文与英文对应，邮件中文全文在前、英文全文在后；StarHub 子页面以 tab 切换语言。
- 有具体人物、约束、行动和细节的叙事；简短现实应用、适用边界、开放问题及示例解答。
- 可追溯出处与带说明的延伸阅读，让感兴趣的人继续读。
- 长期每日更新、事件级去重、GitHub 永久归档；提前准备合格库存，内容质量优先。

## 当前状态：样稿与技术验证阶段

尚未实现或部署自动化服务，也未发送邮件。

1. [完整方案 v2.2](docs/PLAN.md)
2. [内容体验与长期编辑要求](docs/EDITORIAL_BRIEF.md)
3. [四篇双语样稿、证据映射与本地预览](samples/README.md)
4. 评审记录：[Fable](docs/reviews/FABLE_REVIEW.md) → [ChatGPT](docs/reviews/CHATGPT_REVIEW.md) → [Opus 修订与验证](docs/reviews/OPUS_VALIDATION.md)
5. [Claude Opus：后续分阶段实施](prompts/02_OPUS_IMPLEMENT.md)

下一步：两位读者阅读样稿并反馈 → 用户决定是否进入自动供稿流水线实施。

运行环境计划：Raspberry Pi、Hermes（经项目级隔离调用器，不用 `hermes -z`）、Python、SQLite、systemd、SMTP，以及 [StarHub](https://starhub.vip/) 现有静态网站。`validation/` 下是本阶段的验证脚本，不是生产代码。
