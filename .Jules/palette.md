## 2026-04-21 - [Clean Stream UI]
**Learning:** Text-based icons (`=` and `x`) paired with missing `aria-label`s hurt both aesthetic consistency and screen reader usability. Bulky box-shadows and thick borders on chat/stream UI components often contribute to cognitive overload.
**Action:** Always replace purely structural text pseudo-icons with semantic SVGs that gracefully handle color-inversion and hover states. When updating streaming UIs (like chat), default to flatter layouts (removing heavy borders and drop shadows) to emulate modern clean patterns (e.g. Claude Code) while maintaining distinct backgrounds to separate context zones.

## 2026-04-27 - [Form Input Accessibility]
**Learning:** Relying on generic `<div>` or `<span>` elements to serve as visual labels for form inputs, or leaving standalone inputs (like search bars, textareas, or command palettes) without labels entirely, breaks accessibility for screen reader users and reduces overall interface clarity.
**Action:** Always use semantic `<label for="[id]">` elements instead of generic containers for form input descriptions. For standalone inputs where a visible label disrupts the design, provide an explicit `aria-label` attribute to ensure the input's purpose is accessible to assistive technologies.
