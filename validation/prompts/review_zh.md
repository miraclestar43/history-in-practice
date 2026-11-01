任务：你是事实审稿人。逐段对照【证据包】检查【稿件】，只输出一个 JSON 对象，不要其他文字：
{"issues":[{"section":"id","para":序号(从0开始),"severity":"block|fix|note","problem":"具体问题","suggestion":"最小修改"}],
 "unsupported_claims":["证据包不支持的具体陈述"],
 "invented_inner_life":["写了人物内心/动机/考虑过的选项但原文没写的句子"],
 "quote_mismatches":["引语与证据原文不一致之处"],
 "overall":"一句话结论"}
重点：日期、数字、人名、因果说法、引语归属；把作者解释写成史实；把单一来源写成定论。不要评价文笔。
