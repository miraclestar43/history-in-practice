# History in Practice｜每日一鉴

中文约十分钟，英文也约十分钟：一个有依据、值得读的历史故事，一个与生活有关的判断问题。

A daily bilingual history story, grounded in sources and connected to everyday decisions.

## 计划中的阅读体验

- 中国古代 → 世界史 → 中国近现代 → 美国史，连续四期轮换。
- 中文与英文对应，邮件中文全文在前、英文全文在后；StarHub 子页面以 tab 切换语言。
- 有具体人物、约束、行动和细节的叙事；简短现实应用、适用边界、开放问题及示例解答。
- 可追溯出处与带说明的延伸阅读，让感兴趣的人继续读。
- 长期每日更新、事件级去重、GitHub 永久归档；提前准备合格库存，内容质量优先。

## 当前状态：实现开发中（overnight 2026-10-30）

尚未部署、未启用定时任务、未发送真实邮件。AFK 测试期次（隔离网页预览已上线；邮件因发信域名与凭据未配置而未发送）、无人值守 nightly（MiMo 初稿 → Pi 本机 Claude 终审）、库存与书籍导入试点见 [docs/AFK_TEST_AND_BOOKS_REPORT.md](docs/AFK_TEST_AND_BOOKS_REPORT.md)。第三轮（审核 schema 与截止时间修复、Pi 本机 Claude Code CLI 运行验证、具名终审编辑 `hip final-edit`、9 篇待审稿全部经终审入库、覆盖 6 天）见 [docs/FINAL_EDITOR_REPORT.md](docs/FINAL_EDITOR_REPORT.md)。稳定化（发布等待与逾期、轮换覆盖、发信校验、编辑阶段、候选供给）与真实运行结果见 [docs/STABILIZATION_REPORT.md](docs/STABILIZATION_REPORT.md)；overnight 过程见 [docs/OVERNIGHT_REPORT.md](docs/OVERNIGHT_REPORT.md)（顶部有更正）。

当前库存按轮换只有 0 天可排：1 篇可排、9 篇待处理、5 篇样稿待批准。原因和需要人决定的事见稳定化报告第 6 节。

- [完整方案](docs/PLAN.md) · [最新用户要求](docs/USER_REQUIREMENTS_20261030.md) · [编辑规范](docs/EDITORIAL_BRIEF.md) · [发信配置](docs/EMAIL_SETUP.md)
- [五篇样稿、九篇自动供稿文章（含待处理）与预览](samples/README.md)
- 评审：[Fable](docs/reviews/FABLE_REVIEW.md) → [ChatGPT](docs/reviews/CHATGPT_REVIEW.md) → [Opus 验证](docs/reviews/OPUS_VALIDATION.md)

## 代码

| 位置 | 内容 |
|---|---|
| `src/history_in_practice/` | 包：来源取回与分级、证据摘录、episode 注册表与去重、Hermes 隔离调用、校验、同源渲染、SQLite 状态与恢复、网站导出与上线核对、SMTP 发信、自动供稿流水线、CLI |
| `bin/hip` | 命令行入口（用项目 `.venv`） |
| `config/` | 公开配置、别名表、候选题（`candidates/`）、私密配置模板 `runtime.env.example` |
| `tests/` | `unittest`，含本地 SMTPS、站点回退、去重、进程树超时等关键行为 |
| `deploy/systemd/` | 未启用的 user unit 模板 |
| `deploy/website_test/` | StarHub 栏目改动的补丁（未推送到网站仓库） |
| `validation/` | 前期验证脚本、样稿生成、编辑修改（`editor_pass.py`）与统计脚本 |
| `samples/auto/` | 自动供稿文章：模型原始输出、编辑修改记录、证据与成稿 |

```bash
python3 -m venv .venv && .venv/bin/pip install opencc-python-reimplemented   # 一次
bin/hip doctor --probe                       # 环境、Hermes 隔离探针、私密配置（只显示是否已设置）
.venv/bin/python -m unittest discover -s tests
bin/hip render samples/[A-E]/article.json samples/auto/cand-*/article.json --out /tmp/hip-preview
```

私密配置在仓库外：`~/.config/history-in-practice/runtime.env`（权限 600）。真实收件人、密钥只在那里，不进 Git、PR、预览或模型输入。
