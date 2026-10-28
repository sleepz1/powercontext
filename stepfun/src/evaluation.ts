export function qualityMetrics(rankedSources: string[], relevantSources: string[], k = 5) {
  const relevant = new Set(relevantSources);
  // Multiple chunks from the same source must not inflate source-level retrieval quality.
  const ranked = [...new Set(rankedSources)].slice(0, k);
  const hits = ranked.filter(x => relevant.has(x)).length;
  const dcg = ranked.reduce((score, x, i) => score + (relevant.has(x) ? 1 / Math.log2(i + 2) : 0), 0);
  const ideal = Array.from({ length: Math.min(k, relevant.size) }, (_, i) => 1 / Math.log2(i + 2)).reduce((a, b) => a + b, 0);
  return { recall: relevant.size ? hits / relevant.size : 0, ndcg: ideal ? dcg / ideal : 0 };
}
