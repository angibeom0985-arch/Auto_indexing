# Codex Working Rules

## Git Auto-Commit
- At the end of every completed coding task, run `git add -A`, create a commit, and push to `origin`.
- Do not skip commit/push unless the user explicitly says not to push.
- Use clear commit messages that summarize the implemented fix.

## License/Machine ID Critical Policy
- Never create, write, or rely on `machine_id.txt` in any path.
- Machine ID persistence must use only Windows Registry (`HKCU\Software\Auto_indexing\MachineId`) and `license.json`.
- If `machine_id.txt` is discovered in legacy paths, remove it as cleanup only; do not reintroduce text-file based machine ID storage.
- Treat this as a release-blocking rule because it controls 1-user-1-PC enforcement and usage-period validation.
