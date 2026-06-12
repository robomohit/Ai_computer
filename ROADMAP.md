# Orynn Roadmap — one sentence, one spine

> **Orynn is the best agent harness for free models.**

Every line of code either serves that sentence or it waits. This file exists
because the honest feedback was right: spread wide, the project becomes slop.
Pieced out, it becomes a product.

## The spine (active development)

The differentiated tech — things only a $0-token harness can afford to do:

| Pillar | What it is | Status |
| --- | --- | --- |
| **Swarm racing** | Same step on multiple free providers in parallel, fastest token wins, losers cancelled | ✅ shipped (Groq+OpenRouter) |
| **Workflow compiler** | Successful runs compile to traces that replay with ~1 model call; divergence self-heals | ✅ shipped, live-validated |
| **Token diet** | Goal-relevant tool schemas (83→14-26/call), compact descriptions, cache-stable prefixes | ✅ shipped |
| **Tool-call integrity** | Parallel calls execute, malformed args bounce, JSON-mode constrained decoding | ✅ shipped |
| **Retrieval-augmented acting** | Near-miss traces become few-shot hints; the example bank grows itself | ✅ v1 shipped |
| **Benchmark + telemetry** | Per-task stats, replayable goal battery, measured per-model | 🔨 in progress |
| **Postcondition gating** | Harness verifies action outcomes mechanically, retries before waking the model | 📋 next |
| **Desktop DOM** | Live UIA-event-driven index of every window; diffs as observations | 📋 backlog |
| **Self-tuning dojo** | Nightly replays of the battery; routing table updates from measured results | 📋 backlog |

## Surfaces (the spine wears two faces)

- **Dashboard** (`static/`) — the daily driver. Streams, filters, renders. Keep polishing.
- **Capsule** (`app/widget/`) — the identity / demo magnet. Currently good; **parked
  by choice** until the spine work lands. Don't drive-by improve it.

## Frozen (works, but not the mission — do not grow these)

- Discord / Telegram integrations (`app/integrations/`)
- Voice (`app/widget/voice.py`)
- Premium features (`app/premium_features.py`)
- Browser plugin (`app/plugins/browser_plugin.py`)

Freezing ≠ deleting. They stay functional; they just don't get features until
the spine claims its mission.

## Process rules (the anti-slop contract)

1. **One question per branch.** A branch answers one measurable question
   ("does replay work on desktop tasks?"), then merges.
2. **Measured, or it didn't happen.** Performance claims come from
   `scripts/bench.py` runs, not vibes.
3. **The README pitch stays one sentence.** If a feature needs the pitch to
   grow a clause, it's out of scope.
