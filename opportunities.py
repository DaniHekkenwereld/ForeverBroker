"""Whole-market read-only price-spread research.

This scans every public market item, NOT a trade executor. The second ask and
market median are asking prices, not verified buyers. Item IDs may aggregate
random-suffix variants, so a scanner result NEVER creates buy advice alone.
"""
import math
from collections import Counter


def _pos(value):
    return type(value) is int and 0 < value <= 100_000_000_000


def rank_market(market, config, *, limit=80, budget_gold=20):
    """Evaluate every market item, shortlist theoretical spreads.

    budget_gold marks affordability; expensive items aren't silently dropped.
    Outputs ranked candidates and coverage, with all prices in copper.
    """
    if type(market) is not dict:
        return [], {'seen': 0, 'priced': 0, 'spread_positive': 0, 'classes': {}}
    budget = int(max(0, budget_gold) * 10000)
    priced = 0
    candidate_count = 0
    classes = Counter()
    ranked = []
    for item_id, x in market.items():
        if not isinstance(x, dict):
            continue
        classes[str(x.get('cls') or 'Unknown')] += 1
        ask = x.get('ask')
        if not _pos(ask):
            continue
        priced += 1
        second = x.get('ask2')
        if not _pos(second) or second <= ask:
            continue
        median = x.get('median')
        # Model a price BELOW the next listed item; no guaranteed sale.
        target = min(second - 1, median) if _pos(median) else second - 1
        if target <= ask:
            continue
        vendor = x.get('vendor') if type(x.get('vendor')) is int and x['vendor'] >= 0 else 0
        proceeds = target - math.ceil(target * config.get('cut_pct', 5) / 100)
        deposit = math.ceil(vendor * config.get('deposit_vendor_pct', 15) / 100)
        net = proceeds - ask - deposit
        roi = net / ask * 100
        if net <= 0 or roi < 20:
            continue
        candidate_count += 1
        volume = x.get('vol24') if type(x.get('vol24')) is int and x['vol24'] > 0 else 0
        depth = x.get('depth5') if type(x.get('depth5')) is int and x['depth5'] > 0 else 0
        recent = x.get('lastSoldP') if _pos(x.get('lastSoldP')) else None
        sure = x.get('sure24') if type(x.get('sure24')) is int else 0
        if recent and recent >= target * .90 and volume >= 3:
            evidence = 'Laatste gerapporteerde verkoop nabij doelprijs'
            factor = 1.0
        elif recent and recent >= ask * 1.20 and volume >= 3:
            evidence = 'Eerdere verkoop boven vraagprijs, maar onder doel'
            factor = .70
        else:
            evidence = 'Geen aangetoonde verkoop nabij doelprijs'
            factor = .35
        if sure > 0:
            factor = min(1.0, factor + .1)
        if volume == 0:
            factor *= .2
        elif volume < 3:
            factor *= .5
        variant_warning = x.get('cls') in ('Armor', 'Weapon')
        if variant_warning:
            factor *= .7
        qty = 1 if x.get('nc') else min(depth, max(1, volume // 12), 20)
        qty = max(1, qty)
        score = net * qty * factor
        ranked.append(dict(id=int(item_id), name=str(x.get('name') or f'Item {item_id}'),
                           category=str(x.get('cls') or 'Unknown'), ask=ask,
                           next_ask=second, median=median if _pos(median) else None,
                           target=target, net_per_unit=net, net_roi=roi,
                           vol24=volume, depth=depth, estimated_units=qty,
                           estimated_net=qty * net, recent_sale=recent,
                           evidence=evidence, suffix_risk=variant_warning,
                           affordable=ask + deposit <= budget, score=score))
    ranked.sort(key=lambda v:(v['affordable'], v['score'], v['net_per_unit']), reverse=True)
    return ranked[:max(0, limit)], dict(seen=len(market), priced=priced,
                    spread_positive=candidate_count, classes=dict(classes))
