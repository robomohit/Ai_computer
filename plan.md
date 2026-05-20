1. Add `<label for="model-id" class="selector-label">Model</label>` instead of `<div class="selector-label">Model</div>` in `static/index.html`.
2. Add `<label for="mode-id" class="selector-label">Mode</label>` instead of `<div class="selector-label">Mode</div>` in `static/index.html`.
3. Add `<label for="isolated-app-id" class="selector-label">Target App (Locked)</label>` instead of `<div class="selector-label">Target App (Locked)</div>` in `static/index.html`.
4. Add `display: block;` to `.selector-label` in `static/style.css` so that the layout is preserved when changing from `div` to `label`.
