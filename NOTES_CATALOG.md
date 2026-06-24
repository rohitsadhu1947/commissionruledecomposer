# Notes Catalog — SBI General grid (all 5 sheets)

Every free-text note, classified into the schema's rule types:
**ELIG** = eligibility (decline / allow-only), **MOD** = modifier (±% / set), **REF** = referral to UW, **GEN** = general constraint.
"Source" is the verbatim note; "Structured" is how it maps to canonical rules.
Geo lists referencing RTO codes resolve via Ensuredit's existing RTO Cluster Master.

---

## A. General notes (appear on most sheets — apply across categories)

| # | Type | Source (verbatim, condensed) | Structured |
|---|---|---|---|
| G1 | GEN | "Applicable 11th May 26 to 31st May 26. Sourcing from permitted RTOs only… Management reserved the rights to withdraw grid by giving one week notice." | grid_version validity window; not a per-rule rule |
| G2 | GEN | "Comprehensive sourcing allowed up to 20 yr of vehicle age; SATP up to 25 yr." | ELIG: age_band max — COMP age>20 → decline; SATP age>25 → decline |
| G3 | GEN | "Make/GVW change endorsement requires Head Agency approval. Intentional wrong booking on Make & GVW → entire PO forfeited." | policy/process rule; flag, not auto-enforced |
| G4 | REF | "Any motor proposal where IDV > Rs 2 Cr (other than TW; TW above 5 Lakhs) → refer HO Motor UW for RI support & approval." | REF: idv>2Cr (TW idv>5L) → review/refer, not auto-pay |

---

## B. Two-Wheeler (sheet: PCV, MISD & TW) — IMPLEMENTED in POC

| # | Type | Source (condensed) | Structured |
|---|---|---|---|
| TW1 | ELIG | "TW COMP Declined model: Splendor & Passion all variants declined in Bihar/UP/Delhi/NCR." | decline: make HERO model {Splendor,Passion}+variants, policy COMP, states {BR,UP,DL,NCR} |
| TW2 | ELIG | "All sports & cruiser bikes declined" — long make/model list (Hero CBZ/Hunk/Xtreme; Honda CBR/CB series; Bajaj Dominar/Pulsar; KTM/Ducati/BMW/Kawasaki/Triumph/Benelli/Hyosung/CF Moto all; Yamaha FZ/MT/R-series; Suzuki Gixxer/Hayabusa; RE Std; etc.) | decline: policy COMP, sub_segment BIKE, make/model ∈ list, pan-India |
| TW3 | ELIG (allow-only) | "TW SCOOTER COMP doable RTOs: GJ-all, HP-all, KA-all, MH-all, RJ-all, UP-Eastern-all, TN-(specific RTO list); North East & PY → SAOD only." | allow-only: SCOOTER COMP permitted ONLY in listed geos; elsewhere COMP declined (SAOD may still apply) |
| TW4 | ELIG (allow-only) | "TW BIKE COMP doable RTOs: GJ-(GJ01/04/05/06/18/27/28/29), MH-all, UP-Eastern-all, TN-(SAOD only, specific list); NE & PY → SAOD only." | allow-only: BIKE COMP permitted ONLY in listed geos |
| TW5 | ELIG | "TW SCOOTER & BIKE COMP Declined Make per RTO: TVS→CG/KL/MP; HERO→CG/KL/MP/RJ/HP; Royal Enfield→CG/KL/MP/HP/KA/RJ/TN; SUZUKI→CG/KL/MP; YAMAHA→CG/KL/MP; all other makes→CG/KL/MP." | decline: policy COMP, per-make × state list |
| TW6 | ELIG | "TW SCOOTER & BIKE SATP Declined RTO List: GJ,PB,CH,KA,TN,AS,RJ,GA,NL,KL,JK,CG,MP,HR,UA/UK,TR,MZ,AR,ML,MN,PY,DD,DN,SK,AN,LD,LA." | decline: policy SATP, sub_segment {SCOOTER,BIKE}, states ∈ list |

**⚠ Reconciliation flags (need business confirmation):**
- The grid prints scooter/bike rates for several states NOT in the TW3/TW4 COMP doable lists (e.g. WB, Bihar, Odisha, AP, TS). Likely meaning: the grid rate applies to whichever policy type is *doable* in that geo (COMP where listed, else SAOD). Confirm: is the single grid % used for both COMP and SAOD, gated by these notes?
- North East scooter/bike grid cells are blank yet TW3/TW4 say "SAOD only allowed" there — rate source for NE SAOD is unclear.

---

## C. Private Car (sheets: GCV&PvtCar, PV SATP, PV SAOD Highend, Declined Makes)

| # | Type | Source (condensed) | Structured |
|---|---|---|---|
| PC1 | MOD | "Reduction of 5% grid on Private Car NON-NCB Comprehensive and SAOD (Non High-End)." | MOD: SUBTRACT 5 when category PVT_CAR, ncb=NON_NCB, policy∈{COMP,SAOD}, non-highend |
| PC2 | MOD | "Zero payout on High-End NON-NCB policies." | MOD: SET 0 when PVT_CAR highend, ncb=NON_NCB |
| PC3 | MOD | "PVT SATP: Grid lesser by 3% for vehicle age 1-9 years." | MOD: SUBTRACT 3 when PVT_CAR, policy SATP, age 1-9y |
| PC4 | ELIG | "PVT CAR Declined Model (COMP & SATP both)" — Ashok Leyland Stile, Bajaj Tempo Trax/Traveller, Chevrolet Enjoy/Tavera, Datsun GO+, Force all, ICML Rhino, Mahindra (540/555DI/Armada/CDR/…/Jeeto/Voyager), Maruti Eeco/Omni/Versa, Mercedes MB100D/MB Class, Tata 207/Ace/Magic/Venture/Winger/Sumo, Toyota Hiace/Qualis. | decline: PVT_CAR, make/model ∈ list, policy {COMP,SATP} |
| PC5 | ELIG | "Pvt Car Declined Make & Models" sheet — whole makes declined (Audi, BMW-absent? Volvo, Tesla, Porsche, Lamborghini, Bentley, Isuzu, Mitsubishi, etc. = "All Models & Variants"), plus per-make model exclusions (Renault except Duster/Triber/Kwid/Kiger; Ford except Ecosport; Nissan except Magnite/Kicks; Toyota Etios/Camry/…; Maruti Gypsy/Versa/…; Tata Magic/Nano/…; Hyundai Santa Fe/Getz/…; Mahindra Supro/Xylo/…; etc.). | decline: PVT_CAR, make (or make+model) ∈ master list |
| PC6 | ELIG | "Pvt car SATP sourcing allowed excluding declined makes/models per UW guidelines." | cross-ref PC4/PC5 for SATP |
| PC7 | RATE | PV SAOD Highend sheet: per RTO cluster × model-cluster (make+model+fuel) → Package %, SAOD % (mostly 15/20). | RATE rules, category PVT_CAR, segment HIGHEND |

---

## D. GCV / Commercial (sheet: GCV & Pvt Car Payout Condition)

| # | Type | Source (condensed) | Structured |
|---|---|---|---|
| GCV1 | MOD | "All Slab A & B Broker: above 25 Lac → grid applicable; below 25 Lac → less 2% PO." | MOD: SUBTRACT 2 when premium_slab < 25L |
| GCV2 | MOD | "Additional 2% — DL Registration vehicle, 2.5 to 3.5T segment only." | MOD: ADD 2 when gvw 2.5-3.5T, registration_state=DL |
| GCV3 | ELIG/RATE | "20T-40T segment: TN-C payout grid applicable for RTOs TN20, TN54, TN88." | RATE override: map those RTOs to TN-C grid |
| GCV4 | ELIG | "Declined Vehicle Makes (all tonnage): Electric fuel declined for all GCV; all imported makes & Volvo, MAN, AMW, Mercedes, Eicher (>3.5T), Isuzu, Bharat Benz, Hyundai, SCANIA. Above 12T allowed makes = Tata, AL, Mahindra only." | decline: GCV fuel=EV (all); make ∈ list; >12T make ∉ {Tata,AL,Mahindra} |
| GCV5 | ELIG | "GCV 3W Declined RTO Cluster" — separate cluster lists for Upto-5yr and Above-5yr age bands. | decline: GCV 3W, per age_band × cluster list |
| GCV6 | ELIG | "Upto 2.5T GCV Decline Cluster (≤5y & >5y): CH-R, CH-Rest, HR-Rest, MP-GJ, MP-Rest, UP-Rest2." | decline: GCV ≤2.5T, clusters ∈ list |
| GCV7 | ELIG | "Upto 2.5T GCV: Mahindra Supro added under ≤2.0T-all-makes grid; Rest-of-TN = Chennai-II grid for Tata Ace ≤2.0T; UP78 doable on ≤2T Tata Ace only; HR68 doable under Punjab&Chandigarh." | RATE mapping + ELIG specifics |
| GCV8 | ELIG | "2.5T-3.5T GCV Declined Cluster (≤5y & >5y lists); Non-doable RTOs: AP02/03/04/21/26/27." | decline: per age_band × cluster + specific RTO |
| GCV9 | ELIG | "3.5-5.0T, 5.0-7.5T, 7.5-12.0T GCV: Pan-India decline, all cluster/make/model." | decline: GCV those GVW bands → all declined |
| GCV10 | ELIG | "12T-20T & 20T-40T GCV Decline Clusters (separate New/≤5y and >5y lists)." | decline: per GVW × age_band × cluster list |
| GCV11 | ELIG | "Above 40T: New & ≤5y → all clusters declined; >5y → only HP, JK, OD allowed." | decline / allow-only by age_band |

---

## E. PCV / MISD (sheet: PCV, MISD & TW)

| # | Type | Source (condensed) | Structured |
|---|---|---|---|
| PCV1 | MOD | "PCV Taxi (6+1): Non-NCB grid lesser by 5%." | MOD: SUBTRACT 5 when PCV taxi, ncb=NON_NCB |
| PCV2 | ELIG | "PCV 3W (3+1) Doable RTO list" — long per-state RTO + fuel conditions (e.g. MH diesel declined; UP only Bajaj make w/ Battery/Petrol/CNG; Delhi diesel&battery declined). | allow-only + per-geo fuel/make conditions |
| PCV3 | ELIG | "PCV 3W Declined States (all RTO): MP/KL/AS/MN/AR/CG/AN/ML/MZ/SK/TR/NL/DD/DN/PY/HP/HR(excl Gurgaon)/LA/LD/UA/UK." | decline: PCV 3W, states ∈ list |
| PCV4 | ELIG | "PCV 3W: carrying capacity >3 passengers avoided incl EVs." | decline: PCV 3W seating>3 |
| PCV5 | ELIG | "PCV Taxi (6+1): up to 6 passengers; EV TAXI declined Pan-India; allowed-RTO list per CC; >1000CC-only states list; declined model list (Tavera, Innova-only-via-state-capital, Force all, etc.)." | allow-only RTOs + decline EV + decline model list |
| PCV6 | ELIG/RATE | "PCV Taxi State Capital (Innova/Crysta/Hycross/Scorpio/Bolero): specific RTO list." | RATE applies only to listed RTOs+models |
| PCV7 | ELIG | "School Bus: no PO < 18 seater school & staff buses; 18+ package&liability rules; vehicles ≤25yr; >15yr need fitness+permit; in/not-in school name conditions." | ELIG: school bus seating≥18 + doc conditions |
| PCV8 | ELIG | "Staff Bus (>18): doc verification, ≤25yr; all OTHER BUSES (incl <18 seater) declined." | decline: other buses & <18 seater |

---

## F. MISD (sheet: PCV, MISD & TW)

| # | Type | Source (condensed) | Structured |
|---|---|---|---|
| MISD1 | ELIG | "Tractor w/o trailer & Harvester allowed states/RTOs: Punjab, CH, MH, GJ, AP, TS, BR, JH, OD(excl OD16), TN, WB-East (RTO list), UP-Varanasi cluster (RTO list)." | allow-only: MISD tractor, geos ∈ list |
| MISD2 | ELIG | "Tractor WITH trailer allowed: AP, TS, MH, OD, JH, BR." | allow-only: tractor+trailer geos |
| MISD3 | ELIG | "Declined states for Tractor & Harvester: AS,MP,LD,DL,AN,JK,ML,AR,CG,KL,MZ,SK,NL,PY,DD,DN,LA,RJ,TR,MN,UA/UK,HR,KA,HP,NCR." | decline: tractor states ∈ list |
| MISD4 | ELIG | "Declined sub-class (Other MISD): Ambulance, cash vans, excavators, cranes, bulldozers, road rollers, fork lift, fire brigade, hearses, mobile shops, … (long list)." | decline: MISD sub_class ∈ list |
