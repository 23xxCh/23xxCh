/**
 * Heatmap3D component for 3D gas concentration visualization.
 *
 * Uses Three.js via @react-three/fiber for rendering.
 * Displays concentration values as colored voxels with color scale:
 * blue (low) -> yellow -> red (high)
 */
import { useMemo, useRef, useState, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Grid } from "@react-three/drei";
import * as THREE from "three";

/**
 * Custom Axes helper component.
 */
function Axes({ size = 5 }) {
  return (
    <group>
      {/* X axis - red */}
      <line>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={2}
            array={new Float32Array([0, 0, 0, size, 0, 0])}
            itemSize={3}
          />
        </bufferGeometry>
        <lineBasicMaterial color="red" />
      </line>
      {/* Y axis - green */}
      <line>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={2}
            array={new Float32Array([0, 0, 0, 0, size, 0])}
            itemSize={3}
          />
        </bufferGeometry>
        <lineBasicMaterial color="green" />
      </line>
      {/* Z axis - blue */}
      <line>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={2}
            array={new Float32Array([0, 0, 0, 0, 0, size])}
            itemSize={3}
          />
        </bufferGeometry>
        <lineBasicMaterial color="blue" />
      </line>
    </group>
  );
}

/**
 * Color scale: blue (low) -> yellow -> red (high)
 * @param {number} value - Normalized value [0, 1]
 * @returns {[number, number, number]} RGB color values
 */
function getColor(value) {
  const v = Math.max(0, Math.min(1, value));

  if (v < 0.5) {
    // Blue to Yellow
    const t = v * 2;
    return [t, t, 1 - t];
  } else {
    // Yellow to Red
    const t = (v - 0.5) * 2;
    return [1, 1 - t, 0];
  }
}

/**
 * Simple box component for demo/empty state
 */
function DemoBox() {
  const meshRef = useRef();

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.x += 0.01;
      meshRef.current.rotation.y += 0.02;
    }
  });

  return (
    <mesh ref={meshRef}>
      <boxGeometry args={[2, 2, 2]} />
      <meshStandardMaterial color="#6366f1" wireframe />
    </mesh>
  );
}

/**
 * Voxel grid component for concentration visualization.
 */
function VoxelGrid({ grid, opacity = 0.6, threshold = 0.0 }) {
  const meshRef = useRef();

  const { positions, colors, scales, voxelResolution } = useMemo(() => {
    if (!grid || !grid.data) {
      return { positions: [], colors: [], scales: [], voxelResolution: 0.5 };
    }

    const { dimensions, origin, resolution, data } = grid;
    const [nx, ny, nz] = dimensions || [10, 10, 5];
    const [ox, oy, oz] = origin || [0, 0, 0];
    const res = resolution || 0.5;

    const positions = [];
    const colors = [];
    const scales = [];

    // Find max value for normalization
    let maxVal = 0;
    for (let i = 0; i < data.length; i++) {
      if (data[i] > maxVal) maxVal = data[i];
    }

    if (maxVal <= 0) maxVal = 1;

    // Create voxels for non-zero values (limit to prevent performance issues)
    let voxelCount = 0;
    const maxVoxels = 500;

    for (let zi = 0; zi < nz && voxelCount < maxVoxels; zi++) {
      for (let yi = 0; yi < ny && voxelCount < maxVoxels; yi++) {
        for (let xi = 0; xi < nx && voxelCount < maxVoxels; xi++) {
          const idx = xi + yi * nx + zi * nx * ny;
          const val = data[idx] || 0;

          if (val > threshold) {
            const normalizedVal = val / maxVal;
            const [r, g, b] = getColor(normalizedVal);

            positions.push(
              ox + (xi + 0.5) * res,
              oz + (zi + 0.5) * res,
              oy + (yi + 0.5) * res
            );

            colors.push(r, g, b);
            scales.push(normalizedVal);
            voxelCount++;
          }
        }
      }
    }

    return { positions, colors, scales, voxelResolution: res };
  }, [grid, threshold]);

  if (positions.length === 0) {
    return null;
  }

  return (
    <group ref={meshRef}>
      {positions.map((_, i) => {
        const idx = Math.floor(i / 3);
        const x = positions[idx * 3];
        const y = positions[idx * 3 + 1];
        const z = positions[idx * 3 + 2];
        const r = colors[idx * 3];
        const g = colors[idx * 3 + 1];
        const b = colors[idx * 3 + 2];
        const scale = Math.max(0.3, scales[idx]);

        return (
          <mesh
            key={`voxel-${idx}`}
            position={[x, y, z]}
            scale={[scale * 0.8, scale * 0.8, scale * 0.8]}
          >
            <boxGeometry args={[voxelResolution, voxelResolution, voxelResolution]} />
            <meshStandardMaterial
              color={new THREE.Color(r, g, b)}
              transparent
              opacity={opacity * scale}
              side={THREE.DoubleSide}
            />
          </mesh>
        );
      })}
    </group>
  );
}

/**
 * Particle cloud component for particle filter visualization.
 */
function ParticleCloud({ particles }) {
  const pointsRef = useRef();

  const { positions, colors } = useMemo(() => {
    if (!particles || !particles.positions || particles.positions.length === 0) {
      return { positions: [], colors: [] };
    }

    const { positions: posArray, weights } = particles;
    const maxWeight = Math.max(...(weights || [1]), 0.01);

    const positions = [];
    const colors = [];

    // Limit particles for performance
    const maxParticles = 1000;
    const step = Math.max(1, Math.floor(posArray.length / maxParticles));

    for (let i = 0; i < posArray.length; i += step) {
      const [x, y] = posArray[i];
      const weight = (weights && weights[i]) || 0;
      const normalizedWeight = weight / maxWeight;

      // Position at y=0 (2D particles on XY plane)
      positions.push(x, 0.1, y);

      // Color based on weight: cyan for low, white for high
      const intensity = 0.5 + 0.5 * normalizedWeight;
      colors.push(0.2, intensity, intensity);
    }

    return { positions, colors };
  }, [particles]);

  if (positions.length === 0) {
    return null;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(positions, 3)
  );
  geometry.setAttribute(
    "color",
    new THREE.Float32BufferAttribute(colors, 3)
  );

  return (
    <points ref={pointsRef}>
      <bufferGeometry attach="geometry" {...geometry} />
      <pointsMaterial
        attach="material"
        size={0.15}
        vertexColors
        transparent
        opacity={0.8}
        sizeAttenuation
      />
    </points>
  );
}

/**
 * Source estimate marker component.
 */
function EstimateMarker({ estimate }) {
  const markerRef = useRef();

  useFrame((state) => {
    if (markerRef.current) {
      // Animate marker rotation
      markerRef.current.rotation.y += 0.02;
    }
  });

  if (!estimate || !estimate.position) {
    return null;
  }

  const [x, y] = estimate.position;
  const confidence = estimate.confidence || 0;

  return (
    <group ref={markerRef} position={[x, 0.5, y]}>
      {/* Cone marker */}
      <mesh rotation={[Math.PI, 0, 0]} position={[0, 0.5, 0]}>
        <coneGeometry args={[0.3, 0.6, 8]} />
        <meshStandardMaterial
          color={new THREE.Color(1, 1 - confidence, 0)}
          emissive={new THREE.Color(1, 0.5, 0)}
          emissiveIntensity={0.3}
        />
      </mesh>
      {/* Base sphere */}
      <mesh position={[0, 0.1, 0]}>
        <sphereGeometry args={[0.15, 16, 16]} />
        <meshStandardMaterial
          color={new THREE.Color(1, 1 - confidence, 0)}
          transparent
          opacity={0.7}
        />
      </mesh>
    </group>
  );
}

/**
 * Scene lighting setup.
 */
function Lighting() {
  return (
    <>
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 20, 10]} intensity={0.8} />
      <pointLight position={[-10, 10, -10]} intensity={0.4} />
    </>
  );
}

/**
 * Error boundary component for Three.js canvas
 */
function CanvasErrorBoundary({ children }) {
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    const handleError = (event) => {
      if (event.message?.includes('WebGL') || event.message?.includes('Three')) {
        setHasError(true);
      }
    };

    window.addEventListener('error', handleError);
    return () => window.removeEventListener('error', handleError);
  }, []);

  if (hasError) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        color: '#94a3b8',
        fontSize: '14px'
      }}>
        3D渲染不可用，请刷新页面重试
      </div>
    );
  }

  return children;
}

/**
 * Heatmap3D main component.
 *
 * @param {Object} props
 * @param {Object} props.grid - Grid data from useHeatmapData hook
 * @param {Object} props.particles - Particle data from useHeatmapData hook
 * @param {Object} props.estimate - Estimate data from useHeatmapData hook
 * @param {number} props.opacity - Voxel opacity (default 0.6)
 * @param {boolean} props.showAxes - Show axes helper (default true)
 * @param {boolean} props.showGrid - Show grid helper (default true)
 */
function Heatmap3D({
  grid,
  particles,
  estimate,
  opacity = 0.6,
  showAxes = true,
  showGrid = true,
}) {
  // Calculate scene bounds
  const sceneBounds = useMemo(() => {
    if (!grid || !grid.dimensions) {
      return { minX: -10, maxX: 10, minZ: -10, maxZ: 10 };
    }

    const { dimensions, origin, resolution } = grid;
    const [nx, ny] = dimensions;
    const [ox, oy] = origin;

    return {
      minX: ox,
      maxX: ox + nx * resolution,
      minZ: oy,
      maxZ: oy + ny * resolution,
    };
  }, [grid]);

  const centerX = (sceneBounds.minX + sceneBounds.maxX) / 2;
  const centerZ = (sceneBounds.minZ + sceneBounds.maxZ) / 2;

  // Check if we have any data to display
  const hasData = useMemo(() => {
    return (grid && grid.data && grid.data.some(v => v > 0)) ||
           (particles && particles.positions && particles.positions.length > 0) ||
           (estimate && estimate.position);
  }, [grid, particles, estimate]);

  return (
    <div className="heatmap-container">
      <CanvasErrorBoundary>
        <Canvas
          camera={{
            position: [centerX + 15, 15, centerZ + 15],
            fov: 50,
            near: 0.1,
            far: 1000,
          }}
          gl={{ antialias: true, alpha: true }}
          fallback={
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: '#94a3b8',
              fontSize: '14px'
            }}>
              正在加载3D视图...
            </div>
          }
        >
          <color attach="background" args={["#071423"]} />

          <Lighting />

          {showAxes && <Axes size={5} />}
          {showGrid && (
            <Grid
              args={[20, 20]}
              cellSize={1}
              cellThickness={0.5}
              cellColor="#274768"
              sectionSize={5}
              sectionThickness={1}
              sectionColor="#3a5f85"
              fadeDistance={50}
              fadeStrength={1}
              position={[centerX, 0, centerZ]}
            />
          )}

          {hasData ? (
            <>
              <VoxelGrid grid={grid} opacity={opacity} />
              <ParticleCloud particles={particles} />
              <EstimateMarker estimate={estimate} />
            </>
          ) : (
            <DemoBox />
          )}

          <OrbitControls
            makeDefault
            enableDamping
            dampingFactor={0.05}
            minDistance={2}
            maxDistance={100}
            maxPolarAngle={Math.PI / 2.1}
          />
        </Canvas>
      </CanvasErrorBoundary>

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
