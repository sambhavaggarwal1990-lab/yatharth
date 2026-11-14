#!/usr/bin/env python3
"""Yatharth model doctor.

1) tests which Gemini models really answer for your key,
2) tests the same models through Bifrost,
3) writes the working model names into .env.

Run it from the yatharth folder:   python3 fix_models.py
"""
import getpass
import json
import os
import sys
import subprocess
import time

GEM = os.environ.get("YATHARTH_GEMINI_BASE", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
BIFROST = "http://localhost:8080/openai"
FAST = ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite", "gemini-3.5-flash-lite"]
STRONG = ["gemini-3.8-flash", "gemini-3.5-flash"]


def find_env():
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (".env", os.path.join(here, ".env"), os.path.join(here, "yatharth", ".env"),
              os.path.expanduser("~/Downloads/yatharth/.env")):
        if os.path.exists(p):
            return p
    sys.exit("`.env` file nahi mili. Is script ko `yatharth` folder (jisme backend/ aur frontend/ hain) mein chalao.")


def read_env(path):
    d = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def set_env(path, updates):
    lines = open(path).read().splitlines()
    done = set()
    for i, line in enumerate(lines):
        k = line.split("=", 1)[0].strip()
        if not line.lstrip().startswith("#") and k in updates:
            lines[i] = f"{k}={updates[k]}"
            done.add(k)
    lines += [f"{k}={v}" for k, v in updates.items() if k not in done]
    open(path, "w").write("\n".join(lines) + "\n")


def ping(base, model, key, timeout):
    """Uses the system `curl` (Mac Python often lacks SSL certificates, curl does not)."""
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "Reply with the single word: ok"}]})
    cfg = (f'url = "{base}/chat/completions"\nheader = "Content-Type: application/json"\n'
           f'header = "Authorization: Bearer {key}"\ndata = {json.dumps(body)}\n')  # config via stdin keeps the key off the process list
    t0 = time.time()
    try:
        p = subprocess.run(["curl", "-sS", "-m", str(timeout), "-K", "-", "-w", "\n%{http_code}"],
                           input=cfg, capture_output=True, text=True, timeout=timeout + 10)
    except Exception as e:
        return 0, str(e)[:160], time.time() - t0
    text, _, code = p.stdout.rpartition("\n")
    code = int(code) if code.strip().isdigit() else 0
    if code:
        return code, text[:160].replace("\n", " "), time.time() - t0
    why = {7: "Connection refused", 28: "timed out"}.get(p.returncode, p.stderr.strip()[:160] or "no response")
    return 0, why, time.time() - t0


def main():
    path = find_env()
    env = read_env(path)
    key = os.environ.get("GEMINI_KEY") or getpass.getpass("Gemini API key paste karo (screen pe nahi dikhegi): ").strip()

    print("\n1) Google ke saath seedha test")
    ok = {}
    for m in FAST + STRONG:
        s, why, t = ping(GEM, m, key, 25)
        print(f"   {m:24} {'OK  ' if s == 200 else 'FAIL'} {t:5.1f}s  {'' if s == 200 else f'[{s}] {why}'}")
        if s == 200:
            ok[m] = t
    if not ok:
        sys.exit("\nKoi model nahi chala. Key galat hai ya quota khatam hai (aistudio.google.com pe check karo).")
    fast = min((m for m in FAST if m in ok), key=ok.get, default=min(ok, key=ok.get))
    strong = next((m for m in STRONG if m in ok and ok[m] < 15), fast)
    print(f"\n   Chuna gaya: fast = {fast}, strong = {strong}")

    direct_now = "googleapis" in env.get("BIFROST_BASE_URL", "")
    bkey = "bifrost" if direct_now else env.get("BIFROST_API_KEY", "bifrost")
    print(f"\n2) Bifrost ke through test ({BIFROST})")
    bad = None
    for m in dict.fromkeys([fast, strong]):
        s, why, t = ping(BIFROST, "gemini/" + m, bkey, 60)
        print(f"   gemini/{m:24} {'OK  ' if s == 200 else 'FAIL'} {t:5.1f}s  {'' if s == 200 else f'[{s}] {why}'}")
        if s != 200:
            bad = (s, why)

    tk = env.get("TAVILY_API_KEY", "")
    if not tk.startswith("tvly-"):
        print("\n!  .env mein TAVILY_API_KEY sahi nahi lag rahi (wo `tvly-` se shuru hoti hai). Use bhi theek karo.")

    if not bad:
        upd = {"EXTRACT_MODEL": "gemini/" + fast, "JUDGE_MODEL": "gemini/" + strong, "VISION_MODEL": "gemini/" + strong}
        if direct_now:
            upd.update(BIFROST_BASE_URL=BIFROST, BIFROST_API_KEY="bifrost")
        set_env(path, upd)
        print("\nDONE: Bifrost + Gemini dono chal rahe hain. `.env` update ho gayi.")
        print("Ab backend terminal mein Ctrl+C dabao, phir chalao:  python3 -m uvicorn main:app --reload --port 8000")
        return

    s, why = bad
    print("\nBifrost mein dikkat hai, Google theek hai.")
    if s == 0 and "refused" in why.lower():
        print("-> Bifrost chal hi nahi raha. Uske terminal mein chalao: npx -y @maximhq/bifrost")
    elif s == 0:
        print("-> Google jaldi jawab de raha hai par Bifrost atak raha hai. http://localhost:8080 kholo -> Providers -> Gemini:")
        print("   key dobara daalo aur Allowed Models = All Models karo.")
    elif s in (401, 403):
        print("-> Bifrost ne mana kiya (auth). Bifrost ki Security settings mein 'Enforce Virtual Keys on Inference' OFF karo.")
    else:
        print("-> Bifrost ke Gemini provider ki key aur Allowed Models check karo.")
    ans = input("\nAbhi ke liye Bifrost ke bina seedha Gemini se app chalayein (sirf test ke liye)? [y/n]: ").strip().lower()
    if ans == "y":
        set_env(path, {"BIFROST_BASE_URL": GEM, "BIFROST_API_KEY": key, "EXTRACT_MODEL": fast,
                       "JUDGE_MODEL": strong, "VISION_MODEL": strong})
        print("\n`.env` update ho gayi (seedha Gemini). Backend restart karo, app chalega.")
        print("YAAD RAKHO: demo video aur submission Bifrost ke through hi karo. Bifrost theek karke is script ko dobara chalao,")
        print("wo `.env` ko wapas Bifrost pe set kar dega.")


if __name__ == "__main__":
    main()
