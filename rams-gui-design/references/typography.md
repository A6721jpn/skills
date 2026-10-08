# IBM Plex Sans JP

The user-selected typeface is IBM Plex Sans JP. It covers Japanese and Latin text
in one family. Keep the existing product type system when the brief requires it.

## Sources

- Publisher and releases: https://github.com/IBM/plex
- Google Fonts distribution: https://github.com/google/fonts/tree/main/ofl/ibmplexsansjp
- Regular (400), direct TTF download: https://raw.githubusercontent.com/google/fonts/0b58fb370093f9a9f4ff785d94405710b79de67c/ofl/ibmplexsansjp/IBMPlexSansJP-Regular.ttf
- Bold (700), direct TTF download: https://raw.githubusercontent.com/google/fonts/0b58fb370093f9a9f4ff785d94405710b79de67c/ofl/ibmplexsansjp/IBMPlexSansJP-Bold.ttf
- SIL Open Font License 1.1 and IBM copyright notice: https://raw.githubusercontent.com/google/fonts/0b58fb370093f9a9f4ff785d94405710b79de67c/ofl/ibmplexsansjp/OFL.txt

These direct links pin the same revision used in the local comparison. The
unmodified Regular and Bold files were verified in Chromium with Japanese text,
digits, and bold text on 2026-10-08.

## Apply the font

Retrieve the required font files during implementation and keep them in the
project's font assets, with the original copyright notice and OFL license.
Load the bundled files using the platform's local font mechanism. For a web GUI,
serve them from the project rather than requiring an external font service at
display time. Only include the weights actually used.

The URLs identify sources; they do not apply the font by themselves. Specify the
family, load the files, and inspect Japanese text, digits, bold text, and long-name
wrapping in the rendered interface. Confirm that the intended font is actually
used rather than silently accepting a substitute.

If retrieval or loading is unavailable, keep the GUI usable with an existing
Japanese-capable sans-serif font and report the substitution. The skill does not
require installing fonts in the operating system.
