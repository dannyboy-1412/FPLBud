from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fplcore.models import (
    ChipUsed,
    ChipWindow,
    Element,
    Entry,
    EntryHistory,
    EntryHistoryRow,
    MergedEntry,
    PicksPayload,
    TransferRow,
)

WILDCARD_NAMES = {"wildcard", "wc"}
FREEHIT_NAMES = {"freehit", "free_hit", "fh"}
CHIP_CANONICAL = {
    "wildcard": "wildcard",
    "wc": "wildcard",
    "freehit": "freehit",
    "free_hit": "freehit",
    "fh": "freehit",
    "bboost": "bboost",
    "bench_boost": "bboost",
    "3xc": "3xc",
    "triple_captain": "3xc",
}


def derive_free_transfers(
    history: list[EntryHistoryRow],
    chips: list[ChipUsed],
    *,
    max_extra_free_transfers: int = 4,
    next_event: int,
) -> int:
    """FT going into `next_event`. GW1 transfers are unlimited; GW2 starts at 1."""
    chip_by_event = {chip.event: CHIP_CANONICAL.get(chip.name.lower(), chip.name.lower()) for chip in chips}
    ft = 1
    finished = [row for row in history if row.event < next_event]
    finished.sort(key=lambda row: row.event)
    for row in finished:
        if row.event <= 1:
            continue
        played = chip_by_event.get(row.event)
        if played in WILDCARD_NAMES | FREEHIT_NAMES:
            continue
        free_used = row.event_transfers - row.event_transfers_cost / 4
        ft = int(max(1, min(1 + max_extra_free_transfers, ft - free_used + 1)))
    return ft


def estimate_selling_price(
    *,
    player_id: int,
    now_cost: int,
    cost_change_start: int,
    transfers: list[TransferRow],
) -> int:
    inbound = [row for row in transfers if row.element_in == player_id]
    if inbound:
        buy = max(inbound, key=lambda row: (row.time or datetime.min.replace(tzinfo=UTC), row.event)).element_in_cost
    else:
        buy = now_cost - cost_change_start
    if now_cost > buy:
        return buy + (now_cost - buy) // 2
    return now_cost


def chips_available_this_half(
    windows: list[ChipWindow],
    used: list[ChipUsed],
    current_event: int,
) -> list[dict[str, Any]]:
    used_names = {CHIP_CANONICAL.get(c.name.lower(), c.name.lower()) for c in used if c.event <= current_event}
    available: list[dict[str, Any]] = []
    for window in windows:
        name = CHIP_CANONICAL.get(window.name.lower(), window.name.lower())
        if window.start_event <= current_event <= window.stop_event and name not in used_names:
            available.append({"name": name, "stop_event": window.stop_event, "start_event": window.start_event})
    return available


def player_flags(players: dict[int, Element], pick_ids: list[int]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for pid in pick_ids:
        player = players.get(pid)
        if player is None:
            continue
        chance = player.chance_of_playing_next_round
        if player.status != "a" or (chance is not None and chance < 100):
            flags.append(
                {
                    "element": pid,
                    "web_name": player.web_name,
                    "status": player.status,
                    "chance_of_playing_next_round": chance,
                    "news": player.news or "",
                }
            )
    return flags


@dataclass
class TeamSnapshot:
    entry_id: int
    event: int
    season_id: str
    name: str
    manager: str
    overall_rank: int | None
    picks: list[dict[str, Any]]
    bank: int
    team_value: int
    free_transfers: int
    selling_prices: dict[str, int]
    chips_available: list[dict[str, Any]]
    chips_used: list[dict[str, Any]]
    active_chip: str | None
    flags: list[dict[str, Any]]
    overrides: dict[str, Any] | None = None
    content_hash: str = ""
    squad_players: list[dict[str, Any]] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "event": self.event,
            "season_id": self.season_id,
            "name": self.name,
            "manager": self.manager,
            "overall_rank": self.overall_rank,
            "picks": self.picks,
            "bank": self.bank,
            "team_value": self.team_value,
            "free_transfers": self.free_transfers,
            "selling_prices": self.selling_prices,
            "chips_available": self.chips_available,
            "chips_used": self.chips_used,
            "active_chip": self.active_chip,
            "flags": self.flags,
            "overrides": self.overrides,
            "content_hash": self.content_hash,
            "squad_players": self.squad_players,
        }


def apply_overrides(snapshot: TeamSnapshot, overrides: dict[str, Any] | None) -> TeamSnapshot:
    if not overrides:
        return snapshot
    if "free_transfers" in overrides and overrides["free_transfers"] is not None:
        snapshot.free_transfers = int(overrides["free_transfers"])
    if "bank" in overrides and overrides["bank"] is not None:
        snapshot.bank = int(overrides["bank"])
    if "squad" in overrides and overrides["squad"]:
        squad = [int(x) for x in overrides["squad"]]
        snapshot.picks = [
            {**pick, "element": squad[i] if i < len(squad) else pick["element"]}
            for i, pick in enumerate(snapshot.picks)
        ]
    snapshot.overrides = overrides
    return snapshot


def build_snapshot(
    *,
    merged: MergedEntry,
    players: dict[int, Element],
    chip_windows: list[ChipWindow],
    season_id: str,
    max_extra_free_transfers: int = 4,
    overrides: dict[str, Any] | None = None,
) -> TeamSnapshot:
    entry: Entry = merged.entry
    picks_payload: PicksPayload = merged.picks
    history: EntryHistory = merged.history
    transfers: list[TransferRow] = merged.transfers

    pick_ids = [p.element for p in picks_payload.picks]
    selling = {
        str(pid): estimate_selling_price(
            player_id=pid,
            now_cost=players[pid].now_cost if pid in players else 0,
            cost_change_start=players[pid].cost_change_start if pid in players else 0,
            transfers=transfers,
        )
        for pid in pick_ids
    }
    next_event = entry.current_event + 1
    ft = derive_free_transfers(
        history.current,
        history.chips,
        max_extra_free_transfers=max_extra_free_transfers,
        next_event=next_event,
    )
    bank = picks_payload.entry_history.bank or entry.last_deadline_bank or 0
    value = picks_payload.entry_history.value or entry.last_deadline_value or 0
    available = chips_available_this_half(chip_windows, history.chips, entry.current_event)
    used = [{"name": CHIP_CANONICAL.get(c.name.lower(), c.name.lower()), "event": c.event} for c in history.chips]
    flags = player_flags(players, pick_ids)
    squad_players = []
    for pick in picks_payload.picks:
        player = players.get(pick.element)
        if player is None:
            continue
        squad_players.append(
            {
                "element": pick.element,
                "web_name": player.web_name,
                "team_id": player.team,
                "position_id": player.element_type,
                "now_cost": player.now_cost,
                "status": player.status,
                "chance_of_playing_next_round": player.chance_of_playing_next_round,
                "news": player.news,
                "is_captain": pick.is_captain,
                "is_vice_captain": pick.is_vice_captain,
                "squad_position": pick.position,
            }
        )

    snapshot = TeamSnapshot(
        entry_id=entry.id,
        event=entry.current_event,
        season_id=season_id,
        name=entry.name,
        manager=f"{entry.player_first_name} {entry.player_last_name}".strip(),
        overall_rank=entry.summary_overall_rank,
        picks=[p.model_dump() for p in picks_payload.picks],
        bank=bank,
        team_value=value,
        free_transfers=ft,
        selling_prices=selling,
        chips_available=available,
        chips_used=used,
        active_chip=picks_payload.active_chip,
        flags=flags,
        squad_players=squad_players,
    )
    snapshot = apply_overrides(snapshot, overrides)
    payload = snapshot.to_payload()
    payload.pop("content_hash", None)
    snapshot.content_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()
    return snapshot


def merged_from_payloads(
    entry: Entry,
    picks: PicksPayload,
    history: EntryHistory,
    transfers: list[TransferRow],
) -> MergedEntry:
    return MergedEntry(entry=entry, picks=picks, history=history, transfers=transfers)
