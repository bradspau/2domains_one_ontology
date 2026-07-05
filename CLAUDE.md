# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A local, runnable teaching demo of the W3C semantic web / Linked Data idea: two
independent organizational domains (a telco "access" team and an "aggregation"
team) each own and edit their own RDF Turtle file with zero coordination beyond
a shared ontology and IRI naming convention — and the plain union of their data
behaves as one logical, queryable database. See `README.md` for the full
conceptual narrative, the network topology being modeled (OLT/ONT/PON/S-tag/
C-tag on the access side, a two-tier switch fabric on the aggregation side),
and the guided tour of the UI. Read it before making changes — the "why" behind
most design choices here lives there, not in code comments.

## Commands

```bash
# setup (venv already exists, just needs deps)
source .venv/bin/activate
pip install -r requirements.txt

# run the main UI (http://127.0.0.1:5000)
python run.py

# run the two domain SPARQL endpoints for the federated-query demo
# (separate terminal; needed only for the "Federated path trace" canned query)
python run_endpoints.py
```

There is no test suite, linter, or build step in this project. Verification is
done by hitting the Flask API directly, e.g.:

```bash
python -c "
from app import graphs
from app.viz import graph_to_vis
for src in ['ontology', 'access', 'aggregation', 'merged']:
    g = graphs.load_graph(src)
    vis = graph_to_vis(g)
    print(src, len(vis['nodes']), 'nodes,', sum(n['external'] for n in vis['nodes']), 'external')
"
```
Expected node/external counts (a quick sanity check after editing the `.ttl`
data files): access 14/1, aggregation 13/3, merged 23/0.

To sanity-check a SPARQL query change without the UI:
```bash
python -c "
from app import graphs
from app.sparql_queries import QUERIES_BY_ID
q = QUERIES_BY_ID['path-trace-customer-1']
print(graphs.load_graph(q['source']).query(q['sparql']).serialize(format='json').decode())
"
```

## Architecture

**No database, no cache, no reasoner.** Every request re-parses the relevant
`.ttl` file(s) straight off disk (`app/graphs.py`). This is intentional, not a
missing optimization — it means editing a Turtle file and refreshing the
browser shows the change immediately, which is the whole point of the demo
(each domain's file really is its own independently-editable "database").
There is also no OWL/RDFS reasoner loaded anywhere; any instance that needs to
satisfy a superclass query (e.g. `net:Device`) must be multi-typed explicitly
in the data (`a net:Tier1Switch, net:Switch, net:Device`), not inferred.

**Three-layer file structure**, and the boundary between them matters:
- `ontology/network.ttl` — the shared TBox. Owned by neither domain. Defines
  every class/property used anywhere else in the project.
- `data/access/access.ttl` / `data/aggregation/aggregation.ttl` — each
  domain's own ABox, edited independently. Cross-domain references are
  expressed as plain triples pointing at IRIs the file doesn't define (e.g.
  access's NT port has `net:connectsTo` pointing at an aggregation port IRI).
  Each file declares the *other* domain's IRI prefix purely to write those
  compact cross-references — that's deliberate and is called out in comments.
- `graphs.load_graph("merged")` is nothing more than `access_graph +
  aggregation_graph` (rdflib `Graph.__iadd__`) — the ontology/TBox is
  deliberately excluded from the merged/instance-data graph so that node
  counts in the UI stay clean (see the 14/13/23 numbers above); the ontology
  has its own separate tab/view.

**Ownership hierarchy within the access domain**: `net:ISPService` is a
first-class resource (identified by `net:hasSTag`) representing the
provider-level service on an NT port's trunk (`net:carriesISPService`,
NTPort → ISPService). `net:CustomerService` (identified by `net:hasCTag`) is
owned by its `net:Customer` (`net:forCustomer`) and nested under that
ISPService (`net:partOfISPService`) — one S-tag, many C-tags, matching real
802.1ad QinQ semantics. Aggregation only ever references the CustomerService
(via `net:carriesService` on a SwitchPort) — it never needs to know about the
ISPService layer above it.

**`app/viz.py`** turns any rdflib `Graph` into `{nodes, edges}` JSON. A node is
flagged `external: true` when it's referenced as an object in that *specific*
graph but never appears there as a subject — this is what renders as a
dashed/gray node in a single-domain view and is expected to disappear (0
external) in the merged view. `rdf:type` objects are deliberately excluded
from the referenced-node set (they're schema references, not instance nodes) —
see the comment in `graph_to_vis` before changing this logic.

**`app/routes.py`** exposes `GET /api/graphs/<source>` (source ∈ `ontology,
access, aggregation, merged`), `GET /api/queries` (canned queries for the
Query Console), and `POST /api/query` (`{sparql, source}` or `{query_id}` →
runs `Graph.query()` and returns highlighted node/edge IRIs for the UI to
overlay). It only ever calls rdflib's `.query()` — there's no code path to
`.update()`, so SPARQL Update is structurally unreachable, not filtered.
Highlighting works by collecting every `URIRef` that appears in the result
bindings, then scanning the *queried* graph for triples where both subject and
object are in that touched set. **Only variables actually listed in a query's
`SELECT` clause end up in result bindings** — if you add a hop to a canned
query and want it to highlight, its IRI variable (not just its label
variable) must be in the `SELECT` list, and the query-evaluation try/except in
`run_query()` must wrap the row-iteration loop, not just `g.query(...)` —
SPARQL results are lazy, so a `SERVICE` clause's HTTP call (and any failure)
happens during iteration, not at `.query()` time.

**Federated mode is a second, deliberately separate code path**, not an
extension of the in-process merge. `run_endpoints.py` starts two independent
Flask processes (`app/sparql_endpoint.py`, ports 5001/5002), each loading
*only* its own domain's `.ttl` file and implementing enough of the SPARQL 1.1
Protocol (`GET`/`POST /sparql?query=...` → SPARQL Results JSON) for rdflib's
built-in `SERVICE` evaluator to call it. The "federated-path-trace-customer-1"
canned query in `app/sparql_queries.py` runs with `source: "access"` (so the
local graph genuinely contains zero aggregation triples) and has a literal
`SERVICE <http://127.0.0.1:5002/sparql> { ... }` block for the aggregation
half. When editing this query, remember rdflib's bind-join sends already-bound
variables to the remote endpoint via an injected `VALUES` clause per outer
solution — variables not yet bound before the `SERVICE` block aren't available
to push, so ordering of patterns before/inside the block matters.

**Frontend** (`app/static/`) is a single vanilla-JS page, no build step,
vis-network loaded from CDN. Five tabs (Ontology / Access / Aggregation /
Merged / Query Console) all driven by the API above; `app.js` renders graphs
with domain-based node coloring (derived from IRI hostname) and RDF-type-based
shapes, and re-fetches/re-renders with highlight overlays after a query runs.

## Naming conventions used throughout the data

- IRI namespaces: `http://access.example.org/id/` (access-owned),
  `http://aggregation.example.org/id/` (aggregation-owned),
  `http://example.org/ns/network#` (shared ontology, owned by neither).
- Customers/services in the demo data are anonymized by number, not name:
  `Customer` resources are labeled `Customer-1`/`Customer-2`/`Customer-3`;
  `CustomerService` resources are labeled `Service-1`/`Service-2`/`Service-3`
  (same numbering, different resource/label). Do not reintroduce personal
  names into data, queries, or docs.
