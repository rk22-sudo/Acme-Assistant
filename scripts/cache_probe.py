from app.embeddings import embed_texts

PARAPHRASES = [
    ("How many annual leave days are available?", "What is the annual leave allowance?"),
    ("How do I request time off?", "What steps do I follow to request leave?"),
    ("When should I report harassment?", "How soon must witnessed harassment be reported?"),
    ("How do I work remotely?", "What is the process for working remotely?"),
    ("What is the parental leave policy?", "Tell me about the company's parental leave rules."),
    ("How can I get an ergonomic assessment?", "What should I do to request an ergonomic evaluation?"),
]

DIFFERENT = [
    ("How many annual leave days are available?", "How do I request annual leave?"),
    ("When should I report harassment?", "Who investigates a harassment report?"),
    ("What is the remote work policy?", "How do I expense home office equipment?"),
    ("How long is parental leave?", "How do I notify the company of a new child?"),
    ("What is the sick leave policy?", "How do I request a workplace accommodation?"),
    ("How do I get health insurance?", "When does health insurance coverage begin?"),
]

PERSONAL_VS_POLICY = [
    ("How many leave days do I have left?", "What is the annual leave policy?"),
    ("What is my remaining sick leave balance?", "How does sick leave work?"),
    ("How many personal days remain in my balance?", "What is the personal leave policy?"),
    ("How many annual leave days are available to me?", "How many annual leave days do employees receive?"),
]


def report_group(name, pairs):
    prompts = [prompt for pair in pairs for prompt in pair]
    vectors = embed_texts(prompts, "RETRIEVAL_QUERY")
    scores = []
    print(name)
    for index, pair in enumerate(pairs):
        score = float((vectors[index * 2] * vectors[index * 2 + 1]).sum())
        scores.append(score)
        print(f"  {pair[0]!r} <> {pair[1]!r}: {score:.6f}")
    print(f"  min={min(scores):.6f} max={max(scores):.6f}")
    return scores


def main():
    paraphrases = report_group("PARAPHRASES", PARAPHRASES)
    different = report_group("DIFFERENT", DIFFERENT)
    personal_vs_policy = report_group("PERSONAL_VS_POLICY", PERSONAL_VS_POLICY)
    print(
        "highest DIFFERENT and PERSONAL_VS_POLICY vs lowest PARAPHRASES: "
        f"{max(max(different), max(personal_vs_policy)):.6f} vs {min(paraphrases):.6f}"
    )


if __name__ == "__main__":
    main()
