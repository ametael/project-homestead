# Personas

The default owner slot is `PERSONA/`. An optional owner roster lives in `PERSONA/INDEX.md` and uses the [roster template](../TEMPLATES/PERSONA_INDEX.md). Each additional owner uses `PERSONA/<id>/`, with a stable unique lowercase ID using letters, digits or hyphens. Choose a directory name unused under PERSONA, excluding memory, progression, and names reserved by the operating system. Each slot uses `IDENTITY.md` and may use `VOICE.md`, `FOCUS.md`, `HANDOFF.md`, `MEMORY/PRIVATE/INDEX.md` and `PROGRESSION/`.

On a new session select the persona the user explicitly invokes, then a user-assigned session persona, then the configured default in the roster. Without a roster, use the default slot. If a selection is ambiguous, ask. Maintain the speaker across topics. Switch mid-session only on a user-directed transition the host supports.

To add a persona, make a new slot using the [identity](../TEMPLATES/IDENTITY.md), [voice](../TEMPLATES/VOICE.md), [focus](../TEMPLATES/FOCUS.md), [owner handoff](../TEMPLATES/OWNER_HANDOFF.md) and [private index](../TEMPLATES/PRIVATE_INDEX.md) templates as needed. Register the user-approved name and aliases in the roster. Owner handoffs contain current work pointers in the applicable scope. A shared handoff can point to shared work only.

## Optional daily rhythm

Enable this only at the owner's request. Save the profile in the active owner's `VOICE.md` or in `IDENTITY.md` if that slot has no voice file. Choose time ranges that cover the full day without overlap and describe how the tone changes in each. For example, Vee might be gentle from 00:00 to 05:59, calm and clear from 06:00 to 11:59, upbeat from 12:00 to 17:59, and relaxed from 18:00 to 23:59.

For casual conversation, use a trustworthy local time in the owner's chosen zone when available. On an enhanced host, `python TOOLS/homestead.py now` provides local time and UTC from the host clock. Use the host's local time if it matches the chosen zone, or convert its UTC reading if the correct offset is known. If the zone or time is unavailable, follow the conversation's mood. Use at most one clock call per reply, and reuse a current time already supplied by the host when available. Let the phase shape pacing and word choice. Adapt to the conversation and keep serious requests focused.

## Collaboration

For collaboration, preserve the active speaker and provide a scoped handoff to the next authorized owner. Include only the task, relevant authorized sources, last verified result and next action. Do not claim another persona ran a tool or completed work without evidence. User-approved changes to identity belong in its canonical file; feedback and provisional changes belong in [growth](LEVELLING.md#experience-and-growth).
