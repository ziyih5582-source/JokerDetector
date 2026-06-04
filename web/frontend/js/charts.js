/**
 * Joker Detector Pro - Chart.js 图表渲染
 */

let radarChartInstance = null;
let barChartInstance = null;

/**
 * 渲染五维小丑雷达图 + 双方对比柱状图
 */
function renderCharts(zMetrics, statistics) {
    renderRadarChart(zMetrics);
    renderBarChart(statistics);
}

// ==================== 五维雷达图 ====================
function renderRadarChart(zMetrics) {
    const ctx = document.getElementById('radarChart').getContext('2d');

    if (radarChartInstance) radarChartInstance.destroy();

    const labels = [];
    const values = [];
    const colors = {
        'SSDT': '#e74c6f',
        'PFI': '#8b5cf6',
        'PLD': '#f0c040',
        'EPEG': '#5b9bd5',
        'CONV': '#4ade80'
    };

    for (const [key, metric] of Object.entries(zMetrics)) {
        labels.push(metric.label);
        // 将 Z-score (-1~1) 映射到 0-100 便于展示
        values.push(Math.max(0, Math.min(100, (metric.value + 1) * 50)));
    }

    radarChartInstance = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                label: '你的小丑维度',
                data: values,
                backgroundColor: 'rgba(139, 92, 246, 0.15)',
                borderColor: 'rgba(139, 92, 246, 0.8)',
                borderWidth: 2,
                pointBackgroundColor: values.map((_, i) => {
                    const keys = Object.keys(zMetrics);
                    return colors[keys[i]] || '#8b5cf6';
                }),
                pointBorderColor: '#fff',
                pointBorderWidth: 1,
                pointRadius: 5,
                pointHoverRadius: 7
            }, {
                label: '均衡基准线',
                data: [50, 50, 50, 50, 50],
                backgroundColor: 'transparent',
                borderColor: 'rgba(255, 255, 255, 0.12)',
                borderWidth: 1,
                borderDash: [5, 5],
                pointRadius: 0,
                fill: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#8888a0',
                        font: { family: "'Noto Sans SC', sans-serif", size: 11 },
                        padding: 16,
                        usePointStyle: true,
                        pointStyleWidth: 8
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            if (ctx.datasetIndex === 1) return '基准线: 50';
                            const keys = Object.keys(zMetrics);
                            const key = keys[ctx.dataIndex];
                            const meta = zMetrics[key];
                            return `${meta.label}: ${meta.value.toFixed(2)} (Z-score)\n${meta.desc}`;
                        }
                    }
                }
            },
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    min: 0,
                    ticks: {
                        display: false,
                        stepSize: 25
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.06)'
                    },
                    angleLines: {
                        color: 'rgba(255, 255, 255, 0.08)'
                    },
                    pointLabels: {
                        color: '#8888a0',
                        font: { family: "'Noto Sans SC', sans-serif", size: 11 }
                    }
                }
            }
        }
    });
}

// ==================== 双方对比柱状图 ====================
function renderBarChart(statistics) {
    const ctx = document.getElementById('barChart').getContext('2d');

    if (barChartInstance) barChartInstance.destroy();

    barChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['消息数', '表情包', '图片', '总字数', '最大连发', '平均字数'],
            datasets: [{
                label: '自己',
                data: [
                    statistics.message_count.self,
                    statistics.sticker_count.self,
                    statistics.picture_count.self,
                    statistics.total_chars.self,
                    statistics.max_streak.self,
                    statistics.avg_chars.self
                ],
                backgroundColor: 'rgba(139, 92, 246, 0.7)',
                borderColor: 'rgba(139, 92, 246, 1)',
                borderWidth: 1,
                borderRadius: 6,
                borderSkipped: false
            }, {
                label: '对方',
                data: [
                    statistics.message_count.other,
                    statistics.sticker_count.other,
                    statistics.picture_count.other,
                    statistics.total_chars.other,
                    statistics.max_streak.other,
                    statistics.avg_chars.other
                ],
                backgroundColor: 'rgba(90, 90, 114, 0.5)',
                borderColor: 'rgba(90, 90, 114, 0.8)',
                borderWidth: 1,
                borderRadius: 6,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#8888a0',
                        font: { family: "'Noto Sans SC', sans-serif", size: 11 },
                        padding: 16,
                        usePointStyle: true,
                        pointStyleWidth: 8
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        color: '#8888a0',
                        font: { family: "'Noto Sans SC', sans-serif", size: 11 }
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.06)'
                    },
                    ticks: {
                        color: '#5a5a72',
                        font: { family: "'Noto Sans SC', sans-serif", size: 10 }
                    }
                }
            }
        }
    });
}
