(function () {
  "use strict";

  var supportUrl = "/admin/support/";
  var lookupUrl = "/admin/support/lookup";

  function appendCell(row, value) {
    var cell = document.createElement("td");
    cell.textContent = value == null ? "" : String(value);
    row.appendChild(cell);
  }

  function renderEvents(events) {
    var body = document.querySelector("#events tbody");
    body.replaceChildren();
    (events || []).forEach(function (event) {
      var row = document.createElement("tr");
      appendCell(row, event[0]);
      appendCell(row, event[1]);
      body.appendChild(row);
    });
  }

  function renderWarnings(warnings) {
    var body = document.querySelector("#logs tbody");
    body.replaceChildren();
    (warnings || []).forEach(function (entry) {
      var row = document.createElement("tr");
      var timestamp = new Date((entry.ts || 0) * 1000).toISOString();
      appendCell(row, timestamp);
      appendCell(row, entry.level);
      appendCell(row, entry.path);
      appendCell(row, entry.request_id);
      appendCell(row, entry.msg);
      body.appendChild(row);
    });
  }

  async function load() {
    var response = await fetch(supportUrl);
    var data = await response.json();
    document.getElementById("meta").textContent = JSON.stringify(
      {
        service_version: data.service_version,
        deploy_env: data.deploy_env,
        now: data.now
      },
      null,
      2
    );
    renderEvents(data.events);
    renderWarnings(data.recent_warnings);
  }

  document.getElementById("export").addEventListener("click", async function () {
    var response = await fetch(supportUrl);
    var data = await response.json();
    var blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    var link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "support.json";
    link.click();
    URL.revokeObjectURL(link.href);
  });

  document.getElementById("lookup").addEventListener("click", async function () {
    var requestId = document.getElementById("req").value.trim();
    if (!requestId) {
      return;
    }
    var response = await fetch(lookupUrl + "?request_id=" + encodeURIComponent(requestId));
    var data = await response.json();
    alert((data.hits || []).length + " träff(ar) för " + requestId);
  });

  load();
  setInterval(load, 15000);
}());
