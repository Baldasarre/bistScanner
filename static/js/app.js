/**
 * BIST Scanner - Main Application JavaScript
 */

// Global state
const app = {
  activeZones: [],
  completedZones: [],
  currentTab: "active",
  activeViewMode: "treemap", // treemap or list
};

// Initialize app when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  initializeTabs();
  initializeViewToggle();
  loadScanStatus();
  loadActiveZones();
  loadCompletedZones();

  // Auto-refresh every 5 minutes
  setInterval(() => {
    if (app.currentTab === "active") {
      loadActiveZones();
    } else {
      loadCompletedZones();
    }
    loadScanStatus();
  }, 5 * 60 * 1000);
});

/**
 * Initialize tab switching
 */
function initializeTabs() {
  const tabButtons = document.querySelectorAll(".tab-button");

  tabButtons.forEach((button) => {
    button.addEventListener("click", function () {
      const tabName = this.getAttribute("data-tab");
      switchTab(tabName);
    });
  });
}

/**
 * Initialize view toggle for active zones
 */
function initializeViewToggle() {
  const toggleButtons = document.querySelectorAll(".toggle-btn");

  toggleButtons.forEach((button) => {
    button.addEventListener("click", function () {
      const viewMode = this.getAttribute("data-view");
      switchActiveView(viewMode);
    });
  });
}

/**
 * Switch between treemap and list view for active zones
 */
function switchActiveView(viewMode) {
  // Update buttons
  document.querySelectorAll(".toggle-btn").forEach((btn) => {
    btn.classList.remove("active");
  });
  document.querySelector(`[data-view="${viewMode}"]`).classList.add("active");

  // Update app state
  app.activeViewMode = viewMode;

  // Re-render active zones with new view
  if (viewMode === "treemap") {
    renderActiveZonesTreemap(app.activeZones);
  } else {
    renderActiveZonesList(app.activeZones);
  }
}

/**
 * Switch between tabs
 */
function switchTab(tabName) {
  // Update buttons
  document.querySelectorAll(".tab-button").forEach((btn) => {
    btn.classList.remove("active");
  });
  document.querySelector(`[data-tab="${tabName}"]`).classList.add("active");

  // Update content
  document.querySelectorAll(".tab-pane").forEach((pane) => {
    pane.classList.remove("active");
  });
  document.getElementById(`${tabName}-tab`).classList.add("active");

  app.currentTab = tabName;
}

/**
 * Load scan status
 */
async function loadScanStatus() {
  try {
    const response = await fetch("/api/scan-status");
    const data = await response.json();

    if (data.success && data.scan_log) {
      const log = data.scan_log;
      const scanDate = new Date(log.scan_date);
      const dateStr = scanDate.toLocaleDateString("tr-TR", {
        day: "numeric",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });

      document.getElementById("scan-info").innerHTML = `
                <span class="scan-date">Son Tarama: ${dateStr}</span>
                <span class="scan-stats">| ${log.total_tickers} hisse tarandı</span>
            `;
    }
  } catch (error) {
    console.error("Error loading scan status:", error);
  }
}

/**
 * Load active zones
 */
async function loadActiveZones() {
  try {
    const response = await fetch("/api/active-zones");
    const data = await response.json();

    if (data.success) {
      app.activeZones = data.zones;

      // Update badge count
      document.getElementById("active-count").textContent =
        app.activeZones.length;

      // Render treemap
      renderActiveZonesTreemap(app.activeZones);
    }
  } catch (error) {
    console.error("Error loading active zones:", error);
    showError(
      "active-zones-container",
      "Aktif bloklar yüklenirken hata oluştu"
    );
  }
}

/**
 * Load completed zones
 */
async function loadCompletedZones() {
  try {
    const response = await fetch("/api/completed-zones");
    const data = await response.json();

    if (data.success) {
      app.completedZones = data.zones;

      // Update badge count
      document.getElementById("completed-count").textContent =
        app.completedZones.length;

      // Render list
      renderCompletedZonesList(app.completedZones);
    }
  } catch (error) {
    console.error("Error loading completed zones:", error);
    showError(
      "completed-zones-container",
      "Tamamlanan bloklar yüklenirken hata oluştu"
    );
  }
}

/**
 * Render active zones as treemap (delegated to treemap.js)
 */
function renderActiveZonesTreemap(zones) {
  const container = document.getElementById("active-zones-container");

  if (zones.length === 0) {
    container.innerHTML =
      '<div class="loading">Aktif akümülasyon bloğu bulunamadı</div>';
    return;
  }

  // Clear container
  container.innerHTML = '<div id="treemap-container"></div>';

  // Call treemap rendering function
  if (typeof createTreemap === "function") {
    createTreemap(zones, "treemap-container");
  }
}

/**
 * Render active zones as list
 */
function renderActiveZonesList(zones) {
  const container = document.getElementById("active-zones-container");

  if (zones.length === 0) {
    container.innerHTML =
      '<div class="loading">Aktif akümülasyon bloğu bulunamadı</div>';
    return;
  }

  const html = `
        <div class="zones-list">
            ${zones.map((zone) => createActiveZoneCard(zone)).join("")}
        </div>
    `;

  container.innerHTML = html;

  // Add click handlers
  document.querySelectorAll(".zone-card").forEach((card) => {
    card.addEventListener("click", function () {
      const zoneId = parseInt(this.getAttribute("data-zone-id"));
      showZoneDetail(zoneId);
    });
  });
}

/**
 * Create active zone card HTML
 */
function createActiveZoneCard(zone) {
  const ticker = zone.ticker.replace(".IS", "");
  const startDate = formatDate(zone.start_date);
  const scoreChangeClass =
    zone.score_change > 0
      ? "positive"
      : zone.score_change < 0
      ? "negative"
      : "";
  const scoreChangeText =
    zone.score_change !== 0
      ? `${zone.score_change > 0 ? "+" : ""}${zone.score_change.toFixed(1)}`
      : "0";

  return `
        <div class="zone-card active" data-zone-id="${zone.id}">
            <div class="zone-card-flag ${zone.is_flagged ? 'flagged' : ''}" onclick="toggleFlag(event, ${zone.id})">
                ⚑
            </div>
            <div class="zone-card-left">
                <div class="zone-ticker-large">${ticker}</div>
                <div class="zone-start-date">${startDate}</div>
                ${zone.last_comment ? `<div class="zone-last-comment">💬 ${zone.last_comment}</div>` : ''}
            </div>
            <div class="zone-card-middle">
                <div class="zone-stat-row">
                    <div class="zone-stat-item">
                        <span class="stat-label">Skor</span>
                        <span class="stat-value">${Math.round(
                          zone.score
                        )}</span>
                    </div>
                    <div class="zone-stat-item">
                        <span class="stat-label">Değişim</span>
                        <span class="stat-value ${scoreChangeClass}">${scoreChangeText}</span>
                    </div>
                    <div class="zone-stat-item">
                        <span class="stat-label">Mum</span>
                        <span class="stat-value">${zone.candle_count}</span>
                    </div>
                </div>
                <div class="zone-stat-row">
                    <div class="zone-stat-item">
                        <span class="stat-label">Genişlik</span>
                        <span class="stat-value">%${
                          zone.total_diff_percent
                        }</span>
                    </div>
                    <div class="zone-stat-item">
                        <span class="stat-label">RSI</span>
                        <span class="stat-value">${zone.avg_rsi}</span>
                    </div>
                </div>
            </div>
            <div class="zone-card-right">
                <div class="zone-score-badge" style="font-size: 1.5rem;padding-top: 0.2rem;justify-content: center;text-align: center;border-radius: 1rem;width: 6rem;height: 3rem;background-color: ${getZoneColorForBadge(
                  zone.score
                )}">
                    ${Math.round(zone.score)}
                </div>
            </div>
        </div>
    `;
}

/**
 * Get zone color for badge (matching treemap colors)
 */
function getZoneColorForBadge(score) {
  if (score >= 70) {
    return "#48bb78"; // green
  } else if (score >= 50) {
    return "#ed8936"; // orange
  } else if (score >= 30) {
    return "#4299e1"; // blue
  } else {
    return "#a0aec0"; // gray
  }
}

/**
 * Render completed zones as list
 */
function renderCompletedZonesList(zones) {
  const container = document.getElementById("completed-zones-container");

  if (zones.length === 0) {
    container.innerHTML =
      '<div class="loading">Son 3 haftada tamamlanan blok bulunmamaktadır</div>';
    return;
  }

  const html = `
        <div class="zones-list">
            ${zones.map((zone) => createZoneCard(zone)).join("")}
        </div>
    `;

  container.innerHTML = html;

  // Add click handlers
  document.querySelectorAll(".zone-card").forEach((card) => {
    card.addEventListener("click", function () {
      const zoneId = parseInt(this.getAttribute("data-zone-id"));
      showZoneDetail(zoneId);
    });
  });
}

/**
 * Create zone card HTML
 */
function createZoneCard(zone) {
  const statusClass = zone.status === "broken" ? "broken" : "completed";
  const statusText = zone.status === "broken" ? "Kural Dışı" : "Tamamlandı";

  const startDate = formatDate(zone.start_date);
  const endDate = formatDate(zone.end_date);

  return `
        <div class="zone-card ${statusClass}" data-zone-id="${zone.id}">
            <div class="zone-card-header">
                <span class="zone-ticker">${zone.ticker}</span>
                <span class="zone-status ${statusClass}">${statusText}</span>
            </div>
            <div class="zone-card-body">
                <div class="zone-stat">
                    <strong>Skor:</strong> ${zone.score}
                </div>
                <div class="zone-stat">
                    <strong>Mum:</strong> ${zone.candle_count}
                </div>
                <div class="zone-stat">
                    <strong>Genişlik:</strong> %${zone.total_diff_percent}
                </div>
                <div class="zone-stat">
                    <strong>RSI:</strong> ${zone.avg_rsi}
                </div>
                <div class="zone-stat">
                    <strong>Başlangıç:</strong> ${startDate}
                </div>
                <div class="zone-stat">
                    <strong>Bitiş:</strong> ${endDate}
                </div>
                ${zone.last_comment ? `<div class="zone-last-comment-completed">💬 ${zone.last_comment}</div>` : ''}
            </div>
        </div>
    `;
}

/**
 * Show zone detail modal
 */
async function showZoneDetail(zoneId) {
  try {
    const response = await fetch(`/api/zone/${zoneId}`);
    const data = await response.json();

    if (data.success) {
      const zone = data.zone;
      const history = data.history;

      // Load comments
      const commentsResponse = await fetch(`/api/zone/${zoneId}/comments`);
      const commentsData = await commentsResponse.json();
      const comments = commentsData.success ? commentsData.comments : [];

      const modalBody = document.getElementById("modal-body");
      modalBody.innerHTML = `
                <h2>${zone.ticker} - Detaylar</h2>
                <div class="zone-detail">
                    <p><strong>Tarih Aralığı:</strong> ${formatDate(
                      zone.start_date
                    )} - ${formatDate(zone.end_date)}</p>
                    <p><strong>Mum Sayısı:</strong> ${zone.candle_count}</p>
                    <p><strong>Skor:</strong> ${zone.score}</p>
                    <p><strong>Toplam Genişlik:</strong> %${
                      zone.total_diff_percent
                    }</p>
                    <p><strong>Ortalama RSI:</strong> ${zone.avg_rsi}</p>
                    <p><strong>Durum:</strong> ${
                      zone.status === "active"
                        ? "Aktif"
                        : zone.status === "completed"
                        ? "Tamamlandı"
                        : "Kural Dışı"
                    }</p>
                </div>

                ${
                  history.length > 0
                    ? `
                    <h3 class="mt-md">Skor Geçmişi</h3>
                    <div class="history-list">
                        ${history
                          .map(
                            (h) => `
                            <div class="history-item">
                                ${formatDate(h.date)}: Skor ${h.score}
                                ${
                                  h.score_change !== 0
                                    ? `(${
                                        h.score_change > 0 ? "+" : ""
                                      }${h.score_change.toFixed(1)})`
                                    : ""
                                }
                            </div>
                        `
                          )
                          .join("")}
                    </div>
                `
                    : ""
                }

                <h3 class="mt-md">Yorumlar</h3>
                <div class="comments-section">
                    <div class="comments-list" id="comments-list-${zoneId}">
                        ${comments.length > 0 ? comments.map(c => `
                            <div class="comment-item">
                                <div class="comment-header">
                                    <strong>${c.username}</strong>
                                    <div>
                                        <span class="comment-date">${formatDateTime(c.created_at)}</span>
                                        ${c.can_delete ? `<button class="btn-delete-comment" onclick="deleteComment(event, ${c.id}, ${zoneId})">×</button>` : ''}
                                    </div>
                                </div>
                                <div class="comment-text">${c.comment}</div>
                            </div>
                        `).join('') : '<div class="no-comments">Henüz yorum yok</div>'}
                    </div>
                    <div class="comment-form">
                        <textarea id="comment-input-${zoneId}" placeholder="Yorumunuzu yazın..." rows="3"></textarea>
                        <button class="btn btn-primary" onclick="submitComment(${zoneId})">Gönder</button>
                    </div>
                </div>
            `;

      showModal();
    }
  } catch (error) {
    console.error("Error loading zone detail:", error);
  }
}

/**
 * Show modal
 */
function showModal() {
  const modal = document.getElementById("zone-modal");
  modal.classList.add("show");
}

/**
 * Hide modal
 */
function hideModal() {
  const modal = document.getElementById("zone-modal");
  modal.classList.remove("show");
}

// Close modal when clicking X or outside
document.addEventListener("click", function (e) {
  if (e.target.classList.contains("close") || e.target.id === "zone-modal") {
    hideModal();
  }
});

/**
 * Format date
 */
function formatDate(dateStr) {
  if (!dateStr) return "-";
  const date = new Date(dateStr);
  return date.toLocaleDateString("tr-TR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/**
 * Show error message
 */
function showError(containerId, message) {
  const container = document.getElementById(containerId);
  container.innerHTML = `<div class="loading" style="color: var(--accent-red);">${message}</div>`;
}

/**
 * Toggle zone flag
 */
async function toggleFlag(event, zoneId) {
  event.stopPropagation(); // Prevent card click

  try {
    const response = await fetch(`/api/zone/${zoneId}/flag`, {
      method: 'POST'
    });

    const data = await response.json();

    if (data.success) {
      // Reload zones to reflect flag change
      loadActiveZones();
      loadCompletedZones();
    } else {
      alert('Bayrak değiştirilemedi');
    }
  } catch (error) {
    console.error('Error toggling flag:', error);
    alert('Bayrak değiştirilirken hata oluştu');
  }
}

/**
 * Submit comment
 */
async function submitComment(zoneId) {
  const textarea = document.getElementById(`comment-input-${zoneId}`);
  const comment = textarea.value.trim();

  if (!comment) {
    alert('Lütfen bir yorum yazın');
    return;
  }

  try {
    const response = await fetch(`/api/zone/${zoneId}/comments`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ comment })
    });

    const data = await response.json();

    if (data.success) {
      // Reload zone detail to show new comment
      showZoneDetail(zoneId);
      // Reload zones to update comment count
      loadActiveZones();
      loadCompletedZones();
    } else {
      alert(data.error || 'Yorum eklenemedi');
    }
  } catch (error) {
    console.error('Error submitting comment:', error);
    alert('Yorum gönderilirken hata oluştu');
  }
}

/**
 * Delete a comment
 */
async function deleteComment(event, commentId, zoneId) {
  event.stopPropagation();

  if (!confirm('Bu yorumu silmek istediğinizden emin misiniz?')) {
    return;
  }

  try {
    const response = await fetch(`/api/comment/${commentId}`, {
      method: 'DELETE'
    });

    const data = await response.json();

    if (data.success) {
      // Reload zone detail to reflect deletion
      showZoneDetail(zoneId);
      // Reload zones to update comment count
      loadActiveZones();
      loadCompletedZones();
    } else {
      alert(data.error || 'Yorum silinemedi');
    }
  } catch (error) {
    console.error('Error deleting comment:', error);
    alert('Yorum silinirken hata oluştu');
  }
}

/**
 * Format datetime for comments
 */
function formatDateTime(dateString) {
  if (!dateString) return 'N/A';
  const date = new Date(dateString);
  return date.toLocaleString('tr-TR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

