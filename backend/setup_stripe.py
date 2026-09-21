"""Idempotent Stripe catalog setup for SeriesTrack Pro.
Creates products + prices with stable metadata + lookup_keys so re-running
never duplicates. Run manually with: python setup_stripe.py
"""
import os
import stripe
from dotenv import load_dotenv

load_dotenv()
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"

# Amounts in cents (BRL). SeriesTrack Pro plans preserve existing prices.
CATALOG = [
    {
        "emergent_product_id": "seriestrack_pro",
        "name": "SeriesTrack Pro",
        "tax_code": "txcd_10103001",  # SaaS
        "prices": [
            {"lookup_key": "pro_monthly", "amount": 1290, "currency": "brl", "interval": "month"},
            {"lookup_key": "pro_yearly", "amount": 9900, "currency": "brl", "interval": "year"},
        ],
    },
]


def get_or_create_product(entry):
    for p in stripe.Product.list(active=True).auto_paging_iter():
        if p.metadata.get("emergent_product_id") == entry["emergent_product_id"]:
            print(f"[=] product exists: {p.id} ({entry['name']})")
            return p
    p = stripe.Product.create(
        name=entry["name"],
        tax_code=entry.get("tax_code"),
        metadata={"managed_by": "emergent", "emergent_product_id": entry["emergent_product_id"]},
    )
    print(f"[+] product created: {p.id} ({entry['name']})")
    return p


def ensure_price(product_id, p):
    existing = stripe.Price.list(lookup_keys=[p["lookup_key"]], active=True, limit=1).data
    if existing and (existing[0].unit_amount != p["amount"] or existing[0].currency != p["currency"]):
        stripe.Price.modify(existing[0].id, active=False)
        print(f"[~] price rotated (amount/currency changed): {existing[0].id}")
        existing = []
    if existing:
        print(f"[=] price exists: {existing[0].id} ({p['lookup_key']})")
        return existing[0]
    kwargs = dict(
        product=product_id,
        unit_amount=p["amount"],
        currency=p["currency"],
        lookup_key=p["lookup_key"],
        transfer_lookup_key=True,
    )
    if p.get("interval"):
        kwargs["recurring"] = {"interval": p["interval"]}
    price = stripe.Price.create(**kwargs)
    print(f"[+] price created: {price.id} ({p['lookup_key']} — {p['amount']/100:.2f} {p['currency'].upper()})")
    return price


def main():
    for entry in CATALOG:
        product = get_or_create_product(entry)
        for p in entry["prices"]:
            ensure_price(product.id, p)
    print("\nCatalog ready. lookup_keys:", [p["lookup_key"] for e in CATALOG for p in e["prices"]])


if __name__ == "__main__":
    main()
