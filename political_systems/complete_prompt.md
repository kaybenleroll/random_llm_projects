# Expansion Prompt For Another System

You are an expert comparative-politics writer and technical editor. Your job is to expand and improve one existing document without changing its core style, structure, or intent.

## Primary Goal

Expand the document below with substantive, high-signal content in four priority areas:

1. EU decision flow in practice.
2. Country-level mini case studies.
3. Technical analysis toolkit depth.
4. Forecasting and risk indicators.

Do this while keeping the current part-based hierarchy clean and readable.

## File To Edit

- `/home/mcooney/workspace/random_llm_projects/political_systems/european-electoral-systems-primer.md`

## Non-Negotiable Constraints

1. Keep this as a single-document project. Do not create country-specific files.
2. Preserve existing top-level structure:
   - `# Introduction`
   - `# Part 1: Foundational Concepts`
   - `# Part 2: The 10 Electoral Systems`
   - `# Part 3: Comparative Lenses`
   - `# Part 4: Technical Analysis Tools`
   - `# Conclusion`
3. Do not duplicate content in separate “reference notes” sections.
4. Keep the writing voice practical, clear, and plain-English (analytical but readable).
5. Do not add fluff, generic filler, or excessive theory dumps.
6. Keep all claims careful and non-fabricated. If uncertain, use cautious wording.
7. Maintain markdown readability and heading consistency.
8. Preserve existing math notation style (KaTeX-compatible blocks are fine).

## Expansion Requirements

### 1) EU Decision Flow In Practice

Add a new subsection under Part 1 that walks through one concrete policy-flow example from national election results to EU policy outcome.

Include:

1. National election result changes government composition.
2. Effect on Council configuration (relevant ministry and coalition stance).
3. Interaction with European Parliament party groups.
4. Commission agenda and proposal pathway.
5. Trilogues / compromise dynamics.
6. Final implementation implications back at national level.

Keep it procedural and practical, not legalistic.

### 2) Country Mini Case Studies

In Part 2, add compact case-study callouts for each of the 10 countries already covered. Use one recent election cycle per country as an illustrative example.

Each mini case study should include:

1. Vote share snapshot (high level, no overprecision required).
2. Seat share or coalition-forming result.
3. One sentence on why that translation occurred under the specific electoral rules.
4. One sentence on governing consequence (stability, bargaining, or policy direction).

Format should be concise and scannable (short paragraph or 4-bullet micro-template per country).

### 3) Technical Toolkit Upgrade

In Part 4, add two worked micro-examples:

1. Gallagher index worked example:
   - Use a tiny table of vote vs seat shares for 3-4 parties.
   - Show the substitution into the formula.
   - Provide a plain-language interpretation of the result.
2. District magnitude sensitivity example:
   - Hold vote shares constant.
   - Compare seat allocation outcomes at small vs large district magnitude.
   - Explain why small districts raise effective thresholds.

Keep the math lightweight and decision-relevant.

### 4) Forecasting Layer

Add a short subsection (Part 3 or Part 4, whichever fits best) titled similarly to “Early Warning Indicators For Coalition Stress.”

Include a practical indicator list with interpretation guidance, such as:

1. Fragmentation trend (effective number of parties).
2. Distance between likely coalition partners.
3. Minority-government dependency risk.
4. Regional-party pivot leverage.
5. Seat-vote distortion trend.
6. Intra-coalition policy incompatibilities.

For each indicator, provide:

1. What to watch.
2. Why it matters.
3. What a worsening signal looks like.

## Editorial Quality Bar

1. Merge or tighten repetitive passages where needed.
2. Prefer depth over adding many new headings.
3. Ensure transitions between parts are smooth.
4. Keep TOC usable: avoid heading sprawl.
5. Keep final conclusion short and stronger (synthesis, not repetition).

## Target Length

Increase total word count by about 1000 to 1800 words, with most growth in Parts 2-4.

## Output Requirements

Produce two outputs:

1. Updated markdown content for the target file.
2. A short change summary with:
   - sections expanded,
   - approximate words added,
   - any sections merged/trimmed.

## Self-Check Before Finalizing

Verify all checks pass:

1. Single-file workflow preserved.
2. All four expansion requirements completed.
3. No duplicated country-reference appendix introduced.
4. Heading hierarchy remains clean and part-based.
5. Added examples are concrete and readable.
6. Tone remains practical and concise.

If a trade-off is needed between breadth and clarity, choose clarity.