# Guardian

Guardian checks file content before the Homestead Swiss Knife returns it to its caller. The toolbox runs locally. Its output can enter the model context through the host, so ask for permission before requesting or forwarding sensitive content.

## What requires permission

Files that match the shipped public package manifest can be read directly. User files and files whose status is unclear require permission. The search index can find eligible protected files by name and basic metadata. Content search, links extracted from a document, previews, excerpts and summaries follow the same access boundary. The index limits content search to public package files.

Use the file and stated purpose shown by Guardian. Approval applies to those file bytes and that purpose. A changed file needs fresh approval. An explicit refusal remains in effect for that file and purpose until the owner changes it. Recovery files, derived caches and environment files are outside the Guardian read commands.

Always respect the creator’s terms and the owner’s privacy. The local owner decides whether a particular use is permitted and suitable before approving it. An authorized result that is sent to a service is subject to that service’s data policies.

## Confirmation modes

- `false` is the default. If access needs a decision, the toolbox returns `CONSENT_REQUIRED`. Show the request once and let the owner answer it in their local terminal. A recorded approval is reused for the same file and purpose.
- `true` skips the extra question. A file with no approval stays closed and the toolbox returns `DENIED`. The owner can still record a decision directly.
- Mode and decisions are separate. Approving or refusing a file leaves the mode as set by the owner.

In a local terminal under your control:

```text
python TOOLS/homestead.py guardian status
python TOOLS/homestead.py guardian mode false
python TOOLS/homestead.py guardian authorize ASSETS/drawing.png --purpose "Review the composition"
python TOOLS/homestead.py guardian forget ASSETS/drawing.png --purpose "Review the composition"
```

An authorization requires your typed answer in that terminal. Keep the exact purpose when requesting the file. Use a different purpose for a different use. The local decision record is outside the public package.

## Host boundary

Use the toolbox as the file path for the companion, and restrict direct shell and file access in the host when that access must be enforced. Agents should preserve a Guardian denial across tool changes. In a file-only app, ask the owner to share only the approved file and purpose. For image reads, the toolbox can provide a permitted attachment to hosts that accept its output.
