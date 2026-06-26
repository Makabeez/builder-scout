"""
BNB Builder Scout - a CROO agent that scores a DEPLOYER WALLET's reputation
by classifying its recent contract deployments through the PulseBNB Agent.

Dual role:
  - PROVIDER: a caller pays Scout (USDC) with a deployer wallet address.
  - REQUESTER: Scout pays the PulseBNB Agent (USDC) to classify each of that
    wallet's recent deployments, then aggregates into a deployer score.

This is a real agent-to-agent (A2A) relationship: Scout depends on PulseBNB.
"""

import asyncio
import json
import logging
import os

import httpx

from croo import (
    AgentClient, Config, EventType, DeliverableType,
    DeliverOrderRequest, NegotiateOrderRequest, Event,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("builder-scout")

# Redact CROO keys from logs (safe for demo recording).
from log_redact import install_redaction  # noqa: E402
install_redaction()

ETHERSCAN_KEY = os.environ.get("ETHERSCAN_API_KEY", "")
# The PulseBNB Agent's service id (the downstream agent Scout calls).
PULSEBNB_SERVICE_ID = os.environ["PULSEBNB_SERVICE_ID"]
PULSEBNB_API = os.environ.get("PULSEBNB_API", "https://pulsebnb-api.baserep.xyz")
# Max deployments to classify per scout call (cost control).
MAX_DEPLOYMENTS = int(os.environ.get("SCOUT_MAX_DEPLOYMENTS", "3"))


def _extract_address(requirements: str):
    if not requirements:
        return None
    requirements = requirements.strip()
    try:
        obj = json.loads(requirements)
        if isinstance(obj, dict):
            addr = obj.get("address") or obj.get("wallet") or obj.get("deployer")
            if addr:
                requirements = str(addr).strip()
    except (json.JSONDecodeError, TypeError):
        pass
    if requirements.startswith("0x") and len(requirements) == 42:
        return requirements
    return None


async def _recent_deployments(wallet: str):
    """Find contracts deployed by this wallet via the PulseBNB API (free, own data)."""
    url = f"{PULSEBNB_API}/builder/{wallet}"
    async with httpx.AsyncClient(timeout=25.0) as http:
        try:
            r = await http.get(url)
            data = r.json()
        except Exception as e:
            log.warning("pulsebnb /builder lookup failed for %s: %s", wallet[:10], e)
            return []
    contracts = data.get("contracts", [])
    if not isinstance(contracts, list):
        return []
    # newest first, cap at MAX_DEPLOYMENTS
    addrs = []
    for c in contracts:
        addr = c.get("address")
        if addr:
            addrs.append(addr)
        if len(addrs) >= MAX_DEPLOYMENTS:
            break
    return addrs


class Scout:
    """Holds the AgentClient and orchestrates sub-calls to PulseBNB."""

    def __init__(self, client: AgentClient, stream):
        self.client = client
        self.stream = stream
        # Track our OWN sub-call orders (Scout-as-requester) so we don't confuse
        # them with incoming orders (Scout-as-provider).
        self.subcall_events = {}  # order_id -> asyncio.Event
        self.subcall_results = {}  # order_id -> verdict dict
        self.subcall_negotiations = {}  # negotiation_id -> order_id (ours)

    async def classify_one(self, address: str) -> dict:
        """Pay PulseBNB to classify a single contract; wait for the verdict."""
        neg = await self.client.negotiate_order(NegotiateOrderRequest(
            service_id=PULSEBNB_SERVICE_ID,
            requirements=json.dumps({"address": address})))
        self.subcall_negotiations[neg.negotiation_id] = None  # marks it as OURS
        ev = asyncio.Event()
        # We don't know the order_id yet; map by negotiation until order_created.
        # Store the event keyed by negotiation for now.
        self.subcall_results[neg.negotiation_id] = {"_event": ev, "verdict": None}
        try:
            await asyncio.wait_for(ev.wait(), timeout=180)
        except asyncio.TimeoutError:
            return {"address": address, "verdict": "timeout", "confidence": 0}
        return self.subcall_results[neg.negotiation_id]["verdict"] or {
            "address": address, "verdict": "unknown", "confidence": 0}

    async def score_wallet(self, wallet: str) -> dict:
        """The core product: classify recent deployments, aggregate a score."""
        deployments = await _recent_deployments(wallet)
        if not deployments:
            return {"wallet": wallet, "deployer_score": 0,
                    "verdict": "no_deployments",
                    "reason": "No contract deployments found for this wallet.",
                    "classified": []}

        results = []
        for addr in deployments:
            verdict = await self.classify_one(addr)
            results.append(verdict)

        real = [r for r in results if r.get("verdict") == "real"]
        n = len(results)
        real_pct = round(100 * len(real) / n) if n else 0
        # Deployer score: weighted by % real and avg confidence of real builds.
        avg_conf = round(sum(r.get("confidence", 0) for r in real) / len(real)) if real else 0
        deployer_score = round(0.7 * real_pct + 0.3 * avg_conf)

        if real_pct >= 60:
            label = "real_builder"
        elif real_pct >= 30:
            label = "mixed"
        else:
            label = "noise_deployer"

        return {
            "wallet": wallet,
            "verdict": label,
            "deployer_score": deployer_score,        # 0-100
            "deployments_checked": n,
            "real_pct": real_pct,
            "classified": [
                {"address": r.get("address"), "verdict": r.get("verdict"),
                 "confidence": r.get("confidence"),
                 "contract_name": r.get("contract_name")}
                for r in results
            ],
            "source": "BNB Builder Scout (powered by PulseBNB Agent on CROO)",
        }


async def main() -> None:
    client = AgentClient(
        Config(base_url=os.environ["CROO_API_URL"], ws_url=os.environ["CROO_WS_URL"],
               rpc_url=os.environ.get("BASE_RPC_URL", "")),
        os.environ["CROO_SDK_KEY"],
    )
    stream = await client.connect_websocket()
    scout = Scout(client, stream)
    log.info("BNB Builder Scout online. Listening for negotiations...")

    # --- Scout as REQUESTER: handle OUR sub-call orders to PulseBNB ---
    def on_order_created(e: Event) -> None:
        # Is this one of OUR sub-call negotiations?
        if e.negotiation_id in scout.subcall_negotiations:
            scout.subcall_negotiations[e.negotiation_id] = e.order_id
            # migrate the result record to be keyed by negotiation (already is)
            async def _pay() -> None:
                log.info("Scout paying PulseBNB for sub-call order %s...", e.order_id)
                try:
                    await client.pay_order(e.order_id)
                except Exception as err:
                    log.error("scout pay error: %s", err)
            asyncio.create_task(_pay())
    stream.on(EventType.ORDER_CREATED, on_order_created)

    def on_order_completed(e: Event) -> None:
        # Find which of our sub-call negotiations this order belongs to
        neg_id = None
        for nid, oid in scout.subcall_negotiations.items():
            if oid == e.order_id:
                neg_id = nid
                break
        if neg_id is None:
            return  # not ours
        async def _collect() -> None:
            try:
                delivery = await client.get_delivery(e.order_id)
                verdict = json.loads(delivery.deliverable_schema) if delivery.deliverable_schema else {}
                rec = scout.subcall_results.get(neg_id)
                if rec:
                    rec["verdict"] = verdict
                    rec["_event"].set()
            except Exception as err:
                log.error("scout collect error: %s", err)
        asyncio.create_task(_collect())
    stream.on(EventType.ORDER_COMPLETED, on_order_completed)

    # --- Scout as PROVIDER: handle INCOMING orders from end callers ---
    def on_negotiation_created(e: Event) -> None:
        # Ignore our own outbound negotiations (we created those).
        if e.negotiation_id in scout.subcall_negotiations:
            return
        async def _accept() -> None:
            log.info("Incoming scout request %s, accepting...", e.negotiation_id)
            try:
                await client.accept_negotiation(e.negotiation_id)
            except Exception as err:
                log.error("scout accept error: %s", err)
        asyncio.create_task(_accept())
    stream.on(EventType.NEGOTIATION_CREATED, on_negotiation_created)

    def on_incoming_paid(e: Event) -> None:
        # Only handle paid orders that are NOT our sub-calls.
        is_ours = e.order_id in scout.subcall_negotiations.values()
        if is_ours:
            return
        async def _serve() -> None:
            log.info("Scout order %s paid. Scoring wallet...", e.order_id)
            try:
                order = await client.get_order(e.order_id)
                negotiation = await client.get_negotiation(order.negotiation_id)
                wallet = _extract_address(negotiation.requirements)
                if not wallet:
                    result = {"error": "no valid wallet address",
                              "expected": '{"address":"0x...40hex"}'}
                else:
                    result = await scout.score_wallet(wallet)
                await client.deliver_order(e.order_id, DeliverOrderRequest(
                    deliverable_type=DeliverableType.SCHEMA,
                    deliverable_schema=json.dumps(result)))
                log.info("Scout delivered wallet verdict: %s",
                         result.get("verdict", result))
            except Exception as err:
                log.error("scout serve error: %s", err)
        asyncio.create_task(_serve())
    stream.on(EventType.ORDER_PAID, on_incoming_paid)

    stop = asyncio.Event()
    loop = asyncio.get_event_loop()
    try:
        loop.add_signal_handler(__import__("signal").SIGINT, stop.set)
        loop.add_signal_handler(__import__("signal").SIGTERM, stop.set)
    except (NotImplementedError, ValueError):
        pass
    await stop.wait()
    await stream.close()
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
