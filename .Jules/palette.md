## 2024-05-14 - Semantic Form Labels for Accessible Dropdowns
**Learning:** Using generic `<div>` tags for form labels (`<div class="footer-label">Model</div>`) prevents screen readers from associating the label with the input, and breaks the native behavior where clicking the label focuses the input.
**Action:** Always use semantic `<label>` tags with the `for` attribute pointing to the `id` of the input or `<select>` element. This creates a larger clickable target area and provides proper context for assistive technologies.
