"""
Legacy data cleanup — one-off maintenance script.

Actions:
  1. Merge duplicate category "grocery" (and variants) → "Grocery" in hub_vendors + products.
  2. HARD DELETE vendor with phone 1111111111 (user_34d49b4494f5) and all their data
     across every collection, including orders (per user's explicit choice - option "a").

Usage:
    python3 legacy_cleanup.py --dry-run    # preview only
    python3 legacy_cleanup.py --apply      # actually write
"""
import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "vendor_wisher_genie")

TARGET_PHONE = "1111111111"
CATEGORY_VARIANTS = ["grocery", "GROCERY", "Groceries", "groceries", "GROCERIES"]
CANONICAL_CATEGORY = "Grocery"


def banner(text):
    print(f"\n{'=' * 70}\n {text}\n{'=' * 70}")


async def run(dry_run: bool):
    mode = "DRY RUN (no writes)" if dry_run else "APPLY (writes will happen)"
    banner(f"Legacy Cleanup — {mode}")

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # ---------- Discovery ----------
    banner("Step 1 — Discover target vendor")
    target = await db.users.find_one({"phone": TARGET_PHONE})
    if not target:
        print(f"  No user with phone {TARGET_PHONE} — nothing to delete for step 2.")
        target_user_id = None
    else:
        target_user_id = target.get("user_id")
        print(f"  user_id : {target_user_id}")
        print(f"  phone   : {target.get('phone')}")
        print(f"  name    : {target.get('name')}")
        print(f"  shop    : {target.get('vendor_shop_name')}")

    # Count what would be affected across collections for the vendor
    counts = {}
    if target_user_id:
        collections_scan = [
            ("users",         {"user_id": target_user_id}),
            ("products",      {"vendor_id": target_user_id}),
            ("hub_vendors",   {"vendor_id": target_user_id}),
            ("sessions",      {"user_id": target_user_id}),
            ("notifications", {"user_id": target_user_id}),
            ("notifications", {"vendor_id": target_user_id}),
            ("discounts",     {"vendor_id": target_user_id}),
            ("orders",        {"vendor_id": target_user_id}),
            ("wisher_orders", {"vendor_id": target_user_id}),
            ("carpet_genie_orders", {"vendor_id": target_user_id}),
            ("shop_timings", {"vendor_id": target_user_id}),
            ("holidays",     {"vendor_id": target_user_id}),
            ("stock_verifications", {"vendor_id": target_user_id}),
            ("delivery_assignments", {"vendor_id": target_user_id}),
            ("delivery_requests",    {"vendor_id": target_user_id}),
        ]
        banner("Step 2 — Vendor-related documents that will be DELETED")
        for coll_name, query in collections_scan:
            try:
                c = await db[coll_name].count_documents(query)
            except Exception:
                c = 0  # collection may not exist
            key = f"{coll_name}::{list(query.keys())[0]}"
            counts[key] = c
            if c:
                print(f"  {coll_name:<25s} matching {query} : {c}")
        if not any(counts.values()):
            print("  (nothing found)")

    # ---------- Category cleanup ----------
    banner("Step 3 — Category normalization ('grocery' → 'Grocery')")
    hub_variant_count = await db.hub_vendors.count_documents({"category": {"$in": CATEGORY_VARIANTS}})
    prod_variant_count = await db.products.count_documents({"category": {"$in": CATEGORY_VARIANTS}})
    print(f"  hub_vendors with variant category: {hub_variant_count}")
    print(f"  products    with variant category: {prod_variant_count}")

    # Show sample docs
    if hub_variant_count:
        print("  Sample hub_vendors:")
        async for v in db.hub_vendors.find({"category": {"$in": CATEGORY_VARIANTS}}, {"_id": 0, "vendor_id": 1, "name": 1, "category": 1}).limit(5):
            print(f"    - {v.get('vendor_id')} | {v.get('name')} | category='{v.get('category')}'")
    if prod_variant_count:
        print("  Sample products:")
        async for p in db.products.find({"category": {"$in": CATEGORY_VARIANTS}}, {"_id": 0, "product_id": 1, "name": 1, "vendor_id": 1, "category": 1}).limit(5):
            print(f"    - {p.get('product_id')} | {p.get('name')} | vendor={p.get('vendor_id')} | category='{p.get('category')}'")

    # ---------- Apply ----------
    if dry_run:
        banner("DRY RUN complete — no changes written")
        return

    banner("Step 4 — APPLYING writes")

    # 4a. Delete vendor 1111111111 cascade
    total_deleted = 0
    if target_user_id:
        for coll_name, query in collections_scan:
            try:
                res = await db[coll_name].delete_many(query)
                if res.deleted_count:
                    print(f"  {coll_name:<25s} deleted {res.deleted_count}")
                    total_deleted += res.deleted_count
            except Exception as e:
                print(f"  {coll_name}: skipped ({e})")
        print(f"  --> total docs deleted for vendor: {total_deleted}")

    # 4b. Category normalization
    hub_res = await db.hub_vendors.update_many(
        {"category": {"$in": CATEGORY_VARIANTS}},
        {"$set": {"category": CANONICAL_CATEGORY}},
    )
    prod_res = await db.products.update_many(
        {"category": {"$in": CATEGORY_VARIANTS}},
        {"$set": {"category": CANONICAL_CATEGORY}},
    )
    print(f"  hub_vendors updated : {hub_res.modified_count}")
    print(f"  products    updated : {prod_res.modified_count}")

    # ---------- Post-state ----------
    banner("Step 5 — Post-apply state")
    total_users = await db.users.count_documents({})
    total_vendors_in_hub = await db.hub_vendors.count_documents({})
    total_products = await db.products.count_documents({})
    distinct_cats = await db.hub_vendors.distinct("category")
    print(f"  users                : {total_users}")
    print(f"  hub_vendors          : {total_vendors_in_hub}")
    print(f"  products             : {total_products}")
    print(f"  hub_vendors categories: {sorted(distinct_cats)}")

    client.close()


if __name__ == "__main__":
    dry = "--apply" not in sys.argv
    asyncio.run(run(dry_run=dry))
