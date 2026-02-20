# AGENTS.md

## Purpose
This repository contains utility scripts. Keep changes focused, minimal, and easy to review.

## Working agreement for agents
- Prefer small, single-purpose commits.
- Preserve existing behavior unless the task explicitly asks for behavior changes.
- Follow the existing style and conventions in nearby files.
- Avoid adding new dependencies unless they are necessary for the task.

## Editing guidelines
- Update docs/comments when behavior or interfaces change.
- Keep filenames, function names, and CLI flags stable unless requested.
- Do not perform broad refactors when solving a targeted issue.

## Validation
- Run the narrowest relevant checks first (lint/tests for touched code).
- If full test suites are expensive, run focused checks and document what was run.

## Pull request guidance
- Include a concise summary of what changed and why.
- List validation commands and their outcomes.
- Call out trade-offs, limitations, and follow-up work if applicable.
