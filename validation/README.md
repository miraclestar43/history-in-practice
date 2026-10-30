# validation/：本阶段技术验证脚本（不是生产代码）

| 脚本 | 用途 | 运行 |
|---|---|---|
| `hermes_probe.py` | 不调用模型，检查 Hermes 实际构造出的工具与上下文（canary） | 在含 canary `AGENTS.md` 的目录中：`~/.hermes/hermes-agent/venv/bin/python validation/hermes_probe.py cli -z probe -t "" --ignore-rules`；对照：`… hermes_probe.py direct '[]'` |
| `hermes_isolated.py` | 项目级隔离调用器（0 工具、无规则/记忆注入，prompt 走 stdin） | 由 `run_hermes.py` 调用 |
| `run_hermes.py` | 有界调用：进程组超时、运行中输出上限、耗时与字节记录 | `python3 -I -c "import sys; sys.path.insert(0,'validation'); import run_hermes; print(run_hermes.call('…'))"` |
| `fetch_source.py`、`run_fetch.py`、`sources_manifest.json` | 按文档取回、分级、缓存来源 | `python3 -I validation/run_fetch.py "$PWD" data/source_cache` |
| `build_evidence.py`、`excerpt_spec.json` | 用起止锚点从缓存截取逐字摘录，生成 `samples/evidence_*.json` | `python3 -I validation/build_evidence.py "$PWD" data/source_cache` |
| `prompts/`、`draft_pipeline.py` | 样稿三步模型调用（中文稿、审稿、英文） | `python3 -I validation/draft_pipeline.py A B C D`（约 37 分钟，串行） |
| `assemble.py` | 合并中英稿并应用 `samples/X/edits.json`，记录编辑修改 | `python3 -I validation/assemble.py A` |
| `check_article.py` | 证据 ID、引语（繁简/逐字）、数字、结构检查 | `.venv/bin/python -I validation/check_article.py samples/A/article.json samples/evidence_A.json` |
| `render.py`、`site_template/` | 同一对象 → 邮件 HTML/纯文本、网页数据、Markdown | 见 `samples/README.md` |
| `preview_server.py` | 本地预览与截图辅助（只绑定 127.0.0.1） | `python3 -I validation/preview_server.py 18767 samples/preview/site` |
| `dedup_check.py` | 去重方案验收用例 | `.venv/bin/python -I validation/dedup_check.py` |

`.venv/` 只装了 `opencc-python-reimplemented`（繁简转换）；`data/` 是来源缓存与运行日志，均不提交。
