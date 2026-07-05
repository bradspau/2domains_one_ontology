from flask import Blueprint, jsonify, request
from rdflib import URIRef
from rdflib.plugins.sparql.processor import prepareQuery

from . import graphs
from .browse import describe_resource, list_classes, list_instances
from .sparql_queries import QUERIES, QUERIES_BY_ID
from .viz import graph_to_vis

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/graphs/<source>")
def get_graph(source):
    if source not in graphs.VALID_SOURCES:
        return jsonify({"error": f"unknown graph source: {source}"}), 404
    g = graphs.load_graph(source)
    payload = graph_to_vis(g)
    payload["turtle"] = graphs.read_raw_turtle(source)
    payload["source"] = source
    return jsonify(payload)


@bp.get("/browse/<source>/classes")
def browse_classes(source):
    if source not in graphs.VALID_SOURCES:
        return jsonify({"error": f"unknown graph source: {source}"}), 404
    return jsonify(list_classes(graphs.load_graph(source)))


@bp.get("/browse/<source>/instances")
def browse_instances(source):
    if source not in graphs.VALID_SOURCES:
        return jsonify({"error": f"unknown graph source: {source}"}), 404
    class_iri = request.args.get("class")
    if not class_iri:
        return jsonify({"error": "missing 'class' query parameter"}), 400
    return jsonify(list_instances(graphs.load_graph(source), class_iri))


@bp.get("/browse/<source>/resource")
def browse_resource(source):
    if source not in graphs.VALID_SOURCES:
        return jsonify({"error": f"unknown graph source: {source}"}), 404
    iri = request.args.get("iri")
    if not iri:
        return jsonify({"error": "missing 'iri' query parameter"}), 400
    return jsonify(describe_resource(graphs.load_graph(source), iri))


@bp.get("/queries")
def list_queries():
    return jsonify(
        [{k: q[k] for k in ("id", "label", "description", "source", "sparql")} for q in QUERIES]
    )


@bp.post("/query")
def run_query():
    body = request.get_json(force=True, silent=True) or {}
    sparql = body.get("sparql")
    source = body.get("source", "merged")
    query_id = body.get("query_id")

    if query_id:
        canned = QUERIES_BY_ID.get(query_id)
        if canned is None:
            return jsonify({"error": f"unknown query id: {query_id}"}), 404
        sparql = canned["sparql"]
        source = canned["source"]

    if not sparql:
        return jsonify({"error": "missing 'sparql' (or 'query_id')"}), 400
    if source not in graphs.VALID_SOURCES:
        return jsonify({"error": f"unknown graph source: {source}"}), 400

    g = graphs.load_graph(source)

    try:
        prepared = prepareQuery(sparql)
    except Exception as exc:  # rdflib raises plain Exception/ParseException on bad SPARQL
        return jsonify({"error": f"could not parse query: {exc}"}), 400

    # prepareQuery only accepts the SPARQL *query* grammar (SELECT/ASK/
    # CONSTRUCT/DESCRIBE) - there is no code path here that can reach
    # rdflib's .update(), so SPARQL Update statements are structurally
    # rejected rather than string-blacklisted.
    # SPARQL results are evaluated lazily, so a SERVICE clause's actual HTTP
    # request (and any failure - e.g. the other domain's endpoint isn't
    # running) happens while iterating `result`, not at `g.query()` itself.
    # Both stages are wrapped so a dead federation endpoint surfaces as a
    # clean 400 instead of an unhandled exception.
    try:
        result = g.query(prepared)

        if result.type == "ASK":
            return jsonify({"type": "ask", "boolean": result.askAnswer, "source": source})

        columns = [str(v) for v in result.vars]
        rows = []
        touched = set()
        for row in result:
            cells = []
            for var in result.vars:
                value = row[var]
                cells.append(str(value) if value is not None else None)
                if isinstance(value, URIRef):
                    touched.add(value)
            rows.append(cells)
    except Exception as exc:
        return jsonify({"error": f"query failed: {exc}"}), 400

    highlighted_edges = []
    if touched:
        for s, p, o in g:
            if s in touched and o in touched:
                highlighted_edges.append([str(s), str(p), str(o)])

    return jsonify(
        {
            "type": "select",
            "source": source,
            "columns": columns,
            "rows": rows,
            "highlighted_node_iris": [str(iri) for iri in touched],
            "highlighted_edges": highlighted_edges,
        }
    )
