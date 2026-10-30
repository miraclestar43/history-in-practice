# ChatGPT：overnight 交付复核与上线缺口

日期：2026-10-30（America/Los_Angeles）。评审快照：PR #1，`f7e14e4919f340224d29081729625a98bd0a51b8`。

本轮读取实际报告及相关代码，使用原函数的 AST 提取执行做 SQLite/无网络最小复现。未连接 Pi、未独立复跑全部 46 测试、未调用真实 SMTP、未部署或启用任务。下列报告中的模型结果是已有交付记录，不冒充本轮复测。

## 结论

已有长篇样稿、证据包、隔离调用器、发布与邮件骨架，值得进入稳定化和人工阅读验证。**当前仍不能只配置账户后直接启用两个 timer，就视为长期每日供稿已闭环。** 需要补上持续候选供给与编辑、部署延迟重试、正确库存覆盖和发送前校验。

不必为了凑中文 2,800 字给八分钟样稿注水；先真实阅读一篇。英文 A 十三分钟可自然收紧。较大的证据包有助于支撑内容，但摘录数量本身不是充分证据或质量指标。

## P1-1 网站异步部署会令当天邮件一直等待，次日不会自动恢复昨天

位置：`src/history_in_practice/publish.py:43–55,105–127`，`site_export.py:verify`，`cli.py:151–154`，`deploy/systemd/hip-send.service` 与 timer。

`commit_site` push 后立即检查线上 JSON；Cloudflare 尚在构建时会得到旧内容并返回 `waiting`。CLI 将 waiting 当作 exit 0，service 虽有 45 分钟 timeout，却没有轮询/重试；timeout 不会使已结束的进程继续等。日定时器当天不会再调一次。

次日 `schedule(date)` 只找当天的 in-flight edition，昨天的 `site_committed` 不被恢复，而是选择下一类别的新稿。可能持续积累没有发出的旧期次。现有 publish 测试只证明相同日期重跑，不证明跨日恢复；其中一个测试甚至允许前日 email_pending 时次日排新稿。

**本轮复现**：调用原 schedule 函数，第一天 ancient 稿置为 site_committed，第二天调度 world 新稿，第一天仍留在 site_committed。

**修复与验收**：

- 在约定投递窗口内做有限退避重试或独立的短周期 resume 任务，配置截止时间；waiting 必须有已安排的后续动作或告警，不能静默成功。
- 日期切换时明确处理旧任务：恢复、转为逾期并告警或按明示规则跳过，不能永久遗留；不批量补发陈旧邮件。
- 测试 push 后连续几次返回旧版本、随后正确版本；同一天完成发送且不重复；测试跨日未完成状态和两位收件人部分成功。
- SITE_PUSH_ENABLED 从 false 改 true 的恢复也需覆盖：当前一旦记录 site_committed，后续只 verify，不会补做先前未执行的 push。

## P1-2 “12 days”实际是 12 篇，严格轮换只能连续排 10 天

位置：`src/history_in_practice/pipeline.py:241–247`，`publish.py:37–55`，OVERNIGHT_REPORT §1/§8。

inventory 将 checked/scheduled 数量相加并命名 days。按报告的 ancient=3、world=4、modern=2、US=3，从当前默认 A→W→M→U 起点只能排 10 天：第 11 天需要第 3 篇 modern，已经缺稿。

本轮用原 inventory 函数和实际配置复现：返回 days=12、alert=false、missing_categories=[]，但按轮换计算 coverage=10。缺的不是简单的两篇；若想达到连续 14 天，按此起点需 A4/W4/M3/U3，至少补一篇 ancient 和一篇 modern，并确认所有样稿已被正式批准使用。

**修复与验收**：分开显示总篇数、可排篇数、样稿数、按下一类别起点的连续覆盖天数、逐类缺口。低库存告警按连续覆盖算，候选和 pending 不算。samples 只有经过明确编辑审核/准入才计可排库存。测试多种轮换起点及已排期稿，不能重复计未来日期。

## P1-3 当前 timer 没有持续产生新候选或完成编辑

位置：`cli.py:133–148`，`pipeline.py:33–38,223–236`，`deploy/systemd/hip-prepare.service`，`validation/editor_pass.py`。

prepare-queue 只遍历已有的 config/candidates/*.json；只要 edition 已有记录便跳过。八个候选都处理完后，定时器不会自动产生新题目、材料锚点或简报。七份模型稿全部待审，实际靠本次 Claude 编写 edits 文件并调用 editor_pass/admit 才入库。它是有效的编辑结果，但该编辑步骤尚未接进日常任务。

**最小后续实现**：

- 候选库存与合格成稿库存分开；补充候选、检索/取回、证据与简报的生成机制，记录来源基础、类别、去重与拒绝原因。不能只把启动时八个 JSON 当作长期供给。
- 把独立的编辑任务产品化：依据原始证据处理模型 review，记录 before/after/reason，并重查两语言和来源。可以使用 Pi Claude 或另一个经实际评估的编辑模型；不意味着用户每天必须亲自修稿。
- 限制编辑循环；无法解决的事实问题保持 pending，用其他合格稿。不要降低 fix/block 门槛来提高“通过率”。
- 用至少两篇新候选验证完整链路，不能手写最终正文或 edits 后宣称自动闭环。报告真实编辑耗时、成本与成功率。provider 拒绝保持明示，不能靠旧手写样稿掩盖该类自动供应缺口。

## P1-4 零收件人可被当成全部发信成功

位置：`mailer.py:104–132`，`cli.py:129–130`，`publish.py:124–127`。

send_edition 未拒绝空 recipients，返回 []；上层 `all(...)` 对空列表为 true，会返回成功，publish 还可标 complete。

**本轮无网络复现**：原 send_edition，在发送已开启而 recipients=[] 时返回 []，completion predicate=true，没有任何网络调用。

**修复与验收**：真实发送前验证收件人非空、地址格式与显式配置的目标集合、发信配置完整。complete 必须覆盖本期冻结的预期收件人集合，而非仅检查本次返回的列表；测试空配置、部分配置及发送中配置变化，不得假成功。

## P2：编辑准入应绑定最终内容与问题处理记录

位置：`cli.py:157–179`，`validation/editor_pass.py:20–31`。

admit 只检查 checker BLOCK，不要求最终稿对应的 editor/review 记录，也不要求解释尚存 FIX 或原模型 review 的 fix/block。editor_pass 会写 checked 并打印问题，即使仍有 FIX/BLOCK 也写出文件。手动准入可以作为可信编辑的覆核，但不能仅凭调用命令就声称“记录完备且已审核”。

建议记录 final content_sha256、evidence hash、review revision、逐项解决或有理由驳回，并在 admit 核对；剩余 FIX 默认不进入可排库存，需要有明确理由的人工例外。编辑任意改正文后，旧审核记录自动失效。测试未经修改的 pending 稿不得只改 status 就成为已编辑稿。

## P2：首封测试步骤目前自相矛盾

报告要求 EMAIL_SEND_ENABLED=false 直到手动测试，但 `hip send ... --real` 不绕过此开关，mailer 会拒发。步骤应明确：保持 timers 禁用，在私密配置临时开启并执行一次手动测试，测试后关闭；或实现显式的一次性真实测试入口。不能让用户照当前步骤以为已发出去。

From 没有收件箱，而邮件模板要求直接回复以反馈/暂停，因此使用这种 From 时 Reply-To 应配置为可接收地址，或将页脚改为实际可用的反馈方式，不宜一律称其可选。

## 建议执行次序

1. 用户可并行注册 Resend、验证 read.starhub.vip，并私下存 key；不启用定时器。
2. Claude 修复上述发布恢复、库存和发信校验，完成对应回归；把编辑/候选补充接成可运行任务。
3. 用户先读样稿 D 或 B 的中文与英文，反馈节奏、趣味和应用；它们可先用于邮件测试。
4. 确认现有 Cloudflare 自动部署方式，完成网站集成；验证正式网页与两个语言深链。
5. 手动测试到 Gmail/QQ，确认排版、收件与回复路径；再验证一次完整的选稿→发布→等待部署→两位发信流程。
6. 以上通过后，再启用生产排期。不要以“46 个现有测试通过”替代尚未覆盖的这些行为。

本轮只提交评审文件，不合并、不部署、不发信、不变更 Pi 运行状态。
