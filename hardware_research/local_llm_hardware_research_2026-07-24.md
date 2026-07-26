# Local LLM Hardware Options

*Always-on home machine for local LLM inference, Linux, living-room or bedroom placement. Compiled 24 July 2026.*

## Brief

Target machine: many CPU cores, **128GB RAM minimum, no fixed ceiling — open to 256GB+ if it genuinely makes sense**, decent storage, a GPU with at least 24GB VRAM (or an equivalent unified-memory pool), Linux rather than Windows/macOS, similar footprint ambition to a Mac Mini though size is negotiable, tolerant of moderate fan noise, sitting behind a TV. Budget: open, from a couple of thousand dollars up to $15,000–20,000 if justified. Mac hardware considered as an alternative if it makes more sense. Any vendor/product line that has been fully discontinued is excluded from these recommendations.

## Market context: the July 2026 memory/GPU shortage

An active DRAM and GPU memory shortage is distorting every category below. Apple pulled its 128GB+ Mac Studio and Mac Mini configurations between March and May 2026, and discontinued the Mac Pro entirely in March. Discrete GPU prices (RTX 3090/4090/5090, RTX PRO 6000 Blackwell) are all up 30–55% year-on-year. This is a real-time snapshot — recheck prices immediately before any purchase.

**Currency note:** prices below are given in the buyer's actual regional checkout currency wherever one was confirmed to exist (EUR for EU/Irish storefronts, GBP for UK ones). Where no regional storefront was found and the vendor is USD-only, the USD figure is shown alongside an approximate conversion (July 2026 rate: 1 USD ≈ €0.88 / £0.75) — clearly marked as a *converted estimate, not a live checkout price*, and excluding any customs/VAT/duty due on top (see the Ireland/UK sourcing section below). A few figures are JS-rendered and couldn't be confirmed by search/fetch in this audit — Framework's Irish-checkout EUR price (US price is confirmed), Amazon.co.uk's GMKtec listing price, apple.com/ie's own checkout figure, CeX Ireland's listing prices, and Puget's dynamically-loaded configurator base prices — these are flagged individually and should be checked directly before buying.

## Buyer location: Dublin, Ireland (with UK access)

This materially changes which vendors are actually usable and changes the true landed cost. Verdict per vendor:

| Vendor | Verdict |
|---|---|
| **Lambda / Lambda Labs** | Discontinued its entire desktop line (Vector/Vector One/Vector Pro) in Aug 2025 — dead option, dropped from this report entirely. |
| **Puget Systems** | International shipping limited to Canada only. No EU/Ireland shipping or import-of-record support. Not usable for this buyer. |
| **System76** | Ships to Ireland (65 countries/territories), but customs duty + Irish VAT (23%) + broker fees are collected on delivery, not at checkout — budget for a real surcharge on top of list price. |
| **Framework Desktop** | Ships directly to Ireland with a EUR, VAT-inclusive checkout (€12 EU shipping) — confirmed, the smoothest US-brand option here. |
| **Beelink / GMKtec** | Order via their own EU/UK-warehouse checkout (Beelink ships GTR9 Pro from an EU warehouse with "no import fees" stated at checkout; GMKtec EVO-X2 is sold on de.gmktec.com in EUR and listed UK-side on Amazon.co.uk) rather than AliExpress/direct-China — avoids customs delay and VAT-at-the-door surprises. |
| **Minisforum** | Has an EU store ([minisforumpc.eu](https://minisforumpc.eu)) shipping to "24 EU nations" — but Ireland is not explicitly named in its deliverable-areas list; confirm at checkout or via eu@minisforum.com before ordering. |
| **Apple Mac Studio** | apple.com/ie is a full Irish storefront, 23% VAT included in the displayed price. No friction at all. |
| **DIY components (UK retailers)** | Workable — PC components are generally zero-tariff under the UK-EU trade deal, but Irish VAT isn't always collected correctly at smaller UK-only retailers (Amazon UK/DE is safest). From 1 July 2026 a new **€3 per unique item customs charge applies to non-EU consignments valued €150 or less** — mostly irrelevant to the four-figure purchases in this report, but it will hit small accessory/cable orders; the phase-out of the old low-value exemption is the structural change to watch. |
| **Used GPUs** | CeX has a Dublin store plus many UK stores — an easy, already-familiar channel. eBay.ie/eBay.co.uk, adverts.ie, DoneDeal, and GPUsed.co.uk are also viable. |

Brexit note: the UK is a separate customs territory from Ireland. Ordering from a UK retailer risks Irish VAT + duty (plus the new €3/item charge on sub-€150 consignments) unless the retailer collects Irish VAT at checkout (Amazon does; many boutique UK PC shops don't). Hand-carrying a purchase from the UK in personal luggage doesn't get a blanket "personal use" exemption for high-value electronics — Ireland's Green/Red channel rules still apply above personal allowances.

## Tier 1 — Strix Halo mini PC

Closest match to the "Mac Mini but Linux" brief. AMD Ryzen AI Max "Strix Halo" APU sharing one unified memory pool between CPU and GPU (~96GB of a 128GB config is GPU-addressable) rather than a discrete 24GB card, but functionally covers the same ground. Native Linux, ROCm supported since November 2025.

**Correction from an earlier draft of this report:** the four devices below are *not* a single comparable price tier once each is actually configured with the full 128GB of RAM the brief asks for. Earlier figures mixed prices from different RAM/storage configurations of the same device (e.g. a 64GB or lower-storage SKU quoted next to a 128GB one) and cited stale pre-shortage pricing. Reconciled to the specific 128GB configuration for each:

| Device | Config priced | Price | Notes |
|---|---|---|---|
| [GMKtec EVO-X2](https://de.gmktec.com/en/products/gmktec-evo-x2-amd-ryzen%E2%84%A2-ai-max-395-mini-pc-1) | 128GB RAM / 1-2TB SSD | **€3,229.99-3,359.99** (de.gmktec.com, EU store; US store $3,499.99-3,699.99) | **Correction:** an earlier draft of this report attached the *64GB* tier's price (€1,959.99/$1,999.99) to this 128GB row — confirmed via each store's own Shopify variants JSON, which exposes exact per-tier pricing and settles the ambiguity the previous draft flagged but didn't resolve. The true 128GB price is roughly 75-85% higher than previously stated, and GMKtec is **not** the standout-cheap option in this tier — it lands in the same €3,000-3,900 band as the other three devices below. *Why include it anyway:* still among the cheaper of the four at 128GB, and the only one with a confirmed, un-ambiguous live storefront price on both an EU and US site. Tradeoff: budget brand — support/warranty handling is the weakest of the four. |
| [Framework Desktop](https://frame.work/products/desktop-diy-amd-aimax300/configuration/new) | 128GB RAM, barebones (no storage/OS) | **$3,449 USD** on the US configurator (≈€3,030/£2,580 converted, ex-tax) | *Why include it despite the price:* repairable/upgradeable by design, first-class native-Linux support, and Framework ships directly to Ireland with a EUR, VAT-inclusive checkout (€12 EU shipping) — worth the premium if long-term serviceability and a clean warranty path matter more than lowest sticker price. Confirmed live: $3,449 for the 128GB config (launched at $1,999 in Feb 2025 — a 73% DRAM-shortage rise), currently backordered ~2 weeks. This is barebones: add your own NVMe SSD and OS install on top. The Irish-checkout EUR figure is JS-rendered and unconfirmed — expect roughly €3,400-3,800 VAT-inclusive (converted estimate), check at frame.work directly. |
| [Beelink GTR9 Pro](https://www.bee-link.com/products/beelink-gtr9-pro-amd-ryzen-ai-max-395) | 128GB RAM / 2TB SSD (only config sold) | **$4,349 USD** (reduced from $4,699; ≈€3,820/£3,255 converted) | *Why include it:* fully turnkey — RAM, 2TB SSD, dual 10GbE, ready to boot — and shipped from an EU warehouse with "no import fees" stated at checkout. Still the priciest of the four at 128GB, though the gap to GMKtec is now much smaller than previously stated (see the GMKtec correction above) — choose Beelink over GMKtec for cooling, build quality, networking or EU-warehouse fulfilment, not primarily for price anymore. Pricing history now reconciled: reviews quoted $1,899-1,999 as of late May 2026; the storefront jumped to $4,349 during the June-July DRAM crunch — same trajectory as Framework's 73% rise, so treat $4,349 as the real current price, not an error. |
| [Minisforum MS-S1 MAX](https://minisforumpc.eu/products/minisforum-ms-s1-max-mini-pc) | 128GB RAM / 2TB SSD | **€3,879** (sale, reg. €4,849; minisforumpc.eu) | *Why include it:* the only Strix Halo box here with a free PCIe x16 slot — the one Tier 1 device that leaves a path to adding a discrete GPU later instead of replacing the whole machine. Price re-confirmed live on the EU store, and confirmed distinct from the cheaper 64GB "Local AI Pilot Edition" SKU (an earlier draft's €2,599 figure was that 64GB tier). Caveat: the EU store's deliverable-areas list names "24 EU nations" but not Ireland explicitly — confirm Irish delivery before ordering. |

**Bottom line — corrected:** at true 128GB, there is no longer a ~€2,000 option in this tier. All four devices (GMKtec, Framework, Beelink, Minisforum) now land in roughly the same **€3,000-3,900** band, driven by the DRAM shortage — putting the whole tier closer to Tier 2 territory in price, while still offering Tier 1's quiet/low-power/small-footprint profile. GMKtec is the cheapest of the four at ~€3,230-3,360, but the earlier framing of it as a standout ~€2,000 pick was wrong — that figure was for the 64GB variant. Choosing between the four now comes down to serviceability/warranty/networking tradeoffs (see each row above), not price.

Noise: ~36–41 dBA under sustained load — genuinely living-room-safe. Performance: ~5 tok/s on dense 70B models, better on MoE models. Fine for chat-pace use, not fast for batch work.

## Tier 2 — Single discrete GPU tower

128GB system RAM, one 24–32GB GPU.

- **DIY:** AM5 + Ryzen 9 + 128GB DDR5 + used RTX 3090 (24GB, Grade A — re-confirmed live on [GPUsed.co.uk](https://www.gpused.co.uk/collections/graphics-cards): Zotac Trinity £845.99, Gigabyte Eagle £854.99, ASUS ROG Strix £881.99, all in stock; [CeX Ireland](https://ie.webuy.com/search/?productLineId=10)/eBay.ie/adverts.ie/DoneDeal are alternatives — still best VRAM-per-euro) ≈ **€3,500–4,400 all-in** for the full build. *Why this is here:* fastest tokens/sec per euro of any option in this report, standard upgrade path, everything user-serviceable — the right choice if throughput matters more than a mini-PC footprint. Stepping up to an RTX 4090 (24GB): GPUsed also stocks Grade A 4090s at **£1,749.99** (Gainward/Palit/ASUS TUF, in stock — notably under the ~$2,250-2,750 US used/new market), roughly doubling the GPU line item for ~2x inference speed. UK component retailers (Scan.co.uk, Overclockers.co.uk, CCL, Novatech) are workable for the rest of the build — confirm Irish VAT is collected at checkout.
- **Prebuilt, native Linux:** System76 Thelio Mira. *Why it's here:* the only vendor selling a warrantied, Linux-native (Pop!_OS/Ubuntu) 128GB + RTX-class tower that ships to Ireland — the option if you want Tier 2 performance without building it yourself, at a premium plus duty/VAT on delivery. **Pricing caveat (re-verified):** the **$1,699 "starts at" price is a minimal base config** (16GB is the smallest RAM option on the configurator — the memory list runs 16/32/48/64/96/128/192GB, and GPU options run from integrated Radeon up to RTX 5090/4090 Turbo). The configurator's per-option upcharges are dynamically loaded and didn't expose the 128GB + 24GB-GPU total to this research — **get a live quote from system76.com before treating any Thelio Mira figure as the price of the machine this tier describes.** Expect it to land well above the comparable DIY build.

Fastest tokens/sec per euro of any tier here. Caveat: stock GPU coolers are gaming-tuned, not built for sustained inference — power-cap the GPU (70–80%, costs little on memory-bound inference) or choose a vendor build already tuned for quiet operation.

## Tier 3 — Workstation class

256GB RAM, workstation-class GPU (48–96GB).

- **System76 Thelio Major** — *why it's here:* the one vendor-warrantied, Ireland-shippable route to a 256GB + 96GB-GPU Linux workstation without self-building; the RTX PRO 6000 96GB is a genuine configurator option (listed "non-refundable", with a mandatory 2x750W PSU). **Pricing caveat (re-verified live):** the **$6,999 "starts at" price is the base config — Threadripper 9960X, 4GB NVIDIA A400 GPU, 64GB ECC DDR5, 500GB SSD** — nowhere near 256GB RAM + a 96GB RTX PRO 6000 Blackwell. The configurator doesn't publish the upcharges, but given the GPU alone now lists at $13,250 (see below), the realistic fully-specced total is **likely $25,000+**, not $7,000-15,000 as an earlier draft implied. **Get a live configurator quote or talk to System76 sales before budgeting against any "starts at" figure for this build.** Ships to Ireland with duty/VAT/broker fees collected on delivery, on top of whatever that quote comes to.
- **RTX PRO 6000 Blackwell (96GB)** — NVIDIA's own listing is **$13,250** (up 55% since March 2025 launch, driven by the GDDR7 shortage); July 2026 street/tracker pricing for the Max-Q variant runs **~$12,700-15,200** (≈€11,200-13,400 / £9,500-11,400 converted). The $8,000 low-end figure in an earlier draft was stale launch-era pricing, and an $11,000 floor quoted in a later draft is now below anything observable — budget $13,000+ per card.
- **DIY Threadripper PRO/WRX90 + 256GB ECC + this GPU** is the more honestly-priced route at this tier, sourced via UK/EU component retailers or direct import, since you can see each line item rather than trusting a vendor's "starting at" headline. *Who it's for:* only worth it over Tier 2 if you specifically need 48-96GB of VRAM in one box (70B+ dense models at speed, large-context serving) — otherwise Tier 2 delivers most of the throughput at a quarter of the cost. Puget Systems sells an equivalent spec but ships to US/Canada only, so it's not directly purchasable from Ireland.

## Tier 4 — Multi-GPU / crazy money

Multi-GPU builds (2-4x RTX PRO 6000 Blackwell or RTX 5090). **Corrected — an earlier draft attached Puget's headline price to the wrong config:** [Puget's AI page](https://www.pugetsystems.com/solutions/ai/develop/) shows "**Multi GPU Workstation starting at $14,451.78**", but that is the product line's entry headline, *not* the price of a 2x RTX PRO 6000 build — two of those GPUs alone cost ~$26,500 at current list, so $14.5k arithmetically cannot include them. The same page shows the **2x RTX PRO 6000 Blackwell Max-Q + Threadripper PRO 9975WX + 256GB DDR5** spec at a "price as configured" of **$48,952.61**; the configurator's own base (1x RTX PRO 6000 Max-Q, 256GB) loads its price dynamically and couldn't be captured. Realistic budget for a 2x-96GB-GPU machine: **mid-$30,000s to ~$49,000** (≈€30,000-43,000 converted), whoever builds it. Puget itself ships US/Canada only and is cited here purely as a price reference — a DIY build sourced through UK/EU retailers and CeX/GPUsed is the practical route from Ireland. *Who this is for:* diminishing returns for a single-user home setup unless the goal is running 200B+ models at real speed or serving multiple concurrent users; at €30k+ it's lab equipment, not a living-room PC.

## Where Mac stands right now

Capped at 96GB unified memory (Mac Studio M3 Ultra) — it can no longer hit the 128–256GB target at any price, and the Mac Pro that used to go higher is discontinued. Mac Studio inference is quiet (near-silent, ~120–150W under load) and can fit very large models thanks to unified memory, but at meaningfully lower tokens/sec than a discrete-GPU rig for the same money. Off the table unless 96GB and slower throughput is an acceptable trade.

**Irish price — needs a direct check, and note the June 2026 price hike.** [apple.com/ie/mac-studio](https://www.apple.com/ie/mac-studio/) is a genuine EUR, VAT-inclusive storefront with no import friction, but its checkout price didn't render to automated fetching in this research. What did verify: Apple raised M3 Ultra Mac Studio pricing in June 2026 (the 96GB/1TB config is now **$5,299 US**, up ~$1,300), so any EU figure from before June is stale — including the €4,349-4,899 range seen in early-2026 EU listings. Current Irish reseller data points: Elara.ie at **€5,369.75 incl. VAT** (may predate the full hike) and Select at "**from €6,399**" for the M3 Ultra line. Budget roughly €5,400-6,400 and check apple.com/ie directly for the real current figure.

## Going beyond 256GB — is it worth it?

Checked directly, since the brief now allows for it. Verdict: **not worth it right now.**

- **System76 Thelio Major is confirmed capped at 256GB** — no 512GB/1TB configurator option exists on that model.
- **DIY Threadripper PRO/WRX90 can technically go to 1TB+** (WRX90 supports up to 2TB across 8 channels), but DDR5 ECC RDIMM pricing has risen ~116% between Q1 2025 and Q1 2026 amid a structural shortage (fabs reallocating capacity to HBM — 23% of global DRAM wafers in 2026 vs 8% in 2024), and mid-2026 quotes are worse still: a 256GB build that cost $800–1,200 in early 2025 now runs **$2,000–4,000+ in RDIMMs alone**, with the shortage projected to last into Q4 2027. Scaling to 512GB/1TB adds many thousands more in RAM by itself.
- **AMD EPYC platforms** (12-channel, up to 6TB/socket) exist as an alternative, but there's no polished Linux-native one-box product in this space — it's server/HPC-style DIY-adjacent builds (e.g. Velocity Micro ProMagix HD360A), not a System76-equivalent experience.
- **The actual payoff is small.** The use case for 400GB+ RAM is running huge MoE models (DeepSeek-R1/V3 671B-class) via CPU+GPU hybrid offload. Real community builds (e.g. an EPYC 7702 + 512GB DDR4 + 4×RTX 3090 rig, widely cited in the local-LLM community) get DeepSeek R1 671B (Q4_K_M, ~377GB) running at only **~3.5–8 tok/s** depending on quantization and offload technique — usable for batch/offline work, not snappy interactive chat.

Bottom line: extra RAM above 256GB only makes sense as a narrow, deliberate bet on running one specific 600B+ parameter model and accepting single-digit tokens/sec, at a moment when every extra 256GB block costs thousands more than it did a year ago. For general local-LLM experimentation, more/better GPU VRAM is the far more cost-effective lever — stick to 128–256GB unless there's a specific model in mind that demands more.

## Recommendation

Given noise is genuinely tolerable and the goal is to start experimenting, a **Tier 1 Strix Halo mini PC at true 128GB is still the right entry point** — but at 128GB specifically, all four devices now sit in roughly the same **€3,000-3,900** band (an earlier draft wrongly singled out GMKtec at ~€1,960, which was actually its 64GB price). GMKtec is still the cheapest of the four, Framework the best pick if serviceability/native-Linux community support matters, Beelink if you want fully turnkey with EU-warehouse shipping. Since Tier 1 is no longer meaningfully cheaper than a comparably-specced Tier 2 build, it's worth directly comparing a Tier 1 mini PC against a **Tier 2 DIY discrete-GPU tower** (sourcing the GPU from GPUsed.co.uk or CeX Dublin, ~€3,500-4,400 all-in) at similar money — the DIY route gets a real discrete 24GB GPU rather than shared unified memory, likely faster tokens/sec, at a similar price point. For Tier 3, **don't anchor on System76's "$6,999" Thelio Major headline** — that's a 64GB/entry-GPU base config; a genuinely 256GB + RTX PRO 6000 Blackwell build is realistically $25,000+, whether from System76 or DIY, so only go there with a live quote in hand and a clear reason to need that much GPU memory.

## Resources to bookmark

| Site | Use |
|---|---|
| [pcpartpicker.com](https://pcpartpicker.com) | DIY build pricing/compatibility (US-centric; use for spec research, not necessarily checkout) |
| [system76.com](https://system76.com) | Thelio Mira/Major, Pop!_OS or Ubuntu native — ships to Ireland, duty/VAT on delivery |
| [frame.work/desktop](https://frame.work/desktop) | Framework Desktop (Strix Halo) — ships to Ireland, EUR VAT-inclusive checkout |
| [bee-link.com](https://www.bee-link.com/products/beelink-gtr9-pro-amd-ryzen-ai-max-395) | Beelink GTR9 Pro — use EU-warehouse checkout |
| [gmktec.com](https://www.gmktec.com/products/amd-ryzen%e2%84%a2-ai-max-395-evo-x2-ai-mini-pc) | GMKtec EVO-X2 — also on Amazon.co.uk (UK-fulfilled) |
| [minisforumpc.eu](https://minisforumpc.eu/products/minisforum-ms-s1-max-mini-pc) | MS-S1 MAX EU store — confirm Irish delivery before ordering |
| [apple.com/ie/mac-studio](https://www.apple.com/ie/mac-studio/) | Irish Apple storefront, VAT-inclusive, no import friction |
| [llm-tracker.info](https://llm-tracker.info) | Ongoing Strix Halo benchmark tracker |
| reddit.com/r/LocalLLaMA | Community hardware discussion/benchmarks |
| [ie.webuy.com](https://ie.webuy.com/search/?productLineId=10) | CeX Ireland — used GPUs, Dublin store + UK stores |
| [gpused.co.uk](https://www.gpused.co.uk/collections/graphics-cards) | UK used-GPU marketplace |
| eBay.ie, eBay.co.uk, adverts.ie, DoneDeal | Other used-GPU/component marketplaces |
| Scan.co.uk, Overclockers.co.uk, CCL, Novatech | UK component retailers for a DIY build — check Irish VAT is collected at checkout |
| ~~pugetsystems.com~~ | Not usable — ships to US/Canada only |
| ~~lambda.ai~~ | Not usable — discontinued its entire desktop hardware line in Aug 2025 |

## Sources

### Mac

- [Apple removes additional Mac Studio and Mac mini memory configs — MacDailyNews](https://macdailynews.com/2026/05/06/apple-removes-additional-mac-studio-and-mac-mini-memory-configs-as-shortage-worsens/)
- [Apple Cuts More Mac Studio and Mac Mini RAM Options — MacRumors](https://www.macrumors.com/2026/05/05/apple-mac-studio-mac-mini-ram-cuts/)
- [Apple quietly axes 128GB Mac Studio — Tom's Hardware](https://www.tomshardware.com/desktops/apple-quietly-axes-128gb-mac-studio-amid-supply-constraints-and-local-ai-frenzy-highest-memory-capacity-reduced-to-96gb-two-months-after-discontinuation-of-512gb-model)
- [Buy Mac Studio — Apple](https://www.apple.com/shop/buy-mac/mac-studio)
- [Mac Studio M4 Max 128GB: Run 70B Models at 22 tok/s — CraftRigs](https://craftrigs.com/articles/mac-studio-m4-max-128gb-local-llm-what-runs/)
- [Apple Adds More 2026 Macs to Refurbished Store — MacRumors](https://www.macrumors.com/2026/06/26/more-refurbished-2026-apple-products/)
- [Mac Pro discontinuation — Macworld](https://www.macworld.com/article/2320613/new-mac-pro-ultra-release-date-specs-price-m4-m5.html)

### Linux prebuilt workstations

- [Puget Systems AI Training & Inference Server](https://www.pugetsystems.com/landing/ai-training-and-inference-server/)
- [Puget Systems dual RTX 5090 workstations blog](https://www.pugetsystems.com/blog/2025/10/28/our-approach-to-dual-geforce-rtx-5090-workstations/)
- [System76 Thelio Major product page](https://system76.com/desktops/thelio-major)
- [System76 redesign announcement](https://system76.com/blog/post/system76-redefines-linux-platform-with-redesign-of-thelio-desktop-and-workstation)
- [Phoronix: Redesigned Thelio Major review](https://www.phoronix.com/review/system76-thelio-major-9980x)
- [TechRadar: System76 $5,299 RTX 5090 upgrade pricing](https://www.techradar.com/pro/system76-is-charging-an-eye-popping-usd5299-for-an-nvidia-geforce-rtx-5090-gpu-upgrade-on-its-latest-pc-video-card-dwarves-ram-cost-in-latest-thelio-mira-linux-computer)
- [NVIDIA DGX Spark review/pricing](https://intuitionlabs.ai/articles/nvidia-dgx-spark-review)
- [Quiet GPUs for Local AI: Acoustic and Thermal Roundup](https://cornfordandcross.com/digital-ai-art/quiet-gpus-for-local-ai-acoustic-and-thermal-roundup/)

### Small-form-factor unified-memory mini PCs

- [Framework Desktop announcement](https://frame.work/blog/introducing-the-framework-desktop)
- [PCWorld: Framework Desktop review](https://www.pcworld.com/article/2866400/framework-desktop-review.html)
- [EVO-X2 vs GTR9 Pro vs MS-S1 MAX comparison](https://www.upliora.es/blog/gmktec-evo-x2-vs-beelink-gtr9-pro-vs-minisforum-strix-halo-2026)
- [Hardware Corner: Beelink GTR9 Pro launch](https://www.hardware-corner.net/llm-mini-pc-beelink-gtr9-pro-unveiled/)
- [ServeTheHome: Framework Desktop noise measurements](https://www.servethehome.com/framework-desktop-review-a-solid-amd-strix-halo/5/)
- [Strix Halo vs DGX Spark 70B comparison](https://vettedconsumer.com/strix-halo-vs-dgx-spark-running-70b-locally-according-to-people-who-own-both/)
- [DGX Spark price hike to $4,699 — Tom's Hardware](https://www.tomshardware.com/desktops/mini-pcs/nvidia-dgx-spark-gets-18-percent-price-increase-as-memory-shortages-bite-founders-edition-now-usd4-699-up-from-usd3-999)
- [Framework Community: Linux + ROCm stable configs](https://community.frame.work/t/linux-rocm-january-2026-stable-configurations-update/79876)
- [llm-tracker.info: Strix Halo tracker page](https://llm-tracker.info/_TOORG/Strix-Halo)
- [Micro Center: AMD Ryzen AI Halo Developer Platform preview](https://www.microcenter.com/site/mc-news/article/amd-ryzen-ai-halo-preview.aspx)

### DIY tower components

- [Newegg — Best AM5 Motherboards for Ryzen 9000](https://www.newegg.com/insider/best-am5-motherboards-for-ryzen-9000-series-in-2026/)
- [AM5 boards for 256GB DDR5](https://yomotherboard.com/question/looking-for-am5-motherboards-that-can-handle-256gb-of-ddr5-ram/)
- [RTX PRO 6000 Blackwell 96GB listed at $13,250 — VideoCardz](https://videocardz.com/newz/nvidia-now-lists-rtx-pro-6000-blackwell-96gb-gpu-at-13250)
- [RTX Pro 6000 Blackwell pricing hike — Tom's Hardware](https://www.tomshardware.com/pc-components/gpus/nvidia-raises-rtx-pro-6000-blackwell-gpu-pricing-to-usd13-250-55-percent-increase-over-msrp-in-a-years-time)
- [RTX 5090 above $4,300 amid GPU memory crisis — Tech Times](https://www.techtimes.com/articles/320169/20260711/gpu-memory-crisis-prices-rtx-5090-above-4300-nvidia-offers-paper-cards.htm)
- [RTX 4090 discontinued, over $2,500 — WCCFTech](https://wccftech.com/nvidia-geforce-rtx-4090-massive-price-hike-prior-to-rtx-5090-launch-over-2500-usd/)
- [Used RTX 3090 still best value for local AI — XDA Developers](https://www.xda-developers.com/used-rtx-3090-still-best-for-local-ai-in-value/)
- [TRX50 Threadripper 7000 motherboard official prices — WCCFTech](https://wccftech.com/amd-trx50-threadripper-7000-motherboards-official-prices-asus-899-asrock-799-gigabyte-599/)
- [PCPartPicker forum: motherboards supporting 256GB RAM](https://pcpartpicker.com/forums/topic/319938-motherboard-with-support-for-256gb-of-ram)
- [12 Best Silent PC Cases 2026](https://print2webcorp.com/best-silent-pc-cases/)
- [Puget Systems — Solutions for AI Development and Deployment](https://www.pugetsystems.com/solutions/ai/)

### Ireland/UK sourcing

- [System76 shipping policy](https://system76.com/shipping/)
- [Puget Systems international policies](https://www.pugetsystems.com/international-policies/)
- [Lambda's Vector line — discontinuation context](https://lambda.ai/blog/lambdas-vector-nvidia-blackwell)
- [Framework: what countries and regions do you ship to](https://knowledgebase.frame.work/what-countries-and-regions-do-you-ship-to-r1899ikiO)
- [Beelink shipping policy](https://www.bee-link.com/pages/shipping-policy)
- [CeX Dublin store](https://ie.webuy.com/site/storeDetail/?branchId=1500)
- [Irish customs duty on UK online purchases — MoneyGuideIreland](https://www.moneyguideireland.com/irish-customs-duty-on-uk-online-purchases.html)
- [Customs regulations for travellers — Citizens Information](https://www.citizensinformation.ie/en/travel-and-recreation/travel-to-ireland/customs-regulations-for-travellers/)

### Above-256GB RAM viability

- [System76 Thelio Major 2026 — Phoronix](https://www.phoronix.com/news/System76-Thelio-Major-2026)
- [Thelio Major configurator](https://system76.com/desktops/thelio-major-r5-n3/configure)
- [V-Color 2TB RDIMM kits for Threadripper Pro 9000 — Tom's Hardware](https://www.tomshardware.com/pc-components/ram/v-color-announces-2tb-rdimm-kits-for-threadripper-pro-9000-256gb-modules-promise-stability-at-absurdly-high-ram-capacities)
- [2026 Memory Chip Shortage: Server RAM Prices](https://datacenterdisk.com/news/memory-chip-shortage-2026-server-ram-prices)
- [Kingston: Threadripper/PRO DDR5 Memory Population Rules](https://www.kingston.com/en/memory/server-memory/memory-population-rules-wrx90-trx50)
- [AMD EPYC PC Workstations — Velocity Micro](https://www.velocitymicro.com/blog/amd-epyc-pc-workstations-best-of-the-bunch/)
- [Puget Systems Threadripper Workstations](https://www.pugetsystems.com/products/workstations/threadripper/)
- [Running DeepSeek R1 671B Locally — Digital Spaceport](https://digitalspaceport.com/running-deepseek-r1-locally-not-a-distilled-qwen-or-llama/)
- [Guide to optimizing MoE inference across CPU+GPU](https://gist.github.com/DocShotgun/a02a4c0c0a57e43ff4f038b46ca66ae0)
