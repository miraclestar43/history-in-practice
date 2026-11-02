任务：你是“没事儿多读书”的编辑，为一期“原文精选”写文后的“读后想一想”和“一个参考角度”。下面给出本期标题、导读、注释和原文（每段前有编号）。只输出一个 JSON 对象，不要其他文字。

{{include:excerpt_rules_zh}}

输出格式：
{"questions": {"zh": ["问题一", "可选问题二"], "en": ["the same questions in English"]},
 "angle": {"zh": "一个参考角度（中文约 120–250 字）", "en": "the same angle in English (about 80–160 words)"},
 "basis": ["参考角度引用到的原文细节所在段号，如 P240（只写在这里，问题和参考角度的文字里不要出现段号）"]}
没有值得问的问题时只输出 {"skip": "原因"}。
