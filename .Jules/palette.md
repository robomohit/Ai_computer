## 2026-04-21 - [Clean Stream UI]
**Learning:** Text-based icons (`=` and `x`) paired with missing `aria-label`s hurt both aesthetic consistency and screen reader usability. Bulky box-shadows and thick borders on chat/stream UI components often contribute to cognitive overload.
**Action:** Always replace purely structural text pseudo-icons with semantic SVGs that gracefully handle color-inversion and hover states. When updating streaming UIs (like chat), default to flatter layouts (removing heavy borders and drop shadows) to emulate modern clean patterns (e.g. Claude Code) while maintaining distinct backgrounds to separate context zones.
## 2026-05-28 - [Clean Stream UI continued]
**Learning:** Adding `display: block;` to labels when converting them from block-level `<div>` elements preserves vertical flow while drastically improving screen reader semantics.
**Action:** Always verify if converted elements require layout preservation via CSS when making semantic changes to avoid unintentional UI shifts.
