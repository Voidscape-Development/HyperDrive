# Country flags

The `.svg` flags come from [hampusborgos/country-flags](https://github.com/hampusborgos/country-flags)
(commit `c09927e`), which draws each flag to its country's official specification and
proportions. Flags are public domain.

Changes from upstream:

- File names are lowercased (`GB-ENG.svg` → `gb-eng.svg`) to match the codes HyperDrive uses.
- Percentage sizes on `<rect>` (`br`, `by`, `gb-sct`) are converted to viewBox units,
  since Qt's SVG renderer resolves them differently from browsers.
- Optimized with [svgo](https://github.com/svg/svgo) using `multipass`. Each flag uses
  the lowest coordinate precision (1–3 decimals) that renders the same as the original
  in Chromium at 800px wide; two flags (`hr`, `nu`) only get the width and height below.
- Each `<svg>` gets `width="100"` and a matching `height`, so a layout that doesn't
  size its `<img>` shows the flag at the same 100px width as the old PNGs.

The `.png` flags are the previous set. HyperDrive no longer uses them, and they're kept for one
release so layouts that hardcode `country_flag/<code>.png` keep working.
