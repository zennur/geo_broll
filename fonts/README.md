# Bundled fonts

These families are included so a fresh checkout renders typography without
depending on a particular machine’s font path. Each directory has the
font’s own SIL Open Font License (OFL 1.1) text.

| Family | Files | License | Source |
| --- | --- | --- | --- |
| Inter | `Inter-VariableFont_opsz,wght.ttf` | SIL OFL 1.1 | [rsms/inter](https://github.com/rsms/inter) |
| JetBrains Mono | `JetBrainsMono-VariableFont_wght.ttf` | SIL OFL 1.1 | [JetBrains/JetBrainsMono](https://github.com/JetBrains/JetBrainsMono) |
| Liberation Sans | Regular + Bold | SIL OFL 1.1 | [liberationfonts](https://github.com/liberationfonts/liberation-fonts) |
| Liberation Mono | Regular + Bold | SIL OFL 1.1 | same as Liberation Sans |

The OFL allows bundling and redistribution with software; the fonts must
stay under the OFL and may not be sold by themselves. Reserved font names
(including “Liberation”) are unchanged.

`style.py` and `ui_story.py` load these files first, then fall back to
common system paths (and DejaVu) if a file is missing.
