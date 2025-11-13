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

    // Prepare data for treemap
    const data = {
        name: 'zones',
        children: zones.map(zone => ({
            name: zone.ticker,
            value: zone.score, // Use score as the value for sizing
            zone: zone
        }))
    };

    // Create treemap layout
    const treemap = d3.treemap()
        .size([width, height])
        .padding(3)
        .paddingOuter(4)
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

    // Add rectangles
    nodes.append('rect')
        .attr('class', 'zone-cell')
        .attr('width', d => d.x1 - d.x0)
        .attr('height', d => d.y1 - d.y0)
        .attr('fill', d => getZoneColor(d.data.zone.score))
        .attr('rx', 6)
        .attr('ry', 6)
        .on('click', function(event, d) {
            showZoneDetail(d.data.zone.id);
        });

    // Add text content to each cell
    nodes.each(function(d) {
        const node = d3.select(this);
        const cellWidth = d.x1 - d.x0;
        const cellHeight = d.y1 - d.y0;

        // Only add text if cell is large enough
        if (cellWidth < 60 || cellHeight < 50) {
            // Small cell - just show ticker
            if (cellWidth >= 40 && cellHeight >= 20) {
                node.append('text')
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
        let yOffset = 20;

        // Ticker name
        node.append('text')
            .attr('class', 'zone-label')
            .attr('x', cellWidth / 2)
            .attr('y', yOffset)
            .attr('text-anchor', 'middle')
            .text(zone.ticker);

        yOffset += 35;

        // Score (large)
        node.append('text')
            .attr('class', 'zone-score')
            .attr('x', cellWidth / 2)
            .attr('y', yOffset)
            .attr('text-anchor', 'middle')
            .text(Math.round(zone.score));

        yOffset += 20;

        // Score change (if available)
        if (zone.score_change && zone.score_change !== 0) {
            const changeText = zone.score_change > 0 ? `↑ +${zone.score_change.toFixed(1)}` : `↓ ${zone.score_change.toFixed(1)}`;
            node.append('text')
                .attr('class', `score-change ${zone.score_change > 0 ? 'positive' : 'negative'}`)
                .attr('x', cellWidth / 2)
                .attr('y', yOffset)
                .attr('text-anchor', 'middle')
                .text(changeText);

            yOffset += 18;
        }

        // Additional details (if space allows)
        if (cellHeight > 100) {
            node.append('text')
                .attr('class', 'zone-details')
                .attr('x', cellWidth / 2)
                .attr('y', yOffset)
                .attr('text-anchor', 'middle')
                .text(`${zone.candle_count} gün`);

            yOffset += 15;

            node.append('text')
                .attr('class', 'zone-details')
                .attr('x', cellWidth / 2)
                .attr('y', yOffset)
                .attr('text-anchor', 'middle')
                .text(`%${zone.total_diff_percent}`);
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
        // Strong - blue
        return '#4299e1';
    } else if (score >= 30) {
        // Medium - yellow/gold
        return '#ecc94b';
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
        renderActiveZonesTreemap(app.activeZones);
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
