import { useState, useRef, useEffect, useCallback } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const STEP_LABELS = [
  { label: "Design type", hint: "What's being made"  },
  { label: "Purpose",     hint: "What it's for"      },
  { label: "Deadline",    hint: "When you need it"   },
  { label: "Brand refs",  hint: "Style & guidelines" },
  { label: "Budget",      hint: "Investment range"   },
];

const TEAM = [
  { name: "Riya",   role: "Social & Marketing", color: "#3B82F6" },
  { name: "Sameer", role: "Decks & Slides",     color: "#A78BFA" },
  { name: "Priya",  role: "Brand Identity",     color: "#10B981" },
];

const PERSON_COLOR = {
  Riya:   "#3B82F6",
  Sameer: "#A78BFA",
  Priya:  "#10B981",
};

function getColor(name) {
  return PERSON_COLOR[name] || "#5A67F2";
}

function timeAgo(iso) {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)  return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

/* ── Sidebar ────────────────────────────────────────────────────────────── */
function Sidebar({ stage, completed, questionIndex, onAdmin }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <div className="logo-mark">✦</div>
        <div>
          <div className="logo-name">Studio</div>
          <div className="logo-sub">Design Brief</div>
        </div>
      </div>

      <div className="rule" />
      <p className="eyebrow">Intake checklist</p>

      <div className="steps">
        {STEP_LABELS.map((s, i) => {
          const done   = completed[i];
          const active = !done && i === questionIndex && stage === "questions";
          return (
            <div key={i} className={`step${done ? " done" : active ? " active" : ""}`}>
              <div className="step-num">
                {done ? (
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                    <path d="M2 5.5L4 7.5L8 3" stroke="currentColor"
                          strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                ) : i + 1}
              </div>
              <div>
                <div className="step-label">{s.label}</div>
                <div className="step-hint">{s.hint}</div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="sidebar-bottom">
        <div className="rule" />
        <p className="eyebrow" style={{ padding: "14px 22px 10px" }}>Team</p>
        <div className="team-list">
          {TEAM.map(t => (
            <div key={t.name} className="team-chip">
              <div className="chip-avatar" style={{ background: t.color }}>{t.name[0]}</div>
              <div>
                <div className="chip-name">{t.name}</div>
                <div className="chip-role">{t.role}</div>
              </div>
            </div>
          ))}
        </div>
        <button className="admin-btn" onClick={onAdmin}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
            <rect x="3" y="3" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="2"/>
            <rect x="14" y="3" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="2"/>
            <rect x="3" y="14" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="2"/>
            <rect x="14" y="14" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="2"/>
          </svg>
          Admin portal
        </button>
      </div>
    </aside>
  );
}

/* ── Match card (chat) ──────────────────────────────────────────────────── */
function MatchCard({ match, index }) {
  const [bar, setBar] = useState(0);
  const color = getColor(match.name);
  useEffect(() => {
    const t = setTimeout(() => setBar(match.confidence), 80 + index * 100);
    return () => clearTimeout(t);
  }, [match.confidence, index]);

  return (
    <div className="match-card" style={{ animationDelay: `${index * 100}ms` }}>
      <div className="match-head">
        <div className="match-avatar" style={{ background: color }}>{match.name[0]}</div>
        <div className="match-id">
          <span className="match-name">{match.name}</span>
          <span className="match-role">{match.role}</span>
        </div>
        <div className="match-pct" style={{ color }}>{match.confidence}%</div>
      </div>
      {match.reason && (
        <div className="match-reason-block" style={{ borderLeftColor: `${color}60` }}>
          <span className="reason-mark">❝</span>
          {match.reason}
        </div>
      )}
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${bar}%`, background: color }} />
      </div>
    </div>
  );
}

/* ── Admin: brief card ──────────────────────────────────────────────────── */
function MatchRow({ m }) {
  const color = getColor(m.name);
  return (
    <div className="bm-row" style={{ borderLeftColor: `${color}60` }}>
      <div className="bm-head">
        <div className="bm-avatar" style={{ background: color }}>{m.name[0]}</div>
        <div className="bm-id">
          <span className="bm-name">{m.name}</span>
          <span className="bm-role">{m.role}</span>
        </div>
        <span className="bm-conf" style={{ color }}>{m.confidence}%</span>
      </div>
      {m.reason && (
        <p className="bm-reason">{m.reason}</p>
      )}
      <div className="bm-bar-track">
        <div className="bm-bar-fill" style={{ width: `${m.confidence}%`, background: color }} />
      </div>
    </div>
  );
}

function BriefCard({ brief }) {
  const [open, setOpen] = useState(false);
  const assigned = (brief.matches || []);
  const statusLabel = !brief.routed
    ? "Pending"
    : assigned.length > 0 ? "✓ Routed" : "⚠ Unassigned";
  const statusCls = !brief.routed
    ? "pill-gray"
    : assigned.length > 0 ? "pill-green" : "pill-amber";

  return (
    <div className={`brief-card${open ? " open" : ""}`}>
      <div className="brief-header" onClick={() => setOpen(o => !o)}>
        <div className="bh-meta">
          <span className="brief-id">#{brief.session_id.slice(-8)}</span>
          <span className="brief-ts">{timeAgo(brief.created_at)}</span>
          <span className={`pill ${statusCls}`}>{statusLabel}</span>
        </div>
        <div className="brief-query-preview">{brief.original_query}</div>
        <div className="bh-assignees">
          {assigned.map(m => (
            <div key={m.name} className="assignee-dot"
                 style={{ background: getColor(m.name) }} title={m.name} />
          ))}
          {assigned.length === 0 && <span className="no-assignee">—</span>}
        </div>
        <svg className={`chevron${open ? " up" : ""}`} width="14" height="14"
             viewBox="0 0 24 24" fill="none">
          <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2"
                strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>

      {open && (
        <div className="brief-body">
          <p className="brief-full-query">{brief.original_query}</p>

          {brief.qa_pairs?.length > 0 && (
            <div className="qa-section">
              <p className="section-label">Intake answers</p>
              <div className="qa-grid">
                {brief.qa_pairs.map((qa, i) => (
                  <div key={i} className="qa-item">
                    <div className="qa-q">{qa.question}</div>
                    <div className="qa-a">{qa.answer}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {assigned.length > 0 && (
            <div className="routing-section">
              <p className="section-label">Routing result</p>
              <div className="routing-rows">
                {assigned.map((m, i) => <MatchRow key={i} m={m} />)}
              </div>
            </div>
          )}

          {brief.routed && assigned.length === 0 && (
            <div className="notice-amber">
              No designer matched above confidence threshold. Manual assignment required.
            </div>
          )}
          {!brief.routed && (
            <div className="notice-gray">
              Conversation incomplete — client did not finish all questions.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Admin portal ───────────────────────────────────────────────────────── */
function AdminPortal({ onBack }) {
  const [data,    setData]   = useState(null);
  const [loading, setLoad]   = useState(true);
  const [filter,  setFilter] = useState("all");
  const [error,   setError]  = useState("");

  const load = useCallback(() => {
    setLoad(true); setError("");
    fetch(`${API_URL}/admin/briefs?per_page=100&person=${filter}`)
      .then(r => { if (!r.ok) throw new Error("Failed to load"); return r.json(); })
      .then(d  => { setData(d); setLoad(false); })
      .catch(e => { setError(e.message); setLoad(false); });
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const s      = data?.stats  || {};
  const briefs = data?.briefs || [];

  const TABS = [
    { key: "all",        label: "All",        count: s.total      ?? 0 },
    ...TEAM.map(t => ({ key: t.name, label: t.name, count: s[t.name] ?? 0, color: t.color })),
    { key: "unassigned", label: "Unassigned", count: s.unassigned ?? 0 },
    { key: "pending",    label: "Pending",    count: s.pending    ?? 0 },
  ];

  return (
    <div className="admin-shell">
      <div className="admin-header">
        <button className="back-btn" onClick={onBack}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M19 12H5M5 12L12 19M5 12L12 5" stroke="currentColor"
                  strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back
        </button>
        <div className="admin-title-block">
          <h2 className="admin-title">Admin Portal</h2>
          <span className="admin-sub">All briefs · live from database</span>
        </div>
        <button className="refresh-btn" onClick={load}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
            <path d="M1 4v6h6M23 20v-6h-6" stroke="currentColor" strokeWidth="2"
                  strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15"
                  stroke="currentColor" strokeWidth="2"
                  strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="stats-row">
        {[
          { label: "Total",      val: s.total      ?? 0, color: "#5A67F2" },
          { label: "Routed",     val: s.routed     ?? 0, color: "#10B981" },
          { label: "Pending",    val: s.pending    ?? 0, color: "#FBBF24" },
          { label: "Unassigned", val: s.unassigned ?? 0, color: "#F87171" },
          ...TEAM.map(t => ({ label: t.name, val: s[t.name] ?? 0, color: t.color })),
        ].map((item, i) => (
          <div key={i} className="stat-card">
            <div className="stat-val" style={{ color: item.color }}>{item.val}</div>
            <div className="stat-label">{item.label}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="admin-tabs">
        {TABS.map(t => (
          <button
            key={t.key}
            className={`admin-tab${filter === t.key ? " active" : ""}`}
            onClick={() => setFilter(t.key)}
            style={filter === t.key && t.color ? { borderColor: `${t.color}50`, color: t.color } : {}}
          >
            {t.key !== "all" && t.color && (
              <span className="tab-dot" style={{ background: t.color }} />
            )}
            {t.label}
            <span className="tab-count">{t.count}</span>
          </button>
        ))}
      </div>

      {/* List */}
      <div className="admin-list">
        {loading && (
          <div className="admin-loading">
            <div className="loading-dots"><span/><span/><span/></div>
            Loading from database…
          </div>
        )}
        {error && <div className="admin-error">{error}</div>}
        {!loading && briefs.length === 0 && (
          <div className="admin-empty">
            <div style={{ fontSize: 28, marginBottom: 8 }}>📋</div>
            No briefs for this filter.
          </div>
        )}
        {briefs.map(b => <BriefCard key={b.session_id} brief={b} />)}
      </div>
    </div>
  );
}

/* ── Main App ───────────────────────────────────────────────────────────── */
export default function App() {
  const [stage,           setStage]    = useState("input");
  const [query,           setQuery]    = useState("");
  const [sessionId,       setSid]      = useState(null);
  const [qIdx,            setQIdx]     = useState(0);
  const [answerVal,       setAnswer]   = useState("");
  const [completed,       setDone]     = useState(Array(5).fill(false));
  const [messages,        setMessages] = useState([]);
  const [matches,         setMatches]  = useState([]);
  const [loading,         setLoading]  = useState(false);
  const [admin,           setAdmin]    = useState(false);
  const [currentQuestion, setCurrentQ] = useState("");
  const [attachedFile,    setFile]     = useState(null);   // { name, file }
  const [fileError,       setFileErr]  = useState("");

  const bottomRef  = useRef(null);
  const inputRef   = useRef(null);
  const fileRef    = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); },
            [messages, loading, matches]);
  useEffect(() => { if (!loading && !admin) inputRef.current?.focus(); },
            [loading, stage, admin]);

  const push = (role, text) => setMessages(p => [...p, { role, text }]);

  const ALLOWED_EXTS = [".pdf", ".docx", ".md", ".txt"];
  const handleFileSelect = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const ext = f.name.slice(f.name.lastIndexOf(".")).toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
      setFileErr("Only PDF, DOCX, MD, or TXT files are supported.");
      return;
    }
    if (f.size > 5 * 1024 * 1024) {
      setFileErr("File must be under 5 MB.");
      return;
    }
    setFileErr("");
    setFile({ name: f.name, file: f });
    e.target.value = "";
  };

  const handleStart = async () => {
    if (!query.trim() && !attachedFile) return;
    setLoading(true);
    setFileErr("");

    let finalQuery = query.trim();
    const fileLabel = attachedFile
      ? `📎 ${attachedFile.name}${query.trim() ? ` — "${query.trim()}"` : ""}`
      : query.trim();

    // Extract text from attached file first
    if (attachedFile) {
      push("user", fileLabel);
      setQuery(""); setFile(null);
      try {
        const fd = new FormData();
        fd.append("file", attachedFile.file);
        const res = await fetch(`${API_URL}/extract-file`, { method: "POST", body: fd });
        if (!res.ok) throw new Error((await res.json()).detail || "Extraction failed.");
        const { text } = await res.json();
        finalQuery = finalQuery
          ? `${finalQuery}\n\n[From ${attachedFile.name}]:\n${text}`
          : `[From ${attachedFile.name}]:\n${text}`;
      } catch (e) {
        push("bot", `Could not read file: ${e.message} — please paste your brief as text instead.`);
        setLoading(false);
        return;
      }
    } else {
      push("user", query.trim());
      setQuery("");
    }

    try {
      const res = await fetch(`${API_URL}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: finalQuery }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Server error.");
      const d = await res.json();
      setSid(d.session_id);
      if (d.status === "routed") {
        if (d.completed) setDone(d.completed);
        if (d.matches)   setMatches(d.matches);
        push("bot", d.message); setStage("routed");
      } else {
        if (d.completed) setDone(d.completed);
        setQIdx(d.question_index); setCurrentQ(d.question);
        push("bot", d.question); setStage("questions");
      }
    } catch {
      push("bot", "Connection issue — please try sending your request again.");
    } finally {
      setLoading(false);
    }
  };

  const handleAnswer = async () => {
    if (!answerVal.trim()) return;
    setLoading(true);
    const val = answerVal;
    push("user", val);
    setAnswer("");
    try {
      const res = await fetch(`${API_URL}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, answer: val }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Server error.");
      const d = await res.json();
      if (d.status === "vague_retry") {
        push("bot", d.message);
        push("bot", d.question);
        setCurrentQ(d.question);
      } else if (d.status === "next_question") {
        if (d.completed) setDone(d.completed);
        setQIdx(d.question_index);
        setCurrentQ(d.question);
        push("bot", d.question);
      } else if (d.status === "routed") {
        if (d.completed) setDone(d.completed);
        if (d.matches)   setMatches(d.matches);
        push("bot", d.message);
        setStage("routed");
      }
    } catch {
      // ── graceful retry: re-ask the question, restore input ──
      push("bot", "Connection error — let's try that again.");
      if (currentQuestion) push("bot", currentQuestion);
      setAnswer(val);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setStage("input"); setQuery(""); setSid(null); setQIdx(0); setAnswer("");
    setDone(Array(5).fill(false)); setMessages([]); setMatches([]);
    setCurrentQ(""); setFile(null); setFileErr("");
  };

  const onKey = (e, fn) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); fn(); }
  };
  const val    = stage === "input" ? query    : answerVal;
  const setVal = stage === "input" ? setQuery : setAnswer;
  const action = stage === "input" ? handleStart : handleAnswer;
  const canSend = stage === "input" ? (!!val.trim() || !!attachedFile) : !!val.trim();

  if (admin) return (
    <div className="shell">
      <div className="frame admin-frame">
        <AdminPortal onBack={() => setAdmin(false)} />
      </div>
    </div>
  );

  return (
    <div className="shell">
      <div className="frame">
        <Sidebar stage={stage} completed={completed}
                 questionIndex={qIdx} onAdmin={() => setAdmin(true)} />
        <div className="main">
          <div className="messages">
            {messages.length === 0 && (
              <div className="empty">
                <div className="empty-headline">What are you<br/>building?</div>
                <p className="empty-body">
                  Tell us about your project — we'll match you with the right designer.
                </p>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`msg-row ${m.role}`}>
                {m.role === "bot" && <span className="msg-tag">Brief</span>}
                <div className={`msg ${m.role}`}>{m.text}</div>
              </div>
            ))}
            {loading && (
              <div className="msg-row bot">
                <span className="msg-tag">Brief</span>
                <div className="msg bot typing"><span/><span/><span/></div>
              </div>
            )}
            {stage === "routed" && matches.length > 0 && (
              <div className="routed-wrap">
                <div className="routed-header">
                  <span className="check-pill">✓ Routed</span>
                  <span className="routed-label">Assigned to</span>
                </div>
                {matches.map((m, i) => <MatchCard key={i} match={m} index={i} />)}
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="input-bar">
            {stage !== "routed" ? (
              <div className="input-wrap">
                {/* File chip — shown when file is attached */}
                {stage === "input" && attachedFile && (
                  <div className="file-chip">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                      <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66L9.41 17.41a2 2 0 01-2.83-2.83l8.49-8.48"
                            stroke="currentColor" strokeWidth="2"
                            strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    <span>{attachedFile.name}</span>
                    <button className="chip-remove" onClick={() => setFile(null)}>×</button>
                  </div>
                )}
                {fileError && <div className="file-error">{fileError}</div>}
                <div className="input-row">
                  {/* Hidden file input */}
                  <input
                    ref={fileRef} type="file"
                    accept=".pdf,.docx,.md,.txt"
                    style={{ display: "none" }}
                    onChange={handleFileSelect}
                  />
                  {/* Attach button — only on initial input stage */}
                  {stage === "input" && (
                    <button
                      className="attach-btn"
                      onClick={() => fileRef.current?.click()}
                      disabled={loading}
                      title="Attach PDF, DOCX, MD, or TXT"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                        <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66L9.41 17.41a2 2 0 01-2.83-2.83l8.49-8.48"
                              stroke="currentColor" strokeWidth="2"
                              strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </button>
                  )}
                  <textarea
                    ref={inputRef} rows={2} value={val} disabled={loading}
                    onChange={e => setVal(e.target.value)}
                    onKeyDown={e => onKey(e, action)}
                    placeholder={
                      stage === "input"
                        ? attachedFile
                          ? "Add a note or send as-is…"
                          : "Describe your project, or attach a brief…"
                        : "Your answer…"
                    }
                  />
                  <button className="send" onClick={action}
                          disabled={loading || !canSend}>
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
                      <path d="M22 2L11 13M22 2L15 22L11 13L2 9L22 2Z"
                            stroke="white" strokeWidth="2.2"
                            strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </button>
                </div>
              </div>
            ) : (
              <button className="new-brief" onClick={reset}>
                Start a new brief
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}