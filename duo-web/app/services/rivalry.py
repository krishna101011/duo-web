"""Human-written rivalry messages with lead-sensitive tone."""
from __future__ import annotations

import random

TEMPLATES = {
    "tiny": [
        "{lead} has a tiny edge over {other}. {other}, this is absolutely recoverable.",
        "{lead} is nudging ahead of {other}. Time to answer the scoreboard.",
        "{lead} is one step up on {other}. Nobody panic. Yet.",
        "Barely ahead, but {lead} leads {other}. The next move matters.",
        "{lead} stole a little daylight from {other}. Catch-up mode: activated.",
        "{lead} is just ahead of {other}. This rivalry is getting interesting.",
    ],
    "medium": [
        "{lead} is beating {other} today. Come on, {other}!",
        "{lead} is cooking {other} today. {other}, the scoreboard wants a comeback.",
        "{lead} is building a lead over {other}. The comeback window is still open.",
        "{lead} has pulled ahead of {other}. Someone tell {other} to stop being polite.",
        "{lead} is collecting points while {other} is collecting excuses. 😈",
        "{lead} is winning the daily duel over {other}. Your move, {other}.",
        "{lead} has {other} chasing today. Better luck beats better excuses.",
    ],
    "large": [
        "{lead} is running away from {other} today. {other}, emergency comeback meeting.",
        "{lead} is miles ahead of {other}. The scoreboard is starting to look nervous for {other}.",
        "{lead} has entered turbo mode and left {other} behind. Comebacks are welcome.",
        "{lead} is dominating today. {other}, consider this your dramatic training montage.",
        "{lead} is steamrolling the daily score. {other}, the plot needs a twist.",
        "{lead} has built a serious lead over {other}. Time to hunt.",
        "{lead} is eating the leaderboard for breakfast. {other}, make lunch interesting.",
    ],
    "reverse": [
        "{lead} is ahead of {other}, but tomorrow is another arena. Stay sharp.",
        "{lead} has the crown today. {other} still has plenty of runway.",
        "{lead} is on top right now. {other}, don't let one day become a streak.",
        "Today's scoreboard belongs to {lead}. Tomorrow can belong to {other}.",
    ],
}

FLAT_TEMPLATES = [template for group in TEMPLATES.values() for template in group]


def choose_template(lead_name: str, other_name: str, lead_points: int, other_points: int) -> str:
    delta = abs(lead_points - other_points)
    if delta <= 20:
        tone = "tiny"
    elif delta <= 100:
        tone = "medium"
    else:
        tone = "large"
    return random.choice(TEMPLATES[tone]).format(lead=lead_name, other=other_name)


def fallback_rivalry(player1_name: str, player1_points: int, player2_name: str, player2_points: int) -> str:
    if player1_points == player2_points:
        return f"Dead even: {player1_name} and {player2_name} are tied today. Somebody blink first. ⚔️"
    if player1_points > player2_points:
        return choose_template(player1_name, player2_name, player1_points, player2_points)
    return choose_template(player2_name, player1_name, player2_points, player1_points)
