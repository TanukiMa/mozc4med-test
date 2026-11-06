@AGENTS.md

# CLAUDE.md: Claude Code specific notes

Project rules (goals, branch policy, Track A/B/C, patch requirements, phases) live in `AGENTS.md`, imported above. This file only holds what is specific to Claude Code.

## Tool usage
- **Patch authoring**: Before writing any `.patch`, use the `Read` tool on the target file under `src/` to get exact line numbers (AGENTS.md §3.5). Never guess hunk headers.
- **Patch verification**: After writing a patch, run `git apply --check` on it via Bash against the current working tree. For a whole series, use `python mozc4med/tool/validate_and_apply_patches.py mozc4med/common mozc4med/<os>` rather than a hand-rolled loop. Never leave `src/` modified afterward: revert any applied changes (`git checkout -- src`), because `src/` must not be committed directly.
- **File encoding on Windows**: Files created with `Write` must be UTF-8 without BOM and LF. After creating a `.yaml` or `.patch`, confirm with `file <path>` and `grep -c $'\r' <path>` (expect `0`). This session runs on Windows, so be careful with PowerShell redirection (`>` writes UTF-16/BOM in Windows PowerShell 5.1) and use Bash or `Write`/`Edit` for these files.
- **Editing**: Use `Edit` for changes to existing files, not `sed`/PowerShell rewrites, except for mechanical renames.

## Workflow
- Work on `dev` only. Commit or push only when the user asks.
- When the user supplies `gh run view --log-failed` output, follow AGENTS.md §5: find the failing patch or workflow step and fix that specific file.
- Update `mozc4med/ChangeLog-mozc4med.md` when adding or changing a patch or tool in `mozc4med/`.
- Keep user-facing explanations in Japanese; keep files in this repo (patches, YAML, code comments) in the language they already use.
