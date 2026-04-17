<!-- generated-by: gsd-doc-writer -->
<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **net_alpha** (1503 symbols, 3520 relationships, 108 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, use the GitNexus **impact** tool (upstream) and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run the GitNexus detect_changes tool before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use the GitNexus **query** tool to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use the GitNexus **context** tool.

## When Debugging

1. Use the GitNexus **query** tool — find execution flows related to the issue
2. Use the GitNexus **context** tool — see all callers, callees, and process participation
3. `READ gitnexus://repo/net_alpha/process/{processName}` — trace the full execution flow step by step
4. For regressions: use the **detect_changes** tool (compare to main) — see what your branch changed

## When Refactoring

- **Renaming**: MUST use the GitNexus **rename** tool (dry run) first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run the GitNexus **context** tool to see all incoming/outgoing refs, then the **impact** tool (upstream) to find all external callers before moving code.
- After any refactor: run the GitNexus **detect_changes** tool to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running the GitNexus **impact** tool on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use the GitNexus **rename** tool which understands the call graph.
- NEVER commit changes without running the GitNexus **detect_changes** tool to check affected scope.

## Tools Quick Reference

| Tool | When to use | Description |
|------|-------------|-------------|
| `query` | Find code by concept | Search for functional areas or concepts |
| `context` | 360-degree view of one symbol | Comprehensive view of symbol relationships |
| `impact` | Blast radius before editing | Upstream/downstream impact analysis |
| `detect_changes` | Pre-commit scope check | Verify changes against indexed baseline |
| `rename` | Safe multi-file rename | Call-graph aware symbol renaming |
| `cypher` | Custom graph queries | Run custom Cypher queries on the code graph |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/net_alpha/context` | Codebase overview, check index freshness |
| `gitnexus://repo/net_alpha/clusters` | All functional areas |
| `gitnexus://repo/net_alpha/processes` | All execution flows |
| `gitnexus://repo/net_alpha/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. The GitNexus **impact** tool was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. The GitNexus **detect_changes** tool confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
