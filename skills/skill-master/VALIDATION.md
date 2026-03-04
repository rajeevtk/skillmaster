# Validation Rules

Rules applied to every generated SKILL.md before storage.

## YAML Frontmatter

| Rule | Constraint |
|---|---|
| `name` required | Must be present |
| `name` length | ≤ 64 characters |
| `name` format | Lowercase letters, numbers, hyphens only (`^[a-z0-9][a-z0-9-]*[a-z0-9]$`) |
| `name` reserved words | Must not contain "anthropic" or "claude" |
| `name` no XML | Must not contain `<` or `>` |
| `description` required | Must be non-empty |
| `description` length | ≤ 1024 characters |
| `description` no XML | Must not contain XML tags |
| `description` third person | Should not use "I can", "you can", etc. (warning) |

## Body

| Rule | Constraint |
|---|---|
| Line count | ≤ 500 lines |
| Reference depth | File references should be one level deep from SKILL.md |
| Time-sensitive info | Should not contain date-bound statements (warning) |
| Terminology | Should use consistent terms throughout (manual review) |

## Error vs Warning

- **Errors** block storage — the skill must be regenerated with feedback
- **Warnings** are informational — the skill is stored but flagged
