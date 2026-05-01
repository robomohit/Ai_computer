## 2026-04-21 - [Clean Stream UI]
**Learning:** Text-based icons (`=` and `x`) paired with missing `aria-label`s hurt both aesthetic consistency and screen reader usability. Bulky box-shadows and thick borders on chat/stream UI components often contribute to cognitive overload.
**Action:** Always replace purely structural text pseudo-icons with semantic SVGs that gracefully handle color-inversion and hover states. When updating streaming UIs (like chat), default to flatter layouts (removing heavy borders and drop shadows) to emulate modern clean patterns (e.g. Claude Code) while maintaining distinct backgrounds to separate context zones.

## 2026-05-01 - [Semantic Labels for Inputs]
**Learning:** Found that custom layout structures using `<div>` or `<span>` elements positioned near `<input>` or `<select>` fields to act as pseudo-labels break accessibility and make it harder for screen readers to announce inputs properly.
**Action:** Always use semantic `<label for="[id]">` elements instead of `<div>` or `<span>` for form input descriptions. When building standalone inputs (like search bars, textareas, command palette), provide explicit `aria-label` attributes to ensure they are fully screen reader accessible.
