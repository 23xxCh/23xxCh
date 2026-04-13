/**
 * Simple Heatmap component that doesn't use Three.js
 * This ensures the page won't go black
 */
import { useMemo } from "react";

/**
 * Simple 2D heatmap visualization using canvas
 */
function Heatmap2D({ grid, particles, estimate }) {
  const canvasRef = useMemo(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 400;
    canvas.height = 400;
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    return canvas;
  }, []);

  useMemo(() => {
    const ctx = canvasRef.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.fillStyle = '#071423';
    ctx.fillRect(0, 0, canvasRef.width, canvasRef.height);

    // Draw grid
    ctx.strokeStyle = '#274768';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 10; i++) {
      const pos = i * 40;
      ctx.beginPath();
      ctx.moveTo(pos, 0);
      ctx.lineTo(pos, 400);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, pos);
      ctx.lineTo(400, pos);
      ctx.stroke();
    }

    // Draw particles if available
    if (particles && particles.positions && particles.positions.length > 0) {
      const maxWeight = Math.max(...(particles.weights || [1]), 0.01);
      particles.positions.forEach((pos, i) => {
        const weight = (particles.weights && particles.weights[i]) || 0.5;
        const normalizedWeight = weight / maxWeight;
        const x = (pos[0] + 10) * 20;
        const y = 400 - (pos[1] + 10) * 20;

        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        const intensity = Math.floor(100 + normalizedWeight * 155);
        ctx.fillStyle = `rgb(64, ${intensity}, ${intensity})`;
        ctx.fill();
      });
    }

    // Draw estimate if available
    if (estimate && estimate.position) {
      const x = (estimate.position[0] + 10) * 20;
      const y = 400 - (estimate.position[1] + 10) * 20;

      // Draw marker
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(x - 15, y);
      ctx.lineTo(x + 15, y);
      ctx.moveTo(x, y - 15);
      ctx.lineTo(x, y + 15);
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(x, y, 10, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Draw some demo voxels if no data
    if (!grid || !grid.data || grid.data.every(v => v <= 0)) {
      const time = Date.now() / 1000;
      for (let i = 0; i < 20; i++) {
        const x = 100 + Math.sin(time + i) * 80 + i * 10;
        const y = 200 + Math.cos(time + i * 0.7) * 60;
        const radius = 8 + Math.sin(time * 2 + i) * 3;

        const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
        const hue = (i * 30) % 360;
        gradient.addColorStop(0, `hsla(${hue}, 80%, 60%, 0.8)`);
        gradient.addColorStop(1, `hsla(${hue}, 80%, 60%, 0)`);

        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();
      }
    }
  }, [grid, particles, estimate, canvasRef]);

  return canvasRef;
}

/**
 * Heatmap main component - simple 2D version
 */
function Heatmap3D({
  grid,
  particles,
  estimate,
  opacity = 0.6,
  showAxes = true,
  showGrid = true,
}) {
  const canvas = useMemo(() => Heatmap2D({ grid, particles, estimate }), [grid, particles, estimate]);

  return (
    <div className="heatmap-container" style={{ background: '#071423', position: 'relative' }}>
      <div style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <div style={{ width: '100%', height: '100%', position: 'relative' }}>
          <div ref={(el) => {
            if (el && !el.firstChild) {
              el.appendChild(canvas);
            }
          }} style={{ width: '100%', height: '100%' }} />
        </div>
      </div>

      <div className="heatmap-legend">
        <div className="legend-title">浓度</div>
        <div className="legend-bar">
          <span className="legend-low">低</span>
          <div className="legend-gradient"></div>
          <span className="legend-high">高</span>
        </div>
      </div>

      <div style={{
        position: 'absolute',
        top: '10px',
        left: '10px',
        background: 'rgba(7, 20, 35, 0.85)',
        border: '1px solid rgba(148, 163, 184, 0.15)',
        borderRadius: '8px',
        padding: '10px 14px',
        fontSize: '12px',
        color: '#94a3b8'
      }}>
        2D 热力图模式 (简化版)
      </div>
    </div>
  );
}

export default Heatmap3D;
