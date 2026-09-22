# Worked skeleton — research/content crew

An illustration of the method applied, not a prescription.

```
trigger (brief)
  └─ code: validate brief, create run_id, write runs row
  └─ AGENT researcher            [tools: web_search, fetch_page, vector_retrieve]
       → research_result@1
  └─ GATE G1: schema + >=5 sources + URLs resolve        (code)
  └─ code: dedupe claims vs covered_topics (embeddings)  (no model)
  └─ LLM outliner (no tools)     → outline@1
  └─ GATE G2: section count, required sections           (code)
  └─ loop over sections:
       └─ LLM writer (no tools)  → section@1
  └─ LLM editor                  → {pass, issues[]}
  └─ GATE G3: if !pass and attempts<2 → loop to writer   (code counter)
  └─ code: terminology/glossary check against DB table   (no model)
  └─ HUMAN approval (Wait node)
  └─ publish (code-executed intent, not an agent tool)
```

Notes on why it is shaped this way:

- Only **one** true agent (the researcher) — it's the only stage whose next action depends on
  what it just found. Everything else is a fixed chain, which is cheaper and far easier to
  debug.
- Dedupe and terminology compliance are **code**, because they are checkable rules; models
  drift on exactly this kind of constraint.
- The editor produces a **judgment object**, and code decides what to do with it.
- Publishing is never an agent-held tool.
