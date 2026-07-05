from urllib.parse import parse_qs

from flask import Flask, Response, request
from rdflib import Graph


def create_domain_endpoint(name, ttl_path):
    """A minimal SPARQL 1.1 Protocol endpoint serving exactly one domain's
    own Turtle file - nothing else.

    This is what makes a federated SERVICE query "real" rather than
    simulated: the process answering this request never has the other
    domain's data loaded into it, at all. It only ever sees whatever
    variables the calling engine's bind-join sends it in a VALUES clause.
    """
    app = Flask(name)

    @app.route("/sparql", methods=["GET", "POST"])
    def sparql():
        query = request.args.get("query")
        if not query and request.method == "POST":
            # rdflib's SERVICE client always urlencodes query=...&output=json
            # in the POST body, regardless of what Content-Type it sends (or
            # omits) - so parse it directly instead of relying on Flask's
            # form-parsing, which requires a matching Content-Type header.
            parsed = parse_qs(request.get_data(as_text=True))
            if "query" in parsed:
                query = parsed["query"][0]

        if not query:
            return Response("missing 'query' parameter", status=400)

        graph = Graph()
        graph.parse(ttl_path, format="turtle")  # fresh from disk, no caching

        try:
            result = graph.query(query)
        except Exception as exc:
            return Response(f"query failed: {exc}", status=400)

        body = result.serialize(format="json")
        return Response(body, mimetype="application/sparql-results+json")

    return app
