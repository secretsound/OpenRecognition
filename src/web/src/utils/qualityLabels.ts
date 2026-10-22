const ISSUE_LABELS: Record<string, string> = {
  no_samples: "No samples uploaded for this media type",
  no_embeddings: "No embeddings stored yet",
  too_few_samples: "Add more samples (at least 3 recommended)",
  high_variance: "Samples vary a lot — add more consistent examples",
  recommend_more_voice_samples: "Record more phrases (8+ short sentences works best)",
  recommend_more_samples: "A few more samples will raise this score",
  pet_recommend_more_samples: "Pets match best with 10+ varied photos",
};

export function issueLabel(code: string): string {
  return ISSUE_LABELS[code] ?? code.replaceAll("_", " ");
}
