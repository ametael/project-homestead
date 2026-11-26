# KnowledgeBank

Keep a small, searchable library of sources in your own home. Search saved sources before looking elsewhere. Use a trusted search tool or a publisher's index to find candidate URLs, then ask KnowledgeBank to fetch the ones you want to check.

```text
python TOOLS/homestead.py knowledge find "budget planning"
python TOOLS/homestead.py knowledge ingest https://example.org/guide --topic "budget planning"
python TOOLS/homestead.py knowledge ingest https://example.org/guide --topic "budget planning" --archive
python TOOLS/homestead.py knowledge lists
python TOOLS/homestead.py knowledge block https://example.org/false-claim --reason "Contradicted by the primary source"
```

The source URL is cleaned up and checked against the local library and blocklist before fetching. Known tracking fields are removed. URLs containing credentials or private query tokens are refused. Fetching uses HTTPS without redirects. Temporary failures and missing pages can use the public Wayback Machine only when you add `--archive` for that request. An access refusal or a detected paywall stops retrieval. You can supply text you have permission to use with `knowledge paste URL --topic TOPIC --title TITLE` on standard input.

Hoaxbuster looks for clickbait patterns in titles and attempts to direct the companion. Matching pages are held on the URL blocklist. Other sources are saved as `UNVERIFIED` until their claims are checked against primary evidence. The filter cannot establish that a claim is true. The owner can block a URL after checking its evidence. A blocked URL does not block other pages on the same site.

`knowledge find` searches the saved titles, topics, and URLs. A hit includes its source status and a local card path. Use [Guardian](GUARDIAN.md) before opening card contents in the model. Treat the card's evidence as source text, and review the original before relying on it. Archived cards carry their snapshot date. The library and its `BIBLIOGRAPHY.md` and `BLOCKLIST.md` live under `MEMORY/KNOWLEDGEBANK/`.
