# Any OpenAI-compatible client

| Setting | Value |
|---|---|
| Base URL | `http://YOUR-BOX:8080/v1` |
| Model id | `nemotron-bolt-e4b` (the `--alias` in the agent profile; without it the id is the GGUF's Windows path) |
| API key | none; if the client insists, any placeholder string (`sk-local`) |
| Context window | 32768 |
| Max output tokens | 8192 |
| Thinking | off for agent loops: send `"chat_template_kwargs": {"enable_thinking": false}` if the client allows extra body fields |

```bash
export OPENAI_BASE_URL=http://YOUR-BOX:8080/v1
export OPENAI_API_KEY=sk-local
export LLM_URL=http://YOUR-BOX:8080      # used by scripts/client/*.py
```

Before you blame the model, check how many tokens the harness's own system prompt and tool schemas use
(docs/09-agent-harnesses.md). On a 32K window it can be a third of the budget, or more than all of it.
