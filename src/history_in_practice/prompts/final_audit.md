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

只输出一个 JSON 对象，不要其他文字：
{"fields":[{"path":"字段路径（不带 .zh/.en）","checked":["facts","attribution","chronology","causality","quotes","inner_life","interpretation_label","parity"],"issue_ids":["F1"]}],
 "issues":[{"id":"F1","path":"字段路径（不带 .zh/.en）","category":"facts|attribution|chronology|causality|quotes|inner_life|interpretation_label|parity|unsupported|style","severity":"block|fix|note","problem":"具体问题","evidence":[{"id":"证据编号","quote":"证据原文中逐字出现的片段"}],"proposed":"最小修改建议"}],
 "inherited":[{"id":"遗留问题编号","verdict":"valid|invalid|duplicate","same_as":"F编号或空","rationale":"理由","evidence":[{"id":"证据编号","quote":"逐字片段"}]}]}

规则：
1. fields 必须覆盖下面列出的每一个字段路径，一个不漏；checked 写你实际检查过的方面。
2. 事实类问题（除 style 外的所有类别）只能是 fix 或 block，不能降为 note。note 只用于纯文风建议（category=style）。
3. evidence.quote 必须是证据包里逐字出现的片段（可以短，但要逐字）；说明“证据里没有”时 evidence 留空数组即可。
4. 不要评价文笔好坏，除非影响事实理解；不要提出加入证据包以外内容的建议。
