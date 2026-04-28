# REASONING TRACES - VISUAL ARCHITECTURE & FLOW

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        BACKEND PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  INPUT: Article  →  [RKR Filter]  →  [Tarkov Extract]  →  [EEM + NSA] │
│                                                                          │
│     Phase 1              Phase 2           Phase 3                       │
│  Risk Scoring        Article Parse      Event Enrichment                │
│                      Entity Extract     Person Scoring                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Trace Generation Flow (Current)

```
┌────────────────────────────────────────────────────────────────────┐
│ 1. EEM PIPELINE - Event Enrichment Module                          │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  FOR EACH EVENT:                                                  │
│  ├─ _analyze_event()                                             │
│  │  ├─ LLM Analysis (or fallback)                               │
│  │  └─ EEMTraceCollector.collect() ✅ GENERATES                │
│  │     ├─ sentiment_calculation                                │
│  │     ├─ impact_scoring                                       │
│  │     ├─ source_tier_logic                                    │
│  │     └─ keyword_extraction                                   │
│  │                                                              │
│  └─ trace_repo.save()  ❌ NOT COMMITTED TO DB                  │
│     └─ flush() only → Session memory                           │
│        (Lost when session closes)                              │
│                                                                │
│  RESULT: Trace exists in memory but NOT in database ❌         │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│ 2. NSA PIPELINE - Non-Sanctioned Analysis                          │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  FOR EACH PERSON AT FIRM:                                        │
│  ├─ Fetch sanctions evidence                                     │
│  ├─ Fetch news evidence                                          │
│  ├─ score_person()                                               │
│  │  └─ NSATraceCollector.collect() ✅ GENERATES                │
│  │     ├─ evidence_summary                                      │
│  │     ├─ scoring_breakdown (per evidence item)                │
│  │     ├─ aggregation_logic (raw → clamped)                    │
│  │     └─ person_context                                        │
│  │                                                              │
│  └─ trace_repo.save()  ❌ NOT COMMITTED TO DB                  │
│     └─ flush() only → Session memory                           │
│        (Lost when session closes)                              │
│                                                                │
│  RESULT: Trace exists in memory but NOT in database ❌         │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│ 3. TARKOV PIPELINE - Article Extraction                            │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  FOR EACH ARTICLE:                                               │
│  ├─ EventExtractor.extract_events_keyword_based()               │
│  │  ├─ FOR EACH EVENT TYPE MATCHED:                            │
│  │  │  └─ TarkovTraceCollector.collect() ✅ GENERATES          │
│  │  │     ├─ keyword_matching                                  │
│  │  │     ├─ confidence_calculation                            │
│  │  │     ├─ risk_level_assignment                             │
│  │  │     ├─ title_generation                                  │
│  │  │     └─ source_reference                                  │
│  │  │                                                          │
│  │  └─ trace_repo.save()  ❌ NOT COMMITTED TO DB              │
│  │     └─ flush() only → Session memory                       │
│  │                                                            │
│  └─ PersonExtractor (NO TRACES YET) ❌                        │
│  └─ ConnectionExtractor (NO TRACES YET) ❌                    │
│                                                                │
│  RESULT: Event traces in memory but NOT in database ❌        │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│ 4. MARKET PIPELINE - Price & Listing Analysis                      │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  FOR EACH FIRM:                                                  │
│  ├─ TickerSearch                                                 │
│  ├─ ListingFetch                                                 │
│  ├─ MarketTraceCollector.collect() ✅ GENERATES                 │
│  │  ├─ ticker_search                                           │
│  │  ├─ listing_selection                                       │
│  │  ├─ fetch_results                                           │
│  │  └─ fetch_parameters                                        │
│  │                                                              │
│  ├─ db.commit() ← BEFORE TRACE SAVE                           │
│  ├─ trace_repo.save()                                          │
│  │  └─ flush() + db.commit() ✅ WORKS!                        │
│  │                                                              │
│  └─ db.commit() ← AFTER TRACE SAVE                            │
│                                                                │
│  RESULT: Traces persisted to database ✅                      │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│ 5. RKR PIPELINE - Risk Keyword Recognition                         │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  FOR EACH ARTICLE:                                               │
│  ├─ Language detection                                           │
│  ├─ Keyword matching                                             │
│  ├─ Risk score calculation                                       │
│  ├─ Threshold check                                              │
│  │                                                              │
│  └─ NO TRACE COLLECTION ❌                                      │
│     └─ Decision logic not captured                              │
│                                                                │
│  RESULT: Zero traces generated ❌                              │
└────────────────────────────────────────────────────────────────────┘
```

## Data Flow: Session vs Database

```
SESSION (In-Memory)                     DATABASE (Persistent Storage)
═══════════════════════════════════════════════════════════════════════

┌─────────────────────┐
│ trace_repo.save()   │                ┌──────────────────────┐
│ called              │                │ reasoning_traces     │
│                     │                │ table                │
│  model =            │                │ (EMPTY in EEM/NSA)   │
│    ReasoningTrace   │                │                      │
│                     │                └──────────────────────┘
│  session.add()      │                        ▲
│       ↓             │                        │
│  ┌──────────────┐   │               (BLOCKED - no commit)
│  │ Session      │   │
│  │ - pending    │   │
│  │   add        │   │
│  └──────────────┘   │
│       ↓             │
│  session.flush()    │ ✓ Writes to session → memory
│       ↓             │
│  ┌──────────────┐   │
│  │ Session      │   │
│  │ - current    │   │
│  │   (trace)    │   │
│  └──────────────┘   │
│                     │
│  session.commit()   │ ✗ MISSING!
│       ↓             │
│    Database         │ (never reaches here)
│    persisted        │
└─────────────────────┘

WHAT HAPPENS:
1. Session closes → All pending + current objects discarded
2. Traces never reach database
3. Evidence: run_traces_demo.py shows traces in output
   but SELECT COUNT(*) returns 0
```

## Problem Summary Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    REASONING TRACES PIPELINE                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ✅ Trace Collection        (Working)                           │
│     └─ EEMTraceCollector                                         │
│     └─ NSATraceCollector                                         │
│     └─ TarkovTraceCollector                                      │
│     └─ MarketTraceCollector                                      │
│                                                                  │
│  ✅ Trace Generation         (Working)                           │
│     └─ collect() produces complete trace objects                │
│                                                                  │
│  ✅ Trace Schema             (Working)                           │
│     └─ Pydantic models defined and validated                    │
│                                                                  │
│  ✅ Database Model           (Created)                           │
│     └─ reasoning_traces table with indexes                      │
│                                                                  │
│  ✅ Repository CRUD          (Partially working)                 │
│     ├─ save() method exists but...                              │
│     ├─ get_by_classifier() works                                │
│     └─ get_by_id() works                                        │
│                                                                  │
│  ❌ PERSISTENCE              (BROKEN)                            │
│     └─ save() only flushes, doesn't commit                      │
│     └─ Traces lost when session closes                          │
│                                                                  │
│  ❌ RKR Implementation       (Missing)                           │
│     └─ No collector or traces                                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

BLOCKERS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 CRITICAL: Missing db.commit() after trace_repo.save()
 Impact:   ALL traces (EEM, NSA, Tarkov) lost
 Status:   Easy to fix (1 line per location)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 HIGH:     RKR traces not implemented
 Impact:   No decision transparency for keyword scanning
 Status:   Medium effort (new collector + schema)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 MEDIUM:   Person/Connection traces missing
 Impact:   Tarkov partially transparent
 Status:   Medium effort (collectors for other extractors)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Expected State After Fixes

```
┌──────────────────────────────────────────────────────────────────┐
│              REASONING TRACES (AFTER FIXES)                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ✅ Collection            Working                               │
│  ✅ Generation            Working                               │
│  ✅ Schema                Working                               │
│  ✅ Database Model        Working                               │
│  ✅ Repository CRUD       Working                               │
│  ✅ PERSISTENCE           ✓ FIXED                               │
│     └─ db.commit() added at 4 locations                         │
│                                                                  │
│  ❌ RKR Implementation    (To be done)                           │
│  ❌ Tarkov Full Coverage  (To be done)                           │
│                                                                  │
│  RESULT: EEM, NSA, Tarkov, Market traces persist to DB ✅       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

Database Content After Fix:
┌────────────────────────────────────────────────────────────────┐
│ SELECT classifier_name, COUNT(*) as count                       │
│ FROM reasoning_traces                                           │
│ GROUP BY classifier_name;                                       │
├────────────────────────────────────────────────────────────────┤
│ NSA    | 2   (one per person scored)                           │
│ EEM    | 3   (one per event enriched)                          │
│ Tarkov | N   (one per event type matched in articles)          │
│ Market | M   (one per company fetched)                         │
│ RKR    | TBD (zero until implemented)                          │
└────────────────────────────────────────────────────────────────┘
```

## Timeline to Full Implementation

```
PHASE 1: CRITICAL FIX (30 mins)
├─ Add commit to repository.save() ................................. (5 min)
├─ Add commits to EEM pipeline ..................................... (5 min)
├─ Add commits to NSA service ..................................... (5 min)
├─ Add commits to Tarkov processor ................................ (5 min)
├─ Test & verify traces persist ................................... (5 min)
└─ STATUS: All core traces working ✅

                              ↓↓↓

PHASE 2: RKR IMPLEMENTATION (1-1.5 hours)
├─ Create RKRTraceCollector ....................................... (20 min)
├─ Add RKRReasoningTrace schema ................................... (15 min)
├─ Integrate into rkr/pipeline ................................... (20 min)
├─ Test RKR trace generation ..................................... (10 min)
└─ STATUS: 100% keyword scanning transparency ✅

                              ↓↓↓

PHASE 3: EXTENDED COVERAGE (1 hour)
├─ Create PersonTraceCollector ................................... (15 min)
├─ Create ConnectionTraceCollector ............................... (15 min)
├─ Integrate into Tarkov extractors .............................. (20 min)
├─ Test full Tarkov transparency ................................. (10 min)
└─ STATUS: Full article processing transparency ✅

TOTAL ESTIMATED TIME: 2-2.5 hours to complete all phases
```
