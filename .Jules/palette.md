## 2026-04-21 - [Clean Stream UI]
**Learning:** Text-based icons (`=` and `x`) paired with missing `aria-label`s hurt both aesthetic consistency and screen reader usability. Bulky box-shadows and thick borders on chat/stream UI components often contribute to cognitive overload.
**Action:** Always replace purely structural text pseudo-icons with semantic SVGs that gracefully handle color-inversion and hover states. When updating streaming UIs (like chat), default to flatter layouts (removing heavy borders and drop shadows) to emulate modern clean patterns (e.g. Claude Code) while maintaining distinct backgrounds to separate context zones.

## 2024-05-19 - [Accessible Toast Icons]
**Learning:** Hardcoding standard unicode characters like `✕` or `✓` can cause them to be announced inappropriately by screen readers (e.g. "multiply") and may render differently across OS platforms. Using inline SVG data URIs directly in CSS `content:` creates perfectly consistent decorative pseudo-elements, while avoiding screen reader clutter.
**Action:** Always replace decorative pseudo-element UIs containing unicode text icons with inline SVGs in CSS, remembering to URL encode `#` as `%23` for hex colors in the SVG path stroke.
