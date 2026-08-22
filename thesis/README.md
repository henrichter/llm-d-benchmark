# Routing Strategy Evaluation for llm-d / Dynamo EPP

## Research question

For a distributed LLM inference deployment, which endpoint-picker (EPP)
scheduling strategy performs best, and how does that depend on the workload?
Compared across two routing frameworks (llm-d and Dynamo) and a set of
realistic workloads.

## Central claim

Prefix-cache-aware routing does not always win, but its downside when the
workload offers no reuse is negligible, while its upside when reuse exists is
large. Therefore prefix-cache routing should be a default component of any
production scorer pipeline, and the real design question is what to compose
*alongside* it.

## Variables

- **Routing strategy** — the EPP scorer pipeline (random, queue-depth,
  kv-cache-utilization, prefix-cache, latency, token-load, and compositions).
  This is the primary independent variable.
- **Workload** — realistic profiles: batch, agent, chat, RAG. Chosen so each
  exercises the conditions under which a given scorer should shine or fail.
- **Hardware placement** — H200-only, RTX-6000-Pro-only, hybrid. Expressed as a
  node-label selector; a fixed decode config is held constant across placements.
- **Framework** — llm-d vs Dynamo. Bounded by the intersection of scorers each
  framework's EPP image actually implements.

## Held constant

Small-model-equivalent behaviour with a single tensor-parallel group per
replica; the study assumes routing logic is invariant to per-replica scale
(pod = node, replica = node count). vLLM block size and max-model-len are fixed
controls, not variables. Scorer weights in composed pipelines are fixed.

## Iterations

### Iteration 1 — vLLM prefix caching OFF, single scorers

Each scorer alone versus random, with no cache anywhere. Isolates the value of
the routing *logic* itself, uncontaminated by cache effects. Ranks the
load/latency-family scorers. The prefix scorer is expected to be inert here (no
cache to exploit) — a control confirming it does nothing without caching.

### Iteration 2 — vLLM prefix caching ON, random vs prefix vs non-prefix combo

Three arms: random, prefix (single), and a deliberately strong composed pipeline
of the best *non-prefix* scorers. The hypothesis is that even the best
non-prefix combination cannot beat a single prefix scorer where reuse exists,
and only ties it where reuse is absent (e.g. batch). This is the motivating
contrast: it argues that prefix routing should never be omitted, and sets up
iteration 3. The per-workload cut is the point — prefix should dominate on
RAG/agent, tie on batch.

### Iteration 3 — vLLM prefix caching ON, prefix + X

Prefix is the fixed base of every pipeline; each other scorer is layered on top
(prefix, prefix+queue, prefix+kv-util, prefix+latency, ...). Question: given
prefix is handling cache locality, does a secondary scorer recover what
prefix-alone leaves on the table — eviction, ties among prefix-matching
endpoints, contention? An ablation that explains which composition adds value
beyond the cache win.

## Baseline

Random routing (with caching held at the iteration's level) is the universal
reference line on every plot. It absorbs accidental/lucky cache hits, so any
gain a scorer shows above it is attributable to the routing decision, not to
caching existing at all.

## Open verification

Which scorers Dynamo's EPP image implements is unverified and bounds how much of
iterations 1 and 3 include a Dynamo arm. Scorers Dynamo lacks become llm-d-only
results, stated as such.
