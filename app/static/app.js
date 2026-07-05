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

  const container = document.getElementById(canvasId);
  const options = {
    physics: { stabilization: true, barnesHut: { springLength: 140 } },
    interaction: { hover: true },
    edges: { smooth: { type: "dynamic" } },
  };

  if (networks[canvasId]) {
    networks[canvasId].setData({ nodes, edges });
  } else {
    networks[canvasId] = new vis.Network(container, { nodes, edges }, options);
  }
}

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

async function init() {
  setupTabs();
  await Promise.all([
    loadDomainTab("ontology"),
    loadDomainTab("access"),
    loadDomainTab("aggregation"),
    loadDomainTab("merged"),
  ]);
  await setupQueryConsole();
  await runQuery();
}

init();
