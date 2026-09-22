# Architecture

## Chosen topology
<pattern name> — because <reason>

## Rejected alternatives
- <pattern>: rejected because <reason>

## Diagram
<mermaid or ASCII: stages, agents, data flow, gates>

## Control boundary
| Decision | Made by | Why | Cost if wrong |

## State model
- Shared state store: <where>
- Per-agent memory: <scope, TTL>
- What is passed vs. what is looked up

## Non-functional targets
- Latency budget per run:
- Cost budget per run:
- Max concurrency:
- Failure mode: <fail closed / fail open / escalate>
