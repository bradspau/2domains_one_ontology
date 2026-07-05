PATH_TRACE_CUSTOMER_1 = """\
PREFIX net: <http://example.org/ns/network#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?customerLabel ?customer ?serviceLabel ?service ?ctag
       ?ontLabel ?ont ?ponPortLabel ?ponPort ?oltLabel ?olt
       ?ntPortLabel ?ntPort ?ispServiceLabel ?ispService ?stag
       ?tier1PortLabel ?tier1Port ?tier1SwitchLabel ?tier1Switch ?uplinkPort
       ?tier2PortLabel ?tier2Port ?tier2SwitchLabel ?tier2Switch
       ?handoffPortLabel ?handoffPort
WHERE {
  ?customer a net:Customer ; rdfs:label ?customerLabel .
  FILTER(?customerLabel = "Customer-1")

  # --- a CustomerService is owned by its Customer, and nested under the
  # --- ISP-level service (the S-tag) that its trunk carries -------------
  ?service net:forCustomer ?customer ; net:hasCTag ?ctag ; rdfs:label ?serviceLabel .
  ?service net:partOfISPService ?ispService .
  ?ispService a net:ISPService ; rdfs:label ?ispServiceLabel ; net:hasSTag ?stag .

  ?customer net:hasONT ?ont .
  ?ont rdfs:label ?ontLabel .

  ?ponPort net:servesONT ?ont ; rdfs:label ?ponPortLabel .
  ?olt net:hasPort ?ponPort ; rdfs:label ?oltLabel .
  ?olt net:hasPort ?ntPort .
  ?ntPort a net:NTPort ; rdfs:label ?ntPortLabel ; net:carriesISPService ?ispService .

  # --- the cross-domain physical link: access asserts this triple,
  # --- pointing at a port IRI that the aggregation domain owns ---------
  ?ntPort net:connectsTo ?tier1Port .

  # --- the cross-domain proof join: aggregation asserts this triple,
  # --- pointing back at a service IRI that the access domain owns ------
  ?tier1Port rdfs:label ?tier1PortLabel ; net:carriesService ?service .

  ?tier1Switch net:hasPort ?tier1Port ; rdfs:label ?tier1SwitchLabel .
  ?tier1Switch net:hasPort ?uplinkPort .
  ?uplinkPort net:connectsTo ?tier2Port .
  ?tier2Port rdfs:label ?tier2PortLabel .

  ?tier2Switch net:hasPort ?tier2Port ; rdfs:label ?tier2SwitchLabel .
  ?tier2Switch net:hasHandoffPoint ?handoffPort .
  ?handoffPort rdfs:label ?handoffPortLabel .
}
"""

ALL_DEVICES = """\
PREFIX net: <http://example.org/ns/network#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?device ?label ?type
WHERE {
  ?device a net:Device ; a ?type ; rdfs:label ?label .
  FILTER(?type != net:Device)
}
ORDER BY ?label
"""

PHANTOM_REFERENCES = """\
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

# Finds IRIs that this graph *references* (as the object of some property
# other than rdf:type - i.e. not just a class name) but never *defines*
# (never appears as a subject) - i.e. resources owned by some other domain.
# This is the same "phantom node" effect shown visually as a dashed/gray
# node, discovered here purely through a SPARQL query.
SELECT DISTINCT ?iri
WHERE {
  ?s ?p ?iri .
  FILTER(?p != rdf:type)
  FILTER(isIRI(?iri))
  FILTER NOT EXISTS { ?iri ?p2 ?o2 }
}
"""

FEDERATED_PATH_TRACE_CUSTOMER_1 = """\
PREFIX net: <http://example.org/ns/network#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?customerLabel ?customer ?serviceLabel ?service ?ctag
       ?ontLabel ?ont ?ponPortLabel ?ponPort ?oltLabel ?olt
       ?ntPortLabel ?ntPort ?ispServiceLabel ?ispService ?stag ?tier1Port
       ?tier1PortLabel ?tier1SwitchLabel ?tier2SwitchLabel ?handoffPortLabel
WHERE {
  # --- evaluated locally, against the ACCESS domain's own graph only ----
  # --- (this "source" graph never contains a single aggregation triple) -
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

  # --- ?service and ?tier1Port are already bound above. rdflib now sends
  # --- a real HTTP request to the aggregation domain's own SPARQL
  # --- endpoint, with those bindings pushed in as a VALUES clause - the
  # --- aggregation process answering this has never loaded access.ttl. --
  SERVICE <http://127.0.0.1:5002/sparql> {
    ?tier1Port net:carriesService ?service ; rdfs:label ?tier1PortLabel .
    ?tier1Switch net:hasPort ?tier1Port ; rdfs:label ?tier1SwitchLabel .
    ?tier1Switch net:hasPort ?uplinkPort .
    ?uplinkPort net:connectsTo ?tier2Port .
    ?tier2Switch net:hasPort ?tier2Port ; rdfs:label ?tier2SwitchLabel .
    ?tier2Switch net:hasHandoffPoint ?handoffPort .
    ?handoffPort rdfs:label ?handoffPortLabel .
  }
}
"""

QUERIES = [
    {
        "id": "path-trace-customer-1",
        "label": "End-to-end path trace — Customer-1",
        "description": (
            "Traces a single customer's service from its ONT, through the "
            "access domain's OLT, across the cross-domain physical link and "
            "S/C-tag hand-off, through both aggregation tiers, to the "
            "customer handoff point — stitched together purely by shared "
            "IRIs, even though access and aggregation each authored only "
            "their own half."
        ),
        "source": "merged",
        "sparql": PATH_TRACE_CUSTOMER_1,
    },
    {
        "id": "all-devices",
        "label": "All devices, both domains",
        "description": (
            "A plain cross-domain query over net:Device — proves the "
            "merged graph is one queryable dataset, not two."
        ),
        "source": "merged",
        "sparql": ALL_DEVICES,
    },
    {
        "id": "phantom-references",
        "label": "Referenced-but-not-defined IRIs (access domain)",
        "description": (
            "Run purely against the access domain's own file: finds every "
            "IRI it references but doesn't own — the query-level version "
            "of the dashed/gray nodes you see in the Access Domain tab."
        ),
        "source": "access",
        "sparql": PHANTOM_REFERENCES,
    },
    {
        "id": "federated-path-trace-customer-1",
        "label": "⚡ Federated path trace (real SERVICE call)",
        "description": (
            "Same path trace as above, but for real: this runs against the "
            "access domain's graph ONLY, and uses a live SPARQL SERVICE "
            "call to fetch the aggregation half over HTTP from a separate "
            "process that has never loaded access.ttl. Requires "
            "`python run_endpoints.py` to be running in another terminal "
            "(endpoints on :5001/:5002) — otherwise this will fail with a "
            "connection error, which is itself the point: this query "
            "depends on a live network call, not on data already being "
            "merged in memory."
        ),
        "source": "access",
        "sparql": FEDERATED_PATH_TRACE_CUSTOMER_1,
    },
]

QUERIES_BY_ID = {q["id"]: q for q in QUERIES}
