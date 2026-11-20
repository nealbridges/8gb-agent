# 03. Remote access and running headless

**Done when:** SSH works from another machine and the console is signed out.

Tested on 2026-11-12.

The goal: the GPU box sits with nobody signed in, reachable only over your private network, and you drive
everything over SSH. That saves VRAM ([02](02-windows-prep.md), hurdle 7) and keeps an unauthenticated model
server off your LAN.

## The layout

| Piece | Choice | Why |
|---|---|---|
| Private network | Tailscale on the GPU box and on each client | Works through NAT, gives the box a stable address in `100.64.0.0/10` |
| Shell | Windows OpenSSH Server, key-only for an admin account | Everything after this point runs over SSH |
| Model server | llama-server bound to the box's Tailscale IP, port 8080 | Never `0.0.0.0` |
| Firewall | Inbound rule for the server ports, remote address `100.64.0.0/10` only | The server has no auth |
| Desktop | Signed out. RDP only for GUI-only steps, then sign out | VRAM |

Install Tailscale from its website on the box, sign it in, and set it to run unattended so it stays up with no
user signed in. Then:

1. Run `scripts/windows/setup-ssh.ps1` from an **elevated** PowerShell window. It installs and starts the
   OpenSSH Server, opens TCP 22, installs your public key in the admin key file, and fixes that file's ACL.
2. Run `scripts/windows/firewall-tailnet.ps1` to open the llama-server port(s) to the Tailscale range only.
3. From another machine on your tailnet: `ssh you@YOUR-BOX`.
4. Sign out of the console and any RDP session.

`setup-ssh.ps1` opens port 22 on all network profiles. If the box sits on a network you don't fully control,
scope that rule to `100.64.0.0/10` as well.

## Hurdle 12: admin SSH keys go in a different file

- **Symptom:** key auth fails for your account even though the key is in `C:\Users\you\.ssh\authorized_keys`.
  sshd doesn't say why; it just ignores the key.
- **Cause:** for accounts in the Administrators group, Windows OpenSSH ignores the per-user file and reads only
  `C:\ProgramData\ssh\administrators_authorized_keys`. It also silently ignores that file unless only
  Administrators and SYSTEM have access to it.
- **Fix:** put the key in `C:\ProgramData\ssh\administrators_authorized_keys` and lock the ACL:

  ```powershell
  icacls C:\ProgramData\ssh\administrators_authorized_keys /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"
  ```

  `setup-ssh.ps1` does this using the well-known SIDs (`*S-1-5-32-544` and `*S-1-5-18`), so it also works on
  non-English Windows. It writes the per-user file too, in case the account isn't an admin.
- **How we proved it:** key-only SSH from another machine worked after the ACL change.

## Hurdle 13: CUDA from an SSH session (don't panic)

- **Symptom (feared, not seen):** older forum reports (2015–2023) show `CUDA_ERROR_NO_DEVICE` when CUDA programs
  run from SSH or a Windows service, because sshd runs in session 0 with no desktop. If that were still true, you
  would need autologon and a "run at log on" task, or WSL2.
- **Cause:** older driver behaviour.
- **Fix:** none needed on current drivers. Serve from a scheduled task running as SYSTEM, with nobody signed in.
  You do **not** need autologon.
- **How we proved it:** rebooted the box, left it at the sign-in screen, and over SSH ran `nvidia-smi` and
  `llama-cli --list-devices`. Both saw the card. The SYSTEM scheduled task then served models with nobody signed
  in, using 96 MiB of VRAM at idle. Tested on Studio driver 621.14.

## Hurdle 14: bind to the tailnet IP and scope the firewall

- **Symptom:** none, which is the problem. llama-server will happily listen on every interface.
- **Cause:** llama-server has no authentication by default. Anyone who can reach the port can use the model.
  `--host 0.0.0.0` on a home or office LAN exposes it to every device on that network.
- **Fix:** two layers.
  - Bind to the box's Tailscale address only. `serve.ps1` looks it up at start:
    `& 'C:\Program Files\Tailscale\tailscale.exe' ip -4`, then passes it as `--host`.
  - Allow the server port(s) inbound only from `100.64.0.0/10`. The core of `firewall-tailnet.ps1`:

    ```powershell
    New-NetFirewallRule -DisplayName 'llm-server (tailnet only)' -Direction Inbound -Protocol TCP `
        -LocalPort 8080-8089 -RemoteAddress 100.64.0.0/10 -Action Allow
    ```

    We opened 8080–8089 so several servers can run side by side during testing. Open just 8080 if you only
    serve one. Apply the same scoping to RDP if you leave it on.
- **How we proved it:** the endpoint answers at `http://YOUR-BOX:8080` from machines on the tailnet. We did not
  run a separate test from a LAN-only device.

Tailscale's `100.64.0.0/10` is the shared CGNAT range. Scoping to it means "my tailnet", not "the internet", as
long as nothing else on your network uses that range.

## Checklist

- [ ] Tailscale running unattended on the GPU box
- [ ] `ssh you@YOUR-BOX` works with a key, from another machine
- [ ] Over SSH, with nobody signed in: `nvidia-smi` lists the card
- [ ] Firewall rule for 8080 (or 8080–8089) scoped to `100.64.0.0/10`
- [ ] Console and RDP signed out
