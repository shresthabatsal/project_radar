# Radar

Radar is a football scouting decision-support system. It scores player-seasons across leagues, surfaces underpriced players, and models market valuation and risk using trained models.

## Features

- **Player Scoring**: a position-relative composite index, plus moneyball, impact, and other scoring metrics for ranking player-seasons
- **Similarity & Style**: finds comparable players and groups them into playing-style archetypes via clustering
- **Hidden Gems**: flags underpriced-for-output players
- **Market Valuation & Risk**: trained ML models for market valuation and sell-high/decline risk
- **Squad Profiling**: per-team age, contract, and risk views built on top of the above

## Project structure

```
backend/    FastAPI app, routers, and scoring logic
ml/         Training and inference code for the market value, sell-high risk, and style clustering models
data/       Data loading and schema definitions
scripts/    Data ingestion, seeding, and model retraining scripts
frontend/   Next.js app
```

## Getting started

### Backend

```
cd backend
pip install -r ../requirements.txt
python3 main.py
```

### Frontend

```
cd frontend
npm install
npm run dev
```
