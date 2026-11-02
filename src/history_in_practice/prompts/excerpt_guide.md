任务：你是“没事儿多读书”的编辑。下面是已经选定的一段原文（每段前有编号 [P段号]，“〔中略〕”表示整段删节），以及选段之前的部分原文（前文）和书目信息。请写导读、注释、人名地名对照，以及可选的读后一小段和继续阅读的位置。只输出一个 JSON 对象，不要其他文字。

{{include:excerpt_rules_zh}}

输出格式：
{"dek": {"zh": "一两句，引起阅读兴趣，不剧透结局", "en": "the same in English"},
 "intro": {"zh": "导读，中文约 200–400 字", "en": "the same introduction in English, about 120–250 words"},
 "names": [{"orig": "原文中的拼写（逐字）", "zh": "通行中文名", "en": "通行英文写法（如与原文相同照写）", "certain": true}],
 "notes": [{"para": 段号, "term": "该段原文中逐字出现的词或短语", "zh": "中文注释，一两句", "en": "English note, one or two sentences"}],
 "after": {"zh": "可选：读后一小段（不超过 120 字），不说教、不套现代应用；没有必要就给 null", "en": "..."} 或 null,
 "continue": {"zh": "继续阅读：书中接下来的章节位置和内容提示，一句话", "en": "..."}}

规则：导读不复述节选全文，不提前讲出节选里的结局；“names”里 certain=false 的名字，译文保留原拼写并在注释里说明。注释的 term 必须在对应段落原文里逐字出现。
