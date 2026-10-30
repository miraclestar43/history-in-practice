# Opus：ChatGPT 再评审的修订落实与技术验证

日期：2026-10-30（America/Los_Angeles）  
分支：`review/fable-2026-10-30`（PR #1）；基于 `c60c9fa`。  
范围：同步修订 PLAN（v2.2）、EDITORIAL_BRIEF、README、实施 prompt；在 Pi（raspberrypi51）上做 Hermes 隔离、来源与去重的技术验证；完成四类各一篇双语样稿、证据映射、邮件与网页本地预览，并记录真实模型耗时。未合并、未部署、未启用定时任务、未发送邮件；未修改 news-intel、Hermes gateway 或全局 Hermes 配置。

## 1. 结论

1. ChatGPT 的五项 P1 与三项 P2 均已落到文档（第 2 节），其中两项有本轮实测支撑。
2. **Hermes 隔离问题比再评审描述的更严重**：Pi 上 `hermes -z … -t "" --ignore-rules` 不但注入 SOUL、memory 和工作目录 AGENTS.md，还启用了 29 个工具（含 terminal、write_file、execute_code、send_message）并自动批准。项目级隔离调用器经加载器探针验证为 0 工具、无注入。**现有 news-intel 生产正以这种方式调用 Hermes**，需要用户另行决定处理（第 3 节）。
3. 四类题材都取得了可提取正文、可定位摘录、至少两个来源基础（中国古代一篇为同源，已披露）的证据包；挑战页、错 URL、站点回退、可访问但无关四类失败都能被识别（第 4 节）。
4. 去重方案的 13 项验收用例全部通过，含中文二字人名召回（第 5 节）。
5. 四篇样稿由 Hermes 起草、审稿、翻译，再经编辑逐条修改（修改有记录）。模型耗时与编辑介入见第 6 节和 `samples/README.md`。

## 2. ChatGPT 再评审各项的处理

| 编号 | 问题 | 处理 | 位置 | 验证 |
|---|---|---|---|---|
| P1-1 | 固定每周人工批准改变了长期目标 | 改为默认自动准入、异常进入待处理、人工策划可选；准入规则写成清单；记录人工介入时间与原因；模型可提线索，取回与分级由程序完成 | PLAN §1、§4.2；BRIEF“每日新内容”；Opus prompt | 准入规则未实现，留给 Phase 2，验收为两轮四类 dry run |
| P1-2 | 空 cwd 不能证明 Hermes 已隔离 | 推翻 Fable 的结论：源码 + 加载器探针证明 `-z -t "" --ignore-rules` 启用 29 个工具并注入 SOUL/memory/AGENTS；改用项目级隔离调用器，经探针验证；记录版本与 revision；要求升级后重测 | PLAN §2.1–2.2、§6.2；`validation/hermes_*.py` | 第 3 节 |
| P1-3 | 事件粒度与中文召回不足 | 不可变 episode 注册表 + `parent_event` + 规范出处位置 + 别名/繁简/QID 重定向 + 二字切分与 `instr` 召回 + 覆盖全部活动状态 + 并发唯一约束 + 从 Git 重建 | PLAN §4.4；BRIEF | 第 5 节，13/13 通过 |
| P1-4 | “可取回”与“足以支持四类文章”没连起来 | 按文档记录状态阶梯与失败类；四类各建真实证据包；两站镜像不算独立；转载链须注明 | PLAN §2.4、§4.3 | 第 4 节 |
| P1-5 | “两个真实选项”的门槛诱导编造 | 改为有记录的矛盾/约束/行动/后果；动机与“考虑过的选项”只有材料写了才能写；每段标 `kind`；C 篇是无英雄式抉择的制度故事 | BRIEF“叙事骨架”；PLAN §5 规则 6–7 | 四篇逐段标注；审稿捕获并删除了模型写入的人物内心 |
| P2-A | 篇幅应是试稿区间 | 改为以阅读体验为准的试稿区间；页面标注“估算”与口径；样稿实测英/中比例 | PLAN §3 | 双语估算约 11–13 分钟，待读者实测 |
| P2-B | 一次 400 字调用不证明长文吞吐 | 12 次真实调用的耗时与字节表；运行中输出上限、进程组超时；分篇与整批截止 | PLAN §6.3；`samples/model_timings.json` | 第 6 节 |
| P2-C | 部署核验应覆盖正文 | 加 `content_sha256`（双语正文、问题、示例、来源）；首次上线用无头浏览器验证两种语言深链；邮件 90 KB 只是初值，不保证不折叠 | PLAN §8、§9 | 本地预览已用无头 Firefox 渲染并截图 |

Fable 评审文件保留原文作为记录；其中被推翻的结论在 PLAN §13 注明。

## 3. Hermes 隔离（Pi，2026-10-30）

1. **版本**：Hermes Agent v0.14.0（2026.5.16），源码 revision `a6d87153e`，模型 mimo-v2.6-pro，provider xiaomi，无 fallback 链。
2. **源码**：
   - `hermes_cli/oneshot.py` 中，`_normalize_toolsets("")` 返回 None，于是 `use_config_toolsets=True`，启用配置的 CLI 工具集，同时设置 `HERMES_YOLO_MODE=1`。
   - `hermes_cli/main.py` 中，`-z` 在第 13944 行附近分派，而 `HERMES_IGNORE_RULES` 在第 1756 行附近的 chat 路径才设置。
   - `run_oneshot` 构造 `AIAgent` 时没有传 `skip_context_files` / `skip_memory`，两者默认为 False。
3. **加载器探针**（`validation/hermes_probe.py`）：走真实 `hermes` 入口，把 `AIAgent.chat` 替换为输出摘要，因此不调用模型；只打印工具名与布尔值。工作目录放入 canary AGENTS.md。

   | 方式 | 工具 | canary | SOUL | memory |
   |---|---|---|---|---|
   | news-intel 方式 | 29 个，含 terminal、write_file、patch、execute_code、send_message、browser_*、delegate_task，YOLO=1 | 注入 | 注入 | 注入 |
   | 隔离调用器 | 0 | 无 | 无 | 无 |

4. **错误行为**：`hermes -z` 用不存在的模型名时，退出码 0、stdout 为空、stderr 为空。
5. **隔离调用器**（`validation/hermes_isolated.py` + `run_hermes.py`）：
   - 调用前断言 0 工具，否则退出码 5；空输出退出码 3；
   - prompt 走 stdin；工作目录必须为空；
   - 进程组超时；运行中输出上限；
   - 实测 13 次调用全部成功（1 次冒烟 + 12 次样稿），调用前后 `~/.hermes` 文件无变化。
6. **对现有生产的影响**：Pi 上 news-intel 的 `LLM_PROVIDER=hermes_cli`，正按上表第一行的方式把外部新闻文本送进带工具、自动批准的 agent。本轮按范围没有改动 news-intel、gateway 或全局配置。建议用户另行决定是否让 news-intel 改用同类隔离调用。
7. **未验证**：上游是否已修复（未升级生产 Hermes 去测）；MiMo 速率限制；与 gateway / polymarket cron 并发调用的行为。

## 4. 四类来源证据

- **取回结果**：21 个文档/对照项，其中四类样稿用到的 12 个文档达到 `evidence_usable`（详见 PLAN §2.4 与 `validation/fetch_results.json`）。
- **失败类识别**（每类各有对照）：
  - ctext.org：200 JS 验证页 → `challenge_page`；
  - Founders Online：202 空响应 → `challenge_page`；
  - loc.gov：403；
  - 错误的维基文库标题：404 → `wrong_url`；
  - starhub.vip 的 `/data/history/index.json`：首页回退 → `site_fallback`；
  - 《史记》卷一：真实页面但缺少预期内容 → `extractable` 而非 `evidence_usable`；
  - 《清史稿》卷一百七：可取回但与本事件无关。
- **提取缺陷**：zh.wikisource 原始 wikitext 的 `{{ProperNoun|…}}` 模板被清洗时整体删掉，人名消失，而不含人名的标记仍然命中。已改用渲染文本，并把人名加入必现标记。这类缺陷正是“可取回 ≠ 可作证据”的例子。
- **四类证据包**：57 条摘录，全部由起止锚点从缓存文本机械截取，记录偏移与来源 SHA-256。

  | 类别 | 来源基础 |
  |---|---|
  | 中国古代 | 《史记》两篇 + 《汉书》（同源，已披露） |
  | 世界史 | Snow 1855 + 教区调查委员会 1855（含 Whitehead） |
  | 中国近现代 | 容闳 1909 + 《清史纪事本末》1914 + 《游美同学录》1917；美国教育者抗议信只见于容闳书中转载，已注明转载链 |
  | 美国史 | 在场者 Shaw 1783 年 4 月的信 + 《大陆会议日志》第 24 卷 + 维基文库讲话文本 |

- **审稿揭示证据包缺口**：多处模型写对、但摘录截得太短，例如：
  - 陈平“臣躶身來”的回答；
  - 啤酒厂的深井；
  - Whitehead 的委员会身份；
  - 华盛顿事先写好讲稿；
  - 议员来信。

  处理方式是扩充摘录，而不是删掉正确内容。
- **一处我方错误已更正**：Shaw 信件的收信人。原 locator 写作“致 Eliot 牧师”，实际原文未写明，已更正。

## 5. 去重验证（`validation/dedup_check.py`，Pi 上 SQLite 3.40.1）

13/13 通过（`validation/dedup_check.out.txt`）：

- 判为重复：改标题、英文版、繁体、只用别名（亚父/项王/汉王）且换类别、缺 QID 但出处相同、QID 重定向、与“已准备”未发布稿重复；
- 正确区分：同一远征下的不同片段、同人同年同地的不同决定；
- 进入 `review`：同一片段改用另一部作品转述；
- 其他：并发插入被唯一约束拒绝；从导出的 JSON 重建后结论一致；
- 中文召回：“陈平”在 unicode61 与 trigram 中都是 0 命中，二字切分列与 `instr` 都能命中。

测试数据为合成，QID 为假值；规范出处位置必须映射到原作卷/段编号，这是实现时要落实的前提。

## 6. 样稿与真实耗时

见 `samples/README.md`。要点：

- **模型耗时**：12 次调用共 2,203 秒，每篇 447–602 秒，0 次重试，全部一次返回合法 JSON。
- **按证据审稿**：每篇提出 7–16 条意见，多数正确，抓到了时间系错、主语错位、作者推断写成史实、引语强度改变等问题。少数“无证据”判断实为证据包截短。
- **编辑修改**：每篇 10–13 处修改，均有前后与理由记录。审稿没有发现每篇第一条“今天可以怎么用”都与开放问题场景重复，这类问题需要编辑规则或检查来覆盖。
- **篇幅**：英文词数约为中文字数的 0.75–0.9 倍，双语估算约 11–13 分钟，比目标偏长；读者实测前不预先删减。
- **预览**：邮件 HTML 27–29 KB。网页在本地由无头 Firefox 渲染，截图覆盖中/英、桌面/手机、列表、缺稿与站点回退两种错误。
- **工具限制**：本机 Chromium 无头模式无法加载 HTTP 页面，原因未查明，因此改用 Firefox。

## 7. 剩余问题与下一步

1. 两位读者阅读四篇并计时，按 `samples/README.md` 末尾五点反馈。
2. 用户决定 news-intel 的 Hermes 调用是否需要改为隔离方式（不在本项目范围）。
3. 若进入实施：按 Opus prompt 的 Phase 2 实现自动供稿流水线与 dry run。验收为两轮四类、无人工点击，并报告人工介入时间。
4. 仍缺：发信账号、收件人邮箱、发送时间确认、Cloudflare 部署方式。只影响 Phase 3 及以后。
5. 隔离调用器依赖 Hermes 内部 API（`AIAgent` 构造参数），Hermes 升级可能使其失效。实施时应把探针列入 `doctor` 检查。

