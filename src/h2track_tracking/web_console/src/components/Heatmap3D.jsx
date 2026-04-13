/**
 * Simple Heatmap component - no complex dependencies
 */
import { useEffect, useRef } from "react";

/**
 * Heatmap3D main component - super simple 2D canvas version
 */
function Heatmap3D({
  grid,
  particles,
  estimate,
  opacity = 0.6,
  showAxes = true,
  showGrid = true,
  worldBounds = { x: [-10, 10], y: [-10, 10] }, // Configurable world bounds
}) {
  const canvasRef = useRef(null);
  const animationRef = useRef(null);
  const dataRef = useRef({ grid, particles, estimate });

  // Update data ref when props change
  useEffect(() => {
    dataRef.current = { grid, particles, estimate };
  }, [grid, particles, estimate]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    const resize = () => {
      const rect = canvas.parentElement.getBoundingClientRect();
      canvas.width = rect.width || 400;
      canvas.height = rect.height || 400;
    };
    resize();
    window.addEventListener('resize', resize);

    // Calculate world bounds
    const worldWidth = worldBounds.x[1] - worldBounds.x[0];
    const worldHeight = worldBounds.y[1] - worldBounds.y[0];

    // Helper to transform world coordinates to canvas coordinates
    const worldToCanvas = (x, y, w, h) => {
      const canvasX = ((x - worldBounds.x[0]) / worldWidth) * w;
      const canvasY = h - ((y - worldBounds.y[0]) / worldHeight) * h;
      return [canvasX, canvasY];
    };

    // Animation function
    const animate = (time) => {
      const w = canvas.width;
      const h = canvas.height;

      // Clear
      ctx.fillStyle = '#071423';
      ctx.fillRect(0, 0, w, h);

      // Draw grid
      ctx.strokeStyle = 'rgba(39, 71, 104, 0.5)';
      ctx.lineWidth = 1;
      const gridSize = 40;
      for (let x = 0; x < w; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let y = 0; y < h; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      // Get latest data from ref
      const { grid: currentGrid, particles: currentParticles, estimate: currentEstimate } = dataRef.current;

      // Draw particles if available
      if (currentParticles && currentParticles.positions && currentParticles.positions.length > 0) {
        const maxWeight = Math.max(...(currentParticles.weights || [1]), 0.01);
        currentParticles.positions.forEach((pos, i) => {
          const weight = (currentParticles.weights && currentParticles.weights[i]) || 0.5;
          const normalizedWeight = weight / maxWeight;
          const [x, y] = worldToCanvas(pos[0], pos[1], w, h);

          ctx.beginPath();
          ctx.arc(x, y, 3 + normalizedWeight * 3, 0, Math.PI * 2);
          const intensity = Math.floor(100 + normalizedWeight * 155);
          ctx.fillStyle = `rgba(64, ${intensity}, ${intensity}, 0.8)`;
          ctx.fill();
        });
      }

      // Draw estimate if available
      if (currentEstimate && currentEstimate.position) {
        const [x, y] = worldToCanvas(currentEstimate.position[0], currentEstimate.position[1], w, h);

        // Draw crosshair
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(x - 20, y);
        ctx.lineTo(x + 20, y);
        ctx.moveTo(x, y - 20);
        ctx.lineTo(x, y + 20);
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(x, y, 15, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Draw animated demo circles
      const t = time / 1000;
      const hasData = currentGrid && currentGrid.data && currentGrid.data.some(v => v > 0);
      const hasParticles = currentParticles && currentParticles.positions && currentParticles.positions.length > 0;
      const hasEstimate = currentEstimate && currentEstimate.position;

      if (!hasData && !hasParticles && !hasEstimate) {
        for (let i = 0; i < 15; i++) {
          const x = w/2 + Math.sin(t + i * 0.7) * (w/3) + i * 10;
          const y = h/2 + Math.cos(t * 0.8 + i * 0.5) * (h/3);
          const radius = 8 + Math.sin(t * 2 + i) * 4;

          const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
          const hue = (i * 30 + t * 20) % 360;
          gradient.addColorStop(0, `hsla(${hue}, 80%, 60%, 0.9)`);
          gradient.addColorStop(1, `hsla(${hue}, 80%, 60%, 0)`);

          ctx.beginPath();
          ctx.arc(x, y, radius, 0, Math.PI * 2);
          ctx.fillStyle = gradient;
          ctx.fill();
        }
      }

      // Draw some status text
      ctx.fillStyle = 'rgba(148, 163, 184, 0.8)';
      ctx.font = '12px sans-serif';
      ctx.fillText('热力图 - 2D模式', 15, 25);

      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener('resize', resize);
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [worldBounds]);

  return (
    <div className="heatmap-container" style={{ background: '#071423', position: 'relative', width: '100%', height: '100%' }}>
      <canvas
        ref={canvasRef}
        style={{
          width: '100%',
          height: '100%',
          display: 'block'
        }}
      />

      <div className="heatmap-legend">
        <div className="legend-title">浓度</div>
        <div className="legend-bar">
          <span className="legend-low">低</span>
          <div className="legend-gradient"></div>
          <span className="legend-high">高</span>
        </div>
      </div>
    </div>
  );
}

export default Heatmap3D;
