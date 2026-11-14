import os
import time
from collections import defaultdict, deque
from datetime import date

from dotenv import load_dotenv

load_dotenv()  # reads .env from the project root

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import APIConnectionError, AuthenticationError, PermissionDeniedError
from pydantic import BaseModel, Field

from claims import extract_claims
from extract import file_to_text
from verify import verify_claims
from verdict import judge, freshness_score

app = FastAPI(title="Yatharth")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def explain(e: Exception) -> HTTPException:
    """Turn Bifrost/LLM errors into a message the user can act on."""
    if isinstance(e, APIConnectionError):
        return HTTPException(502, "Cannot reach Bifrost. Start it with: npx -y @maximhq/bifrost")
    if isinstance(e, (AuthenticationError, PermissionDeniedError)):
        return HTTPException(502, "Bifrost refused the request (auth). In Bifrost, open Security settings and turn off 'Enforce Virtual Keys on Inference', or put a virtual key (sk-bf-...) in BIFROST_API_KEY in .env.")
    return HTTPException(502, f"Check failed: {e}")


_HITS = defaultdict(deque)
_DAY = {"day": date.today(), "count": 0}


def limit(request: Request):
    """Protects a public deployment from burning your API credits. Off locally; set the env vars on Render."""
    per10 = int(os.getenv("RATE_LIMIT_PER_10MIN", "0"))
    cap = int(os.getenv("DAILY_CAP", "0"))
    now = time.time()
    if _DAY["day"] != date.today():
        _DAY.update(day=date.today(), count=0)
    if cap and _DAY["count"] >= cap:
        raise HTTPException(429, "Daily demo limit reached. Please try again tomorrow.")
    if per10:
        ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()
        q = _HITS[ip]
        while q and now - q[0] > 600:
            q.popleft()
        if len(q) >= per10:
            raise HTTPException(429, "Too many checks from your network. Please wait a few minutes.")
        q.append(now)
    _DAY["count"] += 1


class CheckIn(BaseModel):
    answer_text: str = Field(min_length=10, max_length=8000)


@app.get("/api/health")
def health():
    return {"ok": True}


def run_check(answer_text: str) -> dict:
    try:
        claims = extract_claims(answer_text)  # 1. LLM via Bifrost
        risky = [c for c in claims if c["volatility"] == "high"][: int(os.getenv("MAX_CHECK", 6))]
        evidence = verify_claims(risky) if risky else {}  # 2. Tavily live search
        judged = judge(answer_text, risky, evidence) if risky else {"verdicts": {}, "corrected_answer": answer_text}  # 3. LLM via Bifrost
    except Exception as e:
        raise explain(e)

    risky_ids = {c["id"] for c in risky}
    out = []
    for c in claims:
        base = {"id": c["id"], "text": c["text"], "category": c["category"], "volatility": c["volatility"]}
        if c["id"] in risky_ids:
            v = judged["verdicts"].get(c["id"]) or {"verdict": "unverified", "why": "No verdict returned.", "corrected": None, "evidence": None}
            out.append({**base, **v})
        else:
            out.append({**base, "verdict": "not_checked", "why": "Stable fact, not checked.", "corrected": None, "evidence": None})

    return {
        "freshness_score": freshness_score(out),
        "claims": out,
        "corrected_answer": judged["corrected_answer"],
        "checked_on": date.today().isoformat(),
    }


@app.post("/api/check")
def check(body: CheckIn, _=Depends(limit)):
    return run_check(body.answer_text)


MAX_FILES, MAX_BYTES, MAX_CHARS = 3, 5 * 1024 * 1024, 8000


@app.post("/api/check-files")
def check_files(answer_text: str = Form(""), files: list[UploadFile] = File(default=[]), _=Depends(limit)):
    """Same check, but the answer can come from typed text and/or attached files."""
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"Attach at most {MAX_FILES} files.")
    parts = [answer_text.strip()] if answer_text.strip() else []
    try:
        for f in files:
            data = f.file.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise HTTPException(400, f"{f.filename} is larger than 5 MB.")
            parts.append(file_to_text(f.filename or "", data))
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except (APIConnectionError, AuthenticationError, PermissionDeniedError) as e:
        raise explain(e)
    except Exception as e:
        raise HTTPException(502, f"Could not read the file: {e}")
    text = "\n\n".join(p for p in parts if p)[:MAX_CHARS]
    if len(text) < 10:
        raise HTTPException(400, "Nothing to check. Type or paste an answer, or attach a file that has text in it.")
    return run_check(text)


# Serve the web page from the same server (open http://localhost:8000). Must stay last.
from pathlib import Path
from fastapi.staticfiles import StaticFiles

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
