任务：你是本栏目的具名终审编辑，正在做**来源上下文核查**。证据包里的摘录是从更长的来源里截出来的；截断处之后常常就是事件的结局或关键回应。下面【阅读范围】给出每个来源围绕摘录的完整上下文（短来源是全文；长来源是摘录前后的段落，标有偏移与是否截断）。请通读阅读范围，不要只看摘录。

要做的事：
1. episode：对每个来源，说明这件事在来源里**怎样收尾**（结局、回应、后果），给出阅读范围里的逐字引文；并标明这一结局是否已在证据包摘录里（in_evidence）。
2. additions：凡是阅读范围里有、证据包没有、而写好这件事必须知道的内容（结局、对方的回应、紧接着的转折、会改变读者理解的限定），列为补充摘录：给出来源编号、起始锚点 start 与结束锚点 end（都必须是阅读范围里逐字出现的短片段，start 在前，整段不超过 1500 字），以及理由。不需要补的就给空数组。
3. claims：{稿件模式}对下面【待核断言】里的每一条（以及你在稿件中发现的其他同类断言：凡说“原文/记载/史料/作者/他没有写、未载、没有交代、不详、只记……”，或英文 does not say / no record / unknown 一类），逐条判断：
   - supported：在已读范围内确实没有，并且断言的范围说得准确（scope 写明核查的是哪一篇/哪一章/哪几段）；
   - contradicted：阅读范围里其实有答案——必须给出逐字引文 quote；
   - unnecessary：断言对读者没有必要（删掉不影响理解），应删除；
   - unresolved：需要的上下文不在阅读范围内（被截断、来源过长或缺失），不能下结论；
   - needs_search：仅当来源是“窗口”模式且必须查看其他部分才能判断时使用，同时在 search 里给出最多 6 个检索词（逐字出现在原文里的词，如人名、地名、关键词）；
   - not_a_source_claim：这句话不是关于来源记载与否的断言（例如叙述人物“没有说话”）。
   不要用“摘录没有写”来替代：如果来源其实有答案，就是 contradicted。
4. context_issues：稿件里因为截断而**误导**读者的正面叙述（例如把中途写成结局、漏掉紧接着的回应、因果方向被截断改变），每条给出字段路径、问题、阅读范围里的逐字引文，severity 为 fix（必须改）或 note。

只输出一个 JSON 对象，不要其他文字：
{"episode":[{"source_id":"来源编号","outcome":"一句话","quote":"逐字引文","in_evidence":true}],
 "additions":[{"source_id":"来源编号","start":"起始锚点","end":"结束锚点","why":"理由"}],
 "claims":[{"id":"A1 或 N1（新发现的）","path":"字段路径（不带 .zh/.en）","lang":"zh|en","sentence":"原句","verdict":"supported|contradicted|unnecessary|unresolved|needs_search|not_a_source_claim","source_ids":["来源编号"],"scope":"核查范围","quote":{"source_id":"来源编号","quote":"逐字引文"},"fix":"建议怎么改"}],
 "context_issues":[{"path":"字段路径","problem":"问题","quote":{"source_id":"来源编号","quote":"逐字引文"},"severity":"fix|note"}],
 "search":["检索词"],
 "overall":"一句话结论"}

引文 quote 必须逐字来自【阅读范围】（繁简与空白差异可以忽略）；不确定时宁可 unresolved，也不要猜。
