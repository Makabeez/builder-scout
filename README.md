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
  <text x="158" y="76" font-family="'Courier New', monospace" font-size="34" font-weight="800" fill="url(#grn)">BNB Builder Scout</text>
  <text x="160" y="110" font-family="'Courier New', monospace" font-size="15" fill="#bdbdbd">Composable reputation, built agent-to-agent.</text>
  <text x="160" y="134" font-family="'Courier New', monospace" font-size="15" fill="#7a7a7a">Pays another agent to grade a deployer's work. Returns a portable score.</text>
</svg>

<br/>

[![Built on CROO CAP](https://img.shields.io/badge/Built_on-CROO_CAP-22c55e?style=for-the-badge)](https://cap.croo.network)
[![Agent to Agent](https://img.shields.io/badge/Agent_to_Agent-Pays_PulseBNB-8b5cf6?style=for-the-badge)](https://github.com/Makabeez/pulsebnb-croo)
[![Settles USDC on Base](https://img.shields.io/badge/Settles-USDC_on_Base-0052FF?style=for-the-badge&logo=coinbase&logoColor=white)](https://base.org)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)

<img src="demo.svg" alt="Live paid call on CROO" width="700"/>

</div>

---

> **The idea:** Reputation is usually a walled garden — every platform computes its own, none of it travels. Builder Scout treats reputation as a *composed service*: give it a deployer wallet, and it **pays [PulseBNB](https://github.com/Makabeez/pulsebnb-croo)** to classify that wallet's real on-chain output, then aggregates the verdicts into a single portable score — real builder, mixed, or noise deployer.

## Why this is real agent-to-agent composability

Scout is **both a provider and a requester** on the CROO Agent Protocol — a genuine dual role on one connection:

- **As a provider:** an end caller pays Scout (USDC) with a deployer wallet to score.
- **As a requester:** Scout pays the **PulseBNB Agent** (USDC) to classify each deployment.

One paid order to Scout fans out into *multiple paid sub-orders* to a second agent, all settled through CAP. Scout cannot do its job without hiring another agent — this is composition, not a wrapper.

```
End caller                 Builder Scout                  PulseBNB Agent
    |                            |                              |
    |-- pay (wallet to score) -->|                              |
    |                            |-- look up deployments -------|
    |                            |-- pay + classify contract -->|  (A2A sub-order 1)
    |                            |<------- verdict -------------|
    |                            |-- pay + classify contract -->|  (A2A sub-order 2)
    |                            |<------- verdict -------------|
    |                            |   aggregate -> reputation    |
    |<--- deployer score --------|                              |
    v                            v                              v
```

The dual role runs on one CAP WebSocket — Scout distinguishes incoming orders (it serves) from its own outbound sub-orders (it pays) by tracking negotiation IDs.

## What it delivers

```json
{
  "wallet": "0x...",
  "verdict": "real_builder | mixed | noise_deployer",
  "deployer_score": 0-100,
  "deployments_checked": 3,
  "real_pct": 67,
  "classified": [
    {"address": "0x...", "verdict": "real", "confidence": 85}
  ],
  "source": "BNB Builder Scout (powered by PulseBNB Agent on CROO)"
}
```

The score weights the share of *real* deployments and the average confidence of those builds — a wallet that ships original contracts scores high; a wallet spamming templates scores low.

## 🔗 Verified On-Chain — Base Mainnet

Scout is live on the CROO Agent Store: **6 orders, 100% completion**, dual-role A2A confirmed. Its companion PulseBNB has settled 11+ orders at 100%. Verify any: `https://basescan.org/tx/<hash>`

| PulseBNB order | Verdict | Delivery tx |
|---|---|---|
| `89f94f2b` | real | `0x1b3c7cf3b7b5cf2a6d46100998dea96be32cff43e3e4cf5f19393ccdf262924d` |
| `b1b21dbb` | real | `0xc0ea24d9f62a8eb65a0e87a7403f854e1aee1181e4a7e0dcb5f4af7e902277d1` |
| `9237014b` | real | `0x47766d8e693497a4524429d1c9ba21285431468c28818d78f5d73a8dab14a75b` |

### Cross-team A2A

Our project placed real paid orders on other builders' agents (`ours:false`):

| Called | Team | Pay tx |
|---|---|---|
| VeriClaim | Artema | `0x254359c28e313555cfd7de8a91aeeeebbf0d1beba183fe20759023cfea39a8a2` |
| Manga Localizer | abdulmajeed | `0x79608c7c223fd5b3ee7bd3e9719df184e20f52a9dd2467591c503daccab1ae5d` |
| ZERU | Precious_Noah | `0x99eaa5202e4d9c358efa8bb73ee96f5b0fe57288bef977845b5969064ba8505e` |

## Tech stack

| Layer | Choice |
|---|---|
| Agent protocol | CROO CAP (`croo-sdk`, Python) — dual role |
| Downstream agent | [PulseBNB Agent](https://github.com/Makabeez/pulsebnb-croo) (paid sub-calls) |
| Settlement | USDC on Base |
| Runtime | Python 3.12 async, 24/7 |

## Run it

```bash
git clone https://github.com/Makabeez/builder-scout.git
cd builder-scout
python3 -m venv venv && source venv/bin/activate
pip install croo-sdk httpx python-dotenv
cp .env.example .env   # add CROO_SDK_KEY + PULSEBNB_SERVICE_ID
python3 builder_scout.py
```

## Built for

**CROO Agent Hackathon** — a companion to [PulseBNB](https://github.com/Makabeez/pulsebnb-croo). Together they form a composable two-agent system: signal (PulseBNB) → reputation (Scout), one agent paying another to build a higher-order service.

## License

MIT
