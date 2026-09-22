# Reading list

**Classical agent-oriented software engineering** — still the best source for role and
interaction modelling:

- **Gaia** — roles model, interactions model; then agent, services and acquaintance models.
- **Prometheus** — system specification → architectural design → detailed design.
- **Tropos** (goal-oriented), **MaSE** (organization-oriented).

**LLM-era practice:**

- Anthropic, *Building Effective Agents* — the pattern catalogue (chaining, routing,
  parallelization, orchestrator-workers, evaluator-optimizer, autonomous agents).
- OpenAI, *A Practical Guide to Building Agents* — single-agent-first, manager vs handoff.
- MetaGPT — encoding human SOPs as agent roles.
- CrewAI docs — role/goal/backstory + tasks + sequential/hierarchical process, useful as a
  design template regardless of implementation.

**Research worth reading before you scale:**

- **SEMAP** — behavioral contracts, structured messaging, lifecycle-guided execution with
  verification, as a protocol layer.
- **MAST** (Multi-Agent System Failure Taxonomy) — use as a pre-mortem checklist.
- **"Know the Ropes"** — decompose a known procedure into stages, each a well-formulated
  task `T = (I, O, R)`.
- Surveys of multi-agent orchestration comparing LangGraph / CrewAI / AutoGen / OpenAI
  Agents SDK / MetaGPT / DSPy on state granularity, token cost, and failure recovery.

## Glossary

| Term | Meaning here |
|---|---|
| **Agent** | a model call loop that can choose tools and iterate |
| **Chain** | fixed sequence of model calls, no choice |
| **Crew** | a set of agents coordinating toward one deliverable |
| **Contract** | the `I/O/R` specification of an agent, in `crews/<crew_name>/02-agents/` |
| **Control boundary** | the line between code-made and model-made decisions |
| **Gate** | a code-enforced check between stages |
| **Envelope** | the typed message wrapper passed between agents |
| **Acquaintance matrix** | who may invoke whom |
| **Blackboard** | shared state store all agents can read/write |
| **Golden set** | curated evaluation dataset with expected outputs |
