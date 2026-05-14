## 2026-04-21 - [Clean Stream UI]
**Learning:** Text-based icons (`=` and `x`) paired with missing `aria-label`s hurt both aesthetic consistency and screen reader usability. Bulky box-shadows and thick borders on chat/stream UI components often contribute to cognitive overload.
**Action:** Always replace purely structural text pseudo-icons with semantic SVGs that gracefully handle color-inversion and hover states. When updating streaming UIs (like chat), default to flatter layouts (removing heavy borders and drop shadows) to emulate modern clean patterns (e.g. Claude Code) while maintaining distinct backgrounds to separate context zones.
## 2026-04-22 - [SVG Icons and URL Encoding]
**Learning:** When using inline SVG data URIs in CSS properties (like `content: url("data:image/svg+xml;...")`), hex color codes containing `#` must be URL-encoded as `%23`. If not encoded, browsers may truncate the URI or fail to render the SVG entirely, breaking the intended visual design.
**Action:** Always verify that SVGs injected via CSS data URIs properly encode special characters, particularly `#` to `%23` for colors, and `<` / `>` to `%3C` / `%3E` when appropriate.
