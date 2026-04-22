---
description: Summarizes the API routes and current entity relationships into a temporary file to reduce context window usage.
---
# skeen-brief-be

## Goal
Token optimization during long development sessions.

## Steps
// turbo-all
1. Use a tool (e.g., grep or a custom python script) to list all FastAPI routes and domain entities from `src/`.
2. Write findings to `/tmp/skeen_summary.txt`.
3. Output the contents of `/tmp/skeen_summary.txt` to the user.
