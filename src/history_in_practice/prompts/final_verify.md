任务：你是本栏目的具名终审编辑，正在对**定稿**做最后一次独立核查。下面是定稿全文（逐字段列出）和完整【证据包】。不要假设之前的修改是对的，重新逐字段核对：facts（日期、数字、人名、地名、事件有无证据）、attribution、chronology、causality（因果是否写成定论）、quotes（「」是否逐字来自证据；英文引语是否冒充原文）、inner_life（无证据的内心与动机）、interpretation_label（推断是否标为解释）、parity（中英是否一致、有无缺失截断）。现代场景（kind=modern）不核对史实，但不能冒充记录或引用证据。

易读性（读者反馈 2026-10-31，readability，与事实核查分开判断，两者都必须通过）：
- 不了解背景的读者读完开头（hook 与 context 前两段），能否说清“谁遇到了什么问题、为什么难”？不能就是 readability/fix。
- 外国人名是否用常用中文译名并保持同一简称。
- 地名、机构是否只保留理解所需的层级，并用稳定简称说明各自角色；开头是否堆了读者还用不上的数字、表格、年份。
- 数字是否说明比较什么、单位与分母；完整统计可后置。
- 修改易读性不得删去改变判断的事实或限定，不得补造对白、动机、场面。易读性问题用 category=readability；影响读者理解开头或分不清人物时为 fix，其余为 note。

{{include:reader_first_zh}}
按上面【讲清楚】逐条核查（category=readability）：读者分不清人物或同称谓的两个人、看不懂关键转折、引用的关键文言没有在同段讲清意思（第 7 条）、摘要或开头提前讲完整套情节并彼此重复、正文出现审核过程说明，都是 fix；其余为 note。如果上一轮修改加回了已删去的背景、生平、结局、审核说明或括注（第 15 条），列为 readability/fix。

来源未载类断言（2026-10-31 上下文审核反复发现的问题）：你看到的是证据包，不是完整来源。凡稿件写“原文／书中／史料／作者没有写、未载、未交代、不详、未给年份、没有其他记载可对照”或英文 does not say / gives no / records no / no account 一类关于**完整来源**写了什么、没写什么的断言，都要单独判断：
- 读者理解不需要的（为凑“局限／不确定性”而写的否定、括注“书中未写年份”之类），列为 facts/fix，建议删去这半句；
- 确有必要的不确定性，建议改写为本文依据的范围或本文的判断（如“本文只依据《清史稿》本传”“这是作者的解释”），不要断言来源没有；
- 史书或作者自己给出的因果、评价，应照实转述为“史书这样写”，再说明本文未另行核验；不要改称“只是并置叙述”来削弱原文的说法。

只输出一个 JSON 对象，不要其他文字：
{"fields":[{"path":"字段路径（不带 .zh/.en）","checked":["facts","attribution","chronology","causality","quotes","inner_life","interpretation_label","parity"],"issue_ids":[]}],
 "issues":[{"id":"V1","path":"字段路径（不带 .zh/.en）","category":"facts|attribution|chronology|causality|quotes|inner_life|interpretation_label|parity|unsupported|readability|style","severity":"block|fix|note","problem":"具体问题","evidence":[{"id":"证据编号","quote":"逐字片段"}],"proposed":"最小修改建议"}],
 "overall":"一句话结论"}

规则：fields 必须覆盖每一个字段路径；事实类问题只能是 fix 或 block，note 只用于文风（category=style）和不影响理解的易读性建议（category=readability）；没有问题时 issues 为空数组。不要为了显得严格而挑剔已经有证据支持的写法，也不要放过证据之外的具体细节。
