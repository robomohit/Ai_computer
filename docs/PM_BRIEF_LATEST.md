# PM Brief — 2026-05-25 (automated run)

**Starting commit:** `bf2eb1c`  →  **Ending commit:** `272f9df`
**Run duration:** ~45 min  |  **LOC budget used:** ~146/200
**Run type:** mixed (3 features shipped, 1 new issue filed)

---

## What ran

1. **Synced git** — pulled `origin/feature/new-updates`, confirmed clean baseline.
2. **Full test suite** — `181 passed, 0 failed` at start (Δ: +6 from last run).
3. **UI smoke** — static file split intact; all hardening tests green.
4. **Shipped issues** (in order):
   - **AI-28** (Low): `liquid-glass.css` static asset test added to `test_ui_static_hardening.py`. 9 LOC. Commit `b239d59`.
   - **AI-15** (High): Voice widget v2 — live activity strip (`#vcap-strip`) in HTML/CSS/JS + hotkey toggle fix (`root.hidden = !root.hidden`). 50 LOC. Commit `0b16c1a`. Test `test_ai15_voice_widget_v2_drag_strip_hotkey()` added.
   - **AI-22** (Medium): `BLOCKED_MODELS` + `BLOCKED_PROVIDERS` env-var model governance — three new helpers in `app/providers.py` + blocklist filtering in `_openrouter_models_to_try()`. 87 LOC. Commit `272f9df`. Three new tests in `test_providers.py`.
5. **Board hygiene** — no 30-day stale issues, no blocked issues found.
6. **New issue filed** — AI-29 (Medium, Backlog): extend BLOCKED_MODELS/BLOCKED_PROVIDERS to native provider paths.
7. **Linear updated** — AI-15, AI-28, AI-22 moved to Done with commit-hash comments. AI-29 filed.

---

## Tests

| | Count |
|---|---|
| Passed | 187 |
| Failed | 0 |
| Δ vs last run | +6 |

Suite ran clean after all three shipped issues. No tests deleted, skipped, or weakened.

---

## Repaired

Nothing was red at baseline. No repair pass needed.

---

## Shipped

| Issue | Title | LOC | Commit |
|---|---|---|---|
| AI-28 | liquid-glass.css static asset test | 9 | `b239d59` |
| AI-15 | Voice widget v2 (activity strip + hotkey toggle) | 50 | `0b16c1a` |
| AI-22 | BLOCKED_MODELS + BLOCKED_PROVIDERS governance | 87 | `272f9df` |

---

## New issues filed

- **AI-29** (Medium, Backlog): Extend BLOCKED_MODELS/BLOCKED_PROVIDERS to native provider paths. `_chat_anthropic`, `_chat_google`, `_chat_openai`, `_chat_groq` bypass `_openrouter_models_to_try()` and thus the blocklist. Fix: add `_is_model_blocked` check in `stream_chat_with_tools()` dispatch. ~10-15 LOC.

---

## Decisions I made (and why)

1. **Shipped AI-28 first** (Low priority) — smallest item (9 LOC, pure test), strengthened baseline before touching bigger issues.
2. **Hotkey toggles `root.hidden`, not just focus** — acceptance criteria said summon/dismiss. Interpreted as full hide/show. Focus only granted when `!isTextEntryTarget(e.target)` to avoid stealing focus from other inputs.
3. **Blocklist only in `_openrouter_models_to_try()`, not native paths** — staying within AI-22 scope. Filed AI-29 to track the gap.
4. **Did not attempt AI-7** (Watch & Act, ~150-200 LOC) — only 54 LOC of budget remained after AI-22. Left for next run.

---

## Skipped / blocked

- **AI-7** (Watch & Act slice 1, ~150-200 LOC): insufficient LOC budget after AI-22.
- **AI-13** (Private Context Bridge): `needs-design` label — blocked by policy.
- **AI-21** (Planning mode): Todo, medium — budget exhausted.
- **AI-26** (ALLOWED_MODELS glob): may already be pre-implemented via `fnmatch` — needs verification next run.

---

## Risk flags

None critical. AI-29 (native-path blocklist bypass) is medium severity but not exploitable without attacker control over env vars.

---

## Health snapshot

- Branch: `feature/new-updates` — pushed to origin, clean working tree.
- Tests: 187 passed, 0 failed.
- LOC budget used: ~146/200.
- Commits this run: 3/4 (`b239d59`, `0b16c1a`, `272f9df`).

---

## Next run plans

1. **Verify AI-26** — check if `fnmatch` added for AI-22 already satisfies ALLOWED_MODELS glob; if yes, mark Done with no code change.
2. **AI-7** (Watch & Act slice 1) — highest-priority Todo without `needs-design`; budget the full 200 LOC.
3. **AI-29** (native-path blocklist bypass) — quick fix (~10-15 LOC) if budget allows after AI-7.
