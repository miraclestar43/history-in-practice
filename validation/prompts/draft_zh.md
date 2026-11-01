任务：根据【编辑简报】与【证据包】，写一篇中文稿，输出一个 JSON 对象，不要输出其他任何文字或 markdown 代码块。

JSON 结构：
{
 "title": "标题（具体矛盾，不夸张）",
 "dek": "一两句引子",
 "sections": [
  {"id":"hook","heading":"小标题","paras":[P,...]},
  {"id":"context","heading":"时间、地点、人物","paras":[P]},
  {"id":"story","heading":"小标题","paras":[P,...]},
  {"id":"analysis","heading":"为什么会这样","paras":[P,...]},
  {"id":"today","heading":"今天可以怎么用","paras":[P,P]},
  {"id":"limits","heading":"别照搬的地方","paras":[P]}
 ],
 "reflection": {"type":"问题类型","scenario":"现代虚构情境","question":"一个有真实权衡、允许不同合理答案的问题","example":{"assumptions":"示例思路的假设","steps":"可执行步骤","alternative":"另一种合理选择及其理由"}},
 "uncertainty_note": "出处与不确定性：哪些细节只有单一来源、哪些有争议",
 "quotes": [{"zh":"正文中加引号的原文","evidence":"证据ID","original":"证据中逐字对应的原文片段"}],
 "background_claims": ["正文中使用、但不在证据包里的背景知识（如年份换算、人物通称），逐条列出以便核实"]
}
P = {"t":"段落文字","kind":"record|interpretation|modern|uncertainty","ev":["证据ID",...]}
- kind=record 的段落必须至少引用一个证据 ID；modern 段落是现代虚构场景，ev 为空。
- “today”恰好两段，各含一个具体现代小场景。
- 正文中凡是加引号的古文/原文，都要在 quotes 里列出，original 必须是证据中的逐字片段。
