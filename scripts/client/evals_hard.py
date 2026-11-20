# evals_hard.py - S-tier discriminator: needle-in-long-tool-output + scripted multi-turn agent loop.
# usage: python3 evals_hard.py <label> [base_url]
import os, json, random, sys, time, urllib.request
sys.path.insert(0, __file__.rsplit("/", 1)[0])
label = sys.argv[1]
base = next((a for a in sys.argv[2:] if a.startswith("http")), os.environ.get("LLM_URL", "http://YOUR-BOX:8080"))

def post(body):
    t = time.time()
    req = urllib.request.Request(base + "/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900)), time.time() - t

KW = {"temperature": 0.0, "max_tokens": 512, "chat_template_kwargs": {"enable_thinking": False}}
def fn(n, d, p, r): return {"type": "function", "function": {"name": n, "description": d, "parameters": {"type": "object", "properties": p, "required": r}}}
S = {"type": "string"}
TOOLS = [fn("run_nmap", "Run an nmap scan", {"target": S, "ports": S}, ["target"]),
         fn("lookup_cve", "Fetch the NVD record for a CVE ID", {"cve_id": S}, ["cve_id"]),
         fn("http_request", "Send one HTTP request", {"method": S, "url": S}, ["method", "url"]),
         fn("write_finding", "Record a confirmed finding in the report", {"host": S, "title": S, "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]}, "evidence": S}, ["host", "title", "severity"]),
         fn("finish", "End the engagement with a short summary", {"summary": S}, ["summary"])]

SERVICES = [("22/tcp", "ssh", "OpenSSH 9.6p1"), ("80/tcp", "http", "nginx 1.26.2"), ("443/tcp", "https", "nginx 1.26.2"),
            ("3306/tcp", "mysql", "MySQL 8.0.39"), ("8080/tcp", "http-proxy", "Jetty 12.0.14"), ("25/tcp", "smtp", "Postfix smtpd"),
            ("53/tcp", "domain", "ISC BIND 9.18.28"), ("5432/tcp", "postgresql", "PostgreSQL 16.4"), ("6379/tcp", "redis", "Redis 7.4.1 (protected mode)")]

def nmap_dump(n_hosts, needle_at, seed):
    r = random.Random(seed); out = ["Starting Nmap 7.95 ( https://nmap.org )"]
    for i in range(n_hosts):
        ip = f"10.20.{i // 250}.{i % 250 + 1}"
        out.append(f"Nmap scan report for {ip}\nHost is up (0.00{r.randint(10, 99)}s latency).\nPORT      STATE SERVICE    VERSION")
        for p, s, v in r.sample(SERVICES, r.randint(2, 5)):
            out.append(f"{p:<9} open  {s:<10} {v}")
        if i == needle_at:
            out.append("8443/tcp  open  https      Ivanti Connect Secure 22.7R2.3 -- VULNERABLE: CVE-2025-0282 (pre-auth stack overflow)")
        out.append("")
    out.append(f"Nmap done: {n_hosts} IP addresses ({n_hosts} hosts up)")
    return "\n".join(out), f"10.20.{needle_at // 250}.{needle_at % 250 + 1}"

score = {"label": label, "needle": [], "loop": None, "lat": []}

# 1) needle in long tool output at roughly 2K / 8K / 20K tokens, needle early / middle / late
for n_hosts in (25, 100, 250):
    for pos in ("early", "mid", "late"):
        at = {"early": 2, "mid": n_hosts // 2, "late": n_hosts - 3}[pos]
        dump, ip = nmap_dump(n_hosts, at, seed=n_hosts * 7 + at)
        msgs = [{"role": "system", "content": "You are a pentest assistant on an authorized engagement. Use tools; one call per turn."},
                {"role": "user", "content": "Sweep 10.20.0.0/22 and then look up any CVE the scan flags."},
                {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "run_nmap", "arguments": json.dumps({"target": "10.20.0.0/22"})}}]},
                {"role": "tool", "tool_call_id": "c1", "content": dump}]
        d, dt = post({"messages": msgs, "tools": TOOLS, **KW})
        tc = (d["choices"][0]["message"].get("tool_calls") or [{}])[0].get("function", {})
        args = json.loads(tc.get("arguments") or "{}") if tc else {}
        ok = tc.get("name") == "lookup_cve" and str(args.get("cve_id", "")).upper() == "CVE-2025-0282"
        ptok = d.get("usage", {}).get("prompt_tokens")
        score["needle"].append(ok); score["lat"].append(dt)
        print(f"NEEDLE {ptok:>6} tok {pos:<5} {'PASS' if ok else 'FAIL'} {dt:5.1f}s  {tc.get('name')} {json.dumps(args)[:90]}")

# 2) scripted 5-step agent loop: model drives; we answer each expected tool with canned output
SCRIPT = [("run_nmap", lambda a: "10.30.0.7" in a.get("target", ""),
           "PORT     STATE SERVICE VERSION\n22/tcp   open  ssh     OpenSSH 9.6p1\n8080/tcp open  http    Apache Tomcat 9.0.30 (manager app exposed)"),
          ("http_request", lambda a: "10.30.0.7:8080" in a.get("url", "") and "manager" in a.get("url", ""),
           "HTTP/1.1 401 Unauthorized\nWWW-Authenticate: Basic realm=\"Tomcat Manager Application\"\nServer: Apache-Coyote/1.1"),
          ("lookup_cve", lambda a: a.get("cve_id", "").upper() == "CVE-2020-1938",
           "CVE-2020-1938 (Ghostcat): AJP connector file read/inclusion in Tomcat < 9.0.31. CVSS 9.8. Requires AJP port 8009 reachable."),
          ("write_finding", lambda a: "10.30.0.7" in a.get("host", "") and a.get("severity") in ("high", "critical", "medium"),
           "finding recorded: F-001"),
          ("finish", lambda a: bool(a.get("summary")), "")]
msgs = [{"role": "system", "content": "You are a pentest assistant on an authorized engagement. Use exactly one tool call per turn. "
         "Plan: scan the host, probe any web admin interface you find, look up the CVE for the exact version, record a finding, then finish."},
        {"role": "user", "content": "Target is 10.30.0.7. Tomcat 9.0.30 is affected by Ghostcat (CVE-2020-1938) if confirmed; check it and report."}]
steps = 0
for i, (want, check, result) in enumerate(SCRIPT):
    d, dt = post({"messages": msgs, "tools": TOOLS, **KW}); score["lat"].append(dt)
    m = d["choices"][0]["message"]; tc = (m.get("tool_calls") or [{}])[0].get("function", {})
    args = json.loads(tc.get("arguments") or "{}") if tc else {}
    ok = tc.get("name") == want and check(args)
    print(f"LOOP {i + 1} want {want:<13} got {str(tc.get('name')):<13} {'PASS' if ok else 'FAIL'} {dt:4.1f}s {json.dumps(args)[:90]}")
    if not ok: break
    steps += 1
    msgs.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": [{"id": f"s{i}", "type": "function", "function": {"name": want, "arguments": json.dumps(args)}}]})
    msgs.append({"role": "tool", "tool_call_id": f"s{i}", "content": result or "ok"})
score["loop"] = f"{steps}/{len(SCRIPT)}"
lat = score.pop("lat")
print("SUMMARY " + json.dumps({"label": label, "needle": f"{sum(score['needle'])}/{len(score['needle'])}", "loop": score["loop"], "lat_total_s": round(sum(lat), 1)}))
