const DOMAIN_COLORS = {
  access: "#2f7de1",
  aggregation: "#d9822b",
  ontology: "#6c4fd6",
  other: "#888888",
};

const TYPE_SHAPES = {
  OLT: "box",
  ONT: "box",
  Switch: "box",
  Tier1Switch: "box",
  Tier2Switch: "box",
  PONPort: "ellipse",
  NTPort: "ellipse",
  SwitchPort: "ellipse",
  Customer: "dot",
  CustomerService: "diamond",
  ISPService: "square",
  Class: "triangle",
  Property: "star",
  Ontology: "hexagon",
};

const networks = {};
const graphCache = {};
const NETWORK_OPTIONS = {
  physics: { stabilization: true, barnesHut: { springLength: 140 } },
  interaction: { hover: true },
  edges: { smooth: { type: "dynamic" } },
};

function shapeFor(type) {
  return TYPE_SHAPES[type] || "dot";
}

function renderGraph(canvasId, data, highlight) {
  const highlightNodes = new Set((highlight && highlight.nodeIris) || []);
  const highlightEdgeKeys = new Set((highlight && highlight.edgeKeys) || []);

  const nodes = data.nodes.map((n) => {
    const baseColor = DOMAIN_COLORS[n.domain] || DOMAIN_COLORS.other;
    const isHighlighted = highlightNodes.has(n.id);
    const tooltipLines = [n.id, n.type ? `type: ${n.type}` : null];
    Object.entries(n.attributes || {}).forEach(([k, vals]) => {
      tooltipLines.push(`${k}: ${vals.join(", ")}`);
    });
    return {
      id: n.id,
      label: n.label,
      shape: shapeFor(n.type),
      title: tooltipLines.filter(Boolean).join("\n"),
      color: {
        background: n.external ? "#e8e8e8" : baseColor,
        border: isHighlighted ? "#e6221f" : n.external ? "#999" : baseColor,
        highlight: { background: baseColor, border: "#e6221f" },
      },
      font: { color: n.external ? "#666" : "#111", size: 12 },
      borderWidth: isHighlighted ? 3 : 1,
      shapeProperties: n.external ? { borderDashes: [4, 3] } : {},
    };
  });

  const edges = data.edges.map((e) => {
    const key = `${e.source}|${e.predicate}|${e.target}`;
    const isHighlighted = highlightEdgeKeys.has(key);
    return {
      from: e.source,
      to: e.target,
      label: e.label,
      arrows: "to",
      font: { size: 9, align: "middle" },
      color: { color: isHighlighted ? "#e6221f" : "#c7c7c7", highlight: "#e6221f" },
      width: isHighlighted ? 3 : 1,
    };
  });

  // Cache the transformed data and (re)mount a brand-new vis.Network rather
  // than reusing/feeding an existing one. vis-network measures its container
  // at construction time; if that ever happened while the tab was hidden
  // (display:none => 0x0), its internal view/zoom state can stay wrong even
  // after later setData()/redraw()/fit() calls. Always building fresh from
  // cache - both here and whenever a tab becomes visible, see setupTabs -
  // guarantees the network is only ever constructed while its container has
  // real dimensions.
  graphCache[canvasId] = { nodes, edges };
  mountNetwork(canvasId);
}

function mountNetwork(canvasId) {
  const cached = graphCache[canvasId];
  const container = document.getElementById(canvasId);
  if (!cached || !container) return;
  try {
    if (networks[canvasId]) {
      networks[canvasId].destroy();
    }
    if (typeof vis === "undefined") {
      throw new Error("vis-network failed to load (check the CDN <script> tag / network access)");
    }
    networks[canvasId] = new vis.Network(container, cached, NETWORK_OPTIONS);
    container.dataset.renderError = "";
  } catch (err) {
    container.dataset.renderError = String(err);
    container.textContent = `Graph render error: ${err}`;
    container.style.cssText = "padding:1rem;color:#c0392b;font-size:0.85rem;white-space:pre-wrap;";
    console.error(`mountNetwork(${canvasId}) failed:`, err);
  }
}

window.addEventListener("error", (event) => {
  console.error("Uncaught error:", event.error || event.message);
});

const TAB_CANVAS_IDS = {
  ontology: "canvas-ontology",
  access: "canvas-access",
  aggregation: "canvas-aggregation",
  merged: "canvas-merged",
  query: "canvas-query",
};

async function loadDomainTab(source) {
  const res = await fetch(`/api/graphs/${source}`);
  const data = await res.json();
  renderGraph(`canvas-${source}`, data);
  document.getElementById(`turtle-${source}`).textContent = data.turtle;
  const externalCount = data.nodes.filter((n) => n.external).length;
  document.getElementById(`stats-${source}`).textContent =
    `${data.nodes.length} nodes total, ${data.edges.length} edges, ${externalCount} external (referenced but not defined here)`;
}

function setupTabs() {
  const buttons = document.querySelectorAll(".tab-btn");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`panel-${btn.dataset.tab}`).classList.add("active");
      if (btn.dataset.tab === "explore") {
        initExploreTab();
        return;
      }
      const canvasId = TAB_CANVAS_IDS[btn.dataset.tab];
      if (btn.dataset.tab === "query" && !graphCache[canvasId]) {
        // First visit to the Query Console: there's nothing cached yet
        // (the initial query is only ever run once a container is known
        // to be visible - see the removed eager call in init()), so run
        // it now instead of trying to mount from an empty cache.
        runQuery();
      } else {
        // The tab just went from display:none to visible - rebuild its
        // network fresh (from cache) now that the container has a real
        // size. See the comment in renderGraph() for why this can't just
        // be a redraw/fit on the existing instance.
        mountNetwork(canvasId);
      }
    });
  });
}

let cannedQueries = [];

async function setupQueryConsole() {
  const res = await fetch("/api/queries");
  cannedQueries = await res.json();

  const picker = document.getElementById("query-picker");
  cannedQueries.forEach((q) => {
    const opt = document.createElement("option");
    opt.value = q.id;
    opt.textContent = q.label;
    picker.appendChild(opt);
  });

  const applyCanned = (id) => {
    const q = cannedQueries.find((c) => c.id === id);
    if (!q) return;
    document.getElementById("query-text").value = q.sparql;
    document.getElementById("query-source").value = q.source;
    document.getElementById("query-description").textContent = q.description;
  };

  picker.addEventListener("change", () => applyCanned(picker.value));
  applyCanned(cannedQueries[0].id);

  document.getElementById("run-query").addEventListener("click", runQuery);
}

function renderResultsTable(columns, rows) {
  const table = document.getElementById("results-table");
  table.innerHTML = "";
  const thead = document.createElement("tr");
  columns.forEach((c) => {
    const th = document.createElement("th");
    th.textContent = c;
    thead.appendChild(th);
  });
  table.appendChild(thead);
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    row.forEach((cell) => {
      const td = document.createElement("td");
      td.textContent = cell === null ? "" : cell;
      tr.appendChild(td);
    });
    table.appendChild(tr);
  });
}

async function runQuery() {
  const sparql = document.getElementById("query-text").value;
  const source = document.getElementById("query-source").value;
  const errorBox = document.getElementById("query-error");
  errorBox.textContent = "";

  let res, body;
  try {
    res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sparql, source }),
    });
    body = await res.json();
  } catch (err) {
    errorBox.textContent = `Request failed: ${err}`;
    return;
  }

  if (!res.ok) {
    errorBox.textContent = body.error || "Query failed.";
    document.getElementById("results-table").innerHTML = "";
    return;
  }

  if (body.type === "ask") {
    renderResultsTable(["result"], [[String(body.boolean)]]);
  } else {
    renderResultsTable(body.columns, body.rows);
  }

  const graphRes = await fetch(`/api/graphs/${body.source}`);
  const graphData = await graphRes.json();
  const edgeKeys = (body.highlighted_edges || []).map(([s, p, o]) => `${s}|${p}|${o}`);
  renderGraph("canvas-query", graphData, {
    nodeIris: body.highlighted_node_iris || [],
    edgeKeys,
  });
}

function makeCell(text) {
  const td = document.createElement("td");
  td.textContent = text;
  return td;
}

function makeNumCell(text) {
  const td = makeCell(text);
  td.classList.add("num");
  return td;
}

function makeLinkCell(text, onClick) {
  const td = document.createElement("td");
  const a = document.createElement("a");
  a.href = "#";
  a.textContent = text;
  a.addEventListener("click", (e) => {
    e.preventDefault();
    onClick();
  });
  td.appendChild(a);
  return td;
}

function setTableBody(tableId, rows) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  tbody.innerHTML = "";
  rows.forEach((row) => tbody.appendChild(row));
  return tbody;
}

let exploreLoaded = false;

async function initExploreTab() {
  if (!exploreLoaded) {
    exploreLoaded = true;
    document.getElementById("explore-source").addEventListener("change", loadExploreClasses);
    await loadExploreClasses();
  }
}

async function loadExploreClasses() {
  const source = document.getElementById("explore-source").value;
  const res = await fetch(`/api/browse/${source}/classes`);
  const classes = await res.json();

  setTableBody(
    "explore-class-table",
    classes.map((c) => {
      const tr = document.createElement("tr");
      tr.appendChild(makeCell(c.label));
      tr.appendChild(makeNumCell(String(c.count)));
      tr.addEventListener("click", () => {
        document.querySelectorAll("#explore-class-table tbody tr").forEach((r) => r.classList.remove("selected"));
        tr.classList.add("selected");
        loadExploreInstances(source, c.class, c.label);
      });
      return tr;
    })
  );

  document.getElementById("explore-instances-heading").textContent = "";
  setTableBody("explore-instance-table", []);
  clearExploreResource();
}

async function loadExploreInstances(source, classIri, classLabel) {
  document.getElementById("explore-instances-heading").textContent = `— ${classLabel}`;
  const res = await fetch(`/api/browse/${source}/instances?class=${encodeURIComponent(classIri)}`);
  const instances = await res.json();

  setTableBody(
    "explore-instance-table",
    instances.map((inst) => {
      const tr = document.createElement("tr");
      tr.appendChild(makeCell(inst.label));
      tr.addEventListener("click", () => {
        document.querySelectorAll("#explore-instance-table tbody tr").forEach((r) => r.classList.remove("selected"));
        tr.classList.add("selected");
        loadExploreResource(source, inst.iri);
      });
      return tr;
    })
  );
  clearExploreResource();
}

async function loadExploreResource(source, iri) {
  const res = await fetch(`/api/browse/${source}/resource?iri=${encodeURIComponent(iri)}`);
  const r = await res.json();

  document.getElementById("explore-resource-heading").textContent = r.label;

  const meta = document.getElementById("explore-resource-meta");
  meta.innerHTML = "";
  const iriLine = document.createElement("div");
  iriLine.className = "resource-iri";
  iriLine.textContent = r.iri;
  meta.appendChild(iriLine);

  const typesLine = document.createElement("div");
  typesLine.className = "resource-types";
  typesLine.textContent = r.types.length ? r.types.join(", ") : "(no type asserted in this graph)";
  if (!r.definedHere) {
    const badge = document.createElement("span");
    badge.className = "external-badge";
    badge.textContent = "referenced but not defined here";
    typesLine.appendChild(badge);
  }
  meta.appendChild(typesLine);

  setTableBody(
    "explore-properties-table",
    r.properties.map((p) => {
      const tr = document.createElement("tr");
      tr.appendChild(makeCell(p.predicateLabel));
      if (p.kind === "uri") {
        tr.appendChild(makeLinkCell(p.valueLabel, () => loadExploreResource(source, p.value)));
      } else {
        tr.appendChild(makeCell(p.valueLabel));
      }
      return tr;
    })
  );

  setTableBody(
    "explore-referenced-table",
    r.referencedBy.map((ref) => {
      const tr = document.createElement("tr");
      tr.appendChild(makeLinkCell(ref.subjectLabel, () => loadExploreResource(source, ref.subject)));
      tr.appendChild(makeCell(ref.predicateLabel));
      return tr;
    })
  );
}

function clearExploreResource() {
  document.getElementById("explore-resource-heading").textContent = "Select an instance";
  document.getElementById("explore-resource-meta").innerHTML = "";
  setTableBody("explore-properties-table", []);
  setTableBody("explore-referenced-table", []);
}

async function init() {
  setupTabs();
  await Promise.all([
    loadDomainTab("ontology"),
    loadDomainTab("access"),
    loadDomainTab("aggregation"),
    loadDomainTab("merged"),
  ]);
  await setupQueryConsole();
  // The Query Console's graph is deliberately not rendered here: doing so
  // would construct its vis.Network while the tab is still hidden
  // (Ontology is the default active tab). It's run lazily instead, the
  // first time the Query Console tab is opened - see setupTabs().
}

init();
