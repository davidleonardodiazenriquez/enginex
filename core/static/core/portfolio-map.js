(() => {
  const locations = JSON.parse(document.getElementById("portfolio-locations").textContent);
  const rows = [...document.querySelectorAll("[data-location]")];
  const search = document.getElementById("location-search");
  const explorer = document.querySelector(".explorer");
  const mobileToggle = document.querySelector(".mobile-locations-toggle");
  const announcement = document.getElementById("map-announcement");
  const message = document.getElementById("map-message");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const mobile = () => window.innerWidth <= 760;
  let selected = locations[0].id;
  let filter = "all";
  let map;
  let markers;
  let visibleLocations = locations;
  let initialOverview = true;
  let mobileView = { kind: "overview" };

  function closeList() {
    explorer.classList.remove("list-open");
    mobileToggle.setAttribute("aria-expanded", "false");
  }

  function showPreview(location, focus = true) {
    selected = location.id;
    document.getElementById("preview-image").src = location.image_url;
    document.getElementById("preview-image").alt = `${location.name} community`;
    document.getElementById("preview-number").textContent = `${location.number} / 06`;
    document.getElementById("preview-title").textContent = location.name;
    document.getElementById("preview-area").textContent = location.area;
    document.getElementById("preview-description").textContent = location.description;
    const status = document.getElementById("preview-status");
    status.textContent = location.ready ? "Metrics ready" : "Coming soon";
    status.classList.toggle("ready", location.ready);
    const facts = document.getElementById("preview-facts");
    facts.replaceChildren(...location.facts.map((fact) => {
      const item = document.createElement("div");
      const value = document.createElement("strong");
      const label = document.createElement("span");
      value.textContent = fact.value;
      label.textContent = fact.label;
      item.append(value, label);
      return item;
    }));
    const link = document.getElementById("preview-link");
    link.hidden = !location.ready;
    if (location.metrics_url) link.href = location.metrics_url;
    else link.removeAttribute("href");
    document.getElementById("preview-coming").hidden = location.ready;
    rows.forEach((row) => {
      const active = row.dataset.location === selected;
      row.classList.toggle("is-selected", active);
      row.setAttribute("aria-pressed", String(active));
    });
    announcement.textContent = `${location.name} selected. ${location.ready ? "Metrics available." : "Metrics coming soon."}`;
    closeList();
    if (map) {
      if (focus) {
        if (mobile()) {
          mobileView = { kind: "location", location };
          frameMobileView();
        } else {
          map.flyTo(location.coordinates, 16, { animate: !reduceMotion, duration: 1.35 });
        }
      }
      renderMarkers();
    }
  }

  rows.forEach((row) => row.addEventListener("click", () => {
    showPreview(locations.find((location) => location.id === row.dataset.location));
  }));

  function filterLocations() {
    const query = search.value.trim().toLowerCase();
    visibleLocations = locations.filter((location) => (
      `${location.name} ${location.area}`.toLowerCase().includes(query)
      && (filter === "all" || location.ready)
    ));
    rows.forEach((row) => { row.hidden = !visibleLocations.some((location) => location.id === row.dataset.location); });
    document.querySelector(".location-empty").hidden = visibleLocations.length > 0;
    announcement.textContent = `${visibleLocations.length} locations found.`;
    if (map) renderMarkers();
  }
  search.addEventListener("input", filterLocations);
  document.querySelectorAll("[data-filter]").forEach((button) => button.addEventListener("click", () => {
    filter = button.dataset.filter;
    document.querySelectorAll("[data-filter]").forEach((item) => {
      item.classList.toggle("active", item === button);
      item.setAttribute("aria-pressed", String(item === button));
    });
    filterLocations();
  }));
  mobileToggle.addEventListener("click", () => {
    const open = explorer.classList.toggle("list-open");
    mobileToggle.setAttribute("aria-expanded", String(open));
    if (open) search.focus();
  });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeList(); });

  if (!window.L) {
    message.textContent = "The map could not load. You can still explore locations from the list and open Al Rayyana metrics.";
    message.hidden = false;
    document.querySelectorAll(".map-tools button").forEach((button) => { button.disabled = true; });
    return;
  }

  map = L.map("portfolio-map", {
    zoomControl: false, attributionControl: true, minZoom: mobile() ? 9 : 10, maxZoom: 18,
    zoomSnap: 0.5, scrollWheelZoom: true, maxBounds: [[24.20, 54.15], [24.72, 54.85]],
    maxBoundsViscosity: 0.8,
  });
  map.attributionControl.setPrefix('<a href="https://leafletjs.com/" target="_blank" rel="noopener">Leaflet</a>');
  const satellite = L.tileLayer("https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 18,
    attribution: 'Imagery © Esri, Vantor, Earthstar Geographics, GIS User Community',
  });
  let loadedTiles = 0;
  satellite.on("loading", () => { loadedTiles = 0; });
  satellite.on("tileload", () => { loadedTiles += 1; message.hidden = true; });
  satellite.on("load", () => {
    if (!loadedTiles) {
      message.textContent = "Map imagery is unavailable. You can still select a location from the list.";
      message.hidden = false;
    }
  });
  satellite.addTo(map);
  markers = L.layerGroup().addTo(map);

  function mobilePadding() {
    const frame = map.getContainer().getBoundingClientRect();
    const intro = document.querySelector(".explorer-intro").getBoundingClientRect();
    const preview = document.querySelector(".asset-preview").getBoundingClientRect();
    // Fit the geography into the visible gap, reserving space for marker labels.
    return {
      paddingTopLeft: L.point(28, Math.ceil(intro.bottom - frame.top + 28)),
      paddingBottomRight: L.point(Math.min(132, frame.width * .3), Math.ceil(frame.bottom - preview.top + 38)),
    };
  }

  function frameMobileView(animate = !reduceMotion) {
    if (mobileView.kind === "manual") return;
    const padding = mobilePadding();
    const options = { ...padding, animate, duration: 1.1 };
    if (mobileView.kind === "location") {
      const zoom = 14.5;
      const size = map.getSize();
      const visibleCenter = padding.paddingTopLeft.add(size.subtract(padding.paddingBottomRight)).divideBy(2);
      const center = map.project(mobileView.location.coordinates, zoom).add(size.divideBy(2).subtract(visibleCenter));
      map.flyTo(map.unproject(center, zoom), zoom, options);
    } else {
      const group = mobileView.kind === "reem" ? locations.filter(location => location.area === "Al Reem Island") : locations;
      const bounds = L.latLngBounds(group.map(location => location.coordinates));
      const fit = { ...options, maxZoom: mobileView.kind === "reem" ? 14.5 : 12 };
      if (animate) map.flyToBounds(bounds, fit);
      else map.fitBounds(bounds, fit);
    }
    renderMarkers();
  }

  function overview() {
    if (mobile()) {
      mobileView = { kind: "overview" };
      frameMobileView(initialOverview ? false : !reduceMotion);
      initialOverview = false;
      return;
    }
    const left = explorer.offsetWidth + explorer.offsetLeft + 60;
    const right = document.querySelector(".asset-preview").offsetWidth + 180;
    const bounds = L.latLngBounds(locations.map((location) => location.coordinates));
    const options = {
      paddingTopLeft: [left, 125],
      paddingBottomRight: [right, 130],
      maxZoom: 13, animate: !reduceMotion, duration: 1.25,
    };
    if (initialOverview) {
      map.fitBounds(bounds, { ...options, animate: false });
      initialOverview = false;
    } else map.flyToBounds(bounds, options);
  }

  function accessibleMarker(marker, label, action) {
    marker.on("add", () => {
      const element = marker.getElement();
      element.setAttribute("role", "button");
      element.setAttribute("aria-label", label);
      element.addEventListener("keydown", (event) => {
        if (event.key === " ") { event.preventDefault(); action(); }
      });
    });
    marker.on("click", action).addTo(markers);
  }

  function renderMarkers() {
    markers.clearLayers();
    const reem = visibleLocations.filter((location) => location.area === "Al Reem Island");
    const reemDetail = mobile() && (mobileView.kind === "reem" || mobileView.kind === "location" && mobileView.location.area === "Al Reem Island");
    const clustered = map.getZoom() < 14.5 && reem.length > 1 && !reemDetail;
    if (clustered) {
      const cluster = L.marker([24.501, 54.4085], {
        icon: L.divIcon({ className: "cluster-marker", iconSize: mobile() ? [170, 44] : [204, 58], iconAnchor: mobile() ? [22, 22] : [28, 29],
          html: `<span class="cluster-body"><span class="cluster-count">${reem.length}</span><span class="cluster-copy"><strong>Al Reem Island</strong><small>Gate · Arc · The Bridges II</small></span><span class="cluster-arrow">↗</span></span>` }),
      });
      accessibleMarker(cluster, `Explore ${reem.length} Al Reem Island locations`, () => {
        closeList();
        if (mobile()) {
          mobileView = { kind: "reem" };
          frameMobileView();
        } else map.flyTo([24.5017, 54.408], 15, { animate: !reduceMotion, duration: 1.25 });
      });
    }
    visibleLocations.filter((location) => !clustered || location.area !== "Al Reem Island").forEach((location) => {
      const labelLeft = ["arc", "sas-al-nakhl"].includes(location.id);
      const icon = L.divIcon({
        className: `asset-map-marker${location.ready ? " ready" : ""}${selected === location.id ? " selected" : ""}${labelLeft ? " label-left" : ""}`,
        iconSize: [24, 24], iconAnchor: [12, 12],
        html: `<span class="asset-pin"></span><span class="asset-pin-label"><strong>${location.name}</strong><small>${location.ready ? "Explore metrics ↗" : location.area}</small></span>`,
      });
      const marker = L.marker(location.coordinates, { icon, zIndexOffset: selected === location.id ? 100 : 0 });
      accessibleMarker(marker, `${location.name}. ${location.ready ? "Metrics ready" : "Metrics coming soon"}. Select asset.`, () => showPreview(location));
    });
  }

  map.on("zoomend", renderMarkers);
  map.on("click", closeList);
  map.on("dragstart", () => { mobileView = { kind: "manual" }; });
  document.getElementById("zoom-in").addEventListener("click", () => { mobileView = { kind: "manual" }; map.zoomIn(); });
  document.getElementById("zoom-out").addEventListener("click", () => { mobileView = { kind: "manual" }; map.zoomOut(); });
  document.getElementById("reset-map").addEventListener("click", () => {
    search.value = "";
    filter = "all";
    document.querySelector('[data-filter="all"]').click();
    closeList();
    overview();
  });
  let resizeTimer;
  function resizeMap() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      map.invalidateSize({ pan: false });
      if (mobile()) frameMobileView(false);
      else overview();
    }, 150);
  }
  window.addEventListener("resize", resizeMap);
  const layoutObserver = new ResizeObserver(() => { if (mobile()) resizeMap(); });
  [map.getContainer(), document.querySelector(".asset-preview"), document.querySelector(".explorer-intro")].forEach(element => layoutObserver.observe(element));
  overview();
  renderMarkers();
})();
