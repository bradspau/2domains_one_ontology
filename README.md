# Semantic IRI Demo — Access & Aggregation

A small, local, interactive demo of the core W3C semantic web / Linked Data idea:

> Two separate organizations, with two separate systems, and zero coordination
> beyond agreeing on a shared vocabulary and a shared IRI naming convention,
> can each independently publish their own RDF data (their "ABox") — and the
> plain union of that data behaves as one logical database.

No message queue, no ETL pipeline, no shared schema migration, no API contract
between teams. Just a shared ontology and the discipline of using globally
unique IRIs. That's the whole trick, and it's the thing this demo is built to
make obvious.

## The scenario

This models a ISP/telco network split across two organizational and
technology domains:

- **Access domain** owns the OLT (Optical Line Terminal). Its PON port
  logically serves a handful of ONTs at customer premises (the physical
  1:8/1:4 splitters in between are real but abstracted away here — not worth
  modeling for this demo). The OLT's NT port, facing the aggregation network,
  carries an **ISP Service** — a first-class resource identified by its
  802.1ad **S-tag**, representing the service provider's service on that
  trunk. Each customer has their own **Customer Service** (identified by its
  **C-tag**) — owned by that customer (`net:forCustomer`) and nested under the
  shared ISP Service (`net:partOfISPService`), matching real QinQ semantics:
  one outer S-tag, many inner C-tags.
- **Aggregation domain** owns a two-tier switching network: two Tier-1
  switches (only one of which is actually wired to this OLT — the other is
  idle/spare, on purpose, to prove the merged graph has more in it than just
  the one traced path) and a Tier-2 switch that aggregates both and exposes
  the **customer handoff point** toward the wider network.

```
                          ACCESS DOMAIN                 |  AGGREGATION DOMAIN
                                                          |
  Customer-1 ---\                                        |
  Customer-2 -----+-- ONT(s) -- PON port -- OLT -- NT port +--- Tier-1 Switch A --- Tier-2 Switch --- handoff
  Customer-3 ---/           (S-tag 100, C-tags 201-203)   |                    \
                                                          |   Tier-1 Switch B (idle/spare) --------/
```

Two things cross the domain boundary, and each is modeled differently:

1. **A physical link** — the access domain's NT port asserts
   `net:connectsTo` pointing at a port IRI it doesn't own, minted by
   aggregation. Concretely, `data/access/access.ttl` contains:

   ```turtle
   access:olt-central-1-nt-1 a net:NTPort ;
       net:connectsTo agg:t1-sw-a-p-olt1 .
   ```

   That triple is written entirely by the access team, in their own file, but
   its *object* — `agg:t1-sw-a-p-olt1` — is an IRI in the **aggregation**
   domain's namespace. Access never defines what that IRI *is*: no label, no
   `a net:SwitchPort`, nothing. Opened on its own, `access.ttl` just mentions
   that name in passing — which is exactly why it shows up as the one
   dashed/gray "external" node on the Access Domain tab. The actual
   definition lives entirely on the other side, in
   `data/aggregation/aggregation.ttl`:

   ```turtle
   agg:t1-sw-a-p-olt1 a net:SwitchPort ;
       rdfs:label "T1-SW-A / Port to OLT Central-1" ;
       net:carriesService access:svc-1, access:svc-2, access:svc-3 .
   ```

   Neither team asked the other's permission or copied any data — access
   only had to know the agreed IRI string to reference it, before (or even
   without) it ever being defined in the file access can see. Only once the
   two files are unioned (the Merged Graph tab) do both halves — "connects
   to X" and "here's what X actually is" — land in the same graph and
   resolve into one fact: this access port is physically wired to this
   aggregation port.

2. **A logical/service reference** — the aggregation domain's switch port
   asserts `net:carriesService` pointing at CustomerService IRIs it doesn't
   own, minted by access. Same mechanism as above, mirrored. Concretely,
   `data/aggregation/aggregation.ttl` contains:

   ```turtle
   agg:t1-sw-a-p-olt1 a net:SwitchPort ;
       rdfs:label "T1-SW-A / Port to OLT Central-1" ;
       net:carriesService access:svc-1, access:svc-2, access:svc-3 .
   ```

   The *subject* here, `agg:t1-sw-a-p-olt1`, is a resource aggregation owns
   and fully defines (it has a type and a label). But the three *objects* —
   `access:svc-1`, `access:svc-2`, `access:svc-3` — are IRIs in the
   **access** namespace. Aggregation is asserting "this port of mine carries
   these three services," without ever saying what those services *are*.
   Opened on its own, `aggregation.ttl` just lists three bare names — which
   is exactly why there are three (not one) dashed/gray "external" nodes on
   the Aggregation Domain tab, one per referenced service. The actual
   definitions live entirely on the access side, e.g.
   `data/access/access.ttl`:

   ```turtle
   access:svc-1 a net:CustomerService ;
       rdfs:label "Service-1" ;
       net:forCustomer access:cust-1 ;
       net:partOfISPService access:isp-service-100 ;
       net:hasCTag 201 .
   ```

   That's where you find out `svc-1` is a `CustomerService`, who it belongs
   to (`Customer-1`), and its C-tag (`201`) — none of which ever appears in
   aggregation's file.

   This is what "aggregation can switch on S/C-tag without ever holding a
   customer record" means in practice: aggregation's actual job is traffic
   switching — forward a frame tagged with a given C-tag out the right port.
   To do that, all it needs is *the service IRI* to hang a forwarding rule
   off of; it has no operational reason to know the customer's name, their
   ONT, or anything else access's file holds. With this modeling it
   structurally *can't* end up holding that data even by accident, because
   `carriesService` only ever points at an opaque IRI, never a copy of the
   data behind it — the RDF equivalent of least-privilege: aggregation gets
   exactly the identifier it needs, and nothing more, because it was never
   given more to reference.

**How did aggregation learn about `access:svc-1` in the first place, if it
never reads access's file?** Not by magic, and not by RDF itself — something
outside the graph layer had to hand that identifier across. Minting and
propagating the IRI is a provisioning/orchestration problem, not a semantic
web one: when a customer's service is activated, some real workflow (an
OSS/BSS service order, a network-automation call, an event on a message bus)
has to tell aggregation "program C-tag 201 on this port, and remember it as
`access:svc-1`." Only after that handoff does aggregation write its own
`carriesService` triple. What RDF/shared-IRI modeling buys you is everything
*after* that handoff: once both sides agree to use the same identifier,
their independently-stored facts about it merge for free, with no schema
mapping or reconciliation step. It doesn't solve how the two domains agreed
on the identifier to begin with — the Turtle files in this repo represent
the steady state *after* that provisioning already succeeded, not the
handoff itself.

This also raises a fair design question: given federation exists (see
[Federated mode](#federated-mode-a-real-service-call) below), why does
aggregation bother storing `carriesService` locally at all, instead of just
asking access live, every time, which services a given port carries? Both
are legitimate architectures, and the choice is about *when* the two
domains' facts get joined:
- **Push / cache locally (what this demo's static files model)** — access
  hands aggregation the identifier once, at provisioning time, and
  aggregation writes its own local record. This is what real switches do:
  packet-forwarding decisions happen in nanoseconds, so the VLAN/forwarding
  table has to be local, pre-programmed state — a live cross-domain SPARQL
  query per packet is a non-starter.
- **Pull / query live (what the federated `SERVICE` query demonstrates)** —
  store nothing extra locally; ask the other domain's endpoint live,
  whenever the answer is actually needed. This is fine, and arguably
  better, for anything that isn't real-time forwarding: reporting,
  inventory, auditing, or the path-trace query itself, since there's
  nothing to keep in sync.

Both patterns exist in this repo for exactly that reason: the static merged
graph models the push/cache pattern that real switching hardware needs; the
`SERVICE`-based federated query models the pull/live-lookup pattern that
diagnostics and reporting can use instead.

That cross-domain reference is deliberately aimed at the *CustomerService*,
not the ISP Service — ownership within the access domain itself is explicit:
a Customer owns its CustomerService (`net:forCustomer`), and every
CustomerService is nested under the one ISP Service that its trunk carries
(`net:partOfISPService`). Aggregation only ever needs the C-tag-level
resource to switch traffic; it never has to know about the S-tag/ISP Service
layer above it.

## Shared TBox, separate ABox

`ontology/network.ttl` is the one file neither domain owns. It defines the
classes (`OLT`, `ONT`, `Switch`, `Port`, `Customer`, `CustomerService`,
`ISPService`, ...) and properties (`hasPort`, `connectsTo`, `carriesService`,
`carriesISPService`, `forCustomer`, `partOfISPService`, `hasSTag`, `hasCTag`,
...) that both domains agree to use. Nobody needs write access to anybody
else's database — they just need to agree on this vocabulary and on an IRI
naming convention.

`data/access/access.ttl` and `data/aggregation/aggregation.ttl` are each
edited by one team only. Open them side by side and notice:

- `access.ttl` declares an `agg:` prefix at the top, purely so it can write a
  compact reference to a port it doesn't define.
- `aggregation.ttl` declares an `access:` prefix, purely to reference customer
  services it doesn't define.

That's the whole mechanism. No shared database, no coordination beyond IRIs.

## Repository layout

```
ontology/
  network.ttl               shared TBox — owned by neither domain
data/
  access/access.ttl         access domain's own ABox (their "database")
  aggregation/aggregation.ttl   aggregation domain's own ABox (their "database")
app/
  graphs.py                 loads .ttl files into rdflib Graphs, builds the merged union
  viz.py                    turns an rdflib Graph into {nodes, edges} JSON for the UI
  browse.py                 class/instance/property-table data for the Class Browser tab
  sparql_queries.py         the canned SPARQL queries used by the Query Console
  sparql_endpoint.py        minimal SPARQL 1.1 Protocol endpoint, one per domain
  routes.py                 Flask API endpoints (see below)
  static/                   single-page frontend (vanilla JS + vendored vis-network)
run.py                      entry point — starts the Flask dev server (the UI, port 5000)
run_endpoints.py            starts the two domains as separate real SPARQL endpoints
requirements.txt            rdflib, Flask
```

## How it works

**Backend (Flask + rdflib, no external triple store).** `graphs.py` re-parses
the relevant `.ttl` file(s) from disk on every request — there is no
in-memory cache. `load_graph("merged")` does nothing more than:

```python
g = Graph()
g += parse(access.ttl)
g += parse(aggregation.ttl)
```

That `+=` union is the entire "merge" step. There's no reconciliation logic,
no join keys, no field mapping — it works because both files already use the
same IRIs and the same shared vocabulary from `ontology/network.ttl`.

`viz.py` converts any rdflib `Graph` into a `{nodes, edges}` shape the
frontend can draw. A node is flagged `external: true` when it's referenced as
an object in that particular graph but never appears as a subject there —
i.e. it's a resource some other domain owns. This same flag is what renders
as a dashed/gray node in the UI, and what produces zero results once you're
looking at the merged graph.

`routes.py` exposes these endpoints:

| Method & path | Purpose |
|---|---|
| `GET /api/graphs/<source>` | `source` ∈ `ontology, access, aggregation, merged` → `{nodes, edges, turtle}` for that view |
| `GET /api/queries` | the canned SPARQL queries for the Query Console dropdown |
| `POST /api/query` | body `{sparql, source}` or `{query_id}` → runs `Graph.query(...)` and returns `{columns, rows, highlighted_node_iris, highlighted_edges}` |
| `GET /api/browse/<source>/classes` | every distinct `rdf:type` used in that graph, with instance counts |
| `GET /api/browse/<source>/instances?class=<iri>` | every subject asserted as that type, in that graph |
| `GET /api/browse/<source>/resource?iri=<iri>` | a Protégé-style "individual" view: every outgoing property on that IRI in that graph, plus every incoming one (`referencedBy`) |

The `/api/browse/...` family (`app/browse.py`) backs the **Class Browser**
tab. It's deliberately scoped per-graph, same as everything else here: a
class with zero instances in a given source simply doesn't appear, and a
resource with properties in one graph can show up with an *empty* property
table but a populated `referencedBy` in another — which is exactly what an
"external" node looks like from inside a tabular, non-graph view.

`/api/query` only ever calls rdflib's `.query()` (the SPARQL *Query*
grammar — SELECT/ASK/CONSTRUCT/DESCRIBE). There's no code path to
`.update()`, so SPARQL Update statements are structurally impossible to run
through it, not merely filtered out. After a query runs, every IRI that
appears anywhere in the result rows is collected into a "touched" set; any
triple in the queried graph whose subject *and* object are both touched is
returned as a highlighted edge — that's what lights up the path in the
Query Console's graph canvas.

**Frontend (`app/static/`, vanilla JS + vendored vis-network).** A single
page with six tabs. The four graph tabs each fetch their `/api/graphs/...`
data once on load and render it with vis-network, coloring nodes by owning
domain (derived from the IRI's hostname) and shaping them by RDF type. The
Query Console lets you pick a canned query or type your own SPARQL, choose
which graph to run it against, and re-renders that graph with the query's
highlighted nodes/edges overlaid. The Class Browser is a three-column,
Protégé-style view (classes → instances → a selected resource's property
table) driven entirely by `/api/browse/...`; clicking any property value or
"referenced by" entry that's an IRI navigates to *that* resource's own
property table, so you can walk the graph purely through tables and links,
no graph rendering involved.

## Federated mode: a real `SERVICE` call

Everything above merges the two domains' data by loading both `.ttl` files
into one Python process and taking the union in memory. That's honest for
demonstrating "shared IRIs make separately-authored data mergeable," but it
understates how this actually works in a real deployment: two domains don't
usually load each other's files — each publishes its own SPARQL endpoint,
and a **federated SPARQL query** (the `SERVICE` keyword, SPARQL 1.1
Federated Query) joins across them over HTTP, live, without either side
ever holding the other's data.

`run_endpoints.py` makes that literally true:

```bash
# in a second terminal, with the venv active
python run_endpoints.py
```

This starts two independent Flask processes:
- `http://127.0.0.1:5001/sparql` — has loaded **only** `access.ttl`
- `http://127.0.0.1:5002/sparql` — has loaded **only** `aggregation.ttl`

Each implements the SPARQL 1.1 Protocol (`app/sparql_endpoint.py`): accept a
`query` parameter, run it against that one file, return standard SPARQL
Results JSON. Neither process has ever seen the other domain's Turtle file.

With both running, pick **⚡ Federated path trace (real SERVICE call)** in
the Query Console (`FEDERATED_PATH_TRACE_CUSTOMER_1` in
`app/sparql_queries.py`). Here's what it actually does, step by step.

**Where it runs.** Its `source` is `access` — the backend loads *only*
`access.ttl` into memory for this query. No aggregation data is present
anywhere in that process. (Contrast this with the default "End-to-end path
trace" query, whose `source` is `merged` — both files unioned in memory.)

**Part 1 — resolved entirely locally, against access's own graph:**
```sparql
?customer a net:Customer ; rdfs:label ?customerLabel .
FILTER(?customerLabel = "Customer-1")

?service net:forCustomer ?customer ; net:hasCTag ?ctag ; rdfs:label ?serviceLabel .
?service net:partOfISPService ?ispService .
?ispService a net:ISPService ; rdfs:label ?ispServiceLabel ; net:hasSTag ?stag .

?customer net:hasONT ?ont .
?ont rdfs:label ?ontLabel .
?ponPort net:servesONT ?ont ; rdfs:label ?ponPortLabel .
?olt net:hasPort ?ponPort ; rdfs:label ?oltLabel .
?olt net:hasPort ?ntPort .
?ntPort a net:NTPort ; rdfs:label ?ntPortLabel ; net:carriesISPService ?ispService .
?ntPort net:connectsTo ?tier1Port .
```
This walks Customer-1 → its CustomerService → its ISPService → back up
through the ONT → PON port → OLT → NT port, ending at `?tier1Port` — bound
to `agg:t1-sw-a-p-olt1`. Every pattern here matches against `access.ttl`
alone. At this point the engine has concrete values for `?service`
(`access:svc-1`) and `?tier1Port` (`agg:t1-sw-a-p-olt1`), even though that
second IRI is never *defined* in the graph it's running against — same
external-reference situation as everywhere else in this demo.

**Part 2 — the `SERVICE` block:**
```sparql
SERVICE <http://127.0.0.1:5002/sparql> {
  ?tier1Port net:carriesService ?service ; rdfs:label ?tier1PortLabel .
  ?tier1Switch net:hasPort ?tier1Port ; rdfs:label ?tier1SwitchLabel .
  ?tier1Switch net:hasPort ?uplinkPort .
  ?uplinkPort net:connectsTo ?tier2Port .
  ?tier2Switch net:hasPort ?tier2Port ; rdfs:label ?tier2SwitchLabel .
  ?tier2Switch net:hasHandoffPoint ?handoffPort .
  ?handoffPort rdfs:label ?handoffPortLabel .
}
```
Since `?tier1Port` and `?service` are already bound from Part 1, rdflib
doesn't just paste this block in and hope — it builds a genuine HTTP request
to `http://127.0.0.1:5002/sparql`, injecting a `VALUES` clause carrying
those bindings as constraints (SPARQL's "bind join" — watch the request
land in `run_endpoints.py`'s terminal output). That process
(`app/sparql_endpoint.py`) has loaded *only* `aggregation.ttl`. It has no
idea what `access:svc-1` or "Customer-1" are; it just evaluates the inner
pattern against its own graph, constrained to the specific
`tier1Port`/`service` pair it was given, and returns the matching rows as
standard SPARQL Results JSON.

**Part 3 — the join.** The rows that come back over HTTP
(`tier1SwitchLabel`, `tier2SwitchLabel`, `handoffPortLabel`, etc.) merge
into the same result row as everything resolved in Part 1, purely because
they share variable names. The result: one row with the full path from
Customer-1's ONT to the handoff point, identical in content to the
in-memory "merged" query — but this version never had both domains' triples
sitting in the same graph at any point. They only ever met inside that one
HTTP request/response.

Stop `run_endpoints.py` and re-run the query to see the other side of it:
a clean `query failed: <urlopen error [Errno 61] Connection refused>` — the
federated version genuinely depends on the other domain's endpoint being
reachable, unlike everything else in this demo.

## Class Browser: a Protégé-style resource explorer

The graph tabs and Query Console both show you the data as a *graph* —
nodes and edges. The **Class Browser** tab shows the same data the way a
tool like [Protégé](https://protege.stanford.edu/) (the standard OWL
ontology editor) presents it: as a three-column drill-down of classes →
instances → a single resource's property table. No graph rendering
involved at all — just tables and links.

1. **Column 1 — Classes.** Pick a graph from the dropdown (Ontology /
   Access / Aggregation / Merged), and you get every distinct `rdf:type`
   actually used *in that graph*, with an instance count. Pick "Access
   domain only" and you'll see `OLT (1)`, `Customer (3)`, `CustomerService
   (3)`, `ISPService (1)`, and so on — note there's no `Tier1Switch` here at
   all, because access's file has none. Switch to "Merged" and it appears.
2. **Column 2 — Instances.** Click a class (e.g. `OLT`) and its instances
   appear (`OLT Central-1`).
3. **Column 3 — Resource.** Click an instance and every property assertion
   on it *in the currently selected graph* appears as a Predicate/Value
   table — e.g. `OLT Central-1` shows two `hasPort` rows. Every value that's
   an IRI is a clickable link, and clicking it re-runs this same lookup for
   that IRI — so you can walk the whole graph purely by following links,
   the same way you'd browse Wikipedia.

The interesting part is what happens when you follow a link across a
domain boundary. With "Access domain only" still selected, click into
`OLT Central-1` → `OLT Central-1 / NT-1` → follow its `connectsTo` value.
You land on `t1-sw-a-p-olt1` with:
- **no type shown** ("no type asserted in this graph"),
- **an empty Properties table**,
- **a "referenced but not defined here" badge**, and
- **one row under "Referenced by"** — `OLT Central-1 / NT-1 — connectsTo` —
  linking you right back where you came from.

That's the exact same external/phantom-node concept as the dashed/gray
nodes on the graph tabs, just represented as an ordinary (if suspiciously
empty) row of table data instead of a node shape. Switch the graph dropdown
to "Merged" and click the same resource again: now it has a real type
(`SwitchPort`), a label, and its own outgoing properties — because this
time you're looking at the union, where aggregation's definition of that
same IRI is actually present.

Backed by three endpoints in `app/browse.py` (`GET
/api/browse/<source>/classes`, `.../instances?class=<iri>`, and
`.../resource?iri=<iri>`) — see [How it works](#how-it-works) above for the
implementation details.

## Running it

The project's `.venv` already exists but is empty:

```bash
cd "semantic_iri_demo"
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Then open `http://127.0.0.1:5000`.

## What to click

1. **Ontology tab** — the shared vocabulary both domains build on.
2. **Access Domain tab** — access's own graph and raw Turtle file. Note the
   one dashed/gray node: a Tier-1 switch port it references but doesn't own.
3. **Aggregation Domain tab** — aggregation's own graph. Note the three
   dashed/gray nodes: the access-minted customer services it switches on.
4. **Merged Graph tab** — literally `access.ttl` unioned with
   `aggregation.ttl`. Every gray node from the previous two tabs now resolves
   to a real definition, contributed by whichever domain owns it.
5. **Query Console** — run the default "End-to-end path trace — Customer-1"
   query. It walks from that customer's ONT, through its CustomerService and
   the ISP Service that trunk carries, through the access domain, across
   both cross-domain references, through both aggregation tiers, to the
   customer handoff point — and returns exactly one row, even though no
   single team authored the whole path. Try the other three canned queries
   too:
   - **All devices, both domains** — a plain cross-domain query proving the
     merged graph is one dataset, not two.
   - **Referenced-but-not-defined IRIs (access domain)** — the same
     dashed/gray-node effect, found purely via SPARQL (`FILTER NOT EXISTS`)
     instead of visually.
   - **⚡ Federated path trace (real SERVICE call)** — see below; requires a
     second terminal running `run_endpoints.py`.
6. **Class Browser** — a Protégé-style classes → instances → property-table
   view of whichever graph you pick, with every IRI value clickable. See
   [Class Browser: a Protégé-style resource explorer](#class-browser-a-protégé-style-resource-explorer)
   below for a full walkthrough, including the same external-reference
   concept shown as plain table rows instead of graph shapes.

There's no caching layer anywhere in the backend: every request re-parses the
relevant `.ttl` file straight off disk. Try editing `data/access/access.ttl`
(e.g. change a C-tag) and just refreshing the browser — no server restart
needed. That's meant to reinforce that each domain's file really is its own
independently-editable "database."

## Design notes / simplifications

- No OWL reasoner is loaded. Instances that need to satisfy a superclass
  query (e.g. `net:Device`) are multi-typed explicitly in the data
  (`a net:Tier1Switch, net:Switch, net:Device`) rather than relying on
  `rdfs:subClassOf` entailment.
- The merged graph used for querying and the "Merged Graph" tab is the union
  of the two ABox files only — the ontology/TBox is shown on its own tab and
  isn't mixed into the instance-data node counts.
- IRIs use fictitious, non-dereferenceable hostnames
  (`access.example.org`, `aggregation.example.org`,
  `example.org/ns/network`) — there's nothing to host for a local demo.
- The Query Console's SPARQL endpoint only ever calls rdflib's `.query()`
  (the SPARQL *Query* grammar) — there is no code path to `.update()`, so
  update statements are structurally rejected, not string-blacklisted.
- The domain endpoints started by `run_endpoints.py` are plain Flask dev
  servers with no auth, on localhost only — fine for a local demo of the
  federation mechanism, not something to expose beyond that.
