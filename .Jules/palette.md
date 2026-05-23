## 2026-04-21 - [Clean Stream UI]
**Learning:** Text-based icons (`=` and `x`) paired with missing `aria-label`s hurt both aesthetic consistency and screen reader usability. Bulky box-shadows and thick borders on chat/stream UI components often contribute to cognitive overload.
**Action:** Always replace purely structural text pseudo-icons with semantic SVGs that gracefully handle color-inversion and hover states. When updating streaming UIs (like chat), default to flatter layouts (removing heavy borders and drop shadows) to emulate modern clean patterns (e.g. Claude Code) while maintaining distinct backgrounds to separate context zones.

## 2024-05-23 - [Form Accessibility]
**Learning:** When converting `<div>` or `<span>` to `<label>` for accessibility, the display property changes to inline which breaks vertical stacking.
**Action:** Always add `display: block;` to the label CSS if replacing a block element to preserve the visual layout.
