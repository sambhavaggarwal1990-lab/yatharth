<p align="center"><img src="docs/logo.png" alt="Yatharth logo" width="160"></p>
<h1 align="center">Yatharth</h1>
<p align="center"><b>Every AI answer, checked for freshness.</b></p>
<p align="center">Built for the Global AI Hackathon by Geek Room · Powered by Bifrost and Tavily</p>

---

## The problem

AI models learn from data that stops at some date in the past. They still answer with full confidence about things that keep changing: prices, software versions, laws, fees, deadlines. Nothing tells the user how fresh an answer is.

- A developer follows an old API version and the code breaks.
- A support bot quotes last year's price or refund rule, and the company pays for it.
- A student or user acts on a rule that changed months ago.

## Our solution

Yatharth (यथार्थ) means "reality" or "truth" in Hindi. It takes any AI answer, finds the claims that tend to expire, checks them against the live web, and tells you what is still true.

Each claim gets one of three verdicts:

| Verdict | Meaning |
|---|---|
| Fresh | Matches a current, reliable source |
| Stale | Outdated. We show the correct value, the source link and its date |
| Unverified | No reliable proof found. Flagged, never guessed |

## Features

- **Claim extraction:** splits an answer into small, checkable facts.
- **Volatility tagging:** marks each fact as high or low risk (pricing, versions, regulations and dates are high).
- **Live verification:** only risky claims go to the web, which saves time and cost.
- **Verdict and correction:** per-claim result with evidence URL, date and the corrected value.
- **Freshness score:** one 0–100 number for the whole answer.
- **File attach:** type an answer, attach up to 3 files (.txt, .md, .pdf, .png, .jpg, .webp), or both.
- **Source trust badge:** each source is labelled Official, Official docs, News or Web.
- **Corrected answer:** a rewritten answer you can copy, plus a downloadable Markdown report.
- **Try-an-example buttons** for quick demos.
- **Animated cover screen** (canvas + sound) with a Skip button; it plays once per browser tab.
- **Model disagreement check (optional):** ask 2–3 models the same question; if they disagree, the fact is probably unstable.

## How it works

```
AI answer
   │
   ▼
1. Extract claims ──────────┐
2. Tag volatility ──────────┤  LLM calls go through Bifrost
   │ (high-risk claims only)│
   ▼                        │
3. Verify on the live web   │  Tavily search + extract
   │                        │
   ▼                        │
4. Verdict + corrected answer ┘  LLM via Bifrost
   │
   ▼
Freshness score + report in the web UI
```

## Tech stack

| Part | Tool |
|---|---|
| Backend | Python, FastAPI |
| LLM gateway | **Bifrost** by Maxim AI |
| Live web search | **Tavily** |
| Frontend | HTML, CSS and vanilla JavaScript (single file) |

## How we use Bifrost

All LLM calls in Yatharth go through one Bifrost gateway running locally. Our code talks to it with the normal OpenAI SDK; only the base URL changes.

- **One API, many models:** a cheap, fast model extracts and tags claims; a stronger model writes verdicts.
- **Fallbacks:** if a provider fails or is rate limited, Bifrost retries on another one, so the demo does not break.
- **Semantic caching:** repeated or similar questions are served faster and cheaper.
- **Observability:** the Bifrost dashboard shows every request, latency and cost.

```python
from openai import OpenAI

# Real provider keys live inside Bifrost, not in our code.
llm = OpenAI(base_url="http://localhost:8080/openai", api_key="bifrost")

resp = llm.chat.completions.create(
    model="openai/gpt-4o-mini",  # format: provider/model
    messages=[{"role": "user", "content": "List the factual claims in: ..."}],
)
```

## How we use Tavily

For each high-risk claim, Yatharth builds a search query and asks Tavily for recent, trustworthy evidence.

- `time_range` keeps results recent.
- `include_domains` with `include_domains_mode="prefer"` favours official sites (pricing pages, docs, government sites).
- `extract` reads the exact price, version or rule from the best page.

```python
import os
from tavily import TavilyClient

tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
evidence = tavily.search(
    query="Acme Pro plan price per month",
    search_depth="advanced",
    time_range="year",
    include_domains=["acme.com"],
    include_domains_mode="prefer",
    max_results=5,
)
```

## How AI is used

- **Claim extraction, risk tagging, verdicts and answer rewriting** are done by LLMs, called through Bifrost.
- **Evidence** comes from Tavily live web search, so verdicts rest on real sources, not on the model's memory.
- **AI during development:** [list any AI tools you used to help write code, e.g. coding assistants].

## Project structure

```
heimdall/
├── backend/
│   ├── main.py            # FastAPI app and /api/check endpoint
│   ├── llm.py             # OpenAI client pointed at Bifrost
│   ├── claims.py          # claim extraction and volatility tagging
│   ├── verify.py          # Tavily search + extract
│   ├── verdict.py         # verdicts, freshness score, corrected answer
│   └── requirements.txt
├── frontend/              # web UI
├── docs/                  # logo, screenshots, pitch deck
├── .env.example
└── README.md
```

## Installation

**You need:** Python 3.10+, Node.js (to run Bifrost with `npx`), a Tavily API key, and an API key for at least one LLM provider.

1. **Clone**
   ```bash
   git clone https://github.com/[your-username]/heimdall.git
   cd heimdall
   ```
2. **Start Bifrost** (keep this terminal open). The first time, Bifrost needs a setup token that you choose yourself:
   ```bash
   BIFROST_SETUP_TOKEN=pick-any-long-secret npx -y @maximhq/bifrost
   ```
   Open http://localhost:8080, paste the same token, and create the admin account. For local use, turn off **Enforce Virtual Keys on Inference** (or create a virtual key and put it in `BIFROST_API_KEY`). Then add your provider key in the web UI.
3. **Set up the backend**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   cp ../.env.example ../.env       # then fill in your keys
   uvicorn main:app --reload --port 8000
   ```
4. **Open the frontend** (new terminal):
   ```bash
   cd frontend && python -m http.server 5173
   ```
   Then open http://localhost:5173

   Shortcut: the backend also serves the page, so you can simply open http://localhost:8000. To show it to others on the same Wi-Fi, start the backend with `--host 0.0.0.0` and share `http://<your-ip>:8000`.

`.env.example`:

```
TAVILY_API_KEY=your_tavily_key
BIFROST_BASE_URL=http://localhost:8080/openai
EXTRACT_MODEL=openai/gpt-4o-mini
JUDGE_MODEL=openai/gpt-4o
```

## API

`POST /api/check`

```json
{ "answer_text": "The Pro plan costs $10/month." }
```

Response:

```json
{
  "freshness_score": 62,
  "claims": [
    {
      "id": 1,
      "text": "The Pro plan costs $10/month",
      "category": "pricing",
      "verdict": "stale",
      "evidence": { "url": "https://...", "snippet": "...", "date": "2026-10-01" },
      "corrected": "The Pro plan now costs $12/month"
    }
  ],
  "corrected_answer": "..."
}
```

### Attach files

`POST /api/check-files` takes a multipart form with an optional `answer_text` and up to 3 `files` (.txt, .md, .csv, .json, .pdf, .png, .jpg, .webp, 5 MB each). PDFs are read as text; images are read by a vision model through Bifrost (`VISION_MODEL`). Scanned PDFs are not supported yet, upload them as images.

## Deploy on Render (free)

`render.yaml` describes two free web services: **yatharth-bifrost** (the Bifrost gateway, configured by `bifrost/config.json` and environment variables) and **yatharth** (the FastAPI backend, which also serves the web page).

1. Push this repo to GitHub.
2. On Render: New > Blueprint > pick the repo. Fill the secret values it asks for (Gemini key, Bifrost admin login, a virtual key starting with `sk-bf-`, Tavily key, model names).
3. After the first deploy, copy the Bifrost URL and set `BIFROST_BASE_URL` of the backend to `<bifrost-url>/openai`. Set the backend's `BIFROST_API_KEY` to the same `sk-bf-` virtual key.
4. Open the backend URL. Free services sleep after 15 minutes, so open both URLs a few minutes before a demo to wake them up.

## Demo

- Live demo: [link, optional]
- Demo video: [link]
- Pitch deck: [link or `docs/` path]

## Limitations

- Verdicts are only as good as the sources the search finds. When no reliable source exists, we say "Unverified" instead of guessing.
- Very new events may not be indexed yet.
- Claim extraction is done by an LLM and can miss a claim or split one wrongly.

## What's next

- Browser extension to check chatbot replies in place.
- Company mode: check bots against your own policy documents.
- More languages.

## Team

- [Your name]: [role]
- [Friend's name]: [role]

Built during the Global AI Hackathon 2026 by Geek Room.
