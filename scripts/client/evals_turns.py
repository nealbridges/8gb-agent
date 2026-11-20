# evals_turns.py - per-turn prefill cost over a 10-turn agent loop (does the server reuse the prompt cache?)
# usage: python3 evals_turns.py <label> [base_url] [--hosts N]
import os, json, random, sys, time, urllib.request
label = sys.argv[1]
base = next((a for a in sys.argv[2:] if a.startswith("http")), os.environ.get("LLM_URL", "http://YOUR-BOX:8080"))
hosts = int(sys.argv[sys.argv.index("--hosts") + 1]) if "--hosts" in sys.argv else 100

def post(body):
    t = time.time()
    req = urllib.request.Request(base + "/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900)), time.time() - t

S = {"type": "string"}
TOOLS = [{"type": "function", "function": {"name": "http_request", "description": "Send one HTTP GET",
          "parameters": {"type": "object", "properties": {"url": S}, "required": ["url"]}}}]
r = random.Random(1)
dump = "\n".join(f"Nmap scan report for 10.20.{i // 250}.{i % 250 + 1}\n80/tcp open http nginx 1.26.{r.randint(0, 3)}\n"
                 f"443/tcp open https nginx\n8080/tcp open http-proxy Jetty 12.0.{r.randint(1, 14)}" for i in range(hosts))
msgs = [{"role": "system", "content": "You are a pentest assistant on an authorized engagement. One tool call per turn."},
        {"role": "user", "content": "Here is the sweep. Fetch http://<ip>:8080/ for each host in order, starting at the first, one per turn.\n\n" + dump}]
rows = []
for turn in range(1, 11):
    d, dt = post({"messages": msgs, "tools": TOOLS, "temperature": 0.0, "max_tokens": 128,
                  "chat_template_kwargs": {"enable_thinking": False}})
    t = d.get("timings", {})
    m = d["choices"][0]["message"]
    tc = (m.get("tool_calls") or [{}])[0].get("function", {"name": "none", "arguments": "{}"})
    rows.append((turn, d["usage"]["prompt_tokens"], t.get("prompt_n"), round(t.get("prompt_ms", 0)), round(dt, 2)))
    print(f"turn {turn:2}  ctx {d['usage']['prompt_tokens']:6}  prefilled {t.get('prompt_n'):6}  prefill {t.get('prompt_ms', 0):7.0f} ms  wall {dt:5.2f}s  {tc.get('name')} {tc.get('arguments')[:60]}")
    msgs.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": [{"id": f"t{turn}", "type": "function", "function": tc}]})
    msgs.append({"role": "tool", "tool_call_id": f"t{turn}", "content": "HTTP/1.1 200 OK\nServer: Jetty\n\n<html><title>Jenkins</title></html>"})
later = rows[1:]
print("SUMMARY " + json.dumps({"label": label, "ctx": rows[-1][1], "turn1_prefill_ms": rows[0][3],
      "mean_prefilled_tokens_turns2_10": round(sum(x[2] for x in later) / len(later)),
      "mean_wall_s_turns2_10": round(sum(x[4] for x in later) / len(later), 2)}))
