"""Prices, packs and payment instructions. USD first, naira in brackets."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Pack:
    name: str
    credits: int
    usd: float


@dataclass
class PaymentConfig:
    wallet: str
    network: str
    packs: list[Pack]
    naira_per_usd: float = 0.0     # 0 means do not show naira
    owner_ids: tuple[int, ...] = ()


def load_config(path: str) -> PaymentConfig:
    raw = json.loads(Path(path).read_text())
    packs = [Pack(p["name"], int(p["credits"]), float(p["usd"])) for p in raw["packs"]]
    if not raw.get("wallet") or raw["wallet"].startswith("PUT_"):
        raise ValueError("config: set your real USDT wallet address")
    return PaymentConfig(raw["wallet"], raw["network"], packs, float(raw.get("naira_per_usd", 0)),
                         tuple(int(i) for i in raw.get("owner_ids", [])))


def price_text(usd: float, naira_per_usd: float) -> str:
    text = f"${usd:,.2f}"
    return f"{text} (about ₦{usd * naira_per_usd:,.0f})" if naira_per_usd > 0 else text


def pack_by_name(cfg: PaymentConfig, name: str) -> Pack | None:
    return next((p for p in cfg.packs if p.name.lower() == name.strip().lower()), None)


def payment_instructions(cfg: PaymentConfig, pack: Pack) -> str:
    return (f"{pack.name}: {pack.credits} check(s) for {price_text(pack.usd, cfg.naira_per_usd)}.\n"
            f"Send exactly {pack.usd:,.2f} USDT on {cfg.network} to:\n{cfg.wallet}\n\n"
            f"Then send: /paid {pack.name.lower()} <transaction id>\n"
            "Your checks are added once the payment is confirmed.")


def price_list(cfg: PaymentConfig) -> str:
    return "\n".join(f"- {p.name}: {p.credits} check(s), {price_text(p.usd, cfg.naira_per_usd)}" for p in cfg.packs)
