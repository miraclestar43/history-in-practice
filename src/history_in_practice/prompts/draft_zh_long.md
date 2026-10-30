任务：根据【编辑简报】与【证据包】写一篇中文读者约十分钟读完的完整文章，只输出一个 JSON 对象，不要输出其他文字或 markdown 代码块。

要求：
- 篇幅：正文加开放问题与示例，中文约 2,900–3,400 字。这是参考，不是硬指标；宁可略短，也不要凑字数、重复或空话。
- 内容只能来自【证据包】和【编辑简报】中有记录的背景、过程与解释；可以组织段落、写过渡与解释，但不得引入证据之外的事实。
- 结构为（hook / context / story / analysis / today / limits 六节，reflection，uncertainty_note，quotes，background_claims）。story 节可以有 4–9 段；today 仍恰好两段，且两个场景都不能和开放问题的场景重复。
- 每段标 kind：record（有记录的叙事，必须引用证据 ID）、interpretation（作者解释，要用“一种解释是”“作者推断”等标明）、modern（现代虚构场景，ev 为空）、uncertainty（不确定性说明）。
- 人物动机、想法和“考虑过的选项”只有原文写了才能写；作者提出的替代选择只放在 analysis、limits 或开放问题里，并注明是作者提出的。
- 古文或原文引语用「」，必须是证据中的逐字片段，并在 quotes 中列出。
- 不编造对话、场景画面、数字或人物；不得使用证据包以外的引语。

JSON 结构：
{"title","dek","sections":[{"id","heading","paras":[{"t","kind","ev":[]}]}],
 "reflection":{"type","scenario","question","example":{"assumptions","steps","alternative"}},
 "uncertainty_note","quotes":[{"zh","evidence","original"}],"background_claims":[]}
