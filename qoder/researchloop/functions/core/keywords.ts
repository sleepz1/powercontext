const SPLIT = /[\s,，。.;；、！!？?：:"'“”（）()\[\]【】<>《》\-—/]+/;
const CJK = /[\u3400-\u4dbf\u4e00-\u9fff]/;
const STOP_WORDS = new Set(['怎样', '如何', '为什么', '可以', '需要', '什么', '咱们', '我们', '进行', '相关', '一下']);
const MAX_KEYWORDS = 8;

export function keywords(query: string): string[] {
  const segments = query.split(SPLIT).map(part => part.trim()).filter(Boolean);
  const collected: string[] = [];
  const push = (term: string) => {
    if (term.length < 2 && !CJK.test(term)) return;
    if (STOP_WORDS.has(term)) return;
    if (!collected.includes(term)) collected.push(term);
  };

  for (const segment of segments) {
    if (!CJK.test(segment)) {
      push(segment.toLowerCase());
      continue;
    }
    // Chinese has no spaces: feed the database a sliding bigram window it can match
    // against the ngram(2) fulltext index, and keep the whole phrase for ranking.
    if (segment.length <= 3) push(segment);
    else {
      push(segment.slice(0, 4));
      for (let index = 0; index + 2 <= segment.length && collected.length < MAX_KEYWORDS; index += 1) {
        push(segment.slice(index, index + 2));
      }
    }
  }
  return collected.slice(0, MAX_KEYWORDS);
}
