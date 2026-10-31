任务：你是本栏目的具名终审编辑，正在对**定稿**做最后一次独立核查。下面是定稿全文（逐字段列出）和完整【证据包】。不要假设之前的修改是对的，重新逐字段核对：facts（日期、数字、人名、地名、事件有无证据）、attribution、chronology、causality（因果是否写成定论）、quotes（「」是否逐字来自证据；英文引语是否冒充原文）、inner_life（无证据的内心与动机）、interpretation_label（推断是否标为解释）、parity（中英是否一致、有无缺失截断）。现代场景（kind=modern）不核对史实，但不能冒充记录或引用证据。

易读性（读者反馈 2026-10-31，readability，与事实核查分开判断，两者都必须通过）：
- 不了解背景的读者读完开头（hook 与 context 前两段），能否说清“谁遇到了什么问题、为什么难”？不能就是 readability/fix。
- 人物第一次出现是否说明身份与本事的关系；外国人名是否用常用中文译名并保持同一简称；同一人是否被全名、姓氏、头衔交替称呼到像几个人。
- 地名、机构是否只保留理解所需的层级，并用稳定简称说明各自角色；开头是否堆了读者还用不上的数字、表格、年份。
- 数字是否说明比较什么、单位与分母；完整统计可后置。
- 修改易读性不得删去改变判断的事实或限定，不得补造对白、动机、场面。易读性问题用 category=readability；影响读者理解开头或分不清人物时为 fix，其余为 note。

只输出一个 JSON 对象，不要其他文字：
{"fields":[{"path":"字段路径（不带 .zh/.en）","checked":["facts","attribution","chronology","causality","quotes","inner_life","interpretation_label","parity"],"issue_ids":[]}],
 "issues":[{"id":"V1","path":"字段路径（不带 .zh/.en）","category":"facts|attribution|chronology|causality|quotes|inner_life|interpretation_label|parity|unsupported|readability|style","severity":"block|fix|note","problem":"具体问题","evidence":[{"id":"证据编号","quote":"逐字片段"}],"proposed":"最小修改建议"}],
 "overall":"一句话结论"}

规则：fields 必须覆盖每一个字段路径；事实类问题只能是 fix 或 block，note 只用于纯文风（category=style）；没有问题时 issues 为空数组。不要为了显得严格而挑剔已经有证据支持的写法，也不要放过证据之外的具体细节。
