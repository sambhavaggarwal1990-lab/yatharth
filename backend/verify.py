"""Live web evidence from Tavily + a simple source-trust label."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

NEWS = ("reuters.com", "bbc.com", "apnews.com", "thehindu.com", "indianexpress.com", "timesofindia.indiatimes.com")


def trust_label(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if host.endswith((".gov", ".edu", ".nic.in", ".ac.in")) or ".gov." in host:
        return "Official"
    if host.startswith(("docs.", "developer.", "developers.", "support.", "help.")):
        return "Official docs"
    if any(host == d or host.endswith("." + d) for d in NEWS):
        return "News"
    return "Web"


def _search(claim: dict) -> list[dict]:
    from tavily import TavilyClient  # imported late so a missing key fails with a clear message

    key = os.getenv("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("TAVILY_API_KEY is not set (see .env.example)")
    args = dict(
        query=claim.get("query") or claim["text"],
        search_depth=os.getenv("TAVILY_DEPTH", "basic"),
        max_results=4,
    )
    if os.getenv("TAVILY_TIME_RANGE"):
        args["time_range"] = os.getenv("TAVILY_TIME_RANGE")
    t0 = time.time()
    print(f"[tavily] searching: {args['query']}", flush=True)
    tavily = TavilyClient(api_key=key)
    try:
        res = tavily.search(**args, timeout=25)
    except TypeError:  # older SDK without a timeout argument
        res = tavily.search(**args)
    print(f"[tavily] {len(res.get('results', []))} results in {time.time() - t0:.1f}s", flush=True)
    return [
        {
            "url": r["url"],
            "title": r.get("title", ""),
            "date": r.get("published_date"),
            "snippet": (r.get("content") or "")[:500],
            "trust": trust_label(r["url"]),
        }
        for r in res.get("results", [])
    ]


def verify_claims(claims: list[dict]) -> dict[int, list[dict]]:
    """Search the web for each risky claim, in parallel. Returns {claim_id: [evidence, ...]}."""
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(_search, claims))
    return {c["id"]: r for c, r in zip(claims, results)}
