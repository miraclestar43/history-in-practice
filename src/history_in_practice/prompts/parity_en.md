Task: you check that the English edition says the same thing as the Chinese edition. Below, each line is one field: its path, then the Chinese text and the English text. Compare them field by field and output ONE JSON object only:

{"issues":[{"path":"field path","severity":"fix|note","problem":"what differs","suggestion":"minimal change"}],
 "overall":"one sentence"}

Rate as "fix" only real differences of content: a fact, date, number, name, quotation, attribution, cause, hedge or uncertainty that appears in one language but not the other, or that differs between them; English text that is missing or truncated; Chinese text that contains whole English sentences instead of Chinese. Differences of style, rhythm or idiom are fine and must not be reported as "fix". Do not judge historical accuracy here; only whether the two languages match.
