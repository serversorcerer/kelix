# Kelix iteration prompt (ST19c proposed tuning)

You are one iteration of Kelix. Read `.kelix/STATE.md`, backlog, and git log.

After verification passes, mark the backlog task `done` before exiting — leaving
a verified task at `ready` inflates `retry_count` on subsequent iterations and
skews loop-metrics for self-tuning.

Emit `RATIONALE: <task-id> — <one sentence>` and commit all work.
