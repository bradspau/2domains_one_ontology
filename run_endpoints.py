"""
Starts each domain's own SPARQL 1.1 Protocol endpoint on its own port.

This turns the "two separate domains" story from the main demo into
something literally true at the process level: the access endpoint has
NEVER loaded aggregation.ttl, and vice versa. Run this alongside the main
app (`python run.py`) to try the "Federated path trace (real SERVICE call)"
query in the Query Console - it sends an actual SPARQL SERVICE call over
HTTP from the access domain's graph to the aggregation domain's endpoint.
"""

import threading

from app.graphs import PATHS
from app.sparql_endpoint import create_domain_endpoint

ACCESS_PORT = 5001
AGGREGATION_PORT = 5002


def _run(app, port):
    app.run(host="127.0.0.1", port=port, use_reloader=False)


def main():
    access_app = create_domain_endpoint("access-endpoint", PATHS["access"])
    aggregation_app = create_domain_endpoint("aggregation-endpoint", PATHS["aggregation"])

    threading.Thread(target=_run, args=(access_app, ACCESS_PORT), daemon=True).start()
    threading.Thread(target=_run, args=(aggregation_app, AGGREGATION_PORT), daemon=True).start()

    print(f"Access domain SPARQL endpoint:      http://127.0.0.1:{ACCESS_PORT}/sparql")
    print(f"Aggregation domain SPARQL endpoint: http://127.0.0.1:{AGGREGATION_PORT}/sparql")
    print("Each process only ever loads its own domain's .ttl file.")
    print("Press Ctrl+C to stop.")
    threading.Event().wait()


if __name__ == "__main__":
    main()
