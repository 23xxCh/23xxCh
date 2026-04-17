import { useState, useEffect, useCallback } from "react";
import { Map, AlertCircle, CheckCircle2 } from "lucide-react";

/**
 * SceneSelector component for multi-map support.
 *
 * Fetches available scenes from /api/scenes and provides a dropdown
 * for selecting which map to use for simulation.
 *
 * @param {Object} props
 * @param {string} props.value - Currently selected scene ID
 * @param {function} props.onChange - Callback when scene changes
 * @param {boolean} props.disabled - Whether the selector is disabled
 */
export function SceneSelector({ value, onChange, disabled = false }) {
  const [scenes, setScenes] = useState([]);
  const [defaultScene, setDefaultScene] = useState("warehouse");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchScenes = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch("/api/scenes");
      if (!response.ok) {
        throw new Error(`Failed to fetch scenes: ${response.status}`);
      }
      const data = await response.json();
      const sceneList = data.scenes || [];
      setScenes(sceneList);
      setDefaultScene(data.default || "warehouse");
    } catch (err) {
      setError(err.message);
      // Fallback to default scenes if API fails
      setScenes([
        { id: "warehouse", name: "Warehouse", description: "仓库场景" },
        { id: "baseline", name: "Baseline", description: "实验室场景" }
      ]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchScenes();
  }, [fetchScenes]);

  // Validate current value against available scenes
  useEffect(() => {
    if (scenes.length > 0 && value) {
      const validScene = scenes.find((s) => s.id === value);
      if (!validScene) {
        // If current value is invalid, switch to default
        onChange(defaultScene);
      }
    }
  }, [scenes, value, defaultScene, onChange]);

  const handleChange = (e) => {
    const selectedId = e.target.value;
    onChange(selectedId);
  };

  const selectedScene = scenes.find((s) => s.id === value);

  return (
    <div className="scene-selector">
      <div className="row">
        <label className="scene-label">
          <Map size={16} className="scene-icon" />
          场景选择
        </label>
        <div className="scene-select-wrapper">
          <select
            value={value}
            onChange={handleChange}
            disabled={disabled || loading}
            className={`scene-select ${error ? "error" : ""}`}
          >
            {loading ? (
              <option value="">加载中...</option>
            ) : (
              scenes.map((scene) => (
                <option key={scene.id} value={scene.id}>
                  {scene.name || scene.id}
                </option>
              ))
            )}
          </select>
          {error ? (
            <AlertCircle size={16} className="scene-status-icon error" />
          ) : (
            <CheckCircle2 size={16} className="scene-status-icon success" />
          )}
        </div>
      </div>

      {selectedScene && (
        <div className="scene-info">
          <p className="scene-description">
            {selectedScene.description || "暂无描述"}
          </p>
          <div className="scene-meta">
            {selectedScene.use_gaden !== undefined && (
              <span className={`scene-badge ${selectedScene.use_gaden ? "gaden" : "simplified"}`}>
                {selectedScene.use_gaden ? "GADEN仿真" : "简化气体场"}
              </span>
            )}
            {selectedScene.use_slam && (
              <span className="scene-badge slam">SLAM</span>
            )}
            {selectedScene.metadata?.patrol_points_count !== undefined && (
              <span className="scene-badge">
                {selectedScene.metadata.patrol_points_count} 巡逻点
              </span>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="scene-error">
          <AlertCircle size={14} />
          <span>{error}</span>
          <button onClick={fetchScenes} className="scene-retry-btn">
            重试
          </button>
        </div>
      )}
    </div>
  );
}

export default SceneSelector;
