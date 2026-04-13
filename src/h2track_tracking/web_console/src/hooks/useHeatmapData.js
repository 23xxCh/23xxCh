/**
 * useHeatmapData hook for WebSocket connection to heatmap endpoint.
 *
 * Connects to /ws/heatmap WebSocket endpoint, parses incoming messages,
 * decodes base64 grid data, and returns the heatmap state.
 */
import { useCallback, useEffect, useRef, useState } from "react";

/**
 * @typedef {Object} GridData
 * @property {number} resolution - Grid resolution in meters
 * @property {[number, number, number]} dimensions - Grid dimensions [nx, ny, nz]
 * @property {[number, number, number]} origin - Grid origin [x, y, z]
 * @property {string} data - Base64-encoded float32 array of concentration values
 */

/**
 * @typedef {Object} ParticleData
 * @property {[[number, number]]} positions - Array of [x, y] positions
 * @property {[number]} weights - Array of particle weights
 */

/**
 * @typedef {Object} EstimateData
 * @property {[number, number]} position - Estimated position [x, y]
 * @property {number} confidence - Confidence value [0, 1]
 */

/**
 * @typedef {Object} HeatmapData
 * @property {GridData | null} grid - Concentration grid data
 * @property {ParticleData | null} particles - Particle filter data
 * @property {EstimateData | null} estimate - Source estimate
 * @property {boolean} connected - WebSocket connection status
 * @property {string | null} error - Error message if any
 */

/**
 * Decode base64-encoded grid data to Float32Array.
 * @param {string} base64Data - Base64-encoded float32 data
 * @returns {Float32Array | null} Decoded float32 array or null on error
 */
function decodeGridData(base64Data) {
  if (!base64Data || typeof base64Data !== "string") {
    return null;
  }
  try {
    const binaryString = atob(base64Data);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return new Float32Array(bytes.buffer);
  } catch {
    return null;
  }
}

/**
 * Parse heatmap update message from WebSocket.
 * @param {Object} message - Raw WebSocket message
 * @returns {Object} Parsed heatmap data
 */
function parseHeatmapMessage(message) {
  const result = {
    grid: null,
    particles: null,
    estimate: null,
    timestamp: null,
  };

  if (!message || typeof message !== "object") {
    return result;
  }

  result.timestamp = message.timestamp || null;

  // Parse grid data
  if (message.grid && typeof message.grid === "object") {
    const grid = message.grid;
    const decodedData = decodeGridData(grid.data);

    result.grid = {
      resolution: typeof grid.resolution === "number" ? grid.resolution : 0.5,
      dimensions: Array.isArray(grid.dimensions)
        ? grid.dimensions.map((d) => Math.max(1, Math.floor(d)))
        : [10, 10, 5],
      origin: Array.isArray(grid.origin) ? grid.origin : [0, 0, 0],
      data: decodedData,
    };
  }

  // Parse particles
  if (message.particles && typeof message.particles === "object") {
    const particles = message.particles;
    if (Array.isArray(particles.positions)) {
      result.particles = {
        positions: particles.positions.filter(
          (p) => Array.isArray(p) && p.length >= 2
        ),
        weights: Array.isArray(particles.weights) ? particles.weights : [],
      };
    }
  }

  // Parse estimate
  if (message.estimate && typeof message.estimate === "object") {
    const estimate = message.estimate;
    if (
      Array.isArray(estimate.position) &&
      estimate.position.length >= 2 &&
      typeof estimate.confidence === "number"
    ) {
      result.estimate = {
        position: [estimate.position[0], estimate.position[1]],
        confidence: Math.max(0, Math.min(1, estimate.confidence)),
      };
    }
  }

  return result;
}

/**
 * React hook for WebSocket heatmap data.
 *
 * @returns {HeatmapData} Heatmap data state
 */
export function useHeatmapData() {
  const [state, setState] = useState({
    grid: null,
    particles: null,
    estimate: null,
    connected: false,
    error: null,
  });

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const mountedRef = useRef(true);
  const connectionSeqRef = useRef(0); // Track connection sequence to prevent race conditions

  const connect = useCallback(() => {
    if (!mountedRef.current) {
      return;
    }

    // Increment connection sequence
    const currentSeq = ++connectionSeqRef.current;

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    // Create WebSocket connection
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/heatmap`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current || connectionSeqRef.current !== currentSeq) {
          ws.close();
          return;
        }
        setState((prev) => ({ ...prev, connected: true, error: null }));
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current || connectionSeqRef.current !== currentSeq) {
          return;
        }

        try {
          const message = JSON.parse(event.data);

          // Handle status messages
          if (message.type === "status") {
            return;
          }

          // Handle heatmap update
          if (message.type === "heatmap_update") {
            const parsed = parseHeatmapMessage(message);
            setState((prev) => ({
              ...prev,
              grid: parsed.grid,
              particles: parsed.particles,
              estimate: parsed.estimate,
            }));
          }
        } catch {
          // Ignore parse errors
        }
      };

      ws.onerror = () => {
        if (!mountedRef.current || connectionSeqRef.current !== currentSeq) {
          return;
        }
        setState((prev) => ({
          ...prev,
          connected: false,
          error: "WebSocket connection error",
        }));
      };

      ws.onclose = () => {
        if (!mountedRef.current) {
          return;
        }
        // Only update state if this is still the current connection
        if (connectionSeqRef.current === currentSeq) {
          setState((prev) => ({ ...prev, connected: false }));
          wsRef.current = null;
        }

        // Schedule reconnect only if this is the current connection
        if (connectionSeqRef.current === currentSeq) {
          if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
          }
          reconnectTimeoutRef.current = setTimeout(() => {
            if (mountedRef.current) {
              connect();
            }
          }, 3000);
        }
      };
    } catch (err) {
      setState((prev) => ({
        ...prev,
        connected: false,
        error: `Failed to connect: ${err.message || "Unknown error"}`,
      }));
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const pause = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send("pause");
    }
  }, []);

  const resume = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send("resume");
    }
  }, []);

  return {
    ...state,
    pause,
    resume,
  };
}

export default useHeatmapData;
