# skills

Repository for creating and storing reusable SKILLS for Codex and Gemini.

## Directory structure

- `SKILLS/codex/<skill-name>/SKILL.md`
- `SKILLS/gemini/<skill-name>/SKILL.md`
- `WORKFLOW/<workflow-name>.md`
- `templates/SKILL.md`

## Quick start

1. Create a skill directory.
2. Copy `templates/SKILL.md` into that directory.
3. Fill in the instructions and examples.
4. Commit and push.

Example:

```bash
mkdir -p SKILLS/codex/my-skill
cp templates/SKILL.md SKILLS/codex/my-skill/SKILL.md
```

## Naming convention

- Use lowercase kebab-case for skill directories.
- Keep one skill per directory.
- Keep source references close to the skill if needed, for example: `references/`, `scripts/`, `assets/`.

## Contribution flow

```bash
git checkout -b feat/add-my-skill
git add .
git commit -m "feat: add my-skill for codex"
git push -u origin feat/add-my-skill
```
