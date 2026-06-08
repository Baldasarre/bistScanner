/**
 * Treemap visualization for active accumulation zones
 * Inspired by coin360.com
 */

/**
 * Create treemap visualization
 * @param {Array} zones - Array of zone objects
 * @param {string} containerId - ID of container element
 */
function createTreemap(zones, containerId) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error('Container not found:', containerId);
        return;
    }

    // Filter out zones with score <= 39
    const filteredZones = zones.filter(z => z.score > 39);

    if (filteredZones.length === 0) {
        container.innerHTML = '<div class="loading">Gösterilecek yüksek puanlı (40+) blok bulunamadı</div>';
        return;
    }

    // Clear container
    container.innerHTML = '';

    // Set dimensions
    const width = container.clientWidth || 1000;
    const height = Math.max(500, width * 0.6);

    // Create SVG
    const svg = d3.select(`#${containerId}`)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .style('max-width', '100%')
        .style('height', 'auto');

    // Metin taşmalarını engellemek için clip-path tanımları oluştur
    const defs = svg.append('defs');
    filteredZones.forEach(zone => {
        defs.append('clipPath')
            .attr('id', `clip-${zone.id}`)
            .append('rect')
            .attr('width', 0) // Render sırasında güncellenecek
            .attr('height', 0)
            .attr('rx', 6)
            .attr('ry', 6);
    });

    // Prepare data for treemap
    const data = {
        name: 'zones',
        children: filteredZones.map(zone => ({
            name: zone.ticker.replace('.IS', ''), // Remove .IS suffix
            // Skora 30 taban puan ekleyerek düşük puanlıların çok küçülmesini engelliyoruz
            value: zone.score + 30, 
            zone: zone
        }))
    };

    // Create treemap layout
    const treemap = d3.treemap()
        .size([width, height])
        .tile(d3.treemapSquarify.ratio(1.2)) // Kutuların çok ince/uzun olmasını engeller, kareye yaklaştırır
        .padding(8)        // Inner padding between cells
        .paddingOuter(10)  // Outer padding
        .round(true);

    // Create hierarchy
    const root = d3.hierarchy(data)
        .sum(d => d.value)
        .sort((a, b) => b.value - a.value);

    // Compute treemap layout
    treemap(root);

    // Create groups for each zone
    const nodes = svg.selectAll('g')
        .data(root.leaves())
        .join('g')
        .attr('transform', d => `translate(${d.x0},${d.y0})`);

    // Clip-path boyutlarını hücre boyutlarına göre ayarla
    nodes.each(function(d) {
        d3.select(`#clip-${d.data.zone.id} rect`)
            .attr('width', d.x1 - d.x0)
            .attr('height', d.y1 - d.y0);
    });

    // Add rectangles
    nodes.append('rect')
        .attr('class', d => `zone-cell ${d.data.zone.is_flagged ? 'flagged' : ''}`)
        .attr('width', d => d.x1 - d.x0)
        .attr('height', d => d.y1 - d.y0)
        .attr('fill', d => getZoneColor(d.data.zone.score))
        .attr('rx', 6)
        .attr('ry', 6)
        .on('click', function(event, d) {
            // Check if click was on flag
            if (event.target.classList && event.target.classList.contains('zone-flag')) {
                return; // Flag click handled separately
            }
            showZoneDetail(d.data.zone.id);
        });

    // Add flag icon in top-right corner (only for cells large enough)
    nodes.each(function(d) {
        const cellWidth = d.x1 - d.x0;
        const cellHeight = d.y1 - d.y0;

        if (cellWidth >= 60 && cellHeight >= 50) {
            const zone = d.data.zone;
            const node = d3.select(this);

            node.append('text')
                .attr('class', `zone-flag ${zone.is_flagged ? 'flagged' : ''}`)
                .attr('x', cellWidth - 20)
                .attr('y', 25)
                .attr('text-anchor', 'middle')
                .style('font-size', '24px')
                .style('cursor', 'pointer')
                .style('fill', 'white')
                .style('opacity', zone.is_flagged ? '1' : '0.4')
                .text('⚑')
                .on('click', function(event) {
                    event.stopPropagation();
                    toggleFlag(event, zone.id);
                });
        }
    });

    // Add text content to each cell
    nodes.each(function(d) {
        const node = d3.select(this);
        const cellWidth = d.x1 - d.x0;
        const cellHeight = d.y1 - d.y0;

        // Metin içeriği için ayrı bir grup oluştur ve clip-path'i sadece buna uygula
        const textGroup = node.append('g').attr('clip-path', `url(#clip-${d.data.zone.id})`);

        // Only add text if cell is large enough
        if (cellWidth < 60 || cellHeight < 50) {
            // Small cell - just show ticker
            if (cellWidth >= 40 && cellHeight >= 20) {
                textGroup.append('text')
                    .attr('class', 'zone-label')
                    .attr('x', cellWidth / 2)
                    .attr('y', cellHeight / 2)
                    .attr('text-anchor', 'middle')
                    .attr('dominant-baseline', 'middle')
                    .style('font-size', '10px')
                    .text(d.data.name);
            }
            return;
        }

        const zone = d.data.zone;
        const canFit = (y, buffer = 8) => y < (cellHeight - buffer);

        // Dinamik font hesaplama: Kutunun boyutuna göre ölçekle
        const calculateFontSize = (basePercent, min, max) => {
            const size = Math.min(cellWidth, cellHeight) * basePercent;
            return `${Math.max(min, Math.min(max, size))}px`;
        };

        let yOffset = cellHeight * 0.25; // Başlangıç ofsetini kutu boyuna oranla

        // Ticker name
        if (canFit(yOffset)) {
            textGroup.append('text')
                .attr('class', 'zone-label')
                .attr('x', cellWidth / 2)
                .attr('y', yOffset)
                .attr('text-anchor', 'middle')
                .style('font-size', calculateFontSize(0.2, 12, 28))
                .style('font-weight', 'bold')
                .text(zone.ticker.replace('.IS', ''));
            yOffset += (cellHeight * 0.2);
        }

        // Score (large)
        if (canFit(yOffset)) {
            textGroup.append('text')
                .attr('class', 'zone-score')
                .attr('x', cellWidth / 2)
                .attr('y', yOffset)
                .attr('text-anchor', 'middle')
                .style('font-size', calculateFontSize(0.15, 10, 22))
                .text(`${Math.round(zone.score)} Puan`);
            yOffset += (cellHeight * 0.15);
        }

        // Score change (if available)
        if (zone.score_change && zone.score_change !== 0 && canFit(yOffset)) {
            const changeText = zone.score_change > 0 ? `↑ +${zone.score_change.toFixed(1)}` : `↓ ${zone.score_change.toFixed(1)}`;
            textGroup.append('text')
                .attr('class', `score-change ${zone.score_change > 0 ? 'positive' : 'negative'}`)
                .attr('x', cellWidth / 2)
                .attr('y', yOffset)
                .attr('text-anchor', 'middle')
                .style('font-size', calculateFontSize(0.1, 9, 14))
                .text(changeText);
            yOffset += (cellHeight * 0.12);
        }

        // Additional details (if space allows)
        const details = [`${zone.candle_count} gün`, `% ${zone.total_diff_percent}`];
        details.forEach(detail => {
            if (canFit(yOffset)) {
                textGroup.append('text')
                    .attr('class', 'zone-details')
                    .attr('x', cellWidth / 2)
                    .attr('y', yOffset)
                    .attr('text-anchor', 'middle')
                    .style('font-size', calculateFontSize(0.08, 8, 12))
                    .text(detail);
                yOffset += (cellHeight * 0.1);
            }
        });

        // Last comment (if any and fits)
        if (zone.last_comment && canFit(yOffset + (cellHeight * 0.05))) {
                // Truncate comment if too long for the cell
                const maxLength = Math.floor(cellWidth / 5.5);
                const commentText = zone.last_comment.length > maxLength
                    ? zone.last_comment.substring(0, maxLength) + '...'
                    : zone.last_comment;

                textGroup.append('text')
                    .attr('class', 'zone-details')
                    .attr('x', cellWidth / 2)
                    .attr('y', yOffset + (cellHeight * 0.05))
                    .attr('text-anchor', 'middle')
                    .style('font-size', calculateFontSize(0.09, 9, 13))
                    .style('font-style', 'italic')
                    .style('font-weight', '500')
                    .text(`💬 ${commentText}`);
        }
    });
}

/**
 * Get color based on zone score
 * @param {number} score - Zone score (0-100)
 * @returns {string} - CSS color
 */
function getZoneColor(score) {
    if (score >= 70) {
        // Very strong - green
        return '#48bb78';
    } else if (score >= 50) {
        // Strong - orange
        return '#ed8936';
    } else if (score >= 30) {
        // Medium - blue
        return '#4299e1';
    } else {
        // Weak - gray
        return '#a0aec0';
    }
}

/**
 * Responsive resize handler
 */
window.addEventListener('resize', debounce(function() {
    if (app.currentTab === 'active' && app.activeZones.length > 0) {
        // Mevcut görünüm moduna göre render et
        if (app.activeViewMode === 'treemap') {
            renderActiveZonesTreemap(app.activeZones);
        } else {
            renderActiveZonesList(app.activeZones);
        }
    }
}, 250));

/**
 * Debounce function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
