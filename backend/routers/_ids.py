#!/usr/bin/env python3
"""
Opaque player IDs for the /players/{id} family of routes: the (season,
league, team, player) lookup tuple, base64url-encoded into a single
URL-safe path segment.
"""

import base64
import json


def encode_player_id(season: str, league: str, team: str, player: str) -> str:
    raw = json.dumps([season, league, team, player], separators=(',', ':'))
    token = base64.urlsafe_b64encode(raw.encode('utf-8')).decode('ascii')
    return token.rstrip('=')


def decode_player_id(player_id: str) -> tuple:
    """Returns (season, league, team, player). Raises ValueError if the id
    isn't one this module produced."""
    padded = player_id + '=' * (-len(player_id) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode('ascii')).decode('utf-8')
        parts = json.loads(raw)
        season, league, team, player = parts
    except Exception as e:
        raise ValueError(f'invalid player id: {player_id!r}') from e
    return season, league, team, player
