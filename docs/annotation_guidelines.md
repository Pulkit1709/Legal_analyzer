# Clause-Level Risk Annotation Guidelines

## 1. Taxonomy
- Labels (multi-label allowed): Financial, Compliance, Liability, Operational, Safe
- Severity (choose one): Low (score < 0.5), Medium (0.5–0.74), High (>= 0.75)
- Definitions:
	- Financial: payment terms, penalties, interest, refunds, fees, pricing, currency.
	- Compliance: laws, regulations, sanctions, privacy, data handling, audit duties.
	- Liability: indemnity, limitation/exclusion of liability, warranties, damages.
	- Operational: SLAs, uptime, support, maintenance windows, performance obligations.
	- Safe: informational clauses with no material risk.

## 2. General Rules
- Annotate the minimal text span that justifies a label.
- Multi-label if a clause clearly pertains to multiple categories.
- If unclear, mark Low severity and add a note explaining ambiguity.
- When severity is unclear, use model confidence heuristics examples below.

## 3. Severity Guidance (with examples)
- High (>= 0.75): strong limitation/indemnity, uncapped liability, punitive penalties.
	- "Vendor shall not be liable for any indirect or consequential damages."
	- "Customer agrees to indemnify and hold harmless for all claims without cap."
- Medium (0.5–0.74): moderate penalties, capped liability, narrow indemnities.
	- "Late payments incur 5% monthly interest."
	- "Liability limited to fees paid in the last 12 months."
- Low (< 0.5): soft obligations, standard compliance statements, recoverable timelines.
	- "Parties shall comply with applicable laws and regulations."
	- "Provider will use commercially reasonable efforts to maintain uptime."

## 4. Positive/Negative Examples (abbrev.)
- Financial (positive): interest, penalties, late fees, non-refundable, price escalator.
- Financial (negative): billing address, invoice references without amounts.
- Compliance (positive): GDPR/HIPAA, data processing, audit rights, sanctions.
- Compliance (negative): generic confidentiality without legal refs.
- Liability (positive): indemnify/hold harmless, limitation/exclusion of liability.
- Liability (negative): general best-effort statements.
- Operational (positive): uptime %, response times, maintenance, support tiers.
- Operational (negative): marketing language without measurable commitments.
- Safe: definitions, recitals, headings.

Provide at least 20 positive and 20 negative examples per label during ramp-up. Curate edge cases and store as reference.

## 5. Mixed Clauses
- If a clause contains multiple risk elements, assign multiple labels.
- Choose severity as the highest-risk component present.

## 6. Boundary Cases
- If OCR is noisy, prefer broader span but include key tokens.
- For cross-references ("subject to Section 9"), annotate only the risk-bearing span.

## 7. Procedure
- Two annotators per document. Use the Notes field to capture rationale.
- An adjudicator resolves disagreements.
- Target Cohen’s kappa ≥ 0.7 before model training.

## 8. Output Fields
- clause_id, text (selected span), labels[], severity, notes, annotator_id, timestamp.

## 9. Examples (short)
- Liability/High: "shall not be liable for any damages"
- Compliance/Medium: "comply with GDPR and permit audits"
- Financial/Medium: "late fee of 5% per month"
- Operational/Low: "use commercially reasonable efforts for 99% uptime"
- Safe: "Definitions: 'Agreement' means..."
