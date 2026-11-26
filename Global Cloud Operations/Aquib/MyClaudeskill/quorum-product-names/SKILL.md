---
name: "quorum-product-names"
description: Quorum product, solution, and market naming reference. Use this skill whenever the user is writing, editing, or checking marketing copy, social posts, press releases, case studies, sales content, or web content that mentions Quorum products, solutions, or legacy product names (ValNav, Enersight, PetroVR, Previso, FLOWCAL, zdSCADA, VOR, DaWinci, eONE, Energy Components, Planning Space, Execute, CALCit, and similar). Also use it when the user asks what a Quorum product is called now, which solution or market it belongs to, or what it used to be called, even if they never say "naming" or "hierarchy".
---

# Quorum Product Names

This skill keeps Quorum content consistent with the current product hierarchy, as signed off by the ELT on Sept 29, 2026. The full hierarchy lives in `references/product_hierarchy.json`. Read that file whenever a task involves a Quorum product, solution, or market name.

## How the hierarchy is organized

Master brand (Quorum) > Market classification (Upstream, Midstream, Energy Transition or Renewables) > Qnect Home > Solution (a bundle of products) > Product (specific functionality, sold in a bundle or on its own).

- **Market classifications are internal only.** They give context on the customer's business area but are not part of any product name. Use them to disambiguate and to answer questions, but do not add market labels to customer-facing copy that did not already have them.
- Each product has `legacy_names` (a list), the names it used to go by. An empty list means none was given in the signed-off document, not necessarily that none exists.
- Solutions marked `shared` appear in more than one market: Quorum Measurement, Quorum Land, Quorum zdSCADA, Quorum Supply Chain (plus Quorum Accounting and Quorum Field Operations, which are highlighted as shared but shown only under Upstream).
- Quorum Hydrocarbon Management is not shared, but its product list differs by market (Upstream, Midstream, Energy Transition).
- **Platform:** Qnect AI is the Data & Agentic Platform, offered in Basic, Premium, and Platinum tiers. Each market has its own Qnect Home (formerly On Demand Home). Other platform names: Qnect Foundry (Agentic Runtime), Qnect IQ (Knowledge Base & anthology), QCredit (Quota), and the QAI Basic, QAI Premium, and QAI Platinum chat tiers. Orchestrator and LLM / ML Gateway are pillars with no SKU.
- Quorum Emissions is a sub-SKU of Energy Components, not a standalone product. Do not describe it as one.

## Updating copy

When asked to fix or check copy, replace legacy or shortened names with current names from the JSON file, then list the changes briefly after the revised copy.

1. **Use the full current name.** The product is "Quorum FLOWCAL," not "FLOWCAL" or "Quorum's FLOWCAL." The "Quorum" prefix is part of the name, so skip the possessive to avoid "Quorum's Quorum FLOWCAL."
2. **Swap legacy names for current ones.** Match any entry in `legacy_names` to its current product name. Example: "VOR" becomes "Quorum Supply Chain Orchestration."
3. **Use the right level.** Say "Quorum Measurement" when referring to the solution as a whole, and the product name (such as "Quorum FLOWCAL") when referring to that product. Do not call a solution a product or the reverse.
4. **Check grammar after renaming.** If an old plural phrase like "Field Measurement Apps" becomes a single product name, change the verbs to singular. Note that TESTit, PROVEit, CALCit, PYCit, and ANALYZEit all map to the single product Quorum Field Measurement, so a sentence listing several of them collapses to one name.
5. **Update hashtags too.** For example, #FLOWCAL becomes #QuorumFLOWCAL.
6. **Leave everything else alone.** Do not rewrite sentences that do not mention a product name. Preserve the author's voice, quotes, and customer names.

## When the name is not clear

- If a legacy name is not in the JSON, do not guess. Tell the user the mapping is unconfirmed and ask them to verify.
- Some legacy names map to more than one current product. The `ambiguous_legacy_names` section of the JSON lists them: Energy Components, Portfolio, DaWinci, and eONE. Use the surrounding context to choose, and if the context is not enough, show the options and ask which one is right. Helpful context:
  - **Energy Components**: Production accounting = Quorum Hydrocarbon Production Accounting; revenue accounting = Quorum Hydrocarbon Revenue Accounting; terminals, plants, or energy transition = Quorum Terminal & Plants; midstream pipeline, offshore, or pipeline distribution = Quorum Hydrocarbon Pipeline.
  - **Portfolio**: Asset-level evaluation and optimization in Asset Planning = Quorum Asset Portfolio Optimization; corporate capital allocation in Corporate Planning = Quorum Portfolio Optimization.
  - **DaWinci**: people and crew transport = Quorum Personnel Logistics; cargo and vessel movement = Quorum Cargo Logistics.
  - **eONE**: liquids pipeline = Quorum Liquids Pipeline; marketing and trading = Quorum Energy Marketing.
- A single legacy name may need a different current name depending on market (for example Energy Components in Upstream vs. Midstream). Say which market the answer assumes.

## Answering questions

For questions like "What was ValNav renamed?" or "Which market does Quorum Gas Pipeline belong to?", answer from the JSON in a sentence or two. If the same product appears in several markets, list all of them.

## Example

Input: "Stop by to see how FLOWCAL and VOR work together. #FLOWCAL"

Output: "Stop by to see how Quorum FLOWCAL and Quorum Supply Chain Orchestration work together. #QuorumFLOWCAL"

Changes: added the "Quorum" prefix to FLOWCAL, replaced the legacy name VOR with Quorum Supply Chain Orchestration, and updated the hashtag.
