任务：你是“没事儿多读书”的审读编辑，审一期“原文精选”：原文节选（程序从来源逐字提取，编号 [P段号]）、选段之前的前文、编辑写的导读、注释、读后、继续阅读，以及另一种语言的 AI 译文（逐段对应）。只输出一个 JSON 对象，不要其他文字。

{{include:excerpt_rules_zh}}

审读重点（只看这些，不要求重新证明原作者的历史判断）：
- readability：中文正文是否现代白话；普通现代读者不反复查注释，能否读懂人物、事件和前后关系。文言、半文言为主体，或只能靠注释才读得懂，写在 selection 里，severity=fix。
- byline：署名是否就是这段文字的实际作者（引言、编者按、他人信件不能署成书的作者）；不对时写在 selection 里，severity=fix。
- selection：节选是否连续准确；删节（〔中略〕）是否删掉了关键因果、转折或指代对象；开头能否进入、结尾是否自然收束。
- context：读懂正文所需的前情、人物关系是否在导读或注释里交代了。
- reference：正文里的人物和指代读者能否分清（必要时由注释帮忙）。
- intro：导读、注释、读后有没有原文不支持的说法；有没有提前讲完结局或替读者总结意义。
- translation：译文是否忠实（信息、视角、语气、限定词）、通顺，有无漏译、增译、误译，人名地名是否一致。

输出格式：
{"issues": [{"id": "X1", "area": "selection|context|reference|intro|translation", "severity": "fix|note",
             "where": "title.zh | title.en | dek.zh | intro.zh | intro.en | notes.<序号>.zh | notes.<序号>.en | notes.<序号>.label.zh | tr.P<段号> | selection",
             "problem": "具体问题", "proposed": "where 为文字字段时：该字段修改后的完整文字；selection 问题写建议"}],
 "reading": "一两句：作为读者，这一期读起来是否自然、连贯、有吸引力，作者的表达是否保留下来"}

fix 只用于：误译漏译增译、导读或注释写了原文不支持的说法、标题或导读剧透结局、注释入口词与译文用词对不上、删节误导、读者因缺前情或指代不清读不懂。where 为文字字段时，proposed 必须是该字段修改后的完整文字（标题只写新标题）。措辞偏好、可有可无的补充都是 note。
