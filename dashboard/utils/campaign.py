from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    name: str
    reach: float
    response: float
    discount: float
    contact_cost: float


def evaluate(s: Scenario, customers: float, aov: float, organic: float, margin: float) -> dict:
    reached = customers * s.reach
    buyers = reached * s.response
    revenue = buyers * aov * (1 - s.discount)
    discount_cost = (buyers + reached * organic) * aov * s.discount
    contact_cost = customers * s.contact_cost
    spend = discount_cost + contact_cost
    profit = buyers * aov * margin - spend
    return {
        "scenario": s.name,
        "customers": customers,
        "reached": reached,
        "buyers": buyers,
        "revenue": revenue,
        "discount_cost": discount_cost,
        "contact_cost": contact_cost,
        "spend": spend,
        "profit": profit,
        "roi": profit / spend if spend else None,
        "breakeven": breakeven_response(s, customers, aov, organic, margin),
    }


def breakeven_response(s: Scenario, customers: float, aov: float, organic: float, margin: float):
    reached = customers * s.reach
    unit_gain = reached * aov * (margin - s.discount)
    if unit_gain <= 0:
        return None
    fixed = reached * organic * aov * s.discount + customers * s.contact_cost
    return fixed / unit_gain


def profit_curve(s: Scenario, customers: float, aov: float, organic: float, margin: float, responses):
    return [
        evaluate(Scenario(s.name, s.reach, r, s.discount, s.contact_cost), customers, aov, organic, margin)["profit"]
        for r in responses
    ]
