Task: you check that the English edition says the same thing as the Chinese edition. Below, each line is one field: its path, then the Chinese text and the English text. Compare them field by field and output ONE JSON object only:

{"issues":[{"path":"field path","severity":"fix|note","problem":"what differs","suggestion":"minimal change"}],
 "overall":"one sentence"}

Rate as "fix" only real differences of content: a fact, date, number, name, quotation, attribution, cause, hedge or uncertainty that appears in one language but not the other, or that differs between them; English text that is missing or truncated; Chinese text that contains whole English sentences instead of Chinese. Differences of style, rhythm or idiom are fine and must not be reported as "fix". Also rate as "fix": English whose referent is unclear where the Chinese is clear (he / the ruler / the princess could mean two different people), or two people who share a title in the Chinese but are no longer distinguishable in the English. Do not judge historical accuracy here; only whether the two languages match.
