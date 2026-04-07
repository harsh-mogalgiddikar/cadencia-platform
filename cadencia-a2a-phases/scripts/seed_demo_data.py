"""
Cadencia — Demo Seed Data Script.

Populates the database with demo enterprises, users, capability profiles,
sample RFQs, and agent configurations for development and demo purposes.

Usage:
    docker compose up --wait
    python scripts/seed_demo_data.py

    # Or with custom API base URL:
    API_URL=http://localhost:8000 python scripts/seed_demo_data.py

Creates:
    - 5 enterprises (2 buyers, 3 sellers) with admin users
    - 3 seller capability profiles
    - 3 sample RFQs from buyers
    - 2 agent profile configurations

context.md §4: All API calls use /v1/ prefix.
context.md §10: All responses use ApiResponse[T] envelope.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8000")

# ── Enterprise Definitions ────────────────────────────────────────────────────

ENTERPRISES: list[dict[str, Any]] = [
    {
        "enterprise": {
            "legal_name": "Tata Steel Ltd",
            "pan": "AAACT2727Q",
            "gstin": "27AAACT2727Q1ZV",
            "trade_role": "BUYER",
            "commodities": ["HR_COIL", "CR_SHEET", "TMT_BAR"],
            "min_order_value": 500000,
            "max_order_value": 50000000,
            "industry_vertical": "STEEL",
            "geography": "PAN_INDIA",
        },
        "user": {
            "email": "admin@tatasteel.demo",
            "password": "Demo123!Secure",
            "full_name": "Rajesh Kumar",
            "role": "ADMIN",
        },
    },
    {
        "enterprise": {
            "legal_name": "Mahindra Auto Parts",
            "pan": "AAACM3456R",
            "gstin": "29AAACM3456R1ZT",
            "trade_role": "BUYER",
            "commodities": ["STEEL_PLATE", "ALUMINUM_SHEET"],
            "min_order_value": 200000,
            "max_order_value": 20000000,
            "industry_vertical": "AUTOMOTIVE",
            "geography": "SOUTH_INDIA",
        },
        "user": {
            "email": "admin@mahindra.demo",
            "password": "Demo123!Secure",
            "full_name": "Priya Sharma",
            "role": "ADMIN",
        },
    },
    {
        "enterprise": {
            "legal_name": "JSW Steel Ltd",
            "pan": "AAACJ7890S",
            "gstin": "29AAACJ7890S1ZW",
            "trade_role": "SELLER",
            "commodities": ["HR_COIL", "CR_SHEET", "GALVANIZED_SHEET"],
            "min_order_value": 100000,
            "max_order_value": 100000000,
            "industry_vertical": "STEEL",
            "geography": "PAN_INDIA",
        },
        "user": {
            "email": "admin@jswsteel.demo",
            "password": "Demo123!Secure",
            "full_name": "Amit Patel",
            "role": "ADMIN",
        },
    },
    {
        "enterprise": {
            "legal_name": "SAIL Corporation",
            "pan": "AAACS1234T",
            "gstin": "07AAACS1234T1ZK",
            "trade_role": "SELLER",
            "commodities": ["TMT_BAR", "STEEL_PLATE", "STRUCTURAL_STEEL"],
            "min_order_value": 500000,
            "max_order_value": 200000000,
            "industry_vertical": "STEEL",
            "geography": "NORTH_INDIA",
        },
        "user": {
            "email": "admin@sail.demo",
            "password": "Demo123!Secure",
            "full_name": "Vikram Singh",
            "role": "ADMIN",
        },
    },
    {
        "enterprise": {
            "legal_name": "Vedanta Metals Ltd",
            "pan": "AAACV5678U",
            "gstin": "24AAACV5678U1ZP",
            "trade_role": "SELLER",
            "commodities": ["ALUMINUM_SHEET", "COPPER_CATHODE", "ZINC_INGOT"],
            "min_order_value": 300000,
            "max_order_value": 80000000,
            "industry_vertical": "NON_FERROUS_METALS",
            "geography": "WEST_INDIA",
        },
        "user": {
            "email": "admin@vedanta.demo",
            "password": "Demo123!Secure",
            "full_name": "Neha Gupta",
            "role": "ADMIN",
        },
    },
]

# ── Seller Capability Profiles ────────────────────────────────────────────────

CAPABILITY_PROFILES: list[dict[str, Any]] = [
    {
        "seller_index": 2,  # JSW Steel
        "profile": {
            "product_categories": ["HR_COIL", "CR_SHEET", "GALVANIZED_SHEET"],
            "certifications": ["IS_2062", "IS_513", "BIS_CERTIFIED"],
            "production_capacity_mt_month": 50000,
            "min_order_qty_mt": 50,
            "delivery_regions": ["PAN_INDIA", "EXPORT"],
            "payment_terms": ["LC_AT_SIGHT", "LC_30_DAYS", "ADVANCE"],
            "typical_lead_time_days": 14,
            "quality_standards": "IS 2062 E250/E350, IS 513 O/D/DD grades. BIS certified. "
                                 "Third-party inspection available. Full test certificates provided.",
        },
    },
    {
        "seller_index": 3,  # SAIL
        "profile": {
            "product_categories": ["TMT_BAR", "STEEL_PLATE", "STRUCTURAL_STEEL"],
            "certifications": ["IS_1786", "IS_2062", "IS_2830", "RDSO_APPROVED"],
            "production_capacity_mt_month": 100000,
            "min_order_qty_mt": 100,
            "delivery_regions": ["NORTH_INDIA", "EAST_INDIA", "CENTRAL_INDIA"],
            "payment_terms": ["LC_AT_SIGHT", "CASH_ADVANCE"],
            "typical_lead_time_days": 21,
            "quality_standards": "IS 1786 Fe500D TMT. RDSO approved for railway-grade steel. "
                                 "Full chemical + mechanical test certificates.",
        },
    },
    {
        "seller_index": 4,  # Vedanta Metals
        "profile": {
            "product_categories": ["ALUMINUM_SHEET", "COPPER_CATHODE", "ZINC_INGOT"],
            "certifications": ["LME_REGISTERED", "ISO_9001", "ISO_14001"],
            "production_capacity_mt_month": 25000,
            "min_order_qty_mt": 25,
            "delivery_regions": ["WEST_INDIA", "SOUTH_INDIA", "EXPORT"],
            "payment_terms": ["LC_30_DAYS", "LC_60_DAYS", "USANCE_LC"],
            "typical_lead_time_days": 10,
            "quality_standards": "LME Grade A registered. 99.7% purity aluminum. "
                                 "ISO 9001:2015 certified facility. SGS inspection reports.",
        },
    },
]

# ── Sample RFQs ───────────────────────────────────────────────────────────────

SAMPLE_RFQS: list[dict[str, Any]] = [
    {
        "buyer_index": 0,  # Tata Steel (buying from market)
        "rfq": {
            "raw_text": (
                "Need 500 metric tons of HR Coil, IS 2062 E250 grade, "
                "thickness 2.5mm-6mm, width 1250mm. FOB Mumbai port. "
                "Delivery within 45 days. Budget ₹38,000-42,000 per MT. "
                "Full test certificates required. LC at sight payment."
            ),
        },
    },
    {
        "buyer_index": 0,  # Tata Steel
        "rfq": {
            "raw_text": (
                "Urgent requirement: 200MT Cold Rolled Steel sheets, "
                "0.8mm thickness, CRCA grade, CIF Kolkata. "
                "Payment via LC at sight. Need within 30 days. "
                "BIS certification mandatory."
            ),
        },
    },
    {
        "buyer_index": 1,  # Mahindra Auto
        "rfq": {
            "raw_text": (
                "1000 MT TMT Bars Fe500D for construction project in Bangalore. "
                "IS 1786 grade, 8mm-32mm diameter mix. Delivery to site in batches "
                "over 60 days. Budget ₹45,000-50,000/MT. "
                "Need test certificates for each batch. Payment NET 30."
            ),
        },
    },
]

# ── Agent Configurations ──────────────────────────────────────────────────────

AGENT_CONFIGS: list[dict[str, Any]] = [
    {
        "enterprise_index": 0,  # Tata Steel — aggressive buyer
        "config": {
            "risk_tolerance": 0.7,
            "max_concession_per_round_pct": 5.0,
            "preferred_strategy": "AGGRESSIVE",
            "auto_accept_threshold_pct": 2.0,
            "max_rounds": 8,
        },
    },
    {
        "enterprise_index": 2,  # JSW Steel — moderate seller
        "config": {
            "risk_tolerance": 0.5,
            "max_concession_per_round_pct": 3.0,
            "preferred_strategy": "BALANCED",
            "auto_accept_threshold_pct": 1.5,
            "max_rounds": 10,
        },
    },
]


# ── Seed Runner ───────────────────────────────────────────────────────────────


async def _check_health(client: httpx.AsyncClient) -> bool:
    """Verify API is reachable."""
    try:
        resp = await client.get(f"{API_URL}/health")
        return resp.status_code == 200
    except httpx.ConnectError:
        return False


async def _register_enterprise(
    client: httpx.AsyncClient, data: dict[str, Any]
) -> dict[str, Any]:
    """Register an enterprise and return {enterprise_id, access_token}."""
    resp = await client.post(f"{API_URL}/v1/auth/register", json=data)
    if resp.status_code == 409:
        # Already exists — try to login instead
        login_resp = await client.post(
            f"{API_URL}/v1/auth/login",
            json={
                "email": data["user"]["email"],
                "password": data["user"]["password"],
            },
        )
        if login_resp.status_code != 200:
            print(f"  ⚠ Login failed for {data['user']['email']}: {login_resp.text}")
            return {}
        body = login_resp.json()
        token = body.get("data", {}).get("access_token", "")
        return {"access_token": token, "already_existed": True}

    if resp.status_code not in (200, 201):
        print(f"  ⚠ Register failed for {data['enterprise']['legal_name']}: {resp.text}")
        return {}

    body = resp.json()
    token = body.get("data", {}).get("access_token", "")
    return {"access_token": token, "already_existed": False}


async def _create_capability_profile(
    client: httpx.AsyncClient,
    enterprise_id: str,
    token: str,
    profile: dict[str, Any],
) -> bool:
    """Create a seller capability profile."""
    resp = await client.post(
        f"{API_URL}/v1/marketplace/profiles",
        json=profile,
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.status_code in (200, 201)


async def _upload_rfq(
    client: httpx.AsyncClient,
    token: str,
    rfq: dict[str, Any],
) -> str | None:
    """Upload an RFQ and return its ID."""
    resp = await client.post(
        f"{API_URL}/v1/marketplace/rfqs",
        json=rfq,
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code in (200, 201):
        return resp.json().get("data", {}).get("rfq_id")
    return None


async def _update_agent_config(
    client: httpx.AsyncClient,
    enterprise_id: str,
    token: str,
    config: dict[str, Any],
) -> bool:
    """Update enterprise agent configuration."""
    resp = await client.put(
        f"{API_URL}/v1/enterprises/{enterprise_id}/agent-config",
        json=config,
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.status_code == 200


async def main() -> None:
    """Run the seed data script."""
    print("=" * 60)
    print("Cadencia — Demo Data Seed Script")
    print("=" * 60)
    print(f"API URL: {API_URL}\n")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Health check
        print("1. Checking API health...")
        healthy = await _check_health(client)
        if not healthy:
            print(f"  ✗ API not reachable at {API_URL}")
            print("  → Run: docker compose up --wait")
            sys.exit(1)
        print("  ✓ API is healthy\n")

        # 2. Register enterprises
        print("2. Registering enterprises...")
        registered: list[dict[str, Any]] = []
        for i, ent_data in enumerate(ENTERPRISES):
            result = await _register_enterprise(client, ent_data)
            label = "existed" if result.get("already_existed") else "created"
            token = result.get("access_token", "")
            name = ent_data["enterprise"]["legal_name"]
            role = ent_data["enterprise"]["trade_role"]

            registered.append({
                "index": i,
                "name": name,
                "role": role,
                "email": ent_data["user"]["email"],
                "token": token,
                "enterprise_id": "",  # will be fetched if needed
            })

            if token:
                print(f"  ✓ [{role:6s}] {name} ({label})")
            else:
                print(f"  ✗ [{role:6s}] {name} — failed")

        print()

        # 3. Create capability profiles for sellers
        print("3. Creating seller capability profiles...")
        for cp_data in CAPABILITY_PROFILES:
            idx = cp_data["seller_index"]
            ent = registered[idx]
            if not ent["token"]:
                print(f"  ⊘ Skipping {ent['name']} — no token")
                continue

            ok = await _create_capability_profile(
                client,
                ent.get("enterprise_id", ""),
                ent["token"],
                cp_data["profile"],
            )
            status_icon = "✓" if ok else "✗"
            print(f"  {status_icon} {ent['name']} — capability profile")

        print()

        # 4. Upload sample RFQs
        print("4. Uploading sample RFQs...")
        for rfq_data in SAMPLE_RFQS:
            buyer_idx = rfq_data["buyer_index"]
            buyer = registered[buyer_idx]
            if not buyer["token"]:
                print(f"  ⊘ Skipping RFQ — {buyer['name']} has no token")
                continue

            rfq_id = await _upload_rfq(client, buyer["token"], rfq_data["rfq"])
            if rfq_id:
                snippet = rfq_data["rfq"]["raw_text"][:60]
                print(f"  ✓ RFQ {rfq_id[:8]}… — \"{snippet}…\"")
            else:
                print(f"  ✗ RFQ upload failed for {buyer['name']}")

        print()

        # 5. Update agent configurations
        print("5. Setting agent configurations...")
        for ac_data in AGENT_CONFIGS:
            eidx = ac_data["enterprise_index"]
            ent = registered[eidx]
            if not ent["token"]:
                print(f"  ⊘ Skipping {ent['name']} — no token")
                continue

            ok = await _update_agent_config(
                client,
                ent.get("enterprise_id", ""),
                ent["token"],
                ac_data["config"],
            )
            strategy = ac_data["config"]["preferred_strategy"]
            icon = "✓" if ok else "✗"
            print(f"  {icon} {ent['name']} — {strategy} agent")

        print()

        # ── Summary ───────────────────────────────────────────────────────────
        print("=" * 60)
        print("SEED COMPLETE — Summary")
        print("=" * 60)
        print(f"{'Enterprise':<25} {'Role':<8} {'Email':<30}")
        print("-" * 60)
        for ent in registered:
            print(f"{ent['name']:<25} {ent['role']:<8} {ent['email']:<30}")

        print()
        print("Demo credentials:")
        print(f"  Password: Demo123!Secure (all users)")
        print(f"  Swagger:  {API_URL}/docs")
        print()

        # Print tokens for immediate use
        print("JWT Tokens (for Swagger 'Authorize' button):")
        for ent in registered:
            if ent["token"]:
                # Print first 40 chars only
                t = ent["token"][:40] + "…" if len(ent["token"]) > 40 else ent["token"]
                print(f"  {ent['name']}: {t}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
