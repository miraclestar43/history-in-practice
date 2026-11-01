任务：根据【编辑简报】与【证据包】写一篇中文读者约十分钟读完的完整文章，只输出一个 JSON 对象，不要输出其他文字或 markdown 代码块。

要求：
- 篇幅：正文加开放问题与示例，中文约 2,900–3,400 字。这是参考，不是硬指标；宁可略短，也不要凑字数、重复或空话。
- 内容只能来自【证据包】和【编辑简报】中有记录的背景、过程与解释；可以组织段落、写过渡与解释，但不得引入证据之外的事实。
- 结构为 hook / context / story / analysis / limits 五节，加 reflection、uncertainty_note、quotes、background_claims。story 节可以有 4–9 段。today 一节默认不写（见上文“讲清楚”第 13 条）：全文唯一的现代场景放在 reflection.scenario 里；确需 today 时放在 analysis 与 limits 之间，只写一段，不另设新场景。
- dek（摘要）一两句，提出处境或问题，不交代结局、不罗列人物；hook 展开具体处境，不重复 dek 的情节。
- 每段标 kind：record（有记录的叙事，必须引用证据 ID）、interpretation（解释或评价，用自然的句子让读者看得出是谁的看法，例如“孔飞力认为”“一种可能是”；同一篇不要反复写“作者推断”）、modern（现代虚构场景，ev 为空）、uncertainty（不确定性说明）。
- 人物动机、想法、对白和“考虑过的选项”只有材料写了才能写，并让读者知道是哪本书这样讲；材料是通俗历史、回忆录、小说或寓言时，在正文里自然说明一次（如“据《明朝那些事儿》的讲述”）。作者提出的替代选择只放在 analysis 或开放问题里。
- 写作时逐条执行上文【讲清楚】的要求，尤其是讲清谁是谁、各自想要什么、为什么这样选、结果如何，同称谓人物的区分，以及重要文言在叙述中讲清意思。
- 古文或原文引语用「」，必须是证据中的逐字片段，并在 quotes 中列出。
- 不编造对话、场景画面、数字或人物；不得使用证据包以外的引语。

JSON 结构：
{"title","dek","sections":[{"id","heading","paras":[{"t","kind","ev":[]}]}],
 "reflection":{"type","scenario","question","example":{"assumptions","steps","alternative"}},
 "uncertainty_note","quotes":[{"zh","evidence","original"}],"background_claims":[]}
