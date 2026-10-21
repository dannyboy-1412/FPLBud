from __future__ import annotations

from fplcore.explain.protocol import HorizonResult

REASON_SENTENCES = {
    "FLAG_INJURED_OUT": "A flagged player is unlikely to start, so the agent moved them on.",
    "FIXTURE_SWING": "The incoming player has a kinder run of fixtures.",
    "XGI_UPGRADE": "Expected attacking numbers favour the incoming player.",
    "FORM_UPGRADE": "Recent form is stronger for the player coming in.",
    "HIT_NOT_WORTH": "A hit was considered, but the extra projected points do not cover the cost.",
    "ROLL_PREFERRED": "Holding the free transfer is worth more than the upgrade on offer.",
    "CAPTAIN_MARGIN": "The captain is the starter with the highest projected points.",
    "CHIP_PLAY_NOW": "A chip looks worth playing this week.",
    "CHIP_HOLD": "No chip clears its bar this week.",
}


class TemplateExplainer:
    source = "template"

    def explain(self, result: HorizonResult) -> str:
        horizon = result.get("horizon", 1)
        transfers = result.get("transfers") or []
        hits = result.get("hits") or 0
        gain = result.get("gain_vs_roll") or 0
        captain = result.get("captain") or {}
        vice = result.get("vice") or {}
        codes = result.get("reason_codes") or []

        if not transfers:
            lead = "Roll the transfer"
            body = (
                f"The best move over the next {horizon} gameweek"
                f"{'s' if horizon != 1 else ''} is to hold. "
                f"Rolling is worth about {abs(gain):.1f} projected points versus forcing a deal."
            )
        else:
            bits = [f"Sell {t.get('out_name', t.get('out'))} for {t.get('in_name', t.get('in'))}" for t in transfers]
            lead = ", then ".join(bits)
            body = (
                f"That swap is projected at {gain:+.1f} versus rolling"
                f"{' after a −4 hit' if hits else ''}."
            )
            why_parts = []
            for transfer in transfers:
                deltas = transfer.get("metric_deltas") or {}
                top = sorted(deltas.items(), key=lambda kv: abs(kv[1]), reverse=True)[:2]
                for key, value in top:
                    why_parts.append(f"{key} {value:+.2f}")
            if why_parts:
                body += " The biggest metric swings are " + ", ".join(why_parts) + "."

        cap_name = captain.get("web_name") or captain.get("name") or "the lead starter"
        cap_proj = captain.get("proj")
        vice_name = vice.get("web_name") or vice.get("name")
        cap_line = f" Captain {cap_name}"
        if cap_proj is not None:
            cap_line += f" ({cap_proj:.1f})"
        if vice_name:
            cap_line += f", with {vice_name} as vice."
        else:
            cap_line += "."

        extras = [REASON_SENTENCES[c] for c in codes if c in REASON_SENTENCES]
        extra = (" " + " ".join(extras)) if extras else ""
        return f"{lead}. {body}{cap_line}{extra}"

    def explain_run(self, results: dict[str, HorizonResult]) -> dict[str, str]:
        return {key: self.explain(value) for key, value in results.items()}
