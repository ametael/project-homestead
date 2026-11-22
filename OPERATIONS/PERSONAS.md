# Personas

The default owner slot is `PERSONA/`. An optional owner roster lives in `PERSONA/INDEX.md` and uses the [roster template](../TEMPLATES/PERSONA_INDEX.md). Each additional owner uses `PERSONA/<id>/`, with a stable unique lowercase ID using letters, digits or hyphens. Choose a directory name unused under PERSONA, excluding memory, progression, and names reserved by the operating system. Each slot uses `IDENTITY.md` and may use `VOICE.md`, `FOCUS.md`, `HANDOFF.md`, `MEMORY/PRIVATE/INDEX.md` and `PROGRESSION/`.

On a new session select the persona the user explicitly invokes, then a user-assigned session persona, then the configured default in the roster. Without a roster, use the default slot. If a selection is ambiguous, ask. Maintain the speaker across topics. Switch mid-session only on a user-directed transition the host supports.

To add a persona, make a new slot using the [identity](../TEMPLATES/IDENTITY.md), [voice](../TEMPLATES/VOICE.md), [focus](../TEMPLATES/FOCUS.md), [owner handoff](../TEMPLATES/OWNER_HANDOFF.md) and [private index](../TEMPLATES/PRIVATE_INDEX.md) templates as needed. Register the user-approved name and aliases in the roster. Owner handoffs contain current work pointers in the applicable scope. A shared handoff can point to shared work only.

For collaboration, preserve the active speaker and provide a scoped handoff to the next authorized owner. Include only the task, relevant authorized sources, last verified result and next action. Do not claim another persona ran a tool or completed work without evidence. User-approved changes to identity belong in its canonical file; feedback and provisional changes belong in [growth](LEVELLING.md#experience-and-growth).
