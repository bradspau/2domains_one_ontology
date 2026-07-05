from rdflib import RDF, RDFS, Literal, URIRef

DOMAIN_PREFIXES = [
    ("http://access.example.org/", "access"),
    ("http://aggregation.example.org/", "aggregation"),
    ("http://example.org/ns/network", "ontology"),
]


def local_name(iri):
    s = str(iri)
    if "#" in s:
        return s.rsplit("#", 1)[-1]
    return s.rstrip("/").rsplit("/", 1)[-1]


def domain_tag(iri):
    s = str(iri)
    for prefix, tag in DOMAIN_PREFIXES:
        if s.startswith(prefix):
            return tag
    return "other"


def graph_to_vis(g):
    """Turn an rdflib Graph into {"nodes": [...], "edges": [...]} for the UI.

    A node is flagged "external" when it's referenced (appears as an object)
    but never defined (never appears as a subject) *within this graph* - this
    is what renders as a dashed/gray node in the per-domain views, and what
    disappears once the two domains' files are unioned into the merged view.
    """
    subjects = {s for s in g.subjects() if isinstance(s, URIRef)}
    # rdf:type objects are class IRIs (schema references), not instance
    # nodes to draw - the type is already surfaced per-node below via the
    # "type" field, so exclude them from the referenced/external node set.
    referenced = {o for s, p, o in g if p != RDF.type and isinstance(o, URIRef)}
    all_nodes = subjects | referenced

    nodes = []
    for iri in sorted(all_nodes, key=str):
        label = g.value(iri, RDFS.label)
        rdf_type = None
        for t in g.objects(iri, RDF.type):
            rdf_type = local_name(t)
            break
        attributes = {}
        for p, o in g.predicate_objects(iri):
            if p == RDFS.label or not isinstance(o, Literal):
                continue
            attributes.setdefault(local_name(p), []).append(str(o))
        nodes.append(
            {
                "id": str(iri),
                "label": str(label) if label else local_name(iri),
                "type": rdf_type,
                "domain": domain_tag(iri),
                "external": iri not in subjects,
                "attributes": attributes,
            }
        )

    edges = []
    for s, p, o in g:
        if p == RDF.type or not isinstance(o, URIRef):
            continue
        edges.append(
            {
                "source": str(s),
                "target": str(o),
                "predicate": str(p),
                "label": local_name(p),
            }
        )

    return {"nodes": nodes, "edges": edges}
