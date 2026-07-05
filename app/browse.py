from rdflib import RDF, RDFS, Literal, URIRef

from .viz import local_name


def list_classes(g):
    """Every distinct rdf:type value used as an object in this graph, with
    how many subjects carry it. Deliberately scoped to *this* graph only
    (not the ontology's full class list) - a class with zero instances here
    simply doesn't appear, consistent with the rest of the app's "what does
    this file actually assert" philosophy.
    """
    subjects_by_class = {}
    for s, o in g.subject_objects(RDF.type):
        subjects_by_class.setdefault(o, set()).add(s)

    classes = [
        {"class": str(cls), "label": local_name(cls), "count": len(subjects)}
        for cls, subjects in subjects_by_class.items()
    ]
    return sorted(classes, key=lambda c: c["label"].lower())


def list_instances(g, class_iri):
    cls = URIRef(class_iri)
    instances = []
    for s in g.subjects(RDF.type, cls):
        label = g.value(s, RDFS.label)
        instances.append({"iri": str(s), "label": str(label) if label else local_name(s)})
    return sorted(instances, key=lambda i: i["label"].lower())


def describe_resource(g, iri_str):
    """A Protege-style "individual" view: every outgoing property assertion
    on this resource within this graph, plus (since this project is all
    about who references what) every incoming one too - which is exactly
    how an "external" node shows up here: no properties, but one or more
    entries under referencedBy.
    """
    iri = URIRef(iri_str)
    label = g.value(iri, RDFS.label)
    types = [local_name(t) for t in g.objects(iri, RDF.type)]
    is_defined_here = (iri, None, None) in g

    properties = []
    for p, o in g.predicate_objects(iri):
        if p == RDFS.label or p == RDF.type:
            continue
        if isinstance(o, Literal):
            properties.append(
                {"predicate": str(p), "predicateLabel": local_name(p), "kind": "literal", "value": str(o), "valueLabel": str(o)}
            )
        else:
            o_label = g.value(o, RDFS.label)
            properties.append(
                {
                    "predicate": str(p),
                    "predicateLabel": local_name(p),
                    "kind": "uri",
                    "value": str(o),
                    "valueLabel": str(o_label) if o_label else local_name(o),
                }
            )

    referenced_by = []
    for s, p in g.subject_predicates(iri):
        if p == RDF.type:
            continue
        s_label = g.value(s, RDFS.label)
        referenced_by.append(
            {
                "subject": str(s),
                "subjectLabel": str(s_label) if s_label else local_name(s),
                "predicate": str(p),
                "predicateLabel": local_name(p),
            }
        )

    return {
        "iri": str(iri),
        "label": str(label) if label else local_name(iri),
        "types": types,
        "definedHere": is_defined_here,
        "properties": sorted(properties, key=lambda p: p["predicateLabel"].lower()),
        "referencedBy": sorted(referenced_by, key=lambda r: r["subjectLabel"].lower()),
    }
