/*
 * HemoSlab Frontend Controller
 * Strict schema alignment with FastAPI /api/network/state, /api/transfers/dispatch,
 * /api/briefing, /api/audit, and /api/reset. Zero static mocked metrics.
 */

(() => {
  "use strict";

  const PALETTE = {
    canvas: "#E6ECE7",
    surface: "#F4F7F3",
    inset: "#EAEFE9",
    gridLine: "#D5DDD6",
    ink: "#1C1917",
    inkMuted: "#44403C",
    critical: "#B91C1C",
    criticalTint: "#FEE2E2",
    criticalWash: "#FCF1F1",
    watch: "#B45309",
    watchTint: "#FEF3C7",
    watchWash: "#FCF6E8",
    safe: "#15803D",
    safeTint: "#DCFCE7",
    safeWash: "#EFF7F1",
    edgeIdle: "#8C968D",
  };

  const SCENARIO_LABELS = {
    baseline: "Baseline",
    dengue: "Monsoon Dengue Surge",
    trauma: "Highway Trauma Event",
  };

  const state = {
    scenario: "baseline",
    donationDrop: 0,
    demandMult: 1.0,
    selectedHospitalId: null,
    selectedComponent: "Platelets",
    network: null,
    activeAlert: null,
    activeBriefing: null,
    auditData: null,
    chartInstance: null,
    pieChartInstance: null,
    semiChartInstance: null,
    modalChartInstance: null,
    modalPieChartInstance: null,
    modalSemiChartInstance: null,
    sliderTimer: null,
    pulseTimer: null,
    pulseRafIds: [],
    modalOpen: false,
    modalTab: "topology",
    modalTimelineFilter: "all",
  };

  const els = {
    heroBar: document.getElementById("heroBar"),
    readinessScore: document.getElementById("readinessScore"),
    activeAlertCount: document.getElementById("activeAlertCount"),
    urgentCountdown: document.getElementById("urgentCountdown"),
    urgentBadge: document.getElementById("urgentBadge"),
    urgentTargetLabel: document.getElementById("urgentTargetLabel"),
    unitsSavedCount: document.getElementById("unitsSavedCount"),
    resetDemoBtn: document.getElementById("resetDemoBtn"),

    toggleStressBtn: document.getElementById("toggleStressBtn"),
    resetSlidersBtn: document.getElementById("resetSlidersBtn"),
    stressBody: document.getElementById("stressBody"),
    stressFirstBreach: document.getElementById("stressFirstBreach"),
    donationDropSlider: document.getElementById("donationDropSlider"),
    donationDropValue: document.getElementById("donationDropValue"),
    demandMultSlider: document.getElementById("demandMultSlider"),
    demandMultValue: document.getElementById("demandMultValue"),

    svgEdgesLayer: document.getElementById("svgEdgesLayer"),
    svgTransferPulseLayer: document.getElementById("svgTransferPulseLayer"),
    svgNodesLayer: document.getElementById("svgNodesLayer"),
    transferBanner: document.getElementById("transferBanner"),
    networkComponentTotals: document.getElementById("networkComponentTotals"),
    facilityPulseList: document.getElementById("facilityPulseList"),
    topCorridorStrip: document.getElementById("topCorridorStrip"),

    selectedHospitalTitle: document.getElementById("selectedHospitalTitle"),
    selectedHospitalMeta: document.getElementById("selectedHospitalMeta"),
    inventoryMatrixBody: document.getElementById("inventoryMatrixBody"),
    forecastChart: document.getElementById("forecastChart"),
    hospitalBloodGroupChart: document.getElementById("hospitalBloodGroupChart"),
    hospitalExpirySemiChart: document.getElementById("hospitalExpirySemiChart"),
    bloodGroupPieTotal: document.getElementById("bloodGroupPieTotal"),
    expiryGaugeBadge: document.getElementById("expiryGaugeBadge"),
    expiryGaugeReadout: document.getElementById("expiryGaugeReadout"),

    recSummaryPill: document.getElementById("recSummaryPill"),
    timelineStrip: document.getElementById("timelineStrip"),

    auditDrawer: document.getElementById("auditDrawer"),
    drawerToggleBtn: document.getElementById("drawerToggleBtn"),
    drawerContextBadge: document.getElementById("drawerContextBadge"),
    drawerChevron: document.getElementById("drawerChevron"),
    briefAlertHeadline: document.getElementById("briefAlertHeadline"),
    briefSourceBadge: document.getElementById("briefSourceBadge"),
    briefCause: document.getElementById("briefCause"),
    briefMathTrigger: document.getElementById("briefMathTrigger"),
    briefAction: document.getElementById("briefAction"),
    briefSms: document.getElementById("briefSms"),
    smsCharCount: document.getElementById("smsCharCount"),
    copySmsBtn: document.getElementById("copySmsBtn"),
    rawMathPre: document.getElementById("rawMathPre"),
    auditLedgerList: document.getElementById("auditLedgerList"),

    // Click-to-Zoom Focus Overlay elements
    focusOverlay: document.getElementById("focusOverlay"),
    focusSheet: document.getElementById("focusSheet"),
    closeFocusOverlay: document.getElementById("closeFocusOverlay"),
    modalScenarioBadge: document.getElementById("modalScenarioBadge"),
    modalTabTopology: document.getElementById("modalTabTopology"),
    modalTabForecast: document.getElementById("modalTabForecast"),
    modalTabTimeline: document.getElementById("modalTabTimeline"),
    modalPanelTopology: document.getElementById("modalPanelTopology"),
    modalPanelForecast: document.getElementById("modalPanelForecast"),
    modalPanelTimeline: document.getElementById("modalPanelTimeline"),
    modalSelectedFacilityNote: document.getElementById("modalSelectedFacilityNote"),
    modalJumpToForecastBtn: document.getElementById("modalJumpToForecastBtn"),
    modalSvgStage: document.getElementById("modalSvgStage"),
    modalSvgEdgesLayer: document.getElementById("modalSvgEdgesLayer"),
    modalSvgTransferPulseLayer: document.getElementById("modalSvgTransferPulseLayer"),
    modalSvgNodesLayer: document.getElementById("modalSvgNodesLayer"),
    modalForecastTitle: document.getElementById("modalForecastTitle"),
    modalForecastMeta: document.getElementById("modalForecastMeta"),
    modalChartCanvas: document.getElementById("modalChartCanvas"),
    modalBloodGroupChart: document.getElementById("modalBloodGroupChart"),
    modalExpirySemiChart: document.getElementById("modalExpirySemiChart"),
    modalBloodGroupPieTotal: document.getElementById("modalBloodGroupPieTotal"),
    modalExpiryGaugeBadge: document.getElementById("modalExpiryGaugeBadge"),
    modalExpiryGaugeReadout: document.getElementById("modalExpiryGaugeReadout"),
    modalStockTable: document.getElementById("modalStockTable"),
    modalRecCount: document.getElementById("modalRecCount"),
    modalTimelinePrev: document.getElementById("modalTimelinePrev"),
    modalTimelineNext: document.getElementById("modalTimelineNext"),
    modalTimelineRail: document.getElementById("modalTimelineRail"),
  };

  function statusClass(status) {
    if (status === "Critical") return "status-critical";
    if (status === "Watch") return "status-watch";
    return "status-safe";
  }

  function statusColors(status) {
    if (status === "Critical") {
      return {
        fill: PALETTE.criticalTint,
        wash: PALETTE.criticalWash,
        stroke: PALETTE.critical,
        text: PALETTE.critical,
      };
    }
    if (status === "Watch") {
      return {
        fill: PALETTE.watchTint,
        wash: PALETTE.watchWash,
        stroke: PALETTE.watch,
        text: PALETTE.watch,
      };
    }
    return {
      fill: PALETTE.safeTint,
      wash: PALETTE.safeWash,
      stroke: PALETTE.safe,
      text: PALETTE.safe,
    };
  }

  function mapCoord(x, y, isZoomed = false) {
    if (isZoomed) {
      return {
        cx: 120 + (x / 100) * 800,
        cy: 68 + (y / 100) * 404,
      };
    }
    return {
      cx: 75 + (x / 100) * 650,
      cy: 60 + (y / 100) * 380,
    };
  }

  function formatHours(hours) {
    if (hours >= 336) return ">14d";
    return `${Number(hours).toFixed(1)}h`;
  }

  function buildActiveFefoEdgeSet(net) {
    const activePairs = new Set();
    (net.recommendations || []).forEach((rec) => {
      activePairs.add(`${rec.donor_hospital_id}|${rec.receiver_hospital_id}`);
      activePairs.add(`${rec.receiver_hospital_id}|${rec.donor_hospital_id}`);
    });
    return activePairs;
  }

  async function fetchNetworkState() {
    const params = new URLSearchParams({
      scenario: state.scenario,
      donation_drop: String(state.donationDrop),
      demand_mult: String(state.demandMult),
    });
    const res = await fetch(`/api/network/state?${params.toString()}`);
    if (!res.ok) {
      throw new Error(`Network state fetch failed (${res.status})`);
    }
    const data = await res.json();
    state.network = data;

    if (
      !state.selectedHospitalId ||
      !data.hospitals.some((h) => h.id === state.selectedHospitalId)
    ) {
      state.selectedHospitalId = data.most_urgent_hospital_id || data.hospitals[0]?.id;
    }

    renderAll();

    // Auto-load top alert into Audit & Ask raw math if nothing active
    if (data.alerts.length > 0 && !state.activeAlert) {
      loadAlertBriefing(data.alerts[0], false);
    }
  }

  async function fetchAuditLedger() {
    const res = await fetch("/api/audit");
    if (!res.ok) return;
    state.auditData = await res.json();
    renderAuditLedger();
  }

  function renderAll() {
    if (!state.network) return;
    renderHero();
    renderTopologyMap();
    renderFacilityPulsePanel();
    renderSelectedHospitalPanel();
    renderTimeline72h();
    if (state.modalOpen) {
      renderActiveModalView();
    }
  }

  function renderHero() {
    const net = state.network;
    els.readinessScore.textContent = String(net.network_readiness_score);
    els.activeAlertCount.textContent = `${net.total_active_alerts} active Watch/Critical alerts across 6 facilities`;

    els.urgentCountdown.textContent = formatHours(net.most_urgent_countdown_hours);
    const urgentStatus =
      net.most_urgent_countdown_hours < 48
        ? "Critical"
        : net.most_urgent_countdown_hours <= 120
        ? "Watch"
        : "Safe";
    els.urgentBadge.textContent = urgentStatus;
    els.urgentBadge.className = `status-pill ${statusClass(urgentStatus)}`;
    els.urgentTargetLabel.textContent = net.most_urgent_label;

    els.unitsSavedCount.textContent = String(net.units_saved_from_expiry);
    els.stressFirstBreach.textContent = `${net.most_urgent_label} (${formatHours(
      net.most_urgent_countdown_hours
    )})`;

    if (els.modalScenarioBadge) {
      els.modalScenarioBadge.textContent = SCENARIO_LABELS[net.scenario] || net.scenario;
    }
  }

  function createSvgEl(tag, attrs = {}) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, String(v)));
    return el;
  }

  function renderTopologyInto(edgesLayer, nodesLayer, isZoomed = false) {
    const net = state.network;
    if (!net || !edgesLayer || !nodesLayer) return;

    const hospById = Object.fromEntries(net.hospitals.map((h) => [h.id, h]));
    const activeFefoEdges = buildActiveFefoEdgeSet(net);

    edgesLayer.innerHTML = "";
    nodesLayer.innerHTML = "";

    // 1. Render Cold-Chain Edges (corridorFlow applied ONLY to active FEFO transfer edges)
    net.edges.forEach((edge) => {
      const s = hospById[edge.source_id];
      const t = hospById[edge.target_id];
      if (!s || !t) return;
      const p1 = mapCoord(s.x, s.y, isZoomed);
      const p2 = mapCoord(t.x, t.y, isZoomed);
      const isFefoActive = activeFefoEdges.has(`${edge.source_id}|${edge.target_id}`);

      const line = createSvgEl("line", {
        x1: p1.cx,
        y1: p1.cy,
        x2: p2.cx,
        y2: p2.cy,
        stroke: isFefoActive ? PALETTE.watch : PALETTE.edgeIdle,
        "stroke-width": isFefoActive ? 2.2 : 1.6,
        class: isFefoActive ? "corridor-flow-edge" : "",
      });
      edgesLayer.appendChild(line);

      const mx = (p1.cx + p2.cx) / 2;
      const my = (p1.cy + p2.cy) / 2;
      const pillW = isZoomed ? 48 : 40;
      const pillH = isZoomed ? 20 : 18;
      const pill = createSvgEl("rect", {
        x: mx - pillW / 2,
        y: my - pillH / 2,
        width: pillW,
        height: pillH,
        fill: PALETTE.surface,
        stroke: PALETTE.ink,
        "stroke-width": 1.2,
      });
      const label = createSvgEl("text", {
        x: mx,
        y: my + 4,
        "text-anchor": "middle",
        "font-family": "JetBrains Mono, monospace",
        "font-size": isZoomed ? 11 : 10,
        "font-weight": 700,
        fill: PALETTE.ink,
      });
      label.textContent = `${edge.transit_minutes}m`;
      edgesLayer.appendChild(pill);
      edgesLayer.appendChild(label);
    });

    // 2. Render Elevated 2D-in-3D Hospital Nodes with status-tinted washes
    net.hospitals.forEach((h) => {
      const { cx, cy } = mapCoord(h.x, h.y, isZoomed);
      const w = isZoomed ? 214 : 152;
      const hBox = isZoomed ? 76 : 64;
      const x0 = cx - w / 2;
      const y0 = cy - hBox / 2;
      const colors = statusColors(h.status);
      const isSelected = h.id === state.selectedHospitalId;
      const isMostUrgent = h.id === net.most_urgent_hospital_id && h.min_zero_stock_hours <= 120;

      const g = createSvgEl("g", {
        class: `svg-node ${isSelected ? "is-selected" : ""}`,
        "data-hospital-id": h.id,
      });

      // Restrained criticalRingPulse ONLY on Critical (<48h) nodes
      if (h.status === "Critical") {
        g.appendChild(
          createSvgEl("rect", {
            class: "critical-ring-pulse",
            x: x0 - 4,
            y: y0 - 4,
            width: w + 8,
            height: hBox + 8,
          })
        );
      }

      // Solid hard offset shadow
      g.appendChild(
        createSvgEl("rect", {
          x: x0 + 4,
          y: y0 + 4,
          width: w,
          height: hBox,
          fill: PALETTE.ink,
        })
      );

      // Structural card body using soft status-tinted wash
      g.appendChild(
        createSvgEl("rect", {
          class: "node-body",
          x: x0,
          y: y0,
          width: w,
          height: hBox,
          fill: colors.wash,
          stroke: isMostUrgent ? PALETTE.critical : PALETTE.ink,
          "stroke-width": isSelected ? 2.6 : 1.6,
        })
      );

      // Top clinical accent bar
      g.appendChild(
        createSvgEl("rect", {
          x: x0,
          y: y0,
          width: w,
          height: 6,
          fill: colors.stroke,
        })
      );

      // Facility Code
      const codeText = createSvgEl("text", {
        x: x0 + 9,
        y: y0 + (isZoomed ? 24 : 23),
        "font-family": "JetBrains Mono, monospace",
        "font-size": isZoomed ? 13 : 12,
        "font-weight": 700,
        fill: PALETTE.ink,
      });
      codeText.textContent = h.code;
      g.appendChild(codeText);

      // Status Pill
      const badgeW = isZoomed ? 62 : 54;
      g.appendChild(
        createSvgEl("rect", {
          x: x0 + w - badgeW - 8,
          y: y0 + 11,
          width: badgeW,
          height: 16,
          fill: colors.fill,
          stroke: PALETTE.ink,
          "stroke-width": 1,
        })
      );

      const statusText = createSvgEl("text", {
        x: x0 + w - badgeW / 2 - 8,
        y: y0 + 22.5,
        "text-anchor": "middle",
        "font-family": "JetBrains Mono, monospace",
        "font-size": 9.5,
        "font-weight": 700,
        fill: colors.text,
      });
      statusText.textContent = h.status.toUpperCase();
      g.appendChild(statusText);

      // Facility Name (full untruncated in zoomed overlay)
      const displayName = isZoomed
        ? h.name
        : h.name.length > 21
        ? `${h.name.slice(0, 19)}…`
        : h.name;
      const nameText = createSvgEl("text", {
        x: x0 + 9,
        y: y0 + (isZoomed ? 43 : 39),
        "font-family": "Space Grotesk, sans-serif",
        "font-size": isZoomed ? 11.5 : 10.5,
        "font-weight": 600,
        fill: PALETTE.inkMuted,
      });
      nameText.textContent = displayName;
      g.appendChild(nameText);

      // Min Zero-Stock Countdown & Critical Pair
      const countText = createSvgEl("text", {
        x: x0 + 9,
        y: y0 + (isZoomed ? 62 : 55),
        "font-family": "JetBrains Mono, monospace",
        "font-size": isZoomed ? 11.5 : 10.5,
        "font-weight": 700,
        fill: colors.text,
      });
      countText.textContent = `${formatHours(h.min_zero_stock_hours)} · ${h.critical_pair}`;
      g.appendChild(countText);

      g.addEventListener("click", (evt) => {
        evt.stopPropagation();
        state.selectedHospitalId = h.id;
        renderTopologyMap();
        renderFacilityPulsePanel();
        renderSelectedHospitalPanel();
        if (state.modalOpen) {
          renderActiveModalView();
        }
      });

      nodesLayer.appendChild(g);
    });
  }

  function renderTopologyMap() {
    renderTopologyInto(els.svgEdgesLayer, els.svgNodesLayer, false);
  }

  function renderFacilityPulsePanel() {
    if (!state.network || !els.facilityPulseList) return;
    const net = state.network;

    const totals = { Platelets: 0, RBCs: 0, Plasma: 0 };
    net.hospitals.forEach((h) => {
      h.inventory.forEach((item) => {
        if (Object.prototype.hasOwnProperty.call(totals, item.component)) {
          totals[item.component] += item.total_units;
        }
      });
    });

    if (els.networkComponentTotals) {
      els.networkComponentTotals.textContent = `PLT ${totals.Platelets}u · RBC ${totals.RBCs}u · PLS ${totals.Plasma}u`;
    }

    els.facilityPulseList.innerHTML = net.hospitals
      .map((h) => {
        const exp72 = h.inventory.reduce(
          (sum, item) => sum + Math.min(item.total_units, item.expiring_within_72h),
          0
        );
        const total = Math.max(1, h.total_units);
        const expPct = Math.round((exp72 / total) * 100);
        const safePct = Math.max(0, 100 - expPct);
        const isSel = h.id === state.selectedHospitalId;
        return `
          <button type="button" class="pulse-facility-row ${isSel ? "is-selected" : ""}" data-pulse-hospital="${h.id}">
            <span class="mono pulse-code">${h.code}</span>
            <span class="pulse-name-col">
              <span class="pulse-name">${h.name}</span>
              <span class="mono pulse-sub">${h.total_units}u stock · ${exp72}u &le;72h</span>
            </span>
            <span class="pulse-bar-track" title="${exp72}u expiring <=72h / ${h.total_units}u total">
              <span class="pulse-bar-exp" style="width:${expPct}%"></span>
              <span class="pulse-bar-safe" style="width:${safePct}%"></span>
            </span>
            <span class="mono pulse-buffer">${formatHours(h.min_zero_stock_hours)}</span>
            <span class="status-pill ${statusClass(h.status)}">${h.status}</span>
          </button>
        `;
      })
      .join("");

    els.facilityPulseList.querySelectorAll("[data-pulse-hospital]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.selectedHospitalId = btn.getAttribute("data-pulse-hospital");
        renderTopologyMap();
        renderFacilityPulsePanel();
        renderSelectedHospitalPanel();
        if (state.modalOpen) {
          renderActiveModalView();
        }
      });
    });

    if (els.topCorridorStrip) {
      const topRec = net.recommendations[0];
      if (topRec) {
        const edge = net.edges.find(
          (e) =>
            (e.source_id === topRec.donor_hospital_id && e.target_id === topRec.receiver_hospital_id) ||
            (e.source_id === topRec.receiver_hospital_id && e.target_id === topRec.donor_hospital_id)
        );
        const distLabel = edge ? ` · ${edge.distance_km} km` : "";
        els.topCorridorStrip.innerHTML = `
          <span><strong>TOP CORRIDOR:</strong> ${topRec.donor_code} &rarr; ${topRec.receiver_code} (${topRec.units}u ${topRec.donor_blood_group} ${topRec.component})</span>
          <span>ETA ${topRec.transit_minutes}m${distLabel}</span>
        `;
      } else {
        els.topCorridorStrip.innerHTML = `
          <span><strong>CORRIDORS:</strong> All 6 facilities balanced</span>
          <span>0 urgent transfers queued</span>
        `;
      }
    }
  }

  function stopActiveCourierAnimations() {
    if (Array.isArray(state.pulseRafIds)) {
      state.pulseRafIds.forEach((id) => cancelAnimationFrame(id));
    }
    state.pulseRafIds = [];
    clearTimeout(state.pulseTimer);
  }

  function mountCourierPulse(layer, p1, p2, meta = {}) {
    if (!layer) return;
    layer.innerHTML = "";
    const pulseLine = createSvgEl("line", {
      x1: p1.cx,
      y1: p1.cy,
      x2: p2.cx,
      y2: p2.cy,
      class: "transfer-pulse-line",
    });
    layer.appendChild(pulseLine);

    // Moving courier group along donor -> receiver vector (driven by requestAnimationFrame)
    const courier = createSvgEl("g", {
      transform: `translate(${p1.cx}, ${p1.cy})`,
    });

    // Keep ambulance upright and facing direction of travel
    const dx = p2.cx - p1.cx;
    const dy = p2.cy - p1.cy;
    const goingLeft = dx < 0;
    const rawDeg = (Math.atan2(dy, dx) * 180) / Math.PI;
    const tiltDeg = goingLeft ? rawDeg - 180 : rawDeg;

    const scaleFactor = meta.isZoomed ? 1.25 : 1.15;
    const vehicleTilt = createSvgEl("g", {
      transform: `rotate(${tiltDeg.toFixed(1)}) scale(${goingLeft ? -scaleFactor : scaleFactor}, ${scaleFactor})`,
    });
    const vehicleBody = createSvgEl("g", { class: "dispatch-ambulance-bounce" });

    // Ground shadow
    vehicleBody.appendChild(
      createSvgEl("ellipse", {
        cx: 0,
        cy: 11,
        rx: 20,
        ry: 3,
        fill: PALETTE.ink,
        opacity: 0.35,
      })
    );

    // Headlight cone
    vehicleBody.appendChild(
      createSvgEl("polygon", {
        points: "20,2 36,-4 36,10",
        fill: PALETTE.watchTint,
        opacity: 0.85,
      })
    );

    // Roof emergency lightbar
    vehicleBody.appendChild(
      createSvgEl("rect", {
        x: 5,
        y: -14,
        width: 8,
        height: 4,
        fill: PALETTE.ink,
      })
    );
    vehicleBody.appendChild(
      createSvgEl("rect", {
        x: 5.5,
        y: -13.5,
        width: 3.5,
        height: 3,
        fill: PALETTE.critical,
        class: "dispatch-siren-red",
      })
    );
    vehicleBody.appendChild(
      createSvgEl("rect", {
        x: 9,
        y: -13.5,
        width: 3.5,
        height: 3,
        fill: "#F59E0B",
        class: "dispatch-siren-amber",
      })
    );

    // Main tactile ambulance silhouette
    vehicleBody.appendChild(
      createSvgEl("path", {
        d: "M -20,-10 L 6,-10 L 6,-6 L 14,-6 L 20,0 L 20,8 L -20,8 Z",
        fill: PALETTE.surface,
        stroke: PALETTE.ink,
        "stroke-width": 1.8,
      })
    );

    // Crimson cold-chain stripe
    vehicleBody.appendChild(
      createSvgEl("rect", {
        x: -19,
        y: 1,
        width: 38,
        height: 3,
        fill: PALETTE.critical,
      })
    );

    // Cab windshield
    vehicleBody.appendChild(
      createSvgEl("polygon", {
        points: "8,-4 13,-4 17,0 8,0",
        fill: PALETTE.gridLine,
        stroke: PALETTE.ink,
        "stroke-width": 1.1,
      })
    );

    // Red medical cross
    vehicleBody.appendChild(
      createSvgEl("rect", {
        x: -10,
        y: -7.5,
        width: 2.6,
        height: 7,
        fill: PALETTE.critical,
      })
    );
    vehicleBody.appendChild(
      createSvgEl("rect", {
        x: -12.2,
        y: -5.3,
        width: 7,
        height: 2.6,
        fill: PALETTE.critical,
      })
    );

    // Wheels
    [-11, 11].forEach((wx) => {
      vehicleBody.appendChild(
        createSvgEl("circle", {
          cx: wx,
          cy: 8.5,
          r: 4.2,
          fill: PALETTE.ink,
        })
      );
      vehicleBody.appendChild(
        createSvgEl("circle", {
          cx: wx,
          cy: 8.5,
          r: 1.7,
          fill: PALETTE.inset,
        })
      );
    });

    vehicleTilt.appendChild(vehicleBody);
    courier.appendChild(vehicleTilt);

    // Upright cargo badge floating above the ambulance
    const tagText = meta.label || "FEFO DISPATCH";
    const badgeWidth = Math.max(78, tagText.length * 6.4 + 14);
    const badge = createSvgEl("g", { transform: "translate(0, -28)" });
    badge.appendChild(
      createSvgEl("rect", {
        x: -badgeWidth / 2,
        y: -11,
        width: badgeWidth,
        height: 16,
        fill: PALETTE.ink,
      })
    );
    const labelEl = createSvgEl("text", {
      x: 0,
      y: 0,
      "text-anchor": "middle",
      "font-family": "JetBrains Mono, monospace",
      "font-size": 9.5,
      "font-weight": 700,
      fill: PALETTE.safeTint,
    });
    labelEl.textContent = tagText;
    badge.appendChild(labelEl);
    courier.appendChild(badge);
    layer.appendChild(courier);

    const tripMs = 1900;
    const totalTrips = 3;
    const startTs = performance.now();

    function step(now) {
      const elapsed = now - startTs;
      if (elapsed >= tripMs * totalTrips || !courier.isConnected) {
        return;
      }
      const progress = (elapsed % tripMs) / tripMs;
      // Smooth ease-in-out cubic
      const eased =
        progress < 0.5
          ? 4 * progress * progress * progress
          : 1 - Math.pow(-2 * progress + 2, 3) / 2;
      const cx = p1.cx + dx * eased;
      const cy = p1.cy + dy * eased;
      courier.setAttribute("transform", `translate(${cx.toFixed(2)}, ${cy.toFixed(2)})`);
      const rafId = requestAnimationFrame(step);
      state.pulseRafIds.push(rafId);
    }

    const firstId = requestAnimationFrame(step);
    state.pulseRafIds.push(firstId);
  }

  function animateTransferPulse(donorId, receiverId, meta = {}) {
    if (!state.network) return;
    const hospById = Object.fromEntries(state.network.hospitals.map((h) => [h.id, h]));
    const donor = hospById[donorId];
    const receiver = hospById[receiverId];
    if (!donor || !receiver) return;

    stopActiveCourierAnimations();

    const label =
      meta.units && meta.bloodGroup
        ? `${meta.units}u ${meta.bloodGroup} -> ${receiver.code}`
        : `FEFO -> ${receiver.code}`;

    mountCourierPulse(
      els.svgTransferPulseLayer,
      mapCoord(donor.x, donor.y, false),
      mapCoord(receiver.x, receiver.y, false),
      { label, isZoomed: false }
    );
    if (state.modalOpen && state.modalTab === "topology") {
      mountCourierPulse(
        els.modalSvgTransferPulseLayer,
        mapCoord(donor.x, donor.y, true),
        mapCoord(receiver.x, receiver.y, true),
        { label, isZoomed: true }
      );
    }

    state.pulseTimer = setTimeout(() => {
      stopActiveCourierAnimations();
      if (els.svgTransferPulseLayer) {
        els.svgTransferPulseLayer.innerHTML = "";
      }
      if (els.modalSvgTransferPulseLayer) {
        els.modalSvgTransferPulseLayer.innerHTML = "";
      }
    }, 5900);
  }

  function buildForecastChart(canvasEl, forecastSeries) {
    if (!canvasEl || typeof window.Chart === "undefined") return null;
    const labels = forecastSeries.map((d) => d.label);
    const projectedStock = forecastSeries.map((d) => d.projected_stock);
    const predictedDemand = forecastSeries.map((d) => d.predicted_demand);
    const expiringUnits = forecastSeries.map((d) => d.expiring_units);

    return new window.Chart(canvasEl.getContext("2d"), {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            type: "line",
            label: "Projected Stock",
            data: projectedStock,
            borderColor: PALETTE.ink,
            backgroundColor: "rgba(28, 25, 23, 0.08)",
            borderWidth: 2.5,
            pointRadius: 3,
            pointBackgroundColor: PALETTE.surface,
            pointBorderColor: PALETTE.ink,
            pointBorderWidth: 1.5,
            tension: 0.15,
            fill: true,
            order: 1,
          },
          {
            type: "line",
            label: "Predicted Demand /d",
            data: predictedDemand,
            borderColor: PALETTE.watch,
            borderWidth: 2,
            borderDash: [6, 4],
            pointRadius: 0,
            fill: false,
            order: 2,
          },
          {
            type: "bar",
            label: "Expiring Units",
            data: expiringUnits,
            backgroundColor: PALETTE.criticalTint,
            borderColor: PALETTE.critical,
            borderWidth: 1.5,
            order: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 180 },
        plugins: {
          legend: {
            position: "top",
            labels: {
              boxWidth: 12,
              color: PALETTE.ink,
              font: { family: "JetBrains Mono, monospace", size: 11 },
            },
          },
        },
        scales: {
          x: {
            grid: { color: PALETTE.gridLine },
            ticks: { color: PALETTE.ink, font: { family: "JetBrains Mono, monospace", size: 10.5 } },
          },
          y: {
            beginAtZero: true,
            grid: { color: PALETTE.gridLine },
            ticks: { color: PALETTE.ink, font: { family: "JetBrains Mono, monospace", size: 10.5 } },
          },
        },
      },
    });
  }

  function buildBloodGroupPieChart(canvasEl, rows) {
    if (!canvasEl || typeof window.Chart === "undefined") return null;
    const labels = rows.map((r) => `${r.blood_group} (${r.total_units}u)`);
    const values = rows.map((r) => Math.max(0, r.total_units));
    const total = values.reduce((acc, v) => acc + v, 0);
    const bgColors = rows.map((r) => {
      if (r.status === "Critical") return PALETTE.criticalTint;
      if (r.status === "Watch") return PALETTE.watchTint;
      return PALETTE.safeTint;
    });
    const borderColors = rows.map((r) => {
      if (r.status === "Critical") return PALETTE.critical;
      if (r.status === "Watch") return PALETTE.watch;
      return PALETTE.safe;
    });

    return new window.Chart(canvasEl.getContext("2d"), {
      type: "pie",
      data: {
        labels: total > 0 ? labels : ["Empty Stock"],
        datasets: [
          {
            data: total > 0 ? values : [1],
            backgroundColor: total > 0 ? bgColors : [PALETTE.gridLine],
            borderColor: total > 0 ? borderColors : [PALETTE.ink],
            borderWidth: 1.5,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 180 },
        plugins: {
          legend: {
            position: "right",
            labels: {
              boxWidth: 10,
              padding: 6,
              color: PALETTE.ink,
              font: { family: "JetBrains Mono, monospace", size: 10 },
            },
          },
          tooltip: {
            callbacks: {
              label: (ctx) => (total > 0 ? ` ${ctx.label}` : " 0 units on hand"),
            },
          },
        },
      },
    });
  }

  function buildExpirySemiChart(canvasEl, rows) {
    if (!canvasEl || typeof window.Chart === "undefined") return null;
    let expiring72 = 0;
    let watchUnits = 0;
    let safeUnits = 0;

    rows.forEach((r) => {
      const exp = Math.min(r.total_units, Math.max(0, r.expiring_within_72h));
      const rem = Math.max(0, r.total_units - exp);
      expiring72 += exp;
      if (r.status === "Watch" || r.status === "Critical") {
        watchUnits += rem;
      } else {
        safeUnits += rem;
      }
    });

    const total = expiring72 + watchUnits + safeUnits;

    return new window.Chart(canvasEl.getContext("2d"), {
      type: "doughnut",
      data: {
        labels:
          total > 0
            ? [`Exp ≤72h (${expiring72}u)`, `Watch >72h (${watchUnits}u)`, `Safe >72h (${safeUnits}u)`]
            : ["No Stock"],
        datasets: [
          {
            data: total > 0 ? [expiring72, watchUnits, safeUnits] : [1],
            backgroundColor:
              total > 0
                ? [PALETTE.criticalTint, PALETTE.watchTint, PALETTE.safeTint]
                : [PALETTE.gridLine],
            borderColor:
              total > 0
                ? [PALETTE.critical, PALETTE.watch, PALETTE.safe]
                : [PALETTE.ink],
            borderWidth: 1.5,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        rotation: -90,
        circumference: 180,
        cutout: "62%",
        animation: { duration: 180 },
        plugins: {
          legend: {
            position: "top",
            labels: {
              boxWidth: 9,
              padding: 6,
              color: PALETTE.ink,
              font: { family: "JetBrains Mono, monospace", size: 9.5 },
            },
          },
        },
      },
    });
  }

  function renderSelectedHospitalPanel() {
    const hospital = state.network.hospitals.find((h) => h.id === state.selectedHospitalId);
    if (!hospital) return;

    els.selectedHospitalTitle.textContent = `${hospital.name} (${hospital.code})`;
    els.selectedHospitalMeta.textContent = `${hospital.role} · Total Stock: ${hospital.total_units}u · Min Buffer: ${formatHours(
      hospital.min_zero_stock_hours
    )}`;

    const forecastSeries = hospital.forecasts[state.selectedComponent] || [];
    if (state.chartInstance) {
      state.chartInstance.destroy();
    }
    state.chartInstance = buildForecastChart(els.forecastChart, forecastSeries);

    const rows = hospital.inventory.filter((item) => item.component === state.selectedComponent);
    const compTotal = rows.reduce((sum, item) => sum + item.total_units, 0);
    const compExpiring = rows.reduce((sum, item) => sum + Math.min(item.total_units, item.expiring_within_72h), 0);
    const safePct = compTotal > 0 ? Math.round(((compTotal - compExpiring) / compTotal) * 100) : 0;

    if (els.bloodGroupPieTotal) {
      els.bloodGroupPieTotal.textContent = `${compTotal}u ${state.selectedComponent}`;
    }
    if (els.expiryGaugeBadge) {
      els.expiryGaugeBadge.textContent = `${compExpiring}u ≤72h`;
    }
    if (els.expiryGaugeReadout) {
      els.expiryGaugeReadout.textContent = `${safePct}% >72h`;
    }

    if (state.pieChartInstance) {
      state.pieChartInstance.destroy();
    }
    state.pieChartInstance = buildBloodGroupPieChart(els.hospitalBloodGroupChart, rows);

    if (state.semiChartInstance) {
      state.semiChartInstance.destroy();
    }
    state.semiChartInstance = buildExpirySemiChart(els.hospitalExpirySemiChart, rows);
    els.inventoryMatrixBody.innerHTML = rows
      .map(
        (item) => `
        <tr>
          <td class="mono"><strong>${item.blood_group}</strong></td>
          <td class="mono">${item.total_units}u</td>
          <td class="mono">${item.daily_demand.toFixed(1)}/d</td>
          <td class="mono">${item.expiring_within_72h}u</td>
          <td class="mono">${formatHours(item.zero_stock_hours)}</td>
          <td><span class="status-pill ${statusClass(item.status)}">${item.status}</span></td>
        </tr>
      `
      )
      .join("");
  }

  function buildTimelineEntries(net) {
    const cards = [];
    net.alerts.forEach((alert) => {
      cards.push({
        type: "alert",
        severity: alert.status,
        hour: alert.zero_stock_hours,
        alert,
        rec: alert.recommendation,
      });
    });

    net.timeline_72h
      .filter((ev) => ev.kind === "expiry")
      .slice(0, 8)
      .forEach((ev) => {
        cards.push({
          type: "expiry",
          severity: ev.severity,
          hour: ev.hour_offset,
          event: ev,
        });
      });

    cards.sort((a, b) => a.hour - b.hour);
    return cards;
  }

  function buildTimelineCardElement(entry) {
    const card = document.createElement("div");

    if (entry.type === "alert") {
      const { alert, rec } = entry;
      const sevCls = alert.status === "Critical" ? "sev-critical" : "sev-watch";
      card.className = `timeline-card ${sevCls}`;

      const routeHtml = rec
        ? `<div class="timeline-route mono">
             <strong>FEFO:</strong> ${rec.donor_code} &rarr; ${rec.receiver_code} ·
             ${rec.units}u ${rec.donor_blood_group} (${rec.batch_hours_to_expiry}h exp · ${rec.transit_minutes}m ETA)
           </div>`
        : `<div class="timeline-route mono">No safe donor surplus (&ge;48h) available — mobilize local donors.</div>`;

      card.innerHTML = `
        <div>
          <div class="timeline-top">
            <span class="time-tag mono">T+${formatHours(alert.zero_stock_hours)}</span>
            <span class="status-pill ${statusClass(alert.status)}">${alert.status}</span>
          </div>
          <h3 class="timeline-title">${alert.hospital_code} · ${alert.blood_group} ${alert.component}</h3>
          <p class="timeline-sub">${alert.current_stock}u on hand · ${alert.daily_demand.toFixed(
            1
          )}/d burn · ${alert.expiring_within_72h}u exp &le;72h</p>
        </div>
        ${routeHtml}
        <div class="timeline-actions">
          ${
            rec
              ? `<button type="button" class="btn-tactile btn-sm btn-approve" data-dispatch-rec="${rec.recommendation_id}">
                   Approve FEFO Transfer
                 </button>`
              : ""
          }
          <button type="button" class="btn-tactile btn-sm" data-inspect-alert="${alert.alert_id}">
            Inspect Brief
          </button>
        </div>
      `;
    } else {
      const ev = entry.event;
      const sevCls = ev.severity === "Critical" ? "sev-critical" : "sev-watch";
      card.className = `timeline-card ${sevCls}`;
      card.innerHTML = `
        <div>
          <div class="timeline-top">
            <span class="time-tag mono">EXP T+${ev.hour_offset}h</span>
            <span class="status-pill ${statusClass(ev.severity)}">Expiry</span>
          </div>
          <h3 class="timeline-title">${ev.title}</h3>
          <p class="timeline-sub">${ev.subtitle}</p>
        </div>
        <div class="timeline-route mono">Facility: ${ev.hospital_name}</div>
      `;
    }

    return card;
  }

  function wireTimelineCardActions(container, net) {
    const alertsById = Object.fromEntries(net.alerts.map((a) => [a.alert_id, a]));
    const recsById = Object.fromEntries(net.recommendations.map((r) => [r.recommendation_id, r]));

    container.querySelectorAll("[data-dispatch-rec]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const recId = btn.getAttribute("data-dispatch-rec");
        const rec = recsById[recId];
        if (!rec) return;
        btn.disabled = true;
        btn.textContent = "Dispatching...";
        await executeFefoDispatch(rec);
      });
    });

    container.querySelectorAll("[data-inspect-alert]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const alertId = btn.getAttribute("data-inspect-alert");
        const alert = alertsById[alertId];
        if (alert) {
          loadAlertBriefing(alert, true);
        }
      });
    });
  }

  function renderTimeline72h() {
    const net = state.network;
    els.recSummaryPill.textContent = `${net.recommendations.length} FEFO plans ready`;
    els.timelineStrip.innerHTML = "";

    const cards = buildTimelineEntries(net);
    if (cards.length === 0) {
      els.timelineStrip.innerHTML = `<p class="empty-note">All 6 regional facilities are currently in Safe status (&gt;120h buffer) with no imminent shortages.</p>`;
      return;
    }

    cards.forEach((entry) => {
      els.timelineStrip.appendChild(buildTimelineCardElement(entry));
    });
    wireTimelineCardActions(els.timelineStrip, net);
  }

  /* ---------- Click-to-Zoom Focus Overlay Rendering ---------- */

  function destroyModalChart() {
    if (state.modalChartInstance) {
      state.modalChartInstance.destroy();
      state.modalChartInstance = null;
    }
    if (state.modalPieChartInstance) {
      state.modalPieChartInstance.destroy();
      state.modalPieChartInstance = null;
    }
    if (state.modalSemiChartInstance) {
      state.modalSemiChartInstance.destroy();
      state.modalSemiChartInstance = null;
    }
  }

  function openFocusOverlay(tabName = "topology") {
    state.modalOpen = true;
    state.modalTab = tabName;
    els.focusOverlay.classList.remove("is-hidden");
    document.body.style.overflow = "hidden";
    setModalTab(tabName);
  }

  function closeFocusOverlay() {
    state.modalOpen = false;
    els.focusOverlay.classList.add("is-hidden");
    document.body.style.overflow = "";
    destroyModalChart();
  }

  function setModalTab(tabName) {
    state.modalTab = tabName;
    if (tabName !== "forecast") {
      destroyModalChart();
    }

    document.querySelectorAll(".focus-tab").forEach((btn) => {
      btn.classList.toggle("is-active", btn.getAttribute("data-modal-tab") === tabName);
    });
    els.modalPanelTopology.classList.toggle("is-active", tabName === "topology");
    els.modalPanelForecast.classList.toggle("is-active", tabName === "forecast");
    els.modalPanelTimeline.classList.toggle("is-active", tabName === "timeline");

    renderActiveModalView();
  }

  function renderActiveModalView() {
    if (!state.network || !state.modalOpen) return;

    if (state.modalTab === "topology") {
      renderModalTopology();
    } else if (state.modalTab === "forecast") {
      renderModalForecast();
    } else if (state.modalTab === "timeline") {
      renderModalTimeline();
    }
  }

  function renderModalTopology() {
    renderTopologyInto(els.modalSvgEdgesLayer, els.modalSvgNodesLayer, true);
    const hospital = state.network.hospitals.find((h) => h.id === state.selectedHospitalId);
    if (hospital && els.modalSelectedFacilityNote) {
      els.modalSelectedFacilityNote.textContent = `Selected: ${hospital.name} (${hospital.code}) · ${formatHours(
        hospital.min_zero_stock_hours
      )}`;
    }
  }

  function renderModalForecast() {
    const hospital = state.network.hospitals.find((h) => h.id === state.selectedHospitalId);
    if (!hospital) return;

    els.modalForecastTitle.textContent = `${hospital.name} (${hospital.code})`;
    els.modalForecastMeta.textContent = `${hospital.role} · Total Stock: ${hospital.total_units}u · Min Buffer: ${formatHours(
      hospital.min_zero_stock_hours
    )}`;

    document.querySelectorAll(".modal-comp-tab").forEach((t) => {
      t.classList.toggle("is-active", t.getAttribute("data-modal-component") === state.selectedComponent);
    });

    const forecastSeries = hospital.forecasts[state.selectedComponent] || [];
    destroyModalChart();
    state.modalChartInstance = buildForecastChart(els.modalChartCanvas, forecastSeries);

    const rows = hospital.inventory.filter((item) => item.component === state.selectedComponent);
    const compTotal = rows.reduce((sum, item) => sum + item.total_units, 0);
    const compExpiring = rows.reduce((sum, item) => sum + Math.min(item.total_units, item.expiring_within_72h), 0);
    const safePct = compTotal > 0 ? Math.round(((compTotal - compExpiring) / compTotal) * 100) : 0;

    if (els.modalBloodGroupPieTotal) {
      els.modalBloodGroupPieTotal.textContent = `${compTotal}u ${state.selectedComponent}`;
    }
    if (els.modalExpiryGaugeBadge) {
      els.modalExpiryGaugeBadge.textContent = `${compExpiring}u ≤72h`;
    }
    if (els.modalExpiryGaugeReadout) {
      els.modalExpiryGaugeReadout.textContent = `${safePct}% >72h`;
    }

    state.modalPieChartInstance = buildBloodGroupPieChart(els.modalBloodGroupChart, rows);
    state.modalSemiChartInstance = buildExpirySemiChart(els.modalExpirySemiChart, rows);
    els.modalStockTable.innerHTML = rows
      .map(
        (item) => `
        <tr>
          <td class="mono"><strong>${item.blood_group}</strong></td>
          <td class="mono">${item.total_units}u</td>
          <td class="mono">${item.daily_demand.toFixed(1)}/d</td>
          <td class="mono">${item.scheduled_daily_inflow.toFixed(1)}/d</td>
          <td class="mono">${item.expiring_within_72h}u</td>
          <td class="mono">${formatHours(item.zero_stock_hours)}</td>
          <td><span class="status-pill ${statusClass(item.status)}">${item.status}</span></td>
        </tr>
      `
      )
      .join("");
  }

  function renderModalTimeline() {
    const net = state.network;
    els.modalRecCount.textContent = `${net.recommendations.length} FEFO plans ready`;
    els.modalTimelineRail.innerHTML = "";

    const allCards = buildTimelineEntries(net);
    const filtered =
      state.modalTimelineFilter === "all"
        ? allCards
        : allCards.filter((entry) => entry.severity === state.modalTimelineFilter);

    if (filtered.length === 0) {
      els.modalTimelineRail.innerHTML = `<p class="empty-note">No ${state.modalTimelineFilter} events in the 72-hour window.</p>`;
      return;
    }

    filtered.forEach((entry) => {
      const slot = document.createElement("div");
      slot.className = "rail-slot";

      const axis = document.createElement("div");
      axis.className = "rail-axis-header";

      const node = document.createElement("span");
      const nodeSevClass =
        entry.severity === "Critical"
          ? "node-critical"
          : entry.severity === "Watch"
          ? "node-watch"
          : "";
      node.className = `rail-time-node mono ${nodeSevClass}`;
      node.textContent =
        entry.type === "expiry"
          ? `EXP T+${Number(entry.hour).toFixed(0)}h`
          : `T+${formatHours(entry.hour)}`;

      axis.appendChild(node);
      slot.appendChild(axis);
      slot.appendChild(buildTimelineCardElement(entry));
      els.modalTimelineRail.appendChild(slot);
    });

    wireTimelineCardActions(els.modalTimelineRail, net);
  }

  async function executeFefoDispatch(rec) {
    try {
      const res = await fetch("/api/transfers/dispatch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          donor_hospital_id: rec.donor_hospital_id,
          receiver_hospital_id: rec.receiver_hospital_id,
          batch_id: rec.batch_id,
          units: rec.units,
          scenario: state.scenario,
          donation_drop: state.donationDrop,
          demand_mult: state.demandMult,
          transit_minutes: rec.transit_minutes,
          math_snapshot: rec.math_inputs,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Dispatch failed (${res.status})`);
      }
      const data = await res.json();
      state.network = data.network_state;
      state.selectedHospitalId = rec.receiver_hospital_id;
      renderAll();
      animateTransferPulse(data.donor_hospital_id, data.receiver_hospital_id, {
        units: rec.units,
        bloodGroup: rec.blood_group,
      });

      if (!state.modalOpen && els.svgTransferPulseLayer) {
        const mapPanel = els.svgTransferPulseLayer.closest(".topology-panel");
        if (mapPanel) {
          const rect = mapPanel.getBoundingClientRect();
          if (rect.top < 80 || rect.bottom > window.innerHeight) {
            mapPanel.scrollIntoView({ behavior: "smooth", block: "center" });
          }
        }
      }

      els.transferBanner.textContent = `${data.message} (+${data.units_saved_increment} units saved from expiry)`;
      els.transferBanner.classList.remove("is-hidden");

      await fetchAuditLedger();
    } catch (err) {
      els.transferBanner.textContent = `Transfer error: ${err.message}`;
      els.transferBanner.classList.remove("is-hidden");
    }
  }

  async function loadAlertBriefing(alert, openDrawer = true) {
    state.activeAlert = alert;
    els.drawerContextBadge.textContent = `${alert.hospital_code} · ${alert.blood_group} ${alert.component}`;
    els.briefAlertHeadline.textContent = alert.headline;
    els.rawMathPre.textContent = JSON.stringify(alert.math_inputs, null, 2);

    if (openDrawer) {
      setDrawerOpen(true);
      activateDrawerTab("brief");
    }

    els.briefCause.textContent = "Generating structured clinical briefing...";
    els.briefMathTrigger.textContent = alert.math_inputs.equation;
    els.briefAction.textContent = "Computing FEFO dispatch directive...";
    els.briefSms.textContent = "...";

    try {
      const res = await fetch("/api/briefing", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          alert,
          recommendation: alert.recommendation || null,
        }),
      });
      if (!res.ok) throw new Error("Briefing request failed");
      const brief = await res.json();
      state.activeBriefing = brief;

      els.briefCause.textContent = brief.cause;
      els.briefMathTrigger.textContent = brief.math_trigger;
      els.briefAction.textContent = brief.recommended_action;
      els.briefSms.textContent = brief.donor_sms_draft;
      els.smsCharCount.textContent = `${brief.donor_sms_draft.length}/160`;
      els.briefSourceBadge.textContent =
        brief.source === "gemini" ? "Gemini 3.5 Flash-Lite" : "Deterministic Offline";
    } catch (err) {
      els.briefCause.textContent = `Unable to fetch briefing: ${err.message}`;
    }
  }

  function renderAuditLedger() {
    if (!state.auditData || state.auditData.logs.length === 0) {
      els.auditLedgerList.innerHTML = `<p class="empty-note">No FEFO transfers dispatched yet in this session.</p>`;
      return;
    }
    els.auditLedgerList.innerHTML = state.auditData.logs
      .map((entry) => {
        const ts = new Date(entry.timestamp).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
        return `
          <div class="ledger-item">
            <div class="ledger-item-head">
              <span>#${entry.id} · ${entry.units}u ${entry.blood_group} ${entry.component}</span>
              <span class="mono">${ts}</span>
            </div>
            <div>${entry.donor_hospital_name} &rarr; ${entry.receiver_hospital_name}</div>
            <div class="mono" style="font-size:11px;color:#44403C;margin-top:2px;">
              Batch ${entry.batch_id} · Exp ${entry.hours_to_expiry_at_transfer}h · ETA ${entry.transit_minutes}m · Saved +${entry.units_saved_from_expiry}u
            </div>
          </div>
        `;
      })
      .join("");
  }

  function setDrawerOpen(isOpen) {
    els.auditDrawer.classList.toggle("is-collapsed", !isOpen);
    els.drawerToggleBtn.setAttribute("aria-expanded", String(isOpen));
    els.drawerChevron.textContent = isOpen ? "−" : "+";
  }

  function activateDrawerTab(tabName) {
    document.querySelectorAll(".drawer-tab").forEach((t) => {
      t.classList.toggle("is-active", t.getAttribute("data-tab") === tabName);
    });
    document.getElementById("tabBrief").classList.toggle("is-active", tabName === "brief");
    document.getElementById("tabMath").classList.toggle("is-active", tabName === "math");
    document.getElementById("tabLedger").classList.toggle("is-active", tabName === "ledger");
    if (tabName === "ledger") {
      fetchAuditLedger();
    }
  }

  function selectComponent(comp) {
    if (!comp) return;
    state.selectedComponent = comp;
    document.querySelectorAll(".comp-tab").forEach((t) => {
      t.classList.toggle("is-active", t.getAttribute("data-component") === comp);
    });
    renderSelectedHospitalPanel();
    if (state.modalOpen && state.modalTab === "forecast") {
      renderModalForecast();
    }
  }

  function bindEvents() {
    // Shrinking Hero Status Bar on scroll past 80px
    window.addEventListener(
      "scroll",
      () => {
        els.heroBar.classList.toggle("is-compact", window.scrollY > 80);
      },
      { passive: true }
    );

    // Scenario Switcher
    document.querySelectorAll(".scenario-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const scenario = btn.getAttribute("data-scenario");
        if (!scenario || scenario === state.scenario) return;
        state.scenario = scenario;
        state.activeAlert = null;
        document.querySelectorAll(".scenario-btn").forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        await fetchNetworkState();
      });
    });

    // Reset Demo button
    els.resetDemoBtn.addEventListener("click", async () => {
      els.resetDemoBtn.disabled = true;
      try {
        state.scenario = "baseline";
        state.donationDrop = 0;
        state.demandMult = 1.0;
        state.activeAlert = null;
        els.donationDropSlider.value = "0";
        els.donationDropValue.textContent = "0%";
        els.demandMultSlider.value = "1.0";
        els.demandMultValue.textContent = "1.0x";
        document.querySelectorAll(".scenario-btn").forEach((b) => {
          b.classList.toggle("is-active", b.getAttribute("data-scenario") === "baseline");
        });

        const res = await fetch("/api/reset?scenario=baseline&donation_drop=0&demand_mult=1.0", {
          method: "POST",
        });
        if (res.ok) {
          state.network = await res.json();
          state.selectedHospitalId = state.network.most_urgent_hospital_id;
          els.transferBanner.classList.add("is-hidden");
          renderAll();
          await fetchAuditLedger();
          if (state.network.alerts.length > 0) {
            loadAlertBriefing(state.network.alerts[0], false);
          }
        }
      } finally {
        els.resetDemoBtn.disabled = false;
      }
    });

    // Stress-Test Bar Collapse Toggle
    els.toggleStressBtn.addEventListener("click", () => {
      const hidden = els.stressBody.classList.toggle("is-hidden");
      els.toggleStressBtn.setAttribute("aria-expanded", String(!hidden));
      els.toggleStressBtn.textContent = hidden
        ? "Show Stress-Test Sliders"
        : "Hide Stress-Test Sliders";
    });

    // Live Sliders (debounced 140ms)
    const scheduleSliderSync = () => {
      clearTimeout(state.sliderTimer);
      state.sliderTimer = setTimeout(() => {
        state.activeAlert = null;
        fetchNetworkState();
      }, 140);
    };

    els.donationDropSlider.addEventListener("input", (e) => {
      state.donationDrop = Number(e.target.value);
      els.donationDropValue.textContent = `${state.donationDrop}%`;
      scheduleSliderSync();
    });

    els.demandMultSlider.addEventListener("input", (e) => {
      state.demandMult = Number(e.target.value);
      els.demandMultValue.textContent = `${state.demandMult.toFixed(1)}x`;
      scheduleSliderSync();
    });

    els.resetSlidersBtn.addEventListener("click", () => {
      state.donationDrop = 0;
      state.demandMult = 1.0;
      els.donationDropSlider.value = "0";
      els.donationDropValue.textContent = "0%";
      els.demandMultSlider.value = "1.0";
      els.demandMultValue.textContent = "1.0x";
      state.activeAlert = null;
      fetchNetworkState();
    });

    // Component Tabs (Main + Modal)
    document.querySelectorAll(".comp-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        selectComponent(tab.getAttribute("data-component"));
      });
    });

    document.querySelectorAll(".modal-comp-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        selectComponent(tab.getAttribute("data-modal-component"));
      });
    });

    // Expand Buttons & Non-Interactive Header Zoom Triggers
    document.querySelectorAll("[data-zoom-tab]").forEach((btn) => {
      btn.addEventListener("click", (evt) => {
        evt.stopPropagation();
        openFocusOverlay(btn.getAttribute("data-zoom-tab"));
      });
    });

    document.querySelectorAll("[data-zoom-header]").forEach((hdr) => {
      hdr.addEventListener("click", (evt) => {
        if (evt.target.closest("button, a, input, select, .svg-node, table")) {
          return;
        }
        openFocusOverlay(hdr.getAttribute("data-zoom-header"));
      });
    });

    // Focus Overlay Controls
    els.closeFocusOverlay.addEventListener("click", closeFocusOverlay);
    els.focusOverlay.addEventListener("click", (evt) => {
      if (evt.target === els.focusOverlay) {
        closeFocusOverlay();
      }
    });

    document.addEventListener("keydown", (evt) => {
      if (evt.key === "Escape" && state.modalOpen) {
        closeFocusOverlay();
      }
    });

    document.querySelectorAll(".focus-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        setModalTab(btn.getAttribute("data-modal-tab"));
      });
    });

    els.modalJumpToForecastBtn.addEventListener("click", () => {
      setModalTab("forecast");
    });

    // Modal Horizontal Timeline Filters, Step Arrows & Wheel-to-Horizontal Scroll
    document.querySelectorAll(".timeline-filter-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.modalTimelineFilter = btn.getAttribute("data-timeline-filter") || "all";
        document.querySelectorAll(".timeline-filter-btn").forEach((b) => {
          b.classList.toggle("is-active", b === btn);
        });
        renderModalTimeline();
      });
    });

    els.modalTimelinePrev.addEventListener("click", () => {
      els.modalTimelineRail.scrollBy({ left: -344, behavior: "smooth" });
    });

    els.modalTimelineNext.addEventListener("click", () => {
      els.modalTimelineRail.scrollBy({ left: 344, behavior: "smooth" });
    });

    els.modalTimelineRail.addEventListener(
      "wheel",
      (evt) => {
        if (Math.abs(evt.deltaY) > Math.abs(evt.deltaX)) {
          evt.preventDefault();
          els.modalTimelineRail.scrollLeft += evt.deltaY;
        }
      },
      { passive: false }
    );

    // Audit & Ask Drawer Toggle + Tabs
    els.drawerToggleBtn.addEventListener("click", () => {
      const currentlyCollapsed = els.auditDrawer.classList.contains("is-collapsed");
      setDrawerOpen(currentlyCollapsed);
    });

    document.querySelectorAll(".drawer-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        activateDrawerTab(tab.getAttribute("data-tab"));
      });
    });

    // Copy SMS Button
    els.copySmsBtn.addEventListener("click", async () => {
      const text = els.briefSms.textContent || "";
      if (!text || text === "--") return;
      try {
        await navigator.clipboard.writeText(text);
        els.copySmsBtn.textContent = "Copied!";
        setTimeout(() => {
          els.copySmsBtn.textContent = "Copy SMS";
        }, 1400);
      } catch {
        els.copySmsBtn.textContent = "Select & Copy";
      }
    });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    bindEvents();
    await Promise.all([fetchNetworkState(), fetchAuditLedger()]);
  });
})();
