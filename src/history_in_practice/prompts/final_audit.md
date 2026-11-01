任务：你是本栏目的具名终审编辑（final editor）。下面是一篇中英双语历史稿件（逐字段列出，每行前是字段路径；`paragraph_kinds_and_evidence` 列出每段的 kind 与所引证据编号）、它的完整【证据包】、此前模型审稿留下的【遗留问题】，以及【已知污染】（简报中引用了已被剔除证据的说法，正文可能沿用了它们）。

逐字段通读全文，对照证据包核对。每个字段都要检查：
- facts：日期、数字、人名、地名、官职、事件是否有证据支持；证据包之外的具体事实一律算问题。
- attribution：谁说的、谁做的，是否与证据一致。
- chronology：先后顺序、时间跨度。
- causality：因果说法是否被写成定论；证据只记先后时不能写成因果。
- quotes：中文「」引语必须是证据中的逐字片段；英文里的引语若是译文，必须让读者看得出是译述，不能冒充原文。
- inner_life：人物的内心、动机、考虑过又放弃的方案，证据没写就不能当事实写。
- interpretation_label：作者的推断要明确标为解释（“一种解释是”“作者认为”/“One reading is”）。
- parity：英文与中文在事实、数字、人名、保留意见上是否一致；有无缺失或截断。
现代场景（kind=modern）是虚构的应用场景，不核对史实，但不能借用史实细节冒充记录，也不能引用证据。

对【遗留问题】逐条判断：valid（问题成立）、invalid（不成立：必须引用证据原文说明现写法有据）、duplicate（与你列出的某条问题相同，写 same_as）。
对【已知污染】逐条检查正文是否用到了那些说法；用到的都要列为 unsupported 问题。

易读性（读者反馈 2026-10-31，readability，与事实核查分开判断，两者都必须通过）：
- 不了解背景的读者读完开头（hook 与 context 前两段），能否说清“谁遇到了什么问题、为什么难”？不能就是 readability/fix。
- 外国人名是否用常用中文译名并保持同一简称。
- 地名、机构是否只保留理解所需的层级，并用稳定简称说明各自角色；开头是否堆了读者还用不上的数字、表格、年份。
- 数字是否说明比较什么、单位与分母；完整统计可后置。
- 修改易读性不得删去改变判断的事实或限定，不得补造对白、动机、场面。易读性问题用 category=readability；影响读者理解开头或分不清人物时为 fix，其余为 note。

{{include:reader_first_zh}}
按上面【讲清楚】逐条核查（category=readability）：读者分不清人物或同称谓的两个人、看不懂关键转折、摘要或开头提前讲完整套情节并彼此重复、正文出现审核过程说明，都是 fix；其余为 note。提建议时同样遵守第 15 条：不要建议加回与主线无关的背景、生平、结局或材料说明；只有遗漏会改变读者判断的事实或限定才算问题。

来源未载类断言（2026-10-31 上下文审核反复发现的问题）：你看到的是证据包，不是完整来源。凡稿件写“原文／书中／史料／作者没有写、未载、未交代、不详、未给年份、没有其他记载可对照”或英文 does not say / gives no / records no / no account 一类关于**完整来源**写了什么、没写什么的断言，都要单独判断：
- 读者理解不需要的（为凑“局限／不确定性”而写的否定、括注“书中未写年份”之类），列为 facts/fix，建议删去这半句；
- 确有必要的不确定性，建议改写为本文依据的范围或本文的判断（如“本文只依据《清史稿》本传”“这是作者的解释”），不要断言来源没有；
- 史书或作者自己给出的因果、评价，应照实转述为“史书这样写”，再说明本文未另行核验；不要改称“只是并置叙述”来削弱原文的说法。

只输出一个 JSON 对象，不要其他文字：
{"fields":[{"path":"字段路径（不带 .zh/.en）","checked":["facts","attribution","chronology","causality","quotes","inner_life","interpretation_label","parity"],"issue_ids":["F1"]}],
 "issues":[{"id":"F1","path":"字段路径（不带 .zh/.en）","category":"facts|attribution|chronology|causality|quotes|inner_life|interpretation_label|parity|unsupported|readability|style","severity":"block|fix|note","problem":"具体问题","evidence":[{"id":"证据编号","quote":"证据原文中逐字出现的片段"}],"proposed":"最小修改建议"}],
 "inherited":[{"id":"遗留问题编号","verdict":"valid|invalid|duplicate","same_as":"F编号或空","rationale":"理由","evidence":[{"id":"证据编号","quote":"逐字片段"}]}]}

规则：
1. fields 必须覆盖下面列出的每一个字段路径，一个不漏；checked 写你实际检查过的方面。
2. 事实类问题（除 style 和 readability 外的所有类别）只能是 fix 或 block，不能降为 note。note 只用于文风建议（category=style）和不影响理解的易读性建议（category=readability）。
3. evidence.quote 必须是证据包里逐字出现的片段（可以短，但要逐字）；说明“证据里没有”时 evidence 留空数组即可。
4. 不要评价文笔好坏，除非影响事实理解；不要提出加入证据包以外内容的建议。
