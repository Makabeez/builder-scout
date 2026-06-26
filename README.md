<div align="center">

<svg width="780" height="180" viewBox="0 0 780 180" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0b0b0b"/>
      <stop offset="100%" stop-color="#0a1a14"/>
    </linearGradient>
    <linearGradient id="grn" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#22c55e"/>
      <stop offset="100%" stop-color="#86efac"/>
    </linearGradient>
  </defs>
  <rect width="780" height="180" fill="url(#bg)" rx="14"/>
  <circle cx="90" cy="90" r="6" fill="#22c55e">
    <animate attributeName="r" values="6;26;6" dur="2.4s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="1;0;1" dur="2.4s" repeatCount="indefinite"/>
  </circle>
  <circle cx="90" cy="90" r="6" fill="#22c55e"/>
  <text x="158" y="76" font-family="'Courier New', monospace" font-size="36" font-weight="800" fill="url(#grn)">BNB Builder Scout</text>
  <text x="160" y="110" font-family="'Courier New', monospace" font-size="15" fill="#bdbdbd">A CROO agent that scores a deployer wallet's reputation —</text>
  <text x="160" y="134" font-family="'Courier New', monospace" font-size="15" fill="#bdbdbd">by paying another agent to classify its deployments.</text>
</svg>

<br/>

[![CROO Agent Protocol](https://img.shields.io/badge/Built_on-CROO_CAP-22c55e?style=for-the-badge)](https://cap.croo.network)
[![A2A](https://img.shields.io/badge/Agent_to_Agent-Calls_PulseBNB-8b5cf6?style=for-the-badge)](https://github.com/Makabeez/pulsebnb-croo)
[![Settlement](https://img.shields.io/badge/Settles-USDC_on_Base-0052FF?style=for-the-badge&logo=coinbase&logoColor=white)](https://base.org)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)

</div>
<img src="demo.svg" alt="Live paid call on CROO" width="700"/>
---

> **The pitch:** Builder Scout scores a BNB Chain *deployer wallet's* reputation. Give it a wallet, and it finds that wallet's recent contract deployments and **pays the [PulseBNB Agent](https://github.com/Makabeez/pulsebnb-croo) to classify each one** — then aggregates the verdicts into a deployer score: real builder, mixed, or noise deployer.

## Why this is agent-to-agent (A2A)

Scout is **both a provider and a requester** on the CROO Agent Protocol:

- **As a provider:** an end caller pays Scout (USDC) with a deployer wallet to score.
- **As a requester:** Scout pays the **PulseBNB Agent** (USDC) to classify each of that wallet's deployments.

That's a real, on-chain agent dependency — Scout cannot do its job without calling another agent. One paid order to Scout fans out into multiple paid sub-orders to PulseBNB, all settled through CAP.

```
End caller                 Builder Scout                  PulseBNB Agent
    |                            |                              |
    |-- pay (wallet to score) -->|                              |
    |                            |-- GET /builder/{wallet} -----|  (find deployments)
    |                            |                              |
    |                            |-- pay + classify contract -->|  (A2A sub-order 1)
    |                            |<------- verdict -------------|
    |                            |-- pay + classify contract -->|  (A2A sub-order 2)
    |                            |<------- verdict -------------|
    |                            |   aggregate -> deployer score|
    |<--- deployer reputation ---|                              |
    v                            v                              v
```

## What it delivers

For a deployer wallet, Scout returns a structured verdict:

```json
{
  "wallet": "0x...",
  "verdict": "real_builder | mixed | noise_deployer",
  "deployer_score": 0-100,
  "deployments_checked": 3,
  "real_pct": 67,
  "classified": [
    {"address": "0x...", "verdict": "real", "confidence": 85, "contract_name": "..."}
  ],
  "source": "BNB Builder Scout (powered by PulseBNB Agent on CROO)"
}
```

The score weights the share of *real* deployments and the average confidence of those real builds — so a wallet that ships original contracts scores high, while a wallet that spams templates scores low.

## How it works

1. **Find deployments** — Scout queries the PulseBNB API (`/builder/{wallet}`) for the wallet's indexed contract deployments. Free, and reuses PulseBNB's own index.
2. **Classify each (A2A)** — for each deployment, Scout opens a CAP negotiation with the PulseBNB Agent, pays the USDC fee, and receives a real/noise verdict.
3. **Aggregate** — Scout computes a deployer score from the verdicts and delivers a SCHEMA result to the original caller.

The dual role is handled on a single CAP WebSocket connection: Scout distinguishes incoming orders (it serves) from its own outbound sub-orders (it pays) by tracking negotiation IDs.

## Tech stack

| Layer | Choice |
|---|---|
| Agent protocol | CROO CAP (`croo-sdk`, Python) — dual role |
| Downstream agent | [PulseBNB Agent](https://github.com/Makabeez/pulsebnb-croo) (paid sub-calls) |
| Deployment index | PulseBNB API (`/builder/{wallet}`) |
| Settlement | USDC on Base |
| Runtime | Python 3.12 async |

## Run it

```bash
git clone https://github.com/Makabeez/builder-scout.git
cd builder-scout
python3 -m venv venv && source venv/bin/activate
pip install croo-sdk httpx python-dotenv

cp .env.example .env   # add CROO_SDK_KEY + PULSEBNB_SERVICE_ID
python3 builder_scout.py   # agent goes online, scores wallets on paid orders
```

## Built for

**[CROO Agent Hackathon](https://campaigns.croo.network/hackathon.html)** — a companion agent to [PulseBNB](https://github.com/Makabeez/pulsebnb-croo), demonstrating agent-to-agent composability: one agent paying another to compose a higher-order service.

## License

MIT
