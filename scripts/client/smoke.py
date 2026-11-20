import os, json, sys, time, urllib.request
base = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("LLM_URL", "http://YOUR-BOX:8080")
def post(body):
    t = time.time()
    r = urllib.request.urlopen(urllib.request.Request(base + "/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=300)
    return json.load(r), time.time() - t
kw = {"chat_template_kwargs": {"enable_thinking": False}, "temperature": 0.2}
# 1) chat round-trip
d, dt = post({"messages": [{"role": "user", "content": "In one sentence: what does nmap -sV do?"}], "max_tokens": 80, **kw})
print("CHAT  %.2fs  %s" % (dt, d["choices"][0]["message"]["content"].strip()[:200]))
print("      timings:", {k: round(v, 1) for k, v in d.get("timings", {}).items() if k in ("prompt_per_second", "predicted_per_second", "predicted_n")})
# 2) tool call
tools = [{"type": "function", "function": {"name": "run_nmap", "description": "Run an nmap scan against a target host",
          "parameters": {"type": "object", "properties": {"target": {"type": "string", "description": "IP or hostname"},
          "ports": {"type": "string", "description": "port spec, e.g. 1-1000 or 22,80,443"},
          "service_detection": {"type": "boolean"}}, "required": ["target"]}}}]
d, dt = post({"messages": [{"role": "user", "content": "Scan 10.0.0.5 ports 22,80,443 with service version detection."}], "tools": tools, "max_tokens": 200, **kw})
m = d["choices"][0]["message"]
tc = m.get("tool_calls") or []
if tc:
    f = tc[0]["function"]; args = json.loads(f["arguments"])
    ok = f["name"] == "run_nmap" and args.get("target") == "10.0.0.5" and "22" in str(args.get("ports", "")) and args.get("service_detection") in (True, "true")
    print("TOOL  %.2fs  %s %s  -> %s" % (dt, f["name"], json.dumps(args), "PASS" if ok else "PARTIAL"))
else:
    print("TOOL  %.2fs  NO TOOL CALL. content=%r" % (dt, (m.get("content") or "")[:200]))
