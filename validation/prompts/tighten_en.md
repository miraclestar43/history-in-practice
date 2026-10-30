Task: tighten the English edition of a history article so a reader finishes it in about ten minutes: roughly 1,950–2,150 words in total, counting the sections, the question, the scenario and the example answer. Output ONE JSON object only.

Keep, without exception:
- every fact, name, date, number, place, attribution, hedge ("probably", "the author's inference", "as recorded by ..."), and every limitation or uncertainty;
- every quotation exactly as it is (do not shorten, paraphrase or re-punctuate text inside quotation marks);
- the structure: same section ids, same number and order of paragraphs, same "kind" and "ev" for each paragraph.

Do: cut repetition and padding, merge clauses, prefer plain verbs, remove stock phrases ("it is worth noting", "notably"), and keep it natural, idiomatic English. Do not add anything. The Chinese edition is given only so you can check that nothing of substance is lost.

Return: {"title","dek","sections":[{"id","heading","paras":[{"t","kind","ev"}]}],"reflection":{"type","scenario","question","example":{"assumptions","steps","alternative"}},"uncertainty_note"}
