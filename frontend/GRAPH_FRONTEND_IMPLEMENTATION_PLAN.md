# Frontend Graph Refactor Plan

> Goal: replace the current company-only graph flow with the new backend graph contract from `GET /api/graph/{company_id}`, and render mixed `Company`, `Person`, and `Event` nodes in a way that is both readable and visually rich.

---

## 1. Objective

The frontend currently renders a graph built from two flat datasets:

- `GET /api/companies`
- `GET /api/relations`

That model only supports company-to-company traversal, even when a relation is conceptually caused by a person or event.

The new backend contract already exposes a richer graph:

- `GET /api/graph/{company_id}`
- returns typed nodes and typed edges
- supports `Company`, `Person`, and `Event`
- enriches nodes with Postgres data before sending them to the frontend

The frontend needs to move from "graph as decorated company network" to "graph as first-class typed entity network".

---

## 2. Current State

### 2.1 Data flow today

The current page bootstraps global company and relation state in `src/app/page.tsx`.

- `getCompanies()` loads all sidebar companies
- `getCompanyRelations()` loads all graph edges
- `getCompanyArticles(selectedId)` loads the overview article table

This means the graph view is not loaded independently. It is derived from already-fetched global arrays.

### 2.2 Company-only graph assumptions

The following files hard-code a company-only graph model:

- `src/lib/data.ts`
- `src/lib/api.ts`
- `src/lib/company-graph.ts`
- `src/components/company-graph.tsx`
- `src/components/main-panel.tsx`
- `src/app/page.tsx`
- `src/mocks/handlers.ts`
- `src/mocks/data.ts`
- `src/lib/company-graph.test.ts`
- `src/lib/api.test.ts`

Examples of current assumptions:

- every node is a `Company`
- every graph node contains `company: Company`
- every edge is `sourceCompanyId -> targetCompanyId`
- `buildCompanyGraph()` performs BFS over company ids only
- the detail panel shows only company metrics or a generic relation label

### 2.3 Why people and events do not show now

Even if Neo4j contains `Person` and `Event` nodes, the current frontend drops them for three reasons:

- `getCompanyRelations()` returns company-company relations only
- `buildCompanyGraph()` ignores non-company nodes entirely
- `CompanyGraph` only knows how to render `Company` objects

---

## 3. Target Frontend Architecture

### 3.1 Desired state

The graph view should become its own typed data surface:

- the sidebar and overview can still use `/api/companies` and `/api/companies/{id}/articles`
- the graph view should use `/api/graph/{company_id}` directly
- the graph response should be rendered without first flattening it back into company-only structures

### 3.2 High-level frontend flow

```
Sidebar company selected
        ↓
Overview panel loads company articles as today
        ↓
Graph tab loads /api/graph/{company_id}
        ↓
Frontend parses typed nodes and edges
        ↓
D3 simulation renders:
  Company nodes
  Person nodes
  Event nodes
        ↓
Hover, click, legend, detail panel, and layout all respond by node type
```

### 3.3 Keep the graph API local to the graph view

Do not force the entire app to adopt the graph payload globally on day one.

Recommended boundary:

- keep `Company[]` for sidebar and overview state
- add a dedicated graph-fetch path for the graph tab
- isolate the mixed-node model in new graph-specific types and helpers

This is the smallest correct migration.

---

## 4. Backend Contract To Consume

### 4.1 New API route already available

- frontend proxy: `src/app/api/graph/[companyId]/route.ts`
- backend endpoint: `/api/graph/{company_id}`

### 4.2 Response shape to model explicitly

The frontend should define typed interfaces for:

- `GraphResponse`
- `GraphNode`
- `GraphEdge`

Expected node-level fields:

- common:
  - `id`
  - `entityType`
  - `entityId`
  - `depth`
  - `label`
  - `data`
- company data:
  - trust score
  - trend
  - risk
  - history
  - keyword summary
  - article count
  - country
- person data:
  - name
  - role
  - description
  - affiliated firm
  - event count
- event data:
  - title
  - event type
  - event category
  - risk level
  - occurred at
  - excerpt
  - keywords
  - source name/title/url

Expected edge-level fields:

- `id`
- `source`
- `target`
- `relationshipType`
- `connectionType`
- `intensity`
- `label`
- `sourceUrl`
- `sourceTitle`

---

## 5. File-Level Implementation Plan

## 5.1 `src/lib/data.ts`

Add a dedicated graph domain section instead of extending the existing company-only shapes in an ad hoc way.

Introduce:

- `GraphEntityType = 'Company' | 'Person' | 'Event'`
- `GraphRelationshipType = 'CONNECTION' | 'ABOUT' | 'INVOLVED_IN' | 'AFFILIATED_WITH'`
- `GraphNodeBase`
- `CompanyGraphNodeData`
- `PersonGraphNodeData`
- `EventGraphNodeData`
- discriminated union `GraphNode`
- `GraphEdge`
- `GraphResponse`

Do not overload `CompanyRelation` for this new API. It has different semantics.

## 5.2 `src/lib/api.ts`

Add:

- `getGraph(companyId: string)`

Keep:

- `getCompanies()`
- `getCompanyArticles()`

`getCompanyRelations()` should become deprecated and later removable after the refactor is complete.

## 5.3 `src/lib/company-graph.ts`

This file should be replaced or renamed.

Recommended outcome:

- rename to `src/lib/entity-graph.ts`
- stop building a synthetic graph from company arrays
- instead, transform backend `GraphResponse` into render-friendly simulation data only

Responsibilities of the new helper layer:

- normalize typed node payloads
- compute visual rank or emphasis by type and depth
- derive edge presentation metadata from `relationshipType` and `connectionType`
- precompute summaries used in hover/detail panels
- keep simulation input stable and sorted

It should not re-discover traversal. Traversal already happened in the backend.

## 5.4 `src/components/company-graph.tsx`

This should become the core refactor point.

Recommended outcome:

- rename to `entity-graph.tsx` or keep file name but replace internal model fully

The component must stop assuming `node.company` exists.

New render model:

- `SimNode` contains typed graph node data
- `SimEdge` contains typed graph edge data
- node appearance varies by `entityType`
- edge styling varies by `relationshipType`

Detailed changes required:

- replace `CompanyGraphProps`
  - remove `companies` and `relations`
  - accept `graph: GraphResponse`
  - keep `company` or `selectedCompany` only if needed for header and selection context
- replace `Snapshot` shape
  - store generic node metadata, not `company: Company`
- replace hover logic
  - hover card should switch on entity type
- replace click logic
  - clicking a `Company` node navigates sidebar context
  - clicking `Person` or `Event` should not silently do nothing
  - recommended behavior: keep the selected company, but pin/open detail state for the clicked node

## 5.5 `src/components/main-panel.tsx`

Graph tab messaging and data plumbing must change.

Changes:

- update section title and subtitle to describe mixed entities
- pass graph data into the graph component instead of `companies + relations`
- allow graph loading and graph error states independently from article loading

Recommended copy direction:

- title: `Mapa powiązań`
- subtitle: mention companies, people, and events directly

## 5.6 `src/app/page.tsx`

This file should stop treating graph data as part of the initial page bootstrap.

Recommended state split:

- page-level state:
  - `companies`
  - `articles`
  - `selectedId`
  - `loadingCompanies`
  - `loadingArticles`
  - `companyError`
  - `articleError`
- graph-specific state:
  - either inside `MainPanel`
  - or inside a new `GraphTab` component

Best approach:

- fetch graph lazily when the user opens the graph tab
- cache by selected company id so returning to graph is instant

This avoids loading graph data for every company up front and keeps the overview fast.

## 5.7 `src/mocks/handlers.ts`

Add:

- `GET */api/graph/:companyId`

Keep the current handlers for overview data.

## 5.8 `src/mocks/data.ts`

Stop re-exporting only the old mock structures.

Add graph fixtures:

- one or more `GraphResponse` payloads keyed by company id
- at least one fixture that includes all three node types
- at least one fixture with a person-heavy neighborhood
- at least one fixture with an event-heavy neighborhood

## 5.9 Tests

Update and expand:

- `src/lib/api.test.ts`
  - add `getGraph()` test
- `src/lib/company-graph.test.ts`
  - replace with graph normalization tests for mixed nodes
- add component tests for typed graph rendering if feasible

---

## 6. UI / UX Plan

The graph should feel more like an intelligence map than a generic force-directed chart.

### 6.1 Visual language by node type

Use distinct geometry, not color alone.

Recommended node shapes:

- `Company`
  - filled circle
  - strongest visual weight
  - trust score badge remains on node
- `Person`
  - rounded diamond or pill-shaped lozenge
  - smaller than companies
  - role shown as sublabel on hover or selective inline label
- `Event`
  - hexagon or rounded rectangle
  - tinted by risk level
  - icon cue based on event category if desired

This matters because color-only distinctions become hard to scan once the graph gets denser.

### 6.2 Color system

Keep company risk colors, but separate them from node-type identity.

Recommended rule set:

- type determines base silhouette and stroke pattern
- risk determines glow, badge, and intensity tint
- events use stronger risk tint than companies
- people use more neutral fills with accent strokes

### 6.3 Edge design

Use relationship semantics visibly.

Recommended mapping:

- `AFFILIATED_WITH`
  - soft solid line
  - neutral or muted gold
- `INVOLVED_IN`
  - dotted or segmented line
  - cooler accent
- `ABOUT`
  - thin directional line from company to event
  - subtle arrowhead or taper
- `CONNECTION`
  - strongest line
  - opacity or width influenced by `intensity`

Display `intensity` directly in the graph where available:

- stronger intensity = thicker line and brighter stroke
- low intensity = thinner, more transparent

### 6.4 Detail panel improvements

The current graph detail box is underused. It should become a compact intelligence card.

For `Company` hover/click show:

- full name
- trust score and risk label
- country
- article count
- top keywords

For `Person` hover/click show:

- name
- role
- affiliated company
- number of linked events
- short description

For `Event` hover/click show:

- title
- event category and type
- risk level
- occurred date
- excerpt
- source title / source name
- up to 3 keywords

Recommended behavior:

- hover gives preview
- click pins the card until another node is clicked or cleared

### 6.5 In-graph metadata display

The user asked to display more data on the graph itself. Keep this selective to avoid clutter.

Recommended inline data:

- Company nodes:
  - trust score badge
  - short label
- Person nodes:
  - name label
  - small role chip for direct neighbors only
- Event nodes:
  - short category chip or risk badge
  - event title truncated for direct neighbors only
- Edges:
  - show labels only when hovered or selected

Optional enhancement for readability:

- reveal secondary labels only for depth 0 and depth 1 by default
- hide most depth 2 text until hover

### 6.6 Layout improvements

The current radial layout is tuned for company-only graphs. Mixed entities need more structure.

Recommended layout rules:

- root company remains centered
- depth still affects radial distance
- within each depth, bias by entity type
  - companies slightly closer to center
  - people in a middle orbit
  - events slightly further out
- add stronger collision radius for event labels

Optional second-pass improvement:

- cluster local triangles like Company -> Person -> Event using mild force grouping
- keep graph from collapsing into one dense blob

---

## 7. Interaction Plan

### 7.1 Selection semantics

Click behavior should depend on node type.

Recommended rules:

- click `Company`
  - select that company globally
  - sidebar and overview switch context
  - graph reloads around that company
- click `Person`
  - pin detail panel
  - highlight adjacent company and events
- click `Event`
  - pin detail panel
  - highlight source company and involved people

### 7.2 Highlighting

Improve graph readability through contextual dimming.

Recommended behavior:

- hovering a node highlights:
  - the node
  - first-degree incident edges
  - first-degree neighboring nodes
- non-neighbors fade strongly
- pinned node keeps highlight until dismissed

### 7.3 Legend

The legend should explain both type and relationship semantics.

Split legend into two rows:

- node types: Company, Person, Event
- edge types: Affiliated, Involved, About, Connection

---

## 8. Loading, Error, and Empty States

### 8.1 Loading

Graph loading should be independent from page loading.

Recommended experience:

- overview can render while graph is still loading
- graph tab shows skeleton nodes/edges or a polished shimmer placeholder

### 8.2 Empty state

Replace the current company-only message:

- current: `Brak zdefiniowanych relacji dla ...`
- new: mention that no related companies, people, or events were found in the graph

### 8.3 Error state

Graph fetch failure should not break the overview.

Recommended behavior:

- show graph-local retry UI inside the graph panel
- keep company overview and article list usable

---

## 9. Testing Plan

### 9.1 API tests

Add coverage for:

- `getGraph(companyId)` success
- `getGraph(companyId)` backend failure

### 9.2 Data normalization tests

Test that the graph helper:

- preserves backend node ids exactly
- sorts nodes stably by depth and type
- handles unknown or incomplete optional fields safely
- maps edge styles correctly from `relationshipType`

### 9.3 Component tests

Add targeted tests for:

- rendering all three node types
- clicking a company node calls `onSelectCompany`
- clicking a person node does not change global company selection
- clicking an event node shows event detail content

### 9.4 Manual QA checklist

Verify:

- root company graph renders from seeded backend data
- Jan Kowalski appears as a `Person` node
- event nodes show excerpts and source metadata
- clicking Beta from the graph changes global context cleanly
- mobile layout remains legible
- detail card remains readable with long event titles

---

## 10. Suggested Implementation Sequence

### Phase 1: Data model and fetch path

- add typed graph interfaces to `src/lib/data.ts`
- add `getGraph()` to `src/lib/api.ts`
- add mocks for `/api/graph/:companyId`
- add API tests

### Phase 2: Graph-specific normalization layer

- replace `buildCompanyGraph()` with typed graph normalization helpers
- add tests for mixed-node input

### Phase 3: Component refactor

- refactor `CompanyGraph` into a typed entity graph renderer
- add node-type visuals, hover cards, and edge semantics
- keep company click navigation working

### Phase 4: Main panel integration

- load graph lazily when graph tab opens
- add graph-local loading/error states
- update panel copy and legend

### Phase 5: Polish

- improve label density rules
- tune force layout
- improve hover/pin interactions
- verify desktop and mobile usability

---

## 11. Risks and Design Constraints

### 11.1 Overcrowding

Mixed node graphs can become unreadable faster than company-only graphs.

Mitigation:

- render fewer always-visible labels
- distinguish by shape first, text second
- use pinned detail card for depth

### 11.2 Accidental architecture regression

It would be easy to consume `/api/graph/{company_id}` and then flatten it back into pseudo-company relations.

Do not do this.

That would throw away the value of the new backend contract and make person/event support brittle again.

### 11.3 Graph tab coupling to page bootstrap

If the graph is loaded globally in `page.tsx`, the page becomes slower and harder to reason about.

Mitigation:

- lazy graph fetch by selected company and active tab

---

## 12. Acceptance Criteria

The refactor is complete when all of the following are true:

- the graph tab no longer depends on `/api/relations`
- the graph tab consumes `/api/graph/{company_id}`
- `Company`, `Person`, and `Event` nodes all render visibly
- each node type has distinct visual treatment beyond color alone
- event and person nodes expose richer data through hover or pin detail UI
- company node clicks still change the global selected company
- person/event clicks highlight and pin detail instead of doing nothing
- graph loading and graph errors are isolated from overview loading
- mocks and tests cover the new graph path

---

## 13. Recommended File Changes Summary

Create or heavily refactor:

- `src/lib/data.ts`
- `src/lib/api.ts`
- `src/lib/entity-graph.ts` or replacement for `company-graph.ts`
- `src/components/company-graph.tsx` or renamed replacement
- `src/components/main-panel.tsx`
- `src/app/page.tsx`
- `src/mocks/handlers.ts`
- `src/mocks/data.ts`
- `src/lib/api.test.ts`
- `src/lib/company-graph.test.ts` or replacement test file

Potential cleanup after migration is stable:

- deprecate `src/app/api/relations/route.ts`
- remove `getCompanyRelations()`
- remove old `CompanyRelation` graph-only usage if no longer needed elsewhere

---

## 14. Recommendation

Implement this in two PRs if possible.

PR 1:

- graph data types
- `getGraph()`
- mocks
- lazy graph fetch
- typed renderer refactor without heavy visual polish

PR 2:

- visual differentiation by node type
- pinned detail card
- richer inline metadata
- layout tuning and polish

This reduces risk while still moving decisively to the new backend structure.
