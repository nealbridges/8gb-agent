# spec_bench.py - generation speed (and draft acceptance, if speculative decoding is on) on agent-shaped outputs
# usage: python3 spec_bench.py <label> [base_url] [--temp T]
import os, json, sys, time, urllib.request
label = sys.argv[1]
base = next((a for a in sys.argv[2:] if a.startswith("http")), os.environ.get("LLM_URL", "http://YOUR-BOX:8080"))
temp = float(sys.argv[sys.argv.index("--temp") + 1]) if "--temp" in sys.argv else 0.0

def post(body):
    t = time.time()
    req = urllib.request.Request(base + "/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900)), time.time() - t

NMAP = "\n".join(f"10.0.0.{i}: 22/tcp ssh OpenSSH 8.{i % 10}p1; 80/tcp http nginx 1.2{i % 7}.0; 443/tcp https nginx" for i in range(1, 41))
PROMPTS = [
    "Write a pentest finding for an exposed Tomcat manager (10.30.0.7:8080, Tomcat 9.0.30, default creds tomcat/tomcat). "
    "Sections: Title, Severity, Affected Asset, Description, Evidence, Impact, Remediation. About 300 words.",
    "Summarize this scan as a markdown table with columns host | ssh version | web server, one row per host:\n" + NMAP,
    "Explain, as a numbered checklist of 15 items, how to harden an internet-facing nginx reverse proxy.",
    "Convert this to JSON, an array of objects with keys host, ports (array of ints), services (array of strings):\n" + NMAP[:1500],
]
tot_n = tot_s = dn = da = 0
for i, p in enumerate(PROMPTS, 1):
    d, dt = post({"messages": [{"role": "user", "content": p}], "max_tokens": 700, "temperature": temp, "top_p": 0.95,
                  "chat_template_kwargs": {"enable_thinking": False}})
    t = d.get("timings", {})
    n, ms = t.get("predicted_n", 0), t.get("predicted_ms", 1)
    tot_n += n; tot_s += ms / 1000
    dn += t.get("draft_n", 0) or 0; da += t.get("draft_n_accepted", 0) or 0
    acc = f"  draft {t.get('draft_n_accepted')}/{t.get('draft_n')}" if t.get("draft_n") else ""
    print(f"P{i}  {n:4} tok  {n / (ms / 1000):6.1f} tok/s{acc}")
print("SUMMARY " + json.dumps({"label": label, "temp": temp, "gen_tok": tot_n, "gen_tps": round(tot_n / tot_s, 1),
                               "accept_rate": round(da / dn, 3) if dn else None}))
