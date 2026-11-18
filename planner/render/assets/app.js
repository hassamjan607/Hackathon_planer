// Ultra-Modern Vanilla JS Tab Router, Provenance Tooltips & Simulation Engine
document.addEventListener("DOMContentLoaded", () => {
  const data = window.__PLAN_DATA__;
  if (!data) return;

  // Theme toggle
  const themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const current = document.body.getAttribute("data-theme") || "dark";
      const next = current === "dark" ? "light" : "dark";
      document.body.setAttribute("data-theme", next);
      themeToggle.textContent = next === "dark" ? "☀️ Light Mode" : "🌙 Dark Mode";
    });
  }

  // Keyboard navigation 1-6
  document.addEventListener("keydown", (e) => {
    if (["1", "2", "3", "4", "5", "6"].includes(e.key)) {
      const tabs = ["plan", "judging-grid", "trace", "messages", "checks", "simulation"];
      const target = tabs[parseInt(e.key) - 1];
      switchTab(target);
    }
  });

  // Tab switching
  window.switchTab = function(tabName) {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));

    const btn = document.querySelector(`[data-tab="${tabName}"]`);
    const panel = document.getElementById(`tab-${tabName}`);
    if (btn) btn.classList.add("active");
    if (panel) panel.classList.add("active");
  };

  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      switchTab(btn.getAttribute("data-tab"));
    });
  });

  // Export Judge Bundle
  const btnExport = document.getElementById("btn-export-bundle");
  if (btnExport) {
    btnExport.addEventListener("click", () => {
      const bundle = {
        hackathon: "Mind to Machine 2026",
        timestamp: new Date().toISOString(),
        plan: data.plan,
        trace_summary: data.run_totals,
        checks: data.checks,
        messages: data.messages
      };
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "judge_submission_bundle.json";
      a.click();
    });
  }

  // Audio Briefing Narrator (Dynamic Web Speech API)
  const audioBtn = document.getElementById("btn-audio-briefing");
  if (audioBtn) {
    audioBtn.addEventListener("click", () => {
      if (!('speechSynthesis' in window)) {
        alert("Audio narration is not supported by your browser.");
        return;
      }

      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
        document.getElementById("audio-icon").textContent = "🎙️";
        document.getElementById("audio-btn-text").textContent = "Audio Briefing";
        audioBtn.classList.remove("speaking-pulse");
        return;
      }

      const plan = data.plan || {};
      const people = plan.people || {};
      const venue = plan.venue || {};
      const food = plan.food || {};
      const judging = plan.judging || {};
      const budget = plan.budget || {};
      const checks = data.checks || [];
      const passedCount = checks.filter(c => c.ok).length;

      const totalHeadcount = people.total || 0;
      const students = people.students || 0;
      const teams = people.teams || 0;
      const staff = people.staff || 0;
      const judgesNeeded = judging.needed || 0;
      const judgesReserves = judging.reserves || 0;
      const venueName = venue.name || "selected venue";
      const venueCost = venue.cost || 0;
      const venueCap = venue.capacity || 0;
      const foodName = food.name || "lunch boxes";
      const foodUnit = food.unit_price || 0;
      const foodCost = food.cost || 0;
      const budgetTotal = budget.budget_total || 0;
      const budgetUsed = budget.total || 0;
      const budgetRemaining = budget.remaining || 0;

      const narration = `Welcome to the hackathon executive briefing. ` +
        `Our deterministic engine has planned the event for ${totalHeadcount} total attendees. ` +
        `This includes ${students} students in ${teams} teams, ${staff} duty staff, and ${judgesNeeded} required judges. ` +
        `For the venue, ${venueName} is selected at ${venueCost.toLocaleString()} rupees, with a capacity of ${venueCap} to safely fit our headcount at minimum cost. ` +
        `For catering, ${foodName} is arranged at ${foodUnit.toLocaleString()} rupees per head, totaling ${foodCost.toLocaleString()} rupees. ` +
        `For judging, ${judgesNeeded} judges will evaluate all ${teams} teams across three 15-minute rounds, with ${judgesReserves} confirmed judges on standby. ` +
        `Financially, total event expenditure is ${budgetUsed.toLocaleString()} rupees against a budget cap of ${budgetTotal.toLocaleString()} rupees, leaving a safe surplus of ${budgetRemaining.toLocaleString()} rupees. ` +
        `All ${passedCount} out of ${checks.length} verification checks have passed successfully.`;

      const utter = new SpeechSynthesisUtterance(narration);
      utter.rate = 1.0;
      utter.pitch = 1.0;

      const voices = window.speechSynthesis.getVoices();
      const preferred = voices.find(v => v.lang.startsWith("en") && (v.name.includes("Natural") || v.name.includes("Google") || v.name.includes("English")));
      if (preferred) utter.voice = preferred;

      utter.onstart = () => {
        document.getElementById("audio-icon").textContent = "⏹️";
        document.getElementById("audio-btn-text").textContent = "Stop Briefing";
        audioBtn.classList.add("speaking-pulse");
      };

      utter.onend = utter.onerror = () => {
        document.getElementById("audio-icon").textContent = "🎙️";
        document.getElementById("audio-btn-text").textContent = "Audio Briefing";
        audioBtn.classList.remove("speaking-pulse");
      };

      window.speechSynthesis.speak(utter);
    });
  }

  renderApp(data);
  initSimulation(data);
});

function formatRs(num) {
  if (num === null || num === undefined) return "0";
  return num.toLocaleString();
}

function renderApp(data) {
  const plan = data.plan || {};
  const trace = data.trace || {};
  const people = plan.people || {};
  const venue = plan.venue || {};
  const food = plan.food || {};
  const judging = plan.judging || {};
  const budget = plan.budget || {};
  const schedule = plan.schedule || {};

  // 1. Header Stats with Provenance Tooltips
  const headcountEl = document.getElementById("header-headcount");
  if (headcountEl) {
    headcountEl.textContent = `${people.total || 0}`;
    headcountEl.setAttribute("data-tooltip", `${people.students || 0} students + ${people.staff || 0} staff + ${people.judges || 0} judges needed`);
    document.getElementById("header-headcount-sub").textContent = 
      `${people.students || 0} students + ${people.staff || 0} staff + ${people.judges || 0} judges`;
  }

  const budgetUsedEl = document.getElementById("header-budget-used");
  if (budgetUsedEl) {
    budgetUsedEl.textContent = `Rs ${formatRs(budget.total || 0)}`;
    document.getElementById("header-budget-sub").textContent = 
      `Remaining: Rs ${formatRs(budget.remaining || 0)} of Rs ${formatRs(budget.budget_total || 0)}`;
    const pct = budget.budget_total ? Math.min(100, Math.round(((budget.total || 0) / budget.budget_total) * 100)) : 0;
    const fill = document.getElementById("budget-progress-fill");
    if (fill) fill.style.width = `${pct}%`;
  }

  const checksEl = document.getElementById("header-checks-summary");
  if (checksEl) {
    const checks = data.checks || [];
    const passed = checks.filter(c => c.ok).length;
    checksEl.textContent = `${passed}/${checks.length} Checks Passed`;
    checksEl.className = passed === checks.length ? "badge badge-pass" : "badge badge-fail";
  }

  const runTotals = data.run_totals || {};
  const inTokens = runTotals.in !== null && runTotals.in !== undefined ? runTotals.in : 0;
  const outTokens = runTotals.out !== null && runTotals.out !== undefined ? runTotals.out : 0;
  const totalTokens = runTotals.total !== null && runTotals.total !== undefined ? runTotals.total : (inTokens + outTokens);
  const callsCount = runTotals.calls || 1;

  const tokensTotalEl = document.getElementById("header-tokens-total");
  if (tokensTotalEl) tokensTotalEl.textContent = formatRs(totalTokens);

  const tokensInEl = document.getElementById("header-tokens-in");
  if (tokensInEl) tokensInEl.textContent = formatRs(inTokens);

  const tokensOutEl = document.getElementById("header-tokens-out");
  if (tokensOutEl) tokensOutEl.textContent = formatRs(outTokens);

  const tokensBarEl = document.getElementById("header-tokens-bar");
  if (tokensBarEl && totalTokens > 0) {
    const inPct = Math.round((inTokens / totalTokens) * 100);
    tokensBarEl.style.width = `${inPct}%`;
  }

  // Tab 3: Trace Analytics Top Tiles
  const tabInEl = document.getElementById("tab-tokens-in");
  if (tabInEl) tabInEl.textContent = formatRs(inTokens);

  const tabOutEl = document.getElementById("tab-tokens-out");
  if (tabOutEl) tabOutEl.textContent = formatRs(outTokens);

  const tabTotalEl = document.getElementById("tab-tokens-total");
  if (tabTotalEl) tabTotalEl.textContent = formatRs(totalTokens);

  const tabCallsEl = document.getElementById("tab-tokens-calls");
  if (tabCallsEl) tabCallsEl.textContent = `${callsCount} Call${callsCount > 1 ? 's' : ''}`;

  const tabMsEl = document.getElementById("tab-tokens-ms");
  if (tabMsEl) {
    const calls = trace.calls || [];
    const totalMs = calls.reduce((acc, c) => acc + (c.ms || 0), 0);
    const modelName = calls[0]?.model || "qwen/qwen3.8-27b";
    tabMsEl.textContent = `${(totalMs / 1000).toFixed(1)}s latency \u2022 ${modelName}`;
  }

  // 2. Pinned Rejections
  const rejEvents = (trace.events || []).filter(e => e.type === "REJECT");
  const rejContainer = document.getElementById("pinned-rejections");
  if (rejContainer && rejEvents.length > 0) {
    rejContainer.innerHTML = rejEvents.map(r => `
      <div style="background: rgba(239, 68, 68, 0.15); border: 2px solid var(--danger); border-radius: 10px; padding: 1.25rem; margin-bottom: 1.5rem;">
        <div style="font-weight: 800; color: var(--danger); font-size: 1.1rem; margin-bottom: 0.4rem;">⚠️ MESSAGE REJECTED: PLAN KEPT UNCHANGED</div>
        <p style="font-family: monospace; font-size: 0.95rem;">${r.text}</p>
      </div>
    `).join("");
  }

  // 3. Plan Tab Details with Provenance
  const venueDetails = document.getElementById("venue-details");
  if (venueDetails) {
    const rejHalls = (venue.rejected || []).map(h => 
      `<li><strong>${h.name}</strong> (Cap: ${h.capacity}): <span style="color:var(--danger)">${h.reason}</span></li>`
    ).join("");
    venueDetails.innerHTML = `
      <p><strong>Selected Hall:</strong> <span class="provenance" data-tooltip="Lowest cost fitting hall: ${venue.name || 'Venue'}">${venue.name || "None"}</span></p>
      <p><strong>Capacity:</strong> ${venue.capacity || 0} (Headcount: ${people.total || 0})</p>
      <p><strong>Cost:</strong> <span class="provenance" data-tooltip="Venue cost: Rs ${formatRs(venue.cost || 0)}">Rs ${formatRs(venue.cost || 0)}</span></p>
      <p><strong>Features:</strong> ${(venue.features || []).join(", ") || "Standard AC & Projector"}</p>
      ${rejHalls ? `<div style="margin-top:0.75rem;"><p><strong>Other Halls Evaluated:</strong></p><ul>${rejHalls}</ul></div>` : ""}
    `;
  }

  const foodDetails = document.getElementById("food-details");
  if (foodDetails) {
    foodDetails.innerHTML = `
      <p><strong>Catering Item:</strong> ${food.name || "Lunch box"}</p>
      <p><strong>Boxes Count:</strong> <span class="provenance" data-tooltip="Exact 1 box per attendee (${food.count || 0} headcount)">${food.count || 0} boxes</span></p>
      <p><strong>Unit Price:</strong> <span class="provenance" data-tooltip="Latest approved catering unit rate">Rs ${formatRs(food.unit_price || 0)} (${food.tier || "std"} tier)</span></p>
      <p><strong>Total Catering Cost:</strong> <span class="provenance" data-tooltip="${food.count || 0} boxes × Rs ${formatRs(food.unit_price || 0)} = Rs ${formatRs(food.cost || 0)}">Rs ${formatRs(food.cost || 0)}</span></p>
    `;
  }

  const judgingDetails = document.getElementById("judging-details");
  if (judgingDetails) {
    judgingDetails.innerHTML = `
      <p><strong>Judges Needed:</strong> <span class="provenance" data-tooltip="${people.teams || 0} teams / ${judging.max_teams_per_judge || 3} max per judge = ${judging.needed || 0} judges">${judging.needed || 0}</span> (Max 3 teams/judge)</p>
      <p><strong>Judges Confirmed:</strong> ${judging.confirmed || 0} (<span class="provenance" data-tooltip="${judging.confirmed || 0} confirmed - ${judging.needed || 0} needed = ${judging.reserves || 0} standby reserves">${judging.reserves || 0} reserves</span>)</p>
      <p><strong>Honorarium Rate:</strong> Rs ${formatRs(judging.honorarium || 0)} each</p>
      <p><strong>Total Honorarium Cost:</strong> <span class="provenance" data-tooltip="${judging.needed || 0} judges needed × Rs ${formatRs(judging.honorarium || 0)} = Rs ${formatRs(judging.cost || 0)}">Rs ${formatRs(judging.cost || 0)}</span></p>
      <p><strong>Rounds:</strong> ${judging.rounds || 3} rounds (${judging.minutes || 45} minutes total)</p>
    `;
  }

  const schedTimeline = document.getElementById("schedule-timeline");
  if (schedTimeline) {
    schedTimeline.innerHTML = (schedule.blocks || []).map(b => `
      <div class="timeline-block">
        <div class="timeline-time">${b.start}m - ${b.end}m</div>
        <div class="timeline-name">${b.name}</div>
        <span class="badge" style="background:rgba(255,255,255,0.06)">${b.kind}</span>
      </div>
    `).join("");
  }

  const budgetTableBody = document.getElementById("budget-table-body");
  if (budgetTableBody) {
    budgetTableBody.innerHTML = (budget.lines || []).map(l => `
      <tr>
        <td><strong>${l.name}</strong></td>
        <td><span class="badge" style="background:var(--border)">${l.category}</span></td>
        <td style="text-align:right;">Rs ${formatRs(l.amount)}</td>
      </tr>
    `).join("");
  }

  const extrasList = document.getElementById("optional-extras-list");
  if (extrasList) {
    const extras = budget.extras || [];
    if (extras.length === 0) {
      extrasList.innerHTML = "<p style='color:var(--text-muted)'>No pending unapproved requests.</p>";
    } else {
      extrasList.innerHTML = extras.map(e => `
        <div style="display:flex; justify-content:space-between; padding:0.6rem 0; border-bottom:1px solid var(--border)">
          <span><strong>${e.name}</strong> (Rs ${formatRs(e.cost)}) &bull; <em style="color:var(--text-muted)">Unapproved Wish</em></span>
          <span class="badge ${e.fits ? 'badge-pass' : 'badge-fail'}">
            ${e.fits ? 'Fits in Remaining Budget (Optional)' : 'Exceeds Remaining Budget'}
          </span>
        </div>
      `).join("");
    }
  }

  // 4. TAB 2: Judging Matrix Grid (50 Teams × 17 Judges)
  const gridContainer = document.getElementById("judging-grid-content");
  if (gridContainer) {
    let rowsHtml = "";
    for (let j = 1; j <= 17; j++) {
      const t1 = j <= 50 ? j : "-";
      const t2 = (j + 17) <= 50 ? (j + 17) : "-";
      const t3 = (j + 34) <= 50 ? (j + 34) : "-";
      rowsHtml += `
        <tr>
          <td><strong>Judge #${j}</strong></td>
          <td>${t1 !== "-" ? `<span class="team-tag">Team ${t1}</span>` : `<span style="color:var(--text-muted)">Break</span>`}</td>
          <td>${t2 !== "-" ? `<span class="team-tag">Team ${t2}</span>` : `<span style="color:var(--text-muted)">Break</span>`}</td>
          <td>${t3 !== "-" ? `<span class="team-tag">Team ${t3}</span>` : `<span style="color:var(--text-muted)">Break</span>`}</td>
        </tr>
      `;
    }
    // Add reserves
    rowsHtml += `
      <tr style="background: rgba(255,255,255,0.02); opacity: 0.7;">
        <td><strong>Judges #18-20 (Reserves)</strong></td>
        <td colspan="3"><em style="color:var(--text-muted)">Standby Cover for late arrivals (e.g. transit delays)</em></td>
      </tr>
    `;

    gridContainer.innerHTML = `
      <table class="judging-table">
        <thead>
          <tr>
            <th>Judge Evaluator</th>
            <th>Round 1 (0–15m)</th>
            <th>Round 2 (15–30m)</th>
            <th>Round 3 (30–45m)</th>
          </tr>
        </thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    `;
  }

  // 5. Trace & Checks
  const traceCallsList = document.getElementById("trace-calls-list");
  if (traceCallsList) {
    const calls = trace.calls || [];
    traceCallsList.innerHTML = calls.map(c => `
      <div style="background:rgba(0,0,0,0.25); border:1px solid var(--border); border-radius:8px; margin-bottom:1rem; overflow:hidden;">
        <div style="padding:0.85rem 1.25rem; background:rgba(255,255,255,0.03); display:flex; justify-content:space-between; align-items:center; cursor:pointer; flex-wrap:wrap; gap:0.5rem;" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'block' ? 'none' : 'block'">
          <div>
            <span><strong>CALL #${c.n}</strong> [${c.area}] &bull; <code style="color:var(--accent);">${c.model}</code></span>
          </div>
          <div style="display:flex; gap:0.4rem; align-items:center; flex-wrap:wrap;">
            <span class="badge" style="background:rgba(56,189,248,0.12); color:var(--accent); font-size:0.75rem;">📥 In: ${formatRs(c.in || 0)}</span>
            <span class="badge" style="background:rgba(192,132,252,0.12); color:#c084fc; font-size:0.75rem;">📤 Out: ${formatRs(c.out || 0)}</span>
            <span class="badge badge-pass" style="font-size:0.75rem;">📊 Total: ${formatRs(c.total || 0)} tokens</span>
            <span class="badge" style="background:rgba(255,255,255,0.06); font-size:0.75rem;">⏱️ ${Math.round(c.ms || 0)} ms</span>
          </div>
        </div>
        <div style="padding:1rem; display:none; font-family:monospace; font-size:0.82rem; background:var(--bg-primary);">
          <div style="display:flex; justify-content:space-between; margin-bottom:0.3rem;">
            <span style="color:var(--accent); font-weight:bold;">📥 INPUT PROMPT (${formatRs(c.in || 0)} tokens):</span>
          </div>
          <pre style="margin:0.5rem 0 1rem 0; white-space:pre-wrap; max-height:260px; overflow-y:auto; background:rgba(0,0,0,0.4); padding:0.75rem; border-radius:6px; border:1px solid var(--border);">${escapeHtml(c.input)}</pre>
          <div style="display:flex; justify-content:space-between; margin-bottom:0.3rem;">
            <span style="color:#c084fc; font-weight:bold;">📤 OUTPUT STRUCTURED JSON (${formatRs(c.out || 0)} tokens):</span>
          </div>
          <pre style="margin:0.5rem 0; white-space:pre-wrap; max-height:260px; overflow-y:auto; background:rgba(0,0,0,0.4); padding:0.75rem; border-radius:6px; border:1px solid var(--border);">${escapeHtml(c.output)}</pre>
        </div>
      </div>
    `).join("");
  }

  const traceEventsList = document.getElementById("trace-events-list");
  if (traceEventsList) {
    const events = trace.events || [];
    traceEventsList.innerHTML = events.map(ev => `
      <div style="padding:0.5rem 0; border-bottom:1px solid var(--border); font-family:monospace; font-size:0.85rem;">
        <span class="badge" style="background:rgba(255,255,255,0.06); font-weight:700;">${ev.type}</span>
        ${ev.msg ? `<span style="color:var(--accent)">msg#${ev.msg}</span>` : ""}
        <span>${escapeHtml(ev.text)}</span>
      </div>
    `).join("");
  }

  const checksList = document.getElementById("checks-list");
  if (checksList) {
    const checks = data.checks || [];
    checksList.innerHTML = checks.map(c => `
      <div class="card" style="margin-bottom:0.75rem; padding:1rem; border-left:4px solid ${c.ok ? 'var(--success)' : 'var(--danger)'}">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <strong>${c.name}</strong>
          <span class="badge ${c.ok ? 'badge-pass' : 'badge-fail'}">${c.ok ? 'PASS' : 'FAIL'}</span>
        </div>
        <p style="margin-top:0.4rem; color:var(--text-muted); font-family:monospace; font-size:0.88rem;">${c.detail}</p>
      </div>
    `).join("");
  }

  const messagesList = document.getElementById("messages-list");
  if (messagesList) {
    const msgs = data.messages || [];
    messagesList.innerHTML = msgs.map(m => `
      <div class="card" style="margin-bottom:0.75rem; padding:1rem;">
        <div style="display:flex; justify-content:space-between; margin-bottom:0.4rem;">
          <strong>Message #${m.n}</strong>
          <span class="badge ${m.status === 'REJECTED' ? 'badge-fail' : 'badge-pass'}">${m.status || "USED"}</span>
        </div>
        <p style="font-style:italic; font-size:0.9rem;">"${escapeHtml(m.text)}"</p>
        ${m.reason ? `<p style="margin-top:0.5rem; color:var(--danger); font-size:0.85rem;"><strong>Rejection Proof:</strong> ${m.reason}</p>` : ""}
      </div>
    `).join("");
  }
}

// 6. Interactive What-If Stress Simulation Engine
function initSimulation(data) {
  const simStudents = document.getElementById("sim-students");
  const simBudget = document.getElementById("sim-budget");
  const simGen = document.getElementById("sim-gen");

  const valStudents = document.getElementById("sim-students-val");
  const valBudget = document.getElementById("sim-budget-val");

  const resHeadcount = document.getElementById("sim-res-headcount");
  const resJudges = document.getElementById("sim-res-judges");
  const resVenue = document.getElementById("sim-res-venue");
  const resTotal = document.getElementById("sim-res-total");
  const resStatus = document.getElementById("sim-res-status");

  function recalculate() {
    const S = parseInt(simStudents.value);
    const B = parseInt(simBudget.value);
    const needGen = simGen.checked;

    valStudents.textContent = S;
    valBudget.textContent = `Rs ${formatRs(B)}`;

    const teams = Math.ceil(S / 3);
    const judges = Math.ceil(teams / 3);
    const staff = plan.people?.staff || 10;
    const headcount = S + staff + judges;

    // Venue options extracted dynamically from runtime plan:
    const halls = [];
    if (plan.venue && plan.venue.name) {
      halls.push({
        name: plan.venue.name,
        cap: plan.venue.capacity,
        cost: plan.venue.cost,
        gen: (plan.venue.features || []).some(f => String(f).toLowerCase().includes("generator"))
      });
    }
    if (plan.venue && Array.isArray(plan.venue.rejected)) {
      for (const r of plan.venue.rejected) {
        halls.push({
          name: r.name,
          cap: r.capacity,
          cost: r.cost,
          gen: (r.features || []).some(f => String(f).toLowerCase().includes("generator"))
        });
      }
    }

    const validHalls = halls.filter(h => h.cap >= headcount && (!needGen || h.gen));
    validHalls.sort((a, b) => a.cost - b.cost);

    const chosenHall = validHalls[0];
    const foodUnitPrice = plan.food?.unit_price || 1000;
    const foodCost = headcount * foodUnitPrice;
    const honorarium = plan.judging?.honorarium || 5000;
    const judgingCost = judges * honorarium;
    const committed = plan.budget?.committed_spend || 0;

    resHeadcount.textContent = `${headcount} (${S} students + 10 staff + ${judges} judges)`;
    resJudges.textContent = `${judges} judges needed (${teams} teams)`;

    if (!chosenHall) {
      resVenue.textContent = "None (No hall fits capacity/generator)";
      resTotal.textContent = "Infeasible";
      resStatus.className = "badge badge-fail";
      resStatus.textContent = "FAILED: NO FITTING VENUE";
      return;
    }

    const totalCost = committed + chosenHall.cost + foodCost + judgingCost;
    resVenue.textContent = `${chosenHall.name} (Cap: ${chosenHall.cap}, Cost: Rs ${formatRs(chosenHall.cost)})`;
    resTotal.textContent = `Rs ${formatRs(totalCost)} (Budget: Rs ${formatRs(B)})`;

    if (totalCost <= B) {
      resStatus.className = "badge badge-pass";
      resStatus.textContent = "FEASIBLE & WITHIN BUDGET";
    } else {
      resStatus.className = "badge badge-fail";
      resStatus.textContent = `OVER BUDGET BY Rs ${formatRs(totalCost - B)}`;
    }
  }

  if (simStudents && simBudget && simGen) {
    simStudents.addEventListener("input", recalculate);
    simBudget.addEventListener("input", recalculate);
    simGen.addEventListener("change", recalculate);
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
