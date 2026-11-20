# 09 — Agent harnesses

Goal: an OpenAI-compatible agent harness on another machine runs a multi-turn, tool-using session against the box.

## Connecting

Any harness that speaks the OpenAI chat completions API with tools will work. You need three values:

| Setting | Value |
|---|---|
| Base URL | `http://YOUR-BOX:8080/v1` |
| Model id | `nemotron-bolt-e4b` (from `--alias`; without it the id is the Windows file path) |
| API key | Any placeholder string. The server has no auth; some harnesses refuse an empty key |

Generic snippet: [`config/harness/openai-env.md`](../config/harness/openai-env.md).

Turn thinking off for agent loops (see below). Context window to declare: 32768 on the agent profile, 65536 on
ingest.

## The core lesson: budget context like VRAM

Harness defaults are sized for frontier models with 200K+ windows. On a 32K model, context is the scarce
resource, and three things eat it: the harness's own prompt, tool output, and history. Plan it the way you plan
VRAM: know the fixed cost, cap the variable costs, leave headroom.

### 1. The harness's base prompt (hurdle 24)

**Symptom.** The model "can't even start", or errors on the first request, or compacts immediately.

**Cause.** Harness system prompts plus tool schemas. In the same working folder, one harness cost about **7.6K
tokens** before the first user message; another cost about **39K**, which does not fit a 32K window at all.
Breakdown of the 39K: MCP server tool schemas about 22K, built-in tool schemas about 8.4K, system message about
6.3K, skills list about 2K. Dropping the MCP servers brought it to about 18K. In that harness, MCP servers were
configured profile-wide, not per folder.

**Fix.** Measure the base prompt before blaming the model: send one trivial message and read the prompt token
count from the server log or the response's `timings`. Then cut MCP servers and tools you don't need for this
job. If you can't, run the ingest profile (64K, no speculative decoding).

### 2. Tool output (the one that kills sessions)

**Symptom.** A session that was fine stalls after one tool call. Compaction errors out (for example
`exceed_context_size_error`) and retries don't recover.

**Cause.** One tool returned far more than the window can hold. In our case a command-line security tool, run
without a TTY, printed a progress line for every dictionary word it tried: 8,349 lines, about 380 KB. The harness
kept the head and tail (about 51K characters), which made the next request **40,650 tokens against a 32,768
window**. Compaction itself needs to send the history to the model, so it failed too. Soft compaction ran three
times, the last cut off at its length limit, and the session was dead. The tool's quiet flag (`-v 0`) didn't
help (still 376 KB).

**Fix.**
- Filter noisy output at the source. Piping through `grep -v "<progress line pattern>"` took that same call to
  about 4.5–9K characters with the results intact. We pretested it 3 times; all 3 worked, with one correct call
  each time.
- Set the harness's tool-output cap (if it has one) well under your window. Truncating head and tail is not
  enough if what's left still doesn't fit.
- Prefer tools and flags that print results, not progress.

After the filter, the same full session peaked at about 17.7K of 32K, auto-compaction ran cleanly, and the
heavy step finished at about 16.4K.

A related, quieter failure: when a ~20K-token output was truncated by the harness, the model lost part of the
result. It reported the gap honestly, but the data was gone.

### 3. History

Prompt caching makes long histories cheap in time (cached turns prefill in under a second), but not in space.
Every turn stays in the window until the harness compacts. Know when your harness compacts and make sure
compaction can run before the window is full.

## Other hurdles

### Inherited instruction files (hurdle 25)

**Symptom.** The model follows instructions you didn't give it, or reads files you didn't point it at.

**Cause.** Many harnesses load every `AGENTS.md` / `CLAUDE.md`-style file up the directory tree from where you
start them, and the model will also list and read files in its working directory.

**Fix.** Start the agent from a clean, dedicated folder. Put only what you want it to see there. Keep notes,
old scripts and test fixtures out of it.

### Single slot vs harness side calls (hurdle 26)

**Symptom.** The main request waits before it starts, with nothing visible running.

**Cause.** The server runs one slot (`-np 1`) so the whole context goes to one conversation. Harnesses make
background calls (session title generation and similar) that queue behind the main request.

**Fix.** Turn title generation off, or route side calls to another model.

### Thinking mode (hurdle 27)

**Symptom.** Slow turns, context filling faster than expected.

**Cause.** With thinking on, this 4B model spends 300–2,600 characters reasoning per turn. In our shoot-out a
different 4B model with thinking on took 41 s per knowledge item and exceeded a 4K-token budget on 7 of 12.

**Fix.** Thinking off for agent loops. All our evals ran with it off. With llama.cpp you can pass
`"chat_template_kwargs": {"enable_thinking": false}` per request; check how your harness exposes it.

### Non-interactive runs hang (hurdle 28)

**Symptom.** A scripted, non-interactive harness run never finishes.

**Cause.** The harness waits on stdin.

**Fix.** Redirect it: `your-harness ... </dev/null`.

### Small models chain poorly (hurdle 29)

A 4B model handles a single tool step well: pick the tool, set the flags, read the output, recover from one bad
flag. It does poorly on long stateful chains across shells (log in, carry a token, set a cookie, reuse a
session): it skips a step, everything after it fails, and it doesn't notice. It can also write a summary that
reports intended actions as done. Give it one obvious tool per step (a script that does the stateful part, not a
quoting puzzle), keep a human on the steps that carry state, and check its write-ups against what actually ran.

## Keeping "local" honest

Some harnesses add cloud features by default: web search, an advisor model, a second model for side calls.
Those change the result. In our runs a cloud web search tool refused lookups, and a cloud advisor both rescued
the local model on one step and stopped it on another. If you want to claim the local model did the work,
turn the cloud add-ons off and say so.

## Done when

- `/v1/models` from the harness machine shows `nemotron-bolt-e4b`.
- You know your harness's base prompt cost in tokens.
- Tool output is capped or filtered below what the window can hold.
- A multi-turn, tool-using session completes without a compaction error.
