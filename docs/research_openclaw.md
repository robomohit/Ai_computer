# OpenClaw Research Summary

## Repository Status

The `openclaw/openclaw` GitHub repository is publicly accessible. README, VISION.md,
and all docs under `docs/` are available. The GitHub REST API returns HTTP 403 for
unauthenticated metadata endpoints, but all raw file content is fully readable.

---

## Memory Architecture

### Tiers

OpenClaw uses a **two-tier, file-backed memory model** rooted in `~/.openclaw/workspace`:

- **Short-term** — daily note files written as `memory/YYYY-MM-DD.md`. Today's and
  yesterday's files are auto-loaded at session start. A parallel `memory/.dreams/`
  directory holds recall traces used by the promotion pipeline. Memory is also flushed
  from context before every compaction via a silent "memory flush" turn.
- **Long-term** — a single durable `MEMORY.md` file loaded at every session start.
  An optional companion `DREAMS.md` stores a human-readable dream diary.

### Summarization / Consolidation: Dreaming

Background promotion (short-term → long-term) is called **Dreaming** and runs
on a cron schedule (default 3 AM daily). It has three cooperative phases:

1. **Light** — ingests recent daily signals and recall traces, deduplicates, stages
   candidates, records reinforcement signals. Does not write `MEMORY.md`.
2. **REM** — extracts recurring themes and reflective patterns, writes a managed
   `## REM Sleep` block, records reinforcement signals for deep ranking. Does not
   write `MEMORY.md`.
3. **Deep** — ranks candidates using six weighted scoring signals (frequency 0.24,
   relevance 0.30, query diversity 0.15, recency 0.15, consolidation 0.10,
   conceptual richness 0.06) plus Light/REM reinforcement boosts. Items must pass
   minimum score, recall-count, and unique-query gates before being appended to
   `MEMORY.md`. Writes a `## Deep Sleep` summary to `DREAMS.md`.

An optional **memory-wiki** plugin compiles durable knowledge into a structured wiki
with provenance, contradiction tracking, and generated dashboards.

### Embedding Model

No single fixed model — provider is **auto-detected from available API keys** in this
priority order: local GGUF (`node-llama-cpp`) → OpenAI (`text-embedding-3-small`,
the named default) → Gemini Embedding 2 → Voyage → Mistral → GitHub Copilot →
Bedrock → Ollama. Overridable via `agents.defaults.memorySearch.provider`.

### Retrieval Ranking

Hybrid search: **vector similarity + BM25 keyword path** merged with configurable
weights. Default backend is SQLite (FTS5 + optional `sqlite-vec` acceleration),
chunked at ~400 tokens with 80-token overlap. Optional enhancements:
- **Temporal decay** — notes older than ~30 days lose weight (half-life 30 days);
  evergreen files like `MEMORY.md` are exempt.
- **MMR (Maximal Marginal Relevance)** — suppresses near-duplicate snippets.

Two alternative backends: **QMD** (local-first, reranking + query expansion) and
**Honcho** (cross-session user modeling, multi-agent awareness).

---

## MCP Store / Marketplace / Registry

**No downloadable MCP pack system or MCP marketplace exists in the openclaw repo.**
MCP support is purely a runtime-integration surface:

- `openclaw mcp serve` — runs OpenClaw as an MCP *server*, exposing channel
  conversations to external MCP clients (Claude Code, Codex, etc.).
- `openclaw mcp list/show/set/unset` — manages a per-installation config registry
  of MCP server *definitions* consumed by OpenClaw's own runtimes.

Plugin and skill discovery (including MCP-bundled plugins) is delegated to the
external **[ClawHub](https://clawhub.ai/)** site. VISION.md explicitly states the
project will not merge MCP work that duplicates existing MCP, ACPX, plugin, or
ClawHub paths. ClawHub is a separate site, not part of this repo.

---

## Key Takeaways for Our Architecture

| Dimension | OpenClaw approach | Our current approach |
|-----------|------------------|---------------------|
| Short-term | Daily markdown files, auto-loaded | Single Chroma/fallback collection |
| Long-term | `MEMORY.md`, promoted via Dreaming cron | Same Chroma collection |
| Consolidation | 3-phase cron job (Light→REM→Deep) | Sliding-window trim + summary |
| Embedding | Auto-detected per API key available | all-MiniLM-L6-v2 (fixed) |
| Retrieval | Hybrid BM25 + vector + MMR | Cosine-only via Chroma |
| MCP packs | None — not a concept in openclaw | Not currently planned |
