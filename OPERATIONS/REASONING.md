# Adaptive reasoning and token efficiency

Use this workflow for any Homestead persona when a task needs research, debugging, judgment or several dependent steps. Put it into practice before increasing effort.

1. Define the outcome and the check that would show it is done. Identify the exact owner, project, files and permissions.
2. Start with Low effort for work with clear requirements and a reliable check. Open only the context needed for the task. Read the complete source when understanding or changing it requires that.
3. Look for a proven method or a recorded failure when it could save work. Use the [method catalog](KNOWLEDGE.md), [checkpoints](CONTINUITY.md) and [KnowledgeBank](KNOWLEDGEBANK.md). Compare methods by fit, evidence, compatibility, reliability and cost. Use the best supported method that fits. Develop a new one when the available methods leave a real gap.
4. Work through the task in small steps that can be verified. Use the toolbox for deterministic checks, such as comparing hashes, validating files and running scoped preflight.
5. If a check fails, identify what is missing and change the source, method or implementation that caused it. Move to Medium when relevant uncertainty remains. Reserve High for complexity or risk the earlier checks could not resolve.
6. Save verified lessons and durable decisions at their owning source. A repeated attempt by itself earns zero EXP. Update a checkpoint with the exact next step when work spans sessions.

Low is intended to cover work often assigned to Medium when the references and verification are sufficient. Actual results depend on the model, task and host. If the host has its own reasoning controls, use the effort it supports. Otherwise apply this workflow through context selection and checks. Token efficiency means loading useful context once and avoiding repeated work.
