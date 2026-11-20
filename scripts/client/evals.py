# evals.py - S-tier initial pass: tool-calling + security-knowledge probe against a llama-server.
# usage: python3 evals.py <label> [base_url] [--think]   -> prints per-item lines + a summary JSON row
import os, json, re, sys, time, urllib.request

label = sys.argv[1]
base = next((a for a in sys.argv[2:] if a.startswith("http")), os.environ.get("LLM_URL", "http://YOUR-BOX:8080"))
think = "--think" in sys.argv

def post(body, timeout=600):
    t = time.time()
    req = urllib.request.Request(base + "/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout)), time.time() - t

KW = {"temperature": 0.0, "chat_template_kwargs": {"enable_thinking": think}}

def fn(name, desc, props, req):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": req}}}

S = {"type": "string"}; B = {"type": "boolean"}; I = {"type": "integer"}
TOOLS = [
    fn("run_nmap", "Run an nmap scan against a host or CIDR",
       {"target": S, "ports": {"type": "string", "description": "e.g. 1-1000 or 22,80,443"}, "service_detection": B, "udp": B}, ["target"]),
    fn("run_nuclei", "Run nuclei templates against a URL",
       {"url": S, "tags": {"type": "string", "description": "comma-separated template tags, e.g. cve,rce"}, "severity": {"type": "string", "enum": ["info", "low", "medium", "high", "critical"]}}, ["url"]),
    fn("http_request", "Send one HTTP request and return status, headers and body",
       {"method": {"type": "string", "enum": ["GET", "POST", "HEAD", "PUT", "DELETE"]}, "url": S, "headers": {"type": "object"}, "body": S}, ["method", "url"]),
    fn("lookup_cve", "Fetch the NVD record for a CVE ID", {"cve_id": S}, ["cve_id"]),
    fn("dns_lookup", "Resolve DNS records for a name", {"name": S, "record_type": {"type": "string", "enum": ["A", "AAAA", "MX", "TXT", "NS", "CNAME"]}}, ["name"]),
    fn("read_file", "Read a text file from the engagement workspace", {"path": S, "max_lines": I}, ["path"]),
]

def a(args, k): return str(args.get(k, "")).lower()

# (id, user prompt, check(name, args) -> bool | None for expect-no-tool)
TOOLCASES = [
    ("T01", "Scan 10.0.0.5 ports 22,80,443 with service version detection.",
     lambda n, x: n == "run_nmap" and x.get("target") == "10.0.0.5" and all(p in a(x, "ports") for p in ("22", "80", "443")) and x.get("service_detection") in (True, "true")),
    ("T02", "Do a UDP scan of 192.168.4.0/24 on port 161.",
     lambda n, x: n == "run_nmap" and "192.168.4.0/24" in a(x, "target") and "161" in a(x, "ports") and x.get("udp") in (True, "true")),
    ("T03", "Run nuclei against https://app.example.test with only critical-severity CVE templates.",
     lambda n, x: n == "run_nuclei" and "app.example.test" in a(x, "url") and a(x, "severity") == "critical" and "cve" in a(x, "tags")),
    ("T04", "What's the NVD entry for CVE-2024-3400?",
     lambda n, x: n == "lookup_cve" and a(x, "cve_id") == "cve-2024-3400"),
    ("T05", "Get the MX records for example.org.",
     lambda n, x: n == "dns_lookup" and a(x, "name").rstrip(".") == "example.org" and a(x, "record_type") == "mx"),
    ("T06", "Send a HEAD request to https://portal.example.test/login and show me the headers.",
     lambda n, x: n == "http_request" and a(x, "method") == "head" and "portal.example.test/login" in a(x, "url")),
    ("T07", "POST the JSON {\"user\":\"admin\"} to https://api.example.test/v1/reset with Content-Type application/json.",
     lambda n, x: n == "http_request" and a(x, "method") == "post" and "/v1/reset" in a(x, "url") and "admin" in a(x, "body") and "application/json" in json.dumps(x.get("headers", {})).lower()),
    ("T08", "Open notes/scope.txt from the workspace, first 50 lines only.",
     lambda n, x: n == "read_file" and "notes/scope.txt" in a(x, "path") and str(x.get("max_lines")) == "50"),
    ("T09", "Check whether TXT records for _dmarc.example.com exist.",
     lambda n, x: n == "dns_lookup" and "_dmarc.example.com" in a(x, "name") and a(x, "record_type") == "txt"),
    ("T10", "Full TCP port sweep, all 65535 ports, on host db01.corp.test. No version detection.",
     lambda n, x: n == "run_nmap" and "db01.corp.test" in a(x, "target") and ("65535" in a(x, "ports") or a(x, "ports") in ("-", "1-65535", "all", "p-")) and x.get("service_detection") in (None, False, "false")),
    # no-tool cases: answering directly is correct; a tool call is a miss
    ("N01", "In one sentence, what is the difference between a SYN scan and a connect scan?", None),
    ("N02", "Thanks, that's all for now.", None),
]

# Two-step chains: model sees a tool result and must issue the right follow-up call
CHAINS = [
    ("C01", "Find what's running on 10.0.0.9 and then check any CVE you find.",
     ("run_nmap", {"target": "10.0.0.9"}),
     "PORT    STATE SERVICE VERSION\n443/tcp open  https   Palo Alto GlobalProtect (PAN-OS 11.1.2) -- known vulnerable: CVE-2024-3400",
     lambda n, x: n == "lookup_cve" and a(x, "cve_id") == "cve-2024-3400"),
    ("C02", "Resolve shop.example.test and then scan its web ports 80 and 443.",
     ("dns_lookup", {"name": "shop.example.test", "record_type": "A"}),
     "shop.example.test. 300 IN A 203.0.113.44",
     lambda n, x: n == "run_nmap" and "203.0.113.44" in a(x, "target") or (n == "run_nmap" and "shop.example.test" in a(x, "target") and "80" in a(x, "ports"))),
    ("C03", "Read targets.txt and run nuclei against the first URL in it.",
     ("read_file", {"path": "targets.txt"}),
     "https://intranet.example.test\nhttps://vpn.example.test\n",
     lambda n, x: n == "run_nuclei" and "intranet.example.test" in a(x, "url")),
]

# Short knowledge probe: answer must match regex (case-insensitive)
KNOW = [
    ("K01", "Which TCP port does SMB use by default? Answer with the number only.", r"\b445\b"),
    ("K02", "What is the common name for CVE-2021-44228? Answer in two words or fewer.", r"log4shell|log4j"),
    ("K03", "Which CWE ID is SQL injection? Answer with the ID only.", r"cwe-?89\b|^\s*89\b"),
    ("K04", "Which CWE ID is cross-site scripting? Answer with the ID only.", r"cwe-?79\b|^\s*79\b"),
    ("K05", "What default TCP port does RDP listen on? Number only.", r"\b3389\b"),
    ("K06", "In Kerberoasting, what kind of Kerberos ticket does the attacker request to crack offline? Answer in a few words.", r"\btgs\b|service ticket"),
    ("K07", "What is the maximum CVSS v3.1 base score? Number only.", r"\b10(\.0)?\b"),
    ("K08", "Which HTTP status code means the client is authenticated but not permitted? Number only.", r"\b403\b"),
    ("K09", "Which MITRE ATT&CK technique ID is OS Credential Dumping: LSASS Memory? ID only.", r"t1003\.001"),
    ("K10", "Which Windows Event ID records a successful account logon? Number only.", r"\b4624\b"),
    ("K11", "What nmap flag enables OS detection? Flag only.", r"(?-i:-O)\b"),
    ("K12", "What is the vulnerability class of CVE-2014-0160 (Heartbleed)? A few words.", r"(buffer )?over-?read|memory disclosure|out-of-bounds read|information disclosure"),
]

def tool_call(msg):
    tc = msg.get("tool_calls") or []
    if not tc: return None, None
    f = tc[0]["function"]
    try: args = json.loads(f.get("arguments") or "{}")
    except Exception: args = {"__unparsed__": f.get("arguments")}
    return f.get("name"), args

res = {"label": label, "think": think, "tool": 0, "tool_n": 0, "chain": 0, "chain_n": 0, "know": 0, "know_n": 0,
       "parse_fail": 0, "lat": [], "tps": []}

def timing(d, dt):
    res["lat"].append(dt)
    t = d.get("timings", {})
    if t.get("predicted_per_second"): res["tps"].append(t["predicted_per_second"])

for cid, prompt, check in TOOLCASES:
    d, dt = post({"messages": [{"role": "user", "content": prompt}], "tools": TOOLS, "max_tokens": 4096 if think else 512, **KW})
    timing(d, dt)
    n, x = tool_call(d["choices"][0]["message"])
    if x and "__unparsed__" in x: res["parse_fail"] += 1
    ok = (n is None) if check is None else bool(n and x and check(n, x))
    res["tool"] += ok; res["tool_n"] += 1
    shown = f"{n} {json.dumps(x)}" if n else "(no tool) " + (d["choices"][0]["message"].get("content") or "")[:80].replace("\n", " ")
    print(f"{cid} {'PASS' if ok else 'FAIL'} {dt:5.1f}s  {shown[:160]}")

for cid, prompt, (n1, a1), result, check in CHAINS:
    msgs = [{"role": "user", "content": prompt},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": n1, "arguments": json.dumps(a1)}}]},
            {"role": "tool", "tool_call_id": "call_1", "content": result}]
    d, dt = post({"messages": msgs, "tools": TOOLS, "max_tokens": 4096 if think else 512, **KW})
    timing(d, dt)
    n, x = tool_call(d["choices"][0]["message"])
    ok = bool(n and x and "__unparsed__" not in x and check(n, x))
    res["chain"] += ok; res["chain_n"] += 1
    shown = f"{n} {json.dumps(x)}" if n else "(no tool) " + (d["choices"][0]["message"].get("content") or "")[:80].replace("\n", " ")
    print(f"{cid} {'PASS' if ok else 'FAIL'} {dt:5.1f}s  {shown[:160]}")

for cid, prompt, rx in KNOW:
    d, dt = post({"messages": [{"role": "user", "content": prompt}], "max_tokens": 4096 if think else 64, **KW})
    timing(d, dt)
    txt = (d["choices"][0]["message"].get("content") or "").strip()
    ok = re.search(rx, txt, re.I | re.M) is not None
    res["know"] += ok; res["know_n"] += 1
    print(f"{cid} {'PASS' if ok else 'FAIL'} {dt:5.1f}s  {txt[:100]!r}")

lat = sorted(res.pop("lat")); tps = res.pop("tps")
res["lat_p50"] = round(lat[len(lat) // 2], 2); res["lat_max"] = round(lat[-1], 2)
res["gen_tps_mean"] = round(sum(tps) / len(tps), 1) if tps else None
print("SUMMARY " + json.dumps(res))
