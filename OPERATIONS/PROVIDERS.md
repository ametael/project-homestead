# Optional provider routing

A companion can use this tool to send one text request to a configured HTTPS chat-completions endpoint. Set one or more endpoints in your own `MEMORY/CONFIG.json`. The tool ships with no provider configured. Set `"reasoning_effort": "low"` for a model you know supports this API field. Leave the field out for other providers. The plan shows the configured effort and the tool keeps that choice for each destination. Supply keys in the named environment variables in the shell running the tool.

```json
{
  "schema": 1,
  "providers": {
    "first": {"endpoint": "https://api.example.org/v1/chat/completions", "model": "your-model", "key_env": "HOMESTEAD_FIRST_KEY"},
    "second": {"endpoint": "https://api.example.net/v1/chat/completions", "model": "your-other-model", "key_env": "HOMESTEAD_SECOND_KEY"}
  }
}
```

Create an exact JSON request under `MEMORY/OUTBOX/` with a `messages` list of plain-text `role` and `content` pairs. Use `provider plan` and one `--allow-provider NAME` for each destination, in priority order. The plan shows every endpoint, model and stated purpose without opening the request. In your own terminal, approve the file with `guardian authorize PATH --purpose "EXACT PURPOSE SHOWN BY PLAN"` for each destination you want to allow.

```text
python TOOLS/homestead.py provider plan MEMORY/OUTBOX/request.json --allow-provider first --allow-provider second
python TOOLS/homestead.py provider send MEMORY/OUTBOX/request.json --allow-provider first --allow-provider second
```

A fallback is attempted only after a 503 response, and only after checking Guardian permission for that endpoint and model. Access refusals, rate limits and uncertain delivery stop the operation. A changed endpoint, model or request needs fresh approval. Once sent, the provider's data handling policies apply. The optional local queue stays separate from this command.
