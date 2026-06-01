# Read This Before You Explode Your Repo

## What This Refactor Changed

- The addon no longer depends on PySide6 in the main load path.
- Blender translations now live under `translation/`.
- Human translation files and auto translation files are separated.
- The analyzer now reports only human translation coverage.

## Recommended Shape For The Future

1. Keep runtime addon code and tooling separate.
   - Runtime code should stay import-safe.
   - Tooling should live beside data, not inside startup-critical modules.

2. Treat optional dependencies as isolated features.
   - Do not import PySide6 from the main addon path unless the feature is fully optional.
   - If a feature depends on Qt, keep it in a separate module or entry point.

3. Keep translation data predictable.
   - Human translation files should be the source of truth.
   - Auto-generated files should be ignored by reports unless explicitly requested.
   - Stable naming like `ru.json` and `ru_auto.json` is fine.

4. Do not mix cache artifacts into version control.
   - Remove `__pycache__`, `.pyc`, temp exports, and generated logs from commits.
   - Add them to `.gitignore` if they keep coming back.

5. Translate only what Blender can actually render.
   - UI labels, panel names, operator descriptions, tooltips, and enum labels are realistic targets.
   - Console `print()` output is not automatically localized by Blender.
   - If you want localized logs later, add a dedicated helper and call it explicitly.

6. Keep the analyzer conservative.
   - Report only strings that are actually used by the human-facing UI.
   - Avoid counting auto translations as coverage.
   - Print missing keys with real JSON escaping so the output can be pasted back safely.

## Practical Rule

- If a change can break addon startup, isolate it.
- If a change only helps tooling, keep it out of the runtime import chain.
- If a string is not rendered in Blender UI, do not assume it is supported.
