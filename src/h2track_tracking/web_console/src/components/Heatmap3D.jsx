/**
 * Heatmap3D component for 3D gas concentration visualization.
 *
 * Uses Three.js via @react-three/fiber for rendering.
 * Displays concentration values as colored voxels with color scale:
 * blue (low) -> yellow -> red (high)
 */
import { useMemo, useRef } from "react";
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
 * Voxel grid component for concentration visualization.
 */
function VoxelGrid({ grid, opacity = 0.6, threshold = 0.0 }) {
  const meshRef = useRef();

  const { positions, colors, scales } = useMemo(() => {
    if (!grid || !grid.data) {
      return { positions: [], colors: [], scales: [] };
    }

    const { dimensions, origin, resolution, data } = grid;
    const [nx, ny, nz] = dimensions;
    const [ox, oy, oz] = origin;

    const positions = [];
    const colors = [];
    const scales = [];

    // Find max value for normalization
    let maxVal = 0;
    for (let i = 0; i < data.length; i++) {
      if (data[i] > maxVal) maxVal = data[i];
    }

    if (maxVal <= 0) maxVal = 1;

    // Create voxels for non-zero values
    for (let zi = 0; zi < nz; zi++) {
      for (let yi = 0; yi < ny; yi++) {
        for (let xi = 0; xi < nx; xi++) {
          const idx = xi + yi * nx + zi * nx * ny;
          const val = data[idx];

          if (val > threshold) {
            const normalizedVal = val / maxVal;
            const [r, g, b] = getColor(normalizedVal);

            positions.push(
              ox + (xi + 0.5) * resolution,
              oz + (zi + 0.5) * resolution,
              oy + (yi + 0.5) * resolution
            );

            colors.push(r, g, b);
            scales.push(normalizedVal);
          }
        }
      }
    }

    return { positions, colors, scales };
  }, [grid, threshold]);

  if (positions.length === 0) {
    return null;
  }

  return (
    <group ref={meshRef}>
      {positions.map((_, i) => {
        const idx = i / 3;
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
            <boxGeometry args={[grid.resolution, grid.resolution, grid.resolution]} />
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
    const maxWeight = Math.max(...weights, 0.01);

    const positions = [];
    const colors = [];

    for (let i = 0; i < posArray.length; i++) {
      const [x, y] = posArray[i];
      const weight = weights[i] || 0;
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
      <ambientLight intensity={0.4} />
      <directionalLight position={[10, 20, 10]} intensity={0.8} />
      <pointLight position={[-10, 10, -10]} intensity={0.4} />
    </>
  );
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

  return (
    <div className="heatmap-container">
      <Canvas
        camera={{
          position: [centerX + 15, 15, centerZ + 15],
          fov: 50,
          near: 0.1,
          far: 1000,
        }}
        gl={{ antialias: true, alpha: true }}
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

        <VoxelGrid grid={grid} opacity={opacity} />
        <ParticleCloud particles={particles} />
        <EstimateMarker estimate={estimate} />

        <OrbitControls
          makeDefault
          enableDamping
          dampingFactor={0.05}
          minDistance={2}
          maxDistance={100}
          maxPolarAngle={Math.PI / 2.1}
        />
      </Canvas>

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
