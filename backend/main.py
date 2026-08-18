"""
Radar backend entrypoint: builds the FastAPI app, wires up the typed
routers, and seeds the in-memory data store on startup.
"""
import os
import sys

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(HERE)

# data/ and backend/ are siblings, not subpackages - put both on sys.path
# so imports resolve the same whether run directly or via `uvicorn main:app`.
for _p in (ROOT_DIR, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scout_engine as eng
from data import loader

from routers import players, similarity, gems, market_value, style_archetype, moneyball, admin, meta, benchmark, style, history, squad, impact, raw_data

# engine_module=eng also clears scout_engine's pool cache on later /upload calls.
loader.boot(engine_module=eng)

app = FastAPI(
    title="Radar - Data Scout API",
    description="Football scouting decision-support API: player profiles, "
                 "similarity search, hidden gems, market value, moneyball.",
)

# CORS for the Next.js frontend; configurable via env, defaults to `npm run dev`.
_cors_origins = [
    o.strip() for o in os.environ.get('CORS_ORIGINS', 'http://localhost:3000').split(',') if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(players.router)
app.include_router(similarity.router)
app.include_router(gems.router)
app.include_router(market_value.router)
app.include_router(style_archetype.router)
app.include_router(moneyball.router)
app.include_router(admin.router)
app.include_router(meta.router)
app.include_router(benchmark.router)
app.include_router(style.router)
app.include_router(history.router)
app.include_router(squad.router)
app.include_router(impact.router)
app.include_router(raw_data.router)


@app.post("/upload")
async def upload(
    players: UploadFile = File(None), supplementary: UploadFile = File(None)
):
    """Upload either file on its own, or both. Each replaces just its own table."""
    out = {"ok": True}
    if players is not None:
        p = loader.read_csv_upload(await players.read(), players.filename)
        loader.load_players_frame(p, engine_module=eng)
        out["player_rows"] = len(p)
    if supplementary is not None:
        s = loader.read_csv_upload(await supplementary.read(), supplementary.filename)
        loader.load_supp_frame(s, engine_module=eng)
        out["supplementary_rows"] = len(s)
    if "player_rows" not in out and "supplementary_rows" not in out:
        return {"ok": False, "error": "no file provided"}
    return out


@app.get("/status")
def status():
    return {
        "player_rows": loader.count_rows("league_season_team_player_data"),
        "supplementary_rows": loader.count_rows("player_supplementary_data"),
        "last_updated": loader.get_last_updated(),
    }


if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("  Data Scout is running.")
    print("  ->  Open  http://localhost:8000       in your browser")
    print("  ->  Open  http://localhost:8000/docs   for the API reference")
    print("=" * 60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
