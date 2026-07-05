import os

from rdflib import Graph

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PATHS = {
    "ontology": os.path.join(BASE_DIR, "ontology", "network.ttl"),
    "access": os.path.join(BASE_DIR, "data", "access", "access.ttl"),
    "aggregation": os.path.join(BASE_DIR, "data", "aggregation", "aggregation.ttl"),
}

VALID_SOURCES = ("ontology", "access", "aggregation", "merged")


def _parse(path):
    g = Graph()
    g.parse(path, format="turtle")
    return g


def load_graph(source):
    """Build the requested graph fresh from disk on every call.

    There is no caching layer: this is deliberate so that editing a .ttl
    file and refreshing the browser shows the change immediately, without
    restarting the server - each domain's file is genuinely its own
    independently-editable "database".

    The merged graph is the union of the access and aggregation ABox files
    only (the ontology/TBox is a separate concern, shown on its own tab),
    which is what makes the "two domains, one logical database" point land:
    nothing but a plain graph union is needed to make them queryable as one.
    """
    if source == "merged":
        g = Graph()
        g += _parse(PATHS["access"])
        g += _parse(PATHS["aggregation"])
        return g
    if source not in PATHS:
        raise ValueError(f"unknown graph source: {source}")
    return _parse(PATHS[source])


def read_raw_turtle(source):
    if source == "merged":
        access_text = _read(PATHS["access"])
        aggregation_text = _read(PATHS["aggregation"])
        return (
            "# ============================================================\n"
            "# This is nothing more than the two files below, stacked.\n"
            "# No merge script, no ETL, no shared database - just a union.\n"
            "# ============================================================\n\n"
            "# --- data/access/access.ttl --------------------------------\n\n"
            f"{access_text}\n"
            "# --- data/aggregation/aggregation.ttl ----------------------\n\n"
            f"{aggregation_text}"
        )
    if source not in PATHS:
        raise ValueError(f"unknown graph source: {source}")
    return _read(PATHS[source])


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()
