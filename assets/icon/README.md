# Icon

The Tarot Reader icon is the Hermit's lantern (IX The Hermit), drawn in charcoal `#1C1C1E` and off-white `#F2EFE8`.
The plugin ships `plugin/icon.svg`; this folder holds the same mark for directory listings, which crop icons to their
own shape, so every file here is a full-bleed square.

| File | Use |
| --- | --- |
| `tarot-reader-dark.svg`, `tarot-reader-light.svg` | Vector source, charcoal and inverted |
| `tarot-reader-{dark,light}-1024.png`, `-512.png` | Claude connector or plugin directory listing |
| `tarot-reader-{dark,light}-64.png` | ChatGPT app directory logo (light and dark mode) |
| `tarot-reader-{dark,light}-256.png`, `-128.png`, `-32.png` | Other surfaces and favicons |

The PNGs are rendered from the SVGs. Re-export them all if the mark changes.
