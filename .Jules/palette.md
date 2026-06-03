## 2026-04-21 - [Clean Stream UI]
**Learning:** Text-based icons (`=` and `x`) paired with missing `aria-label`s hurt both aesthetic consistency and screen reader usability. Bulky box-shadows and thick borders on chat/stream UI components often contribute to cognitive overload.
**Action:** Always replace purely structural text pseudo-icons with semantic SVGs that gracefully handle color-inversion and hover states. When updating streaming UIs (like chat), default to flatter layouts (removing heavy borders and drop shadows) to emulate modern clean patterns (e.g. Claude Code) while maintaining distinct backgrounds to separate context zones.

## 2026-06-03 - [Semantic Icons and Aria Labels]
**Learning:** Hardcoded Unicode characters (like `✕` for close) can cause font-rendering inconsistencies and lack semantic meaning, hindering accessibility. Standalone input fields that only rely on `placeholder` text lack explicit labels for screen readers.
**Action:** Replace hardcoded text icons used in structural UI elements with standard semantic SVGs and ensure `aria-hidden="true"` is set when the parent element provides the accessible name via `aria-label`. Always provide explicit `aria-label` attributes to standalone inputs that lack a dedicated `<label>` element.
