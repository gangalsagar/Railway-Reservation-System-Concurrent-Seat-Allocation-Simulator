// Railway Reservation System - Frontend Client Scripts

/**
 * Display a non-blocking toast notification
 */
function showToast(message, type = "info", duration = 3500) {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

/**
 * Generate or retrieve an idempotency key for booking attempts
 */
function getOrCreateIdempotencyKey(reset = false) {
  const STORAGE_KEY = "railway_current_idempotency_key";
  if (!reset) {
    const existing = sessionStorage.getItem(STORAGE_KEY);
    if (existing) return existing;
  }
  const newKey = "IDEMP-" + (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15) + Date.now());
  sessionStorage.setItem(STORAGE_KEY, newKey);
  return newKey;
}

// -------------------------------------------------------------
// Home Page: Journey Search
// -------------------------------------------------------------
async function searchJourneys(event) {
  if (event) event.preventDefault();

  const source = document.getElementById("search-source")?.value.trim() || "";
  const destination = document.getElementById("search-destination")?.value.trim() || "";
  const date = document.getElementById("search-date")?.value || "";

  const resultsContainer = document.getElementById("journey-results");
  if (!resultsContainer) return;

  resultsContainer.innerHTML = '<div style="text-align:center; padding:30px;"><p>Searching journeys...</p></div>';

  try {
    const params = new URLSearchParams();
    if (source) params.append("source", source);
    if (destination) params.append("destination", destination);
    if (date) params.append("date", date);

    const response = await fetch(`/api/journeys?${params.toString()}`);
    const data = await response.json();

    if (!data.success || !data.journeys || data.journeys.length === 0) {
      resultsContainer.innerHTML = `
        <div class="card" style="text-align:center; padding: 40px;">
          <p style="color: var(--text-muted); font-size: 16px;">No train journeys found matching your criteria.</p>
          <button class="btn btn-outline" style="margin-top: 12px;" onclick="resetSearch()">Show All Journeys</button>
        </div>
      `;
      return;
    }

    resultsContainer.innerHTML = data.journeys.map(j => `
      <div class="journey-card">
        <div class="journey-info">
          <h3>Train ${j.train_number}</h3>
          <div class="journey-meta">
            <span><strong>From:</strong> ${j.source}</span>
            <span><strong>To:</strong> ${j.destination}</span>
            <span><strong>Date:</strong> ${j.journey_date}</span>
          </div>
        </div>
        <div>
          <a href="/seats/${j.journey_id}" class="btn btn-primary">
            Select Seats &rarr;
          </a>
        </div>
      </div>
    `).join("");

  } catch (err) {
    resultsContainer.innerHTML = `
      <div class="card" style="text-align:center; color: var(--danger);">
        <p>Failed to load journeys. Please ensure the server is running.</p>
      </div>
    `;
    showToast("Network error while searching journeys", "error");
  }
}

function resetSearch() {
  if (document.getElementById("search-source")) document.getElementById("search-source").value = "";
  if (document.getElementById("search-destination")) document.getElementById("search-destination").value = "";
  if (document.getElementById("search-date")) document.getElementById("search-date").value = "";
  searchJourneys();
}

// -------------------------------------------------------------
// Seats Page: Seat Layout & Interactive Selection
// -------------------------------------------------------------
let allSeatsCache = [];
let selectedSeat = null;

async function loadSeatsForJourney(journeyId) {
  const grid = document.getElementById("seats-grid");
  const metaContainer = document.getElementById("journey-meta-bar");
  if (!grid) return;

  grid.innerHTML = '<p style="grid-column: 1/-1; text-align:center; padding: 30px;">Loading seat map...</p>';

  try {
    const res = await fetch(`/api/seats/${journeyId}`);
    const data = await res.json();

    if (!data.success) {
      grid.innerHTML = `<p style="grid-column: 1/-1; color:var(--danger);">${data.error || "Failed to load seats"}</p>`;
      return;
    }

    allSeatsCache = data.seats;
    renderSeatsGrid("ALL");
    updateSelectedSeatUI();

  } catch (err) {
    grid.innerHTML = '<p style="grid-column: 1/-1; color:var(--danger);">Error loading seat availability.</p>';
    showToast("Error retrieving seats", "error");
  }
}

function filterCoachSeats(type) {
  document.querySelectorAll(".coach-tab").forEach(tab => {
    tab.classList.toggle("active", tab.dataset.type === type);
  });
  renderSeatsGrid(type);
}

function renderSeatsGrid(filterType = "ALL") {
  const grid = document.getElementById("seats-grid");
  if (!grid) return;

  const filtered = filterType === "ALL" 
    ? allSeatsCache 
    : allSeatsCache.filter(s => s.seat_type === filterType);

  if (filtered.length === 0) {
    grid.innerHTML = '<p style="grid-column: 1/-1; text-align:center;">No seats available in this class.</p>';
    return;
  }

  grid.innerHTML = filtered.map(s => {
    const isSelected = selectedSeat && selectedSeat.seat_id === s.seat_id;
    let statusClass = s.status === "BOOKED" ? "booked" : (isSelected ? "selected" : "available");
    let disabledAttr = s.status === "BOOKED" ? "disabled" : "";

    return `
      <button type="button" 
              class="seat-btn ${statusClass}" 
              ${disabledAttr}
              onclick="onSeatClick(${s.seat_id})"
              id="seat-btn-${s.seat_id}"
              title="${s.seat_number} (${s.seat_type}) - ${s.status}">
        <span>${s.seat_number}</span>
        <span class="seat-type-tag">${s.seat_type}</span>
      </button>
    `;
  }).join("");
}

function onSeatClick(seatId) {
  const seat = allSeatsCache.find(s => s.seat_id === seatId);
  if (!seat || seat.status === "BOOKED") return;

  if (selectedSeat && selectedSeat.seat_id === seatId) {
    selectedSeat = null; // Deselect
  } else {
    selectedSeat = seat;
  }

  renderSeatsGrid(document.querySelector(".coach-tab.active")?.dataset.type || "ALL");
  updateSelectedSeatUI();
}

function updateSelectedSeatUI() {
  const bar = document.getElementById("selected-seat-summary");
  const btn = document.getElementById("btn-proceed-booking");
  const label = document.getElementById("selected-seat-label");

  if (!bar || !btn) return;

  if (selectedSeat) {
    bar.style.display = "flex";
    btn.removeAttribute("disabled");
    if (label) label.innerText = `${selectedSeat.seat_number} (${selectedSeat.seat_type})`;
    btn.onclick = () => {
      window.location.href = `/booking?journey_id=${selectedSeat.journey_id}&seat_id=${selectedSeat.seat_id}&seat_number=${encodeURIComponent(selectedSeat.seat_number)}&seat_type=${encodeURIComponent(selectedSeat.seat_type)}`;
    };
  } else {
    btn.setAttribute("disabled", "true");
    if (label) label.innerText = "None selected";
  }
}

// -------------------------------------------------------------
// Booking Page: Execution & Idempotency
// -------------------------------------------------------------
function initBookingForm() {
  const params = new URLSearchParams(window.location.search);
  const journeyId = params.get("journey_id");
  const seatId = params.get("seat_id");
  const seatNumber = params.get("seat_number");
  const seatType = params.get("seat_type");

  if (!journeyId || !seatId) {
    showToast("Invalid booking parameters. Returning to journeys.", "error");
    setTimeout(() => { window.location.href = "/"; }, 2000);
    return;
  }

  const seatElem = document.getElementById("booking-seat-display");
  if (seatElem) seatElem.innerText = `${seatNumber || "Seat #" + seatId} (${seatType || ""})`;

  // Display or generate idempotency key
  const keyInput = document.getElementById("booking-idempotency-key");
  if (keyInput) {
    keyInput.value = getOrCreateIdempotencyKey();
  }
}

async function handleBookingSubmit(event) {
  event.preventDefault();
  const submitBtn = document.getElementById("submit-booking-btn");
  const originalText = submitBtn ? submitBtn.innerText : "Confirm Booking";

  const params = new URLSearchParams(window.location.search);
  const journeyId = parseInt(params.get("journey_id"), 10);
  const seatId = parseInt(params.get("seat_id"), 10);
  const seatNumber = params.get("seat_number") || "";
  const passengerSelect = document.getElementById("passenger-select");
  const passengerId = parseInt(passengerSelect?.value || "1", 10);
  const idempotencyKey = document.getElementById("booking-idempotency-key")?.value.trim() || getOrCreateIdempotencyKey();

  if (submitBtn) {
    submitBtn.setAttribute("disabled", "true");
    submitBtn.innerText = "Claiming Seat (Atomic Lock)...";
  }

  try {
    const res = await fetch("/api/bookings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        passenger_id: passengerId,
        journey_id: journeyId,
        seat_id: seatId,
        idempotency_key: idempotencyKey,
      }),
    });

    const data = await res.json();

    if (res.status === 201 || res.status === 200) {
      showToast("Booking CONFIRMED!", "success");
      // Reset key for future unique bookings
      sessionStorage.removeItem("railway_current_idempotency_key");
      setTimeout(() => {
        window.location.href = `/confirmation?booking_id=${data.booking.booking_id}&status=confirmed`;
      }, 600);
    } else if (res.status === 409) {
      // Conflict: Tatkal double-booking collision
      showToast(data.error || "Seat unavailable: already booked!", "error");
      setTimeout(() => {
        window.location.href = `/confirmation?status=rejected&seat_number=${encodeURIComponent(seatNumber)}&journey_id=${journeyId}`;
      }, 800);
    } else {
      showToast(data.error || "Failed to complete booking", "error");
      if (submitBtn) {
        submitBtn.removeAttribute("disabled");
        submitBtn.innerText = originalText;
      }
    }
  } catch (err) {
    showToast("Network error during booking submission", "error");
    if (submitBtn) {
      submitBtn.removeAttribute("disabled");
      submitBtn.innerText = originalText;
    }
  }
}

// -------------------------------------------------------------
// Confirmation Page: Ticket Rendering
// -------------------------------------------------------------
async function loadConfirmationDetails() {
  const params = new URLSearchParams(window.location.search);
  const bookingId = params.get("booking_id");
  const status = params.get("status");

  const confirmedView = document.getElementById("confirmed-view");
  const rejectedView = document.getElementById("rejected-view");

  if (status === "rejected") {
    if (confirmedView) confirmedView.style.display = "none";
    if (rejectedView) {
      rejectedView.style.display = "block";
      const seatNum = params.get("seat_number");
      const jId = params.get("journey_id");
      const seatSpan = document.getElementById("rejected-seat-label");
      if (seatSpan) seatSpan.innerText = seatNum || "Requested Seat";
      const backLink = document.getElementById("rejected-back-link");
      if (backLink && jId) backLink.href = `/seats/${jId}`;
    }
    return;
  }

  if (bookingId && confirmedView) {
    try {
      const res = await fetch(`/api/bookings/${bookingId}`);
      const data = await res.json();

      if (data.success && data.booking) {
        const b = data.booking;
        document.getElementById("ticket-booking-id").innerText = `#${b.booking_id}`;
        document.getElementById("ticket-train").innerText = `${b.train_number || "Express"} (${b.source || ""} → ${b.destination || ""})`;
        document.getElementById("ticket-date").innerText = b.journey_date || "Confirmed";
        document.getElementById("ticket-passenger").innerText = `${b.passenger_name || "Passenger"} (${b.email || ""})`;
        document.getElementById("ticket-seat").innerText = `${b.seat_number || ""} (${b.seat_type || ""})`;
        document.getElementById("ticket-time").innerText = b.booking_time || "Now";
        document.getElementById("ticket-idemp").innerText = b.idempotency_key || "N/A";
      }
    } catch (err) {
      showToast("Error retrieving ticket details", "error");
    }
  }
}

// -------------------------------------------------------------
// Admin Dashboard: Telemetry & Metrics
// -------------------------------------------------------------
let adminPollInterval = null;

async function loadAdminData() {
  try {
    // 1. Fetch live metrics
    const metricsRes = await fetch("/api/admin/metrics");
    const metricsData = await metricsRes.json();

    if (metricsData.success) {
      const m = metricsData.metrics;
      const s = metricsData.seats_summary;

      document.getElementById("metric-total-requests").innerText = m.total_requests;
      document.getElementById("metric-success-requests").innerText = m.successful_requests;
      document.getElementById("metric-rejected-requests").innerText = m.rejected_requests;
      document.getElementById("metric-error-rate").innerText = `${m.error_rate_percent}%`;
      document.getElementById("metric-avg-latency").innerText = `${m.avg_processing_time_ms} ms`;
      document.getElementById("metric-p95-latency").innerText = `${m.p95_processing_time_ms} ms`;

      document.getElementById("metric-total-seats").innerText = s.total_seats;
      document.getElementById("metric-available-seats").innerText = s.available_seats;
      document.getElementById("metric-booked-seats").innerText = s.booked_seats;
    }

    // 2. Fetch recent bookings
    const bookingsRes = await fetch("/api/admin/bookings?limit=30");
    const bookingsData = await bookingsRes.json();

    const tbody = document.getElementById("admin-bookings-table-body");
    if (tbody && bookingsData.success) {
      if (bookingsData.bookings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">No bookings recorded yet.</td></tr>';
      } else {
        tbody.innerHTML = bookingsData.bookings.map(b => `
          <tr>
            <td><strong>#${b.booking_id}</strong></td>
            <td>${b.passenger_name}</td>
            <td>Train ${b.train_number}</td>
            <td><span class="badge badge-info">${b.seat_number} (${b.seat_type})</span></td>
            <td><span class="badge badge-success">${b.booking_status}</span></td>
            <td style="font-size:12px; color:var(--text-muted);">${b.booking_time}</td>
            <td style="font-size:11px; font-family:monospace;">${b.idempotency_key}</td>
          </tr>
        `).join("");
      }
    }

  } catch (err) {
    showToast("Error updating admin telemetry", "error");
  }
}

function toggleAdminAutoRefresh(enabled) {
  if (enabled) {
    adminPollInterval = setInterval(loadAdminData, 4000);
    showToast("Live telemetry auto-refresh enabled (4s)", "info");
  } else {
    clearInterval(adminPollInterval);
    adminPollInterval = null;
    showToast("Auto-refresh paused", "info");
  }
}

