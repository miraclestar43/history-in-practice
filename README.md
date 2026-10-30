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

尚未部署、未启用定时任务、未发送真实邮件。进展与验证结果见 [docs/OVERNIGHT_REPORT.md](docs/OVERNIGHT_REPORT.md)。

- [完整方案](docs/PLAN.md) · [最新用户要求](docs/USER_REQUIREMENTS_20261030.md) · [编辑规范](docs/EDITORIAL_BRIEF.md) · [发信配置](docs/EMAIL_SETUP.md)
- [五篇样稿、七篇自动供稿文章（中英各约十分钟目标）与预览](samples/README.md)
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
