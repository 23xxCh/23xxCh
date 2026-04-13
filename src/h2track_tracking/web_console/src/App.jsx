import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  Wind,
  Zap,
  Search,
  Cpu,
  Play,
  Square,
  RefreshCw,
  Settings,
  MessageSquare,
  Terminal,
  CheckCircle2,
  AlertCircle,
  XCircle,
  ChevronRight,
  Map,
  Brain,
  FileText,
  Radar,
  Save,
  Cloud,
  Bot
} from "lucide-react";
import Heatmap3D from "./components/Heatmap3D";
import { useHeatmapData } from "./hooks/useHeatmapData";

const DEFAULT_PROFILE = {
  scene: "warehouse",
  use_gaden: "true",
  use_slam: "true",
  use_rviz: "true",
  headless: "false"
};

const TAB_LIST = [
  { id: "overview", label: "总览", icon: Activity },
  { id: "heatmap", label: "热力图", icon: Map },
  { id: "ai", label: "AI 策略", icon: Brain },
  { id: "diagnostics", label: "诊断日志", icon: Terminal }
];

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data?.detail || data?.message || `请求失败(${response.status})`;
    throw new Error(detail);
  }
  return data;
}

function valueByPath(obj, path, fallback = "N/A") {
  const target = path.split(".").reduce((acc, key) => (acc == null ? acc : acc[key]), obj);
  return target == null ? fallback : target;
}

function modeLabel(mode) {
  const map = {
    PATROL: "巡检",
    SEEK_CONFIRM: "确认",
    SEEK_TRACK: "追踪",
    SOURCE_FOUND: "已找到源"
  };
  return map[String(mode || "").toUpperCase()] || (mode || "N/A");
}

function gasSignalLabel(status) {
  const map = {
    active: "正常供数",
    flatline_zero: "全零平线",
    stale: "话题过期",
    no_samples: "未收到原始读数",
    simplified_field: "简化气体场"
  };
  return map[String(status || "").toLowerCase()] || "未知";
}

function safeNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function parseTabFromHash() {
  const hash = String(window.location.hash || "").trim();
  if (!hash.startsWith("#/")) {
    return "overview";
  }
  const tab = hash.replace("#/", "");
  return TAB_LIST.some((item) => item.id === tab) ? tab : "overview";
}

function TrendChart({ points, color }) {
  const width = 520;
  const height = 110;
  const pad = 10;
  const list = points.slice(-80);
  if (list.length <= 1) {
    return <div className="trend-empty">暂无趋势数据</div>;
  }
  const ys = list.map((item) => safeNumber(item.value, 0));
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const span = Math.max(maxY - minY, 1e-6);
  const polyline = list
    .map((item, idx) => {
      const x = pad + (idx / (list.length - 1)) * (width - 2 * pad);
      const y = height - pad - ((safeNumber(item.value, 0) - minY) / span) * (height - 2 * pad);
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="trend-svg" aria-label="trend-chart">
      <polyline fill="none" stroke={color} strokeWidth="2.4" points={polyline} />
    </svg>
  );
}

function LogRow({ row }) {
  const text = String(row?.text || "");
  const source = String(row?.source || "system");
  const isErr = /error|failed|exception|traceback/i.test(text);
  return (
    <div className={`log-row ${isErr ? "err" : ""}`}>
      <span className={`tag tag-${source}`}>{source}</span>
      <span className="ts">{row?.timestamp || ""}</span>
      <span className="text">{text}</span>
    </div>
  );
}

function PhaseTimeline({ timeline }) {
  const rows = Array.isArray(timeline) ? timeline.slice(-12) : [];
  if (!rows.length) {
    return <div className="trend-empty">暂无阶段时间线</div>;
  }
  return (
    <div className="phase-list">
      {rows.map((row) => {
        const phase = String(row?.phase || "N/A");
        const reason = String(row?.reason || "-");
        const duration = row?.duration_ms == null ? "进行中" : `${Number(row.duration_ms).toFixed(0)} ms`;
        const key = `${phase}-${row?.start_ts || row?.end_ts || Date.now()}-${reason.slice(0, 20)}`;
        return (
          <div key={key} className="phase-item">
            <strong>{phase}</strong>
            <span>{duration}</span>
            <span className="muted">原因: {reason}</span>
          </div>
        );
      })}
    </div>
  );
}

function StatCard({ title, value, icon: Icon }) {
  return (
    <article className="card">
      <div className="card-header">
        <span>{title}</span>
        <div className="card-icon">
          <Icon size={18} style={{ color: "#818cf8" }} />
        </div>
      </div>
      <strong>{String(value)}</strong>
    </article>
  );
}

export function App() {
  const [activeTab, setActiveTab] = useState(parseTabFromHash);
  const [status, setStatus] = useState({});
  const [metrics, setMetrics] = useState({});
  const [logs, setLogs] = useState([]);
  const [conn, setConn] = useState("连接中");
  const [toast, setToast] = useState("");
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [autoScroll, setAutoScroll] = useState(true);
  const [profile, setProfile] = useState(DEFAULT_PROFILE);
  const [uiMeta, setUiMeta] = useState({ mode: "legacy_inline", bundle_ready: false });
  const [llmProfiles, setLlmProfiles] = useState([]);
  const [activeProfileId, setActiveProfileId] = useState("");
  const [llmForm, setLlmForm] = useState({
    name: "astron-code-latest-maas",
    base_url: "",
    api_key: "",
    model: "",
    protocol: "dual"
  });
  const [llmPrompt, setLlmPrompt] = useState("分析当前状态并给出下一步建议");
  const [llmReply, setLlmReply] = useState("");
  const [llmActions, setLlmActions] = useState([]);
  const [llmAuditRows, setLlmAuditRows] = useState([]);
  const [llmHistoryRows, setLlmHistoryRows] = useState([]);

  // Heatmap WebSocket data
  const heatmapData = useHeatmapData();

  const logBoxRef = useRef(null);
  const eventSourceRef = useRef(null);

  const showToast = (message) => {
    setToast(message);
    window.clearTimeout(showToast._t);
    showToast._t = window.setTimeout(() => setToast(""), 2800);
  };

  const refreshStatus = async () => {
    const data = await fetchJson("/api/sim/status");
    setStatus(data);
    const next = data?.launch_profile || DEFAULT_PROFILE;
    setProfile({
      scene: String(next.scene || "warehouse"),
      use_gaden: String(next.use_gaden || "true"),
      use_slam: String(next.use_slam || "true"),
      use_rviz: String(next.use_rviz || "true"),
      headless: String(next.headless || "false")
    });
  };

  const refreshMetrics = async () => {
    const data = await fetchJson("/api/metrics/recent?limit=260");
    setMetrics(data);
  };

  const refreshLogs = async () => {
    const data = await fetchJson("/api/logs/recent?limit=800");
    setLogs(data.logs || []);
  };

  const refreshUiMeta = async () => {
    const data = await fetchJson("/api/ui/meta");
    setUiMeta(data);
  };

  const loadLlmProfiles = async () => {
    const data = await fetchJson("/api/llm/profiles");
    const rows = Array.isArray(data.profiles) ? data.profiles : [];
    setLlmProfiles(rows);
    setActiveProfileId(String(data.active_profile_id || rows[0]?.id || ""));
  };

  const refreshLlmAudit = async () => {
    const [audit, history] = await Promise.all([
      fetchJson("/api/llm/audit?limit=120"),
      fetchJson("/api/llm/history?limit=80")
    ]);
    setLlmAuditRows(Array.isArray(audit.rows) ? audit.rows : []);
    setLlmHistoryRows(Array.isArray(history.rows) ? history.rows : []);
  };

  const connectSse = (afterId = 0) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    const es = new EventSource(`/api/logs/stream?after_id=${afterId}`);
    eventSourceRef.current = es;
    es.addEventListener("log", (evt) => {
      try {
        const row = JSON.parse(evt.data || "{}");
        setLogs((prev) => [...prev, row].slice(-2000));
      } catch {
        // ignore malformed row
      }
      setConn("已连接");
    });
    es.addEventListener("ping", () => setConn("已连接"));
    es.onerror = () => {
      setConn("重连中");
    };
  };

  useEffect(() => {
    const onHash = () => {
      setActiveTab(parseTabFromHash());
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    const bootstrap = async () => {
      await Promise.all([
        refreshUiMeta(),
        refreshStatus(),
        refreshMetrics(),
        refreshLogs(),
        loadLlmProfiles(),
        refreshLlmAudit()
      ]);
      connectSse(0);
    };
    bootstrap().catch((err) => showToast(`初始化失败: ${err.message}`));

    const timer = window.setInterval(() => {
      refreshStatus().catch(() => {});
      refreshMetrics().catch(() => {});
      if (activeTab === "ai") {
        refreshLlmAudit().catch(() => {});
      }
    }, 2200);

    return () => {
      window.clearInterval(timer);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [activeTab]);

  useEffect(() => {
    if (!autoScroll || !logBoxRef.current) {
      return;
    }
    logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight;
  }, [logs, autoScroll]);

  const filteredLogs = useMemo(() => {
    const q = query.trim().toLowerCase();
    return logs.filter((row) => {
      if (sourceFilter !== "all" && String(row?.source || "") !== sourceFilter) {
        return false;
      }
      if (!q) {
        return true;
      }
      return String(row?.text || "").toLowerCase().includes(q);
    });
  }, [logs, query, sourceFilter]);

  const setTab = (tab) => {
    const next = TAB_LIST.some((item) => item.id === tab) ? tab : "overview";
    window.location.hash = `/${next}`;
    setActiveTab(next);
  };

  const startSim = async () => {
    try {
      const data = await fetchJson("/api/sim/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile)
      });
      showToast(data.message || "启动请求已发送");
      await Promise.all([refreshStatus(), refreshMetrics(), refreshLogs()]);
    } catch (err) {
      showToast(`启动失败: ${err.message}`);
    }
  };

  const stopSim = async () => {
    try {
      const data = await fetchJson("/api/sim/stop", { method: "POST" });
      showToast(data.message || "停止请求已发送");
      await Promise.all([refreshStatus(), refreshMetrics()]);
    } catch (err) {
      showToast(`停止失败: ${err.message}`);
    }
  };

  const saveLlmProfile = async () => {
    try {
      await fetchJson("/api/llm/profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...llmForm, set_active: true })
      });
      showToast("模型配置已保存");
      await Promise.all([loadLlmProfiles(), refreshLlmAudit()]);
    } catch (err) {
      showToast(`保存失败: ${err.message}`);
    }
  };

  const activateProfile = async () => {
    if (!activeProfileId) {
      showToast("请选择一个模型配置");
      return;
    }
    try {
      await fetchJson(`/api/llm/profiles/${encodeURIComponent(activeProfileId)}/activate`, { method: "POST" });
      showToast("已设为当前模型");
      await refreshLlmAudit();
    } catch (err) {
      showToast(`激活失败: ${err.message}`);
    }
  };

  const checkProfile = async () => {
    if (!activeProfileId) {
      showToast("请选择一个模型配置");
      return;
    }
    try {
      const data = await fetchJson(`/api/llm/profiles/${encodeURIComponent(activeProfileId)}/check`, {
        method: "POST"
      });
      showToast(`连接通过: ${data.preview || data.protocol_used || "OK"}`);
    } catch (err) {
      showToast(`连接失败: ${err.message}`);
    }
  };

  const sendAi = async () => {
    if (!llmPrompt.trim()) {
      showToast("请输入 AI 指令");
      return;
    }
    try {
      const data = await fetchJson("/api/llm/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_id: activeProfileId,
          message: llmPrompt,
          include_context: true
        })
      });
      setLlmReply(String(data.analysis || ""));
      setLlmActions(Array.isArray(data.actions) ? data.actions : []);
      await refreshLlmAudit();
    } catch (err) {
      showToast(`AI 调用失败: ${err.message}`);
    }
  };

  const runAiOnce = async () => {
    if (!llmPrompt.trim()) {
      showToast("请输入 AI 目标");
      return;
    }
    try {
      const data = await fetchJson("/api/llm/loop/run-once", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_id: activeProfileId,
          objective: llmPrompt,
          include_context: true
        })
      });
      const chat = data.chat || {};
      setLlmReply(String(chat.analysis || data.message || "AI 单轮已执行"));
      setLlmActions(Array.isArray(chat.actions) ? chat.actions : []);
      await Promise.all([refreshStatus(), refreshMetrics(), refreshLogs(), refreshLlmAudit()]);
    } catch (err) {
      showToast(`单轮执行失败: ${err.message}`);
    }
  };

  const executeAction = async (action) => {
    if (!action || typeof action !== "object") {
      return;
    }
    const confirmMessage = `确认执行动作：${action.title || action.type || "未知动作"}？\n风险等级：${action.risk_level || "medium"}`;
    if (!window.confirm(confirmMessage)) {
      return;
    }
    try {
      const data = await fetchJson("/api/llm/action/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action })
      });
      showToast(data.message || "动作执行完成");
      await Promise.all([refreshStatus(), refreshMetrics(), refreshLogs(), refreshLlmAudit()]);
    } catch (err) {
      showToast(`动作执行失败: ${err.message}`);
    }
  };

  const navSuccess = safeNumber(valueByPath(metrics, "nav.goal_succeeded", 0));
  const navFail = safeNumber(valueByPath(metrics, "nav.failed_to_make_progress", 0));
  const navCancel = safeNumber(valueByPath(metrics, "nav.goal_canceled", 0));
  const navMean = valueByPath(metrics, "nav.mean_goal_time_sec", "N/A");
  const gasHistory = Array.isArray(valueByPath(metrics, "gas.history", [])) ? valueByPath(metrics, "gas.history", []) : [];
  const gasRaw = valueByPath(metrics, "gas.raw_current", "N/A");
  const gasSignalStatus = valueByPath(metrics, "gas.signal_status", "unknown");
  const gasSignalReason = valueByPath(metrics, "gas.signal_reason", "暂无气体链路诊断");
  const mode = valueByPath(metrics, "mode.current", "N/A");
  const gas = valueByPath(metrics, "gas.current", "N/A");
  const sourceFound = valueByPath(metrics, "source_found.current", "N/A");
  const phase = valueByPath(metrics, "phase.current", "N/A");
  const phaseTimeline = Array.isArray(valueByPath(metrics, "phase.timeline", [])) ? valueByPath(metrics, "phase.timeline", []) : [];
  const nodeRows = Array.isArray(valueByPath(metrics, "node_health.nodes", [])) ? valueByPath(metrics, "node_health.nodes", []) : [];
  const topicHealth = valueByPath(metrics, "topic_health", {});
  const gasRawTopic = topicHealth?.["/gaden/sensor_reading"] || {};
  const state = valueByPath(status, "state", "idle");
  const statusClass = `state-pill state-${String(state).toLowerCase()}`;

  const StatusIcon = state === "running" ? CheckCircle2 :
                    state === "error" ? XCircle : AlertCircle;

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-main">
          <div className="hero-icon">
            <Cloud size={28} color="white" />
          </div>
          <div className="hero-text">
            <h1>H2Track 仓库智能控制台</h1>
            <p>仿真启动、实时日志、AI 决策建议与执行审计</p>
          </div>
        </div>
        <div className="hero-right">
          <div className={statusClass}>
            <span className="state-dot" />
            <StatusIcon size={14} />
            {String(state).toUpperCase()}
          </div>
          <div className="conn">
            <span className="conn-dot" />
            {conn}
          </div>
        </div>
      </header>

      <nav className="top-nav">
        {TAB_LIST.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              className={`tab-btn ${activeTab === tab.id ? "active" : ""}`}
              onClick={() => setTab(tab.id)}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </nav>

      {toast ? <div className="toast">{toast}</div> : null}

      {activeTab === "overview" && (
        <>
          <section className="grid cards">
            <StatCard title="当前阶段" value={phase} icon={Zap} />
            <StatCard title="机器人模式" value={modeLabel(mode)} icon={Radar} />
            <StatCard title="气体浓度" value={String(gas)} icon={Wind} />
            <StatCard title="源点状态" value={String(sourceFound)} icon={Search} />
          </section>

          <section className="grid control-grid">
            <article className="panel">
              <div className="panel-header">
                <h2>仿真控制</h2>
                <Settings size={18} style={{ color: "var(--muted)" }} />
              </div>
              <div className="row">
                <label>场景</label>
                <select value={profile.scene} onChange={(e) => {
                  const val = e.target.value;
                  setProfile(prev => ({ ...prev, scene: val }));
                }}>
                  <option value="warehouse">warehouse</option>
                  <option value="baseline">baseline</option>
                </select>
              </div>
              <div className="row">
                <label>GADEN</label>
                <select value={profile.use_gaden} onChange={(e) => {
                  const val = e.target.value;
                  setProfile(prev => ({ ...prev, use_gaden: val }));
                }}>
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              </div>
              <div className="row">
                <label>SLAM</label>
                <select value={profile.use_slam} onChange={(e) => {
                  const val = e.target.value;
                  setProfile(prev => ({ ...prev, use_slam: val }));
                }}>
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              </div>
              <div className="row">
                <label>RViz</label>
                <select value={profile.use_rviz} onChange={(e) => {
                  const val = e.target.value;
                  setProfile(prev => ({ ...prev, use_rviz: val }));
                }}>
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              </div>
              <div className="row">
                <label>headless</label>
                <select value={profile.headless} onChange={(e) => {
                  const val = e.target.value;
                  setProfile(prev => ({ ...prev, headless: val }));
                }}>
                  <option value="false">false</option>
                  <option value="true">true</option>
                </select>
              </div>
              <div className="btn-row">
                <button className="btn primary" onClick={startSim}>
                  <Play size={16} />
                  开始仿真
                </button>
                <button className="btn danger" onClick={stopSim}>
                  <Square size={16} />
                  停止仿真
                </button>
                <button className="btn" onClick={() => Promise.all([refreshStatus(), refreshMetrics(), refreshLogs()])}>
                  <RefreshCw size={16} />
                  刷新状态
                </button>
              </div>
              <div className="meta">UI 模式：{uiMeta.mode} | bundle_ready：{String(uiMeta.bundle_ready)}</div>
            </article>

            <article className="panel">
              <div className="panel-header">
                <h2>导航与浓度趋势</h2>
                <Activity size={18} style={{ color: "var(--muted)" }} />
              </div>
              <div className="metric-line">
                导航：成功 {navSuccess} / 前进失败 {navFail} / 取消 {navCancel} / 平均到点 {String(navMean)}
              </div>
              <div className="gas-diagnostics">
                <div className="gas-diag-card">
                  <span>气体链路诊断</span>
                  <small className="gas-diag-caption">信号状态</small>
                  <strong className={`gas-signal gas-signal-${String(gasSignalStatus).toLowerCase()}`}>
                    {gasSignalLabel(gasSignalStatus)}
                  </strong>
                </div>
                <div className="gas-diag-card">
                  <span>原始读数</span>
                  <strong>{String(gasRaw)}</strong>
                </div>
                <div className="gas-diag-card">
                  <span>原始话题</span>
                  <strong>{String(gasRawTopic.status || "N/A")}</strong>
                </div>
              </div>
              <div className="gas-diag-reason">{String(gasSignalReason)}</div>
              <TrendChart points={gasHistory} color="#40c4ff" />
            </article>
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2>阶段时间线</h2>
              <FileText size={18} style={{ color: "var(--muted)" }} />
            </div>
            <PhaseTimeline timeline={phaseTimeline} />
          </section>
        </>
      )}

      {activeTab === "heatmap" && (
        <section className="panel heatmap-panel">
          <div className="panel-header">
            <h2>3D 气体浓度热力图</h2>
            <Map size={18} style={{ color: "var(--muted)" }} />
          </div>
          <div className="heatmap-status">
            <span className={`heatmap-conn ${heatmapData.connected ? "connected" : ""}`}>
              {heatmapData.connected ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
              {heatmapData.connected ? "已连接" : "未连接"}
            </span>
            {heatmapData.error && (
              <span className="heatmap-error">
                <AlertCircle size={14} />
                {heatmapData.error}
              </span>
            )}
            {heatmapData.estimate && (
              <span className="heatmap-estimate">
                <Search size={14} />
                估计位置: ({heatmapData.estimate.position[0].toFixed(2)}, {heatmapData.estimate.position[1].toFixed(2)})
                {" "}
                置信度: {(heatmapData.estimate.confidence * 100).toFixed(1)}%
              </span>
            )}
          </div>
          <div className="heatmap-wrapper">
            <Heatmap3D
              grid={heatmapData.grid}
              particles={heatmapData.particles}
              estimate={heatmapData.estimate}
              opacity={0.6}
            />
          </div>
          <div className="heatmap-controls">
            <button className="btn" onClick={heatmapData.pause}>暂停</button>
            <button className="btn" onClick={heatmapData.resume}>继续</button>
          </div>
        </section>
      )}

      {activeTab === "ai" && (
        <section className="panel">
          <div className="panel-header">
            <h2>AI 助手（分析 + 建议 + 半自动执行）</h2>
            <Brain size={18} style={{ color: "var(--muted)" }} />
          </div>
          <div className="grid ai-grid">
            <div className="ai-card">
              <div className="row">
                <label>配置</label>
                <select value={activeProfileId} onChange={(e) => setActiveProfileId(e.target.value)}>
                  {llmProfiles.map((item) => (
                    <option key={item.id} value={item.id}>{item.name} ({item.model || "no-model"})</option>
                  ))}
                </select>
              </div>
              <div className="row"><label>名称</label><input value={llmForm.name} onChange={(e) => {
                const val = e.target.value;
                setLlmForm(prev => ({ ...prev, name: val }));
              }} /></div>
              <div className="row"><label>URL</label><input value={llmForm.base_url} onChange={(e) => {
                const val = e.target.value;
                setLlmForm(prev => ({ ...prev, base_url: val }));
              }} /></div>
              <div className="row"><label>API Key</label><input type="password" value={llmForm.api_key} onChange={(e) => {
                const val = e.target.value;
                setLlmForm(prev => ({ ...prev, api_key: val }));
              }} /></div>
              <div className="row"><label>模型</label><input value={llmForm.model} onChange={(e) => {
                const val = e.target.value;
                setLlmForm(prev => ({ ...prev, model: val }));
              }} /></div>
              <div className="row">
                <label>协议</label>
                <select value={llmForm.protocol} onChange={(e) => {
                  const val = e.target.value;
                  setLlmForm(prev => ({ ...prev, protocol: val }));
                }}>
                  <option value="dual">dual</option>
                  <option value="responses">responses</option>
                  <option value="chat">chat</option>
                </select>
              </div>
              <div className="btn-row">
                <button className="btn" onClick={saveLlmProfile}>
                  <Save size={16} />
                  保存配置
                </button>
                <button className="btn" onClick={loadLlmProfiles}>
                  <RefreshCw size={16} />
                  刷新配置
                </button>
                <button className="btn" onClick={activateProfile}>
                  <CheckCircle2 size={16} />
                  设为当前
                </button>
                <button className="btn" onClick={checkProfile}>
                  <Zap size={16} />
                  连接测试
                </button>
              </div>
            </div>

            <div className="ai-card">
              <div className="row row-col">
                <label>AI 指令</label>
                <textarea rows={3} value={llmPrompt} onChange={(e) => setLlmPrompt(e.target.value)} />
              </div>
              <div className="btn-row">
                <button className="btn primary" onClick={sendAi}>
                  <MessageSquare size={16} />
                  发送给 AI
                </button>
                <button className="btn" onClick={runAiOnce}>
                  <Bot size={16} />
                  执行 AI 单轮流程
                </button>
              </div>
              <div className="reply">
                {llmReply || "AI 分析结果会显示在这里。"}
              </div>
              <div className="actions">
                {llmActions.map((action, idx) => (
                  <div key={`${action.type}-${action.title || ""}-${idx}`} className="action-item">
                    <div>
                      <strong>{action.title || action.type}</strong>
                      <div className="muted">风险：{action.risk_level || "medium"} | 类型：{action.type}</div>
                      <div className="muted">{action.reason || ""}</div>
                    </div>
                    <button className="btn" onClick={() => executeAction(action)}>
                      <ChevronRight size={16} />
                      执行动作
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="grid ai-audit-grid">
            <article className="panel inset">
              <h3>AI 对话历史</h3>
              <table className="table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>模型</th>
                    <th>摘要</th>
                  </tr>
                </thead>
                <tbody>
                  {llmHistoryRows.slice(-12).reverse().map((row) => (
                    <tr key={`history-${row.timestamp || ""}-${row.model || "unknown"}`}>
                      <td>{String(row.timestamp || "").replace("T", " ").slice(0, 19)}</td>
                      <td>{row.model || "-"}</td>
                      <td>{String(row.analysis || row.message || "-").slice(0, 80)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </article>

            <article className="panel inset">
              <h3>动作执行审计</h3>
              <table className="table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>动作</th>
                    <th>风险</th>
                    <th>结果</th>
                  </tr>
                </thead>
                <tbody>
                  {llmAuditRows.slice(-20).reverse().map((row) => (
                    <tr key={`audit-${row.timestamp || ""}-${row.title || row.type || "unknown"}`}>
                      <td>{String(row.timestamp || "").replace("T", " ").slice(0, 19)}</td>
                      <td>{row.title || row.type || "-"}</td>
                      <td>{row.risk_level || "-"}</td>
                      <td>{row.result?.ok ? "成功" : `失败: ${row.result?.message || "-"}`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </article>
          </div>
        </section>
      )}

      {activeTab === "diagnostics" && (
        <>
          <section className="grid diagnostics-grid">
            <article className="panel inset">
              <div className="panel-header">
                <h2>节点健康</h2>
                <Cpu size={18} style={{ color: "var(--muted)" }} />
              </div>
              <table className="table">
                <thead>
                  <tr>
                    <th>节点</th>
                    <th>状态</th>
                    <th>重启次数</th>
                  </tr>
                </thead>
                <tbody>
                  {nodeRows.map((row) => (
                    <tr key={`node-${row.node || "unknown"}`}>
                      <td>{row.node || "-"}</td>
                      <td>{row.up ? "UP" : "DOWN"}</td>
                      <td>{safeNumber(row.restart_count, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </article>

            <article className="panel inset">
              <div className="panel-header">
                <h2>话题健康</h2>
                <Activity size={18} style={{ color: "var(--muted)" }} />
              </div>
              <table className="table">
                <thead>
                  <tr>
                    <th>话题</th>
                    <th>状态</th>
                    <th>频率(Hz)</th>
                    <th>延迟(s)</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(topicHealth || {}).map(([topic, row]) => (
                    <tr key={topic}>
                      <td>{topic}</td>
                      <td>{row?.status || "-"}</td>
                      <td>{safeNumber(row?.hz, 0).toFixed(2)}</td>
                      <td>{row?.stale_sec == null ? "-" : safeNumber(row?.stale_sec, 0).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </article>
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2>运行日志</h2>
              <Terminal size={18} style={{ color: "var(--muted)" }} />
            </div>
            <div className="log-tools">
              <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
                <option value="all">全部来源</option>
                <option value="control">control</option>
                <option value="sim">sim</option>
                <option value="demo_prep">demo_prep</option>
                <option value="system">system</option>
              </select>
              <input placeholder="搜索日志..." value={query} onChange={(e) => setQuery(e.target.value)} />
              <label className="auto-scroll">
                <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)} />
                自动滚动
              </label>
              <span className="muted">{filteredLogs.length} 行</span>
            </div>
            <div ref={logBoxRef} className="log-box">
              {filteredLogs.map((row) => <LogRow key={row.id} row={row} />)}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
