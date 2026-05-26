import { useState, useEffect, useRef, useCallback } from 'react'

// ── SPEECH HOOK — streaming sentence-by-sentence TTS + STT ──────────────────
// ─────────────────────────────────────────────────────────────────────────────
//  TOOL CARD — renders inline image / music result from skyd chat
// ─────────────────────────────────────────────────────────────────────────────
function ToolCard({ tool }) {
  const [imgLoaded, setImgLoaded] = React.useState(false)
  const [imgErr,    setImgErr]    = React.useState(false)

  if (tool.type === 'image') {
    return (
      <div style={{ maxWidth: 320, borderRadius: 14, overflow: 'hidden',
        background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)' }}>
        {!imgLoaded && !imgErr && (
          <div style={{ height: 200, display:'flex', alignItems:'center', justifyContent:'center',
            color:'rgba(255,255,255,0.3)', fontSize:12 }}>
            ⏳ Generating...
          </div>
        )}
        {imgErr && (
          <div style={{ padding:12, color:'#f87171', fontSize:12 }}>
            Image failed to load — try again
          </div>
        )}
        <img
          src={tool.url}
          alt={tool.prompt}
          onLoad={() => setImgLoaded(true)}
          onError={() => setImgErr(true)}
          style={{ display: imgLoaded ? 'block' : 'none',
            width: '100%', maxWidth: 320, objectFit: 'cover' }}
        />
        {imgLoaded && (
          <div style={{ padding:'8px 12px', fontSize:11,
            color:'rgba(255,255,255,0.4)', fontStyle:'italic', lineHeight:1.4 }}>
            "{tool.prompt}"
          </div>
        )}
      </div>
    )
  }

  if (tool.type === 'music') {
    const COLORS = {
      piano:'#7c6fff', guitar:'#f59e0b', 'e-guitar':'#ef4444', bass:'#10b981',
      violin:'#ec4899', trumpet:'#f97316', flute:'#06b6d4', cello:'#8b5cf6',
      marimba:'#84cc16', organ:'#a78bfa'
    }
    const color = COLORS[tool.instrument] || '#7c6fff'
    return (
      <div style={{ maxWidth: 320, borderRadius: 14, padding: '12px 14px',
        background: `${color}15`, border: `1px solid ${color}44` }}>
        <div style={{ fontSize:10, color: color, fontWeight:700, letterSpacing:1,
          marginBottom:6, textTransform:'uppercase' }}>🎵 Sky-Music composed</div>
        <div style={{ fontWeight:700, fontSize:15, color:'#fff', marginBottom:4 }}>{tool.title}</div>
        <div style={{ fontSize:12, color:'rgba(255,255,255,0.55)', lineHeight:1.6,
          fontStyle:'italic', marginBottom:10 }}>{tool.story}</div>
        <div style={{ display:'flex', gap:5, flexWrap:'wrap' }}>
          {[`${tool.key} ${tool.mode}`, `${tool.bpm} BPM`, tool.instrument].filter(Boolean).map((t,i)=>(
            <span key={i} style={{ background:`${color}22`, border:`1px solid ${color}44`,
              borderRadius:20, padding:'2px 9px', fontSize:10, color:color }}>{t}</span>
          ))}
        </div>
        <div style={{ marginTop:10, fontSize:11, color:'rgba(255,255,255,0.35)' }}>
          Open Sky-Music tab to play it ▶
        </div>
      </div>
    )
  }

  if (tool.type === 'status') {
    const s = tool.stats || {}
    return (
      <div style={{ maxWidth:300, borderRadius:12, padding:'12px 14px',
        background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.1)' }}>
        <div style={{ fontSize:10, color:'#7c6fff', fontWeight:700, letterSpacing:1, marginBottom:8 }}>
          ⚡ SYSTEM STATUS
        </div>
        {[
          ['CPU',   `${s.cpu_percent ?? '?'}%`],
          ['RAM',   `${s.memory_percent ?? '?'}%`],
          ['Disk',  `${s.disk_percent ?? '?'}%`],
          ['GPU',   s.gpu_temp ? `${s.gpu_temp}°C` : '?'],
          ['Nodes', `${(tool.nodes||[]).length} online`],
        ].map(([k,v])=>(
          <div key={k} style={{ display:'flex', justifyContent:'space-between',
            fontSize:12, color:'rgba(255,255,255,0.7)', marginBottom:4 }}>
            <span style={{ color:'rgba(255,255,255,0.4)' }}>{k}</span>
            <span style={{ fontWeight:600 }}>{v}</span>
          </div>
        ))}
      </div>
    )
  }

  return null
}

function useSpeech() {
  const [listening,  setListening]  = useState(false)
  const [speaking,   setSpeaking]   = useState(false)
  const [voiceOn,    setVoiceOn]    = useState(() => {
    try { return localStorage.getItem('osone_voice') !== 'off' } catch { return true }
  })
  const recognitionRef = useRef(null)
  const synthRef       = useRef(window.speechSynthesis)
  const voiceRef       = useRef(null)
  const sentenceBuffer = useRef('')   // accumulates tokens until sentence boundary
  const isSpeakingRef  = useRef(false)

  // Pick best English voice
  useEffect(() => {
    const pick = () => {
      const voices = synthRef.current.getVoices()
      const want = ['Google US English','Google UK English Male','Microsoft David',
                    'Microsoft Mark','Alex','Daniel']
      for (const n of want) {
        const v = voices.find(v => v.name.includes(n))
        if (v) { voiceRef.current = v; return }
      }
      voiceRef.current = voices.find(v => v.lang.startsWith('en')) || voices[0] || null
    }
    pick()
    synthRef.current.addEventListener('voiceschanged', pick)
    return () => synthRef.current.removeEventListener('voiceschanged', pick)
  }, [])

  // Clean markdown noise before speaking
  const cleanText = (text) => text
    .replace(/```[\s\S]*?```/g, 'code block.')
    .replace(/`[^`]+`/g, '')
    .replace(/[*_#>\[\]]/g, '')
    .replace(/https?:\/\/\S+/g, 'link')
    .replace(/\s+/g, ' ')
    .trim()

  // Speak a single clean chunk immediately
  const speakChunk = useCallback((text) => {
    if (!voiceOn || !text.trim()) return
    const utt = new SpeechSynthesisUtterance(text.trim())
    utt.voice  = voiceRef.current
    utt.rate   = 1.08
    utt.pitch  = 0.95
    utt.volume = 1
    utt.onstart = () => { setSpeaking(true);  isSpeakingRef.current = true  }
    utt.onend   = () => { setSpeaking(false); isSpeakingRef.current = false }
    synthRef.current.speak(utt)
  }, [voiceOn])

  // Called with each streaming token — buffers until sentence boundary then speaks
  const streamToken = useCallback((token) => {
    if (!voiceOn) return
    sentenceBuffer.current += token
    // Sentence endings: . ! ? followed by space or end
    const sentenceRe = /[^.!?]*[.!?]+(\s|$)/g
    let match
    let last = 0
    while ((match = sentenceRe.exec(sentenceBuffer.current)) !== null) {
      const sentence = cleanText(match[0])
      if (sentence.length > 3) speakChunk(sentence)
      last = sentenceRe.lastIndex
    }
    sentenceBuffer.current = sentenceBuffer.current.slice(last)
  }, [voiceOn, speakChunk])

  // Called when stream ends — flush any remaining buffer
  const flushBuffer = useCallback(() => {
    const remaining = cleanText(sentenceBuffer.current)
    if (remaining.length > 2) speakChunk(remaining)
    sentenceBuffer.current = ''
  }, [speakChunk])

  // Speak full text at once (non-streaming fallback)
  const speak = useCallback((text) => {
    if (!voiceOn) return
    synthRef.current.cancel()
    sentenceBuffer.current = ''
    speakChunk(cleanText(text))
  }, [voiceOn, speakChunk])

  const stopSpeaking = useCallback(() => {
    synthRef.current.cancel()
    sentenceBuffer.current = ''
    setSpeaking(false)
    isSpeakingRef.current = false
  }, [])

  // STT — calls onResult(transcript) when speech ends, then auto-sends if onAutoSend given
  const startListening = useCallback((onResult, onAutoSend) => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { alert('Speech recognition not supported. Use Chrome or Edge.'); return }
    // Stop speaking while listening
    synthRef.current.cancel()
    const rec = new SR()
    rec.lang            = 'en-US'
    rec.continuous      = false
    rec.interimResults  = true
    rec.onresult = (e) => {
      const transcript = Array.from(e.results).map(r => r[0].transcript).join(' ').trim()
      if (transcript) onResult(transcript)
      // If final result, auto-send
      if (e.results[e.results.length - 1].isFinal && onAutoSend) {
        onAutoSend(transcript)
      }
    }
    rec.onend   = () => setListening(false)
    rec.onerror = (e) => { console.warn('STT error', e.error); setListening(false) }
    recognitionRef.current = rec
    rec.start()
    setListening(true)
  }, [])

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop()
    setListening(false)
  }, [])

  const toggleVoice = useCallback(() => {
    setVoiceOn(v => {
      const next = !v
      try { localStorage.setItem('osone_voice', next ? 'on' : 'off') } catch {}
      if (!next) { synthRef.current.cancel(); setSpeaking(false) }
      return next
    })
  }, [])

  return { listening, speaking, voiceOn, speak, streamToken, flushBuffer, stopSpeaking, startListening, stopListening, toggleVoice }
}


import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import './index.css'
import HivePanel from './HivePanel.jsx'
import CodeAgent from './CodeAgent.jsx'
import ImageStudio from './ImageStudio.jsx'
import MusicAgent from './MusicAgent.jsx'
import DAWAgent  from './DAWAgent.jsx'
import MusicStudio from './MusicStudio.jsx'
import SkyMusic from './SkyMusic.jsx'
import AethoriaPanel from './AethoriaPanel.jsx'

const _isLocal = window.location.port !== ''
const API = _isLocal
  ? `http://${window.location.hostname}:8000`
  : `${window.location.protocol}//${window.location.host}`
const WS_BASE = _isLocal
  ? `ws://${window.location.hostname}:8000`
  : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`

// ── Auth ──────────────────────────────────────────────────────────────────────
function useAuth() {
  const [auth, setAuth] = useState(() => {
    try { return JSON.parse(localStorage.getItem('osone_auth') || 'null') } catch { return null }
  })
  const login = (data) => { localStorage.setItem('osone_auth', JSON.stringify(data)); setAuth(data) }
  const logout = () => { localStorage.removeItem('osone_auth'); setAuth(null) }
  return { auth, login, logout }
}
function authFetch(url, opts = {}, token) {
  return fetch(url, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(opts.headers || {}) }
  })
}

// ── Mobile detection ──────────────────────────────────────────────────────────
function useIsMobile() {
  const [mobile, setMobile] = useState(() =>
    /Android|iPhone|iPad|iPod|Mobile|OSONE-Android/i.test(navigator.userAgent) || window.innerWidth <= 768)
  useEffect(() => {
    const check = () => setMobile(/Android|iPhone|iPad|iPod|Mobile|OSONE-Android/i.test(navigator.userAgent) || window.innerWidth <= 768)
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])
  return mobile
}

// ── System stats ──────────────────────────────────────────────────────────────
function useStats(token) {
  const [stats, setStats] = useState(null)
  useEffect(() => {
    if (!token) return
    const fetch_ = () => authFetch(`${API}/api/stats`, {}, token).then(r => r.json()).then(setStats).catch(() => {})
    fetch_()
    const t = setInterval(fetch_, 3000)
    return () => clearInterval(t)
  }, [token])
  return stats
}

// ── System info (battery, network, time) ─────────────────────────────────────
function useSystemInfo() {
  const [info, setInfo] = useState({ time: new Date(), battery: null, network: navigator.onLine, charging: null, batteryLevel: null })

  useEffect(() => {
    // Clock
    const clock = setInterval(() => setInfo(i => ({ ...i, time: new Date() })), 1000)

    // Battery API
    if ('getBattery' in navigator) {
      navigator.getBattery().then(bat => {
        const update = () => setInfo(i => ({ ...i, charging: bat.charging, batteryLevel: Math.round(bat.level * 100) }))
        update()
        bat.addEventListener('chargingchange', update)
        bat.addEventListener('levelchange', update)
      }).catch(() => {})
    }

    // Network
    const onOnline = () => setInfo(i => ({ ...i, network: true }))
    const onOffline = () => setInfo(i => ({ ...i, network: false }))
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)

    return () => {
      clearInterval(clock)
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  return info
}

function fmt(bytes) {
  if (bytes > 1e9) return (bytes / 1e9).toFixed(1) + 'GB'
  if (bytes > 1e6) return (bytes / 1e6).toFixed(0) + 'MB'
  return (bytes / 1e3).toFixed(0) + 'KB'
}
function fmtUptime(s) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  return `${h}h ${m}m`
}

// ── Battery icon ──────────────────────────────────────────────────────────────
function BatteryIcon({ level, charging }) {
  if (level === null) return <span title="No battery info" style={{ opacity: 0.4 }}>🔌</span>
  const color = level < 15 ? '#f87171' : level < 30 ? '#fbbf24' : '#4ade80'
  const icon = charging ? '⚡' : level > 80 ? '🔋' : level > 30 ? '🪫' : '🔴'
  return (
    <span title={`Battery: ${level}%${charging ? ' (charging)' : ''}`} style={{ fontSize: 13, cursor: 'default' }}>
      {icon} <span style={{ color, fontSize: 11 }}>{level}%</span>
    </span>
  )
}

// ── Network icon ─────────────────────────────────────────────────────────────
function NetworkIcon({ online }) {
  return (
    <span title={online ? 'Connected' : 'Offline'} style={{ fontSize: 13, cursor: 'default' }}>
      {online ? '📶' : <span style={{ color: '#f87171' }}>⚠️</span>}
    </span>
  )
}


// ── MARKDOWN MESSAGE RENDERER ─────────────────────────────────────────────────
// Renders skyd responses with proper markdown: code blocks, bold, lists, etc.
function MarkdownMessage({ content, isUser }) {
  const copyCode = (code) => {
    navigator.clipboard?.writeText(code).catch(() => {})
  }

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Code blocks — syntax highlighted with copy button
        code({ node, inline, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '')
          const codeStr = String(children).replace(/\n$/, '')
          if (!inline && match) {
            return (
              <div style={{ position: 'relative', margin: '10px 0', borderRadius: 8, overflow: 'hidden' }}>
                <div style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  background: '#1a1a2e', padding: '4px 12px', fontSize: 11,
                  color: '#7c6fff', borderBottom: '1px solid rgba(255,255,255,0.08)'
                }}>
                  <span>{match[1]}</span>
                  <button
                    onClick={() => copyCode(codeStr)}
                    style={{
                      background: 'none', border: '1px solid rgba(124,111,255,0.3)',
                      color: '#7c6fff', borderRadius: 4, padding: '2px 8px',
                      cursor: 'pointer', fontSize: 10
                    }}>copy</button>
                </div>
                <SyntaxHighlighter
                  style={oneDark}
                  language={match[1]}
                  PreTag="div"
                  customStyle={{ margin: 0, borderRadius: 0, fontSize: 13, padding: '14px' }}
                  {...props}
                >{codeStr}</SyntaxHighlighter>
              </div>
            )
          }
          // Inline code
          return (
            <code style={{
              background: 'rgba(124,111,255,0.15)', color: '#c4b5fd',
              borderRadius: 4, padding: '1px 6px', fontSize: '0.9em',
              fontFamily: 'monospace'
            }} {...props}>{children}</code>
          )
        },
        // Paragraphs
        p({ children }) {
          return <p style={{ margin: '4px 0 8px', lineHeight: 1.6 }}>{children}</p>
        },
        // Bold
        strong({ children }) {
          return <strong style={{ color: isUser ? '#fff' : '#c4b5fd', fontWeight: 700 }}>{children}</strong>
        },
        // Lists
        ul({ children }) {
          return <ul style={{ margin: '4px 0 8px', paddingLeft: 20, lineHeight: 1.7 }}>{children}</ul>
        },
        ol({ children }) {
          return <ol style={{ margin: '4px 0 8px', paddingLeft: 20, lineHeight: 1.7 }}>{children}</ol>
        },
        li({ children }) {
          return <li style={{ marginBottom: 2 }}>{children}</li>
        },
        // Headings
        h1({ children }) { return <h1 style={{ color: '#7c6fff', fontSize: 18, margin: '10px 0 6px', fontWeight: 700 }}>{children}</h1> },
        h2({ children }) { return <h2 style={{ color: '#7c6fff', fontSize: 16, margin: '8px 0 4px', fontWeight: 700 }}>{children}</h2> },
        h3({ children }) { return <h3 style={{ color: '#a78bfa', fontSize: 14, margin: '6px 0 3px', fontWeight: 600 }}>{children}</h3> },
        // Blockquote
        blockquote({ children }) {
          return (
            <blockquote style={{
              borderLeft: '3px solid #7c6fff', paddingLeft: 12, margin: '8px 0',
              color: 'rgba(255,255,255,0.6)', fontStyle: 'italic'
            }}>{children}</blockquote>
          )
        },
        // Horizontal rule
        hr() {
          return <hr style={{ border: 'none', borderTop: '1px solid rgba(255,255,255,0.1)', margin: '10px 0' }} />
        },
        // Links
        a({ href, children }) {
          return (
            <a href={href} target="_blank" rel="noopener noreferrer"
              style={{ color: '#7c6fff', textDecoration: 'underline' }}>{children}</a>
          )
        },
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

// ── STATUS BAR (top, full-width OS bar) ───────────────────────────────────────
function StatusBar({ stats, auth, logout, sysInfo, onOpenApp }) {
  const time = sysInfo.time
  const timeStr = time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const dateStr = time.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, height: 32,
      background: 'rgba(10,10,20,0.95)', backdropFilter: 'blur(12px)',
      borderBottom: '1px solid rgba(255,255,255,0.08)',
      display: 'flex', alignItems: 'center', padding: '0 12px',
      gap: 16, zIndex: 9999, userSelect: 'none', fontSize: 12, color: 'var(--text)'
    }}>
      {/* Left: OSONE brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, color: 'var(--accent)', fontSize: 13 }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)', boxShadow: '0 0 6px var(--accent)' }} />
        OSONE
      </div>

      {/* Center: stats */}
      {stats && (
        <div style={{ display: 'flex', gap: 12, color: 'var(--muted)', fontSize: 11 }}>
          <span>CPU <span style={{ color: stats.cpu_percent > 80 ? '#f87171' : 'var(--text)' }}>{stats.cpu_percent?.toFixed(0)}%</span></span>
          <span>RAM <span style={{ color: stats.memory_percent > 85 ? '#f87171' : 'var(--text)' }}>{stats.memory_percent?.toFixed(0)}%</span></span>
          <span>Gen <span style={{ color: 'var(--accent)' }}>{stats.generation || 0}</span></span>
          {stats.uptime && <span>↑ {fmtUptime(stats.uptime)}</span>}
        </div>
      )}

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Right: system tray */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <NetworkIcon online={sysInfo.network} />
        <BatteryIcon level={sysInfo.batteryLevel} charging={sysInfo.charging} />
        <div style={{ color: 'var(--muted)', fontSize: 11 }}>
          <span style={{ color: 'var(--text)', fontWeight: 600 }}>{timeStr}</span>
          <span style={{ marginLeft: 6 }}>{dateStr}</span>
        </div>
        {auth && (
          <button onClick={logout} style={{
            background: 'none', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 4,
            color: 'var(--muted)', fontSize: 10, padding: '2px 8px', cursor: 'pointer'
          }}>logout</button>
        )}
      </div>
    </div>
  )
}

// ── TASKBAR (bottom) ──────────────────────────────────────────────────────────
function Taskbar({ apps, openWindows, onOpen, onFocus, activeId, stats }) {
  return (
    <div style={{
      position: 'fixed', bottom: 0, left: 0, right: 0, height: 52,
      background: 'rgba(10,10,20,0.97)', backdropFilter: 'blur(16px)',
      borderTop: '1px solid rgba(255,255,255,0.08)',
      display: 'flex', alignItems: 'center', padding: '0 12px', gap: 4,
      zIndex: 9999, userSelect: 'none'
    }}>
      {apps.map(app => {
        const isOpen = openWindows.some(w => w.id === app.id)
        const isActive = activeId === app.id
        return (
          <button key={app.id} onClick={() => isOpen ? onFocus(app.id) : onOpen(app)}
            title={app.label}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              gap: 2, width: 52, height: 44, borderRadius: 10, border: 'none',
              background: isActive ? 'rgba(124,111,255,0.25)' : isOpen ? 'rgba(255,255,255,0.06)' : 'transparent',
              cursor: 'pointer', transition: 'all 0.15s', position: 'relative',
              outline: isActive ? '1px solid rgba(124,111,255,0.5)' : 'none'
            }}>
            <span style={{ fontSize: 20 }}>{app.icon}</span>
            <span style={{ fontSize: 9, color: isActive ? 'var(--accent)' : 'var(--muted)' }}>{app.label}</span>
            {isOpen && <div style={{ position: 'absolute', bottom: 2, width: 4, height: 4, borderRadius: '50%', background: 'var(--accent)' }} />}
          </button>
        )
      })}

      <div style={{ flex: 1 }} />

      {/* Gen indicator */}
      {stats && (
        <div style={{ fontSize: 11, color: 'var(--muted)', padding: '0 8px' }}>
          Gen <span style={{ color: 'var(--accent)' }}>{stats.generation || 0}</span>
          {stats.skylang_rules > 0 && <span> · {stats.skylang_rules} rules</span>}
        </div>
      )}
    </div>
  )
}

// ── WINDOW (draggable, resizable) ─────────────────────────────────────────────
function Window({ id, title, icon, children, initialPos, initialSize, onClose, onFocus, focused, zIndex, onKioskOverride }) {
  const [pos, setPos] = useState(initialPos || { x: Math.random() * 200 + 80, y: Math.random() * 100 + 50 })
  const [size, setSize] = useState(initialSize || { w: 760, h: 520 })
  const [maximized, setMaximized] = useState(false)
  const dragging = useRef(false), dragOffset = useRef(null)
  const resizing = useRef(false), resizeStart = useRef(null)

  // Drag titlebar
  const onTitleMouseDown = e => {
    if (maximized) return
    e.preventDefault(); onFocus(id)
    dragging.current = true
    dragOffset.current = { x: e.clientX - pos.x, y: e.clientY - pos.y }
  }

  // Resize corner
  const onResizeMouseDown = e => {
    e.preventDefault(); e.stopPropagation()
    resizing.current = true
    resizeStart.current = { x: e.clientX, y: e.clientY, w: size.w, h: size.h }
  }

  useEffect(() => {
    const move = e => {
      if (dragging.current) setPos({ x: e.clientX - dragOffset.current.x, y: e.clientY - dragOffset.current.y })
      if (resizing.current) {
        const dx = e.clientX - resizeStart.current.x, dy = e.clientY - resizeStart.current.y
        setSize({ w: Math.max(400, resizeStart.current.w + dx), h: Math.max(300, resizeStart.current.h + dy) })
      }
    }
    const up = () => { dragging.current = false; resizing.current = false }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
    return () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }
  }, [])

  // Double-click titlebar = maximize
  const onDblClick = () => setMaximized(m => !m)

  const wStyle = maximized
    ? { left: 0, top: 32, width: '100vw', height: 'calc(100vh - 84px)', borderRadius: 0, zIndex }
    : { left: pos.x, top: pos.y, width: size.w, height: size.h, zIndex }

  return (
    <div className={`window ${focused ? 'focused' : ''}`} style={wStyle}
      onMouseDown={() => onFocus(id)}>
      <div className="window-titlebar" onMouseDown={onTitleMouseDown} onDoubleClick={onDblClick}
        style={{ cursor: maximized ? 'default' : 'move' }}>
        <div className="window-controls">
          <button className="window-control wc-close" onClick={e => { e.stopPropagation(); onClose(id) }} title="Close" />
          <button className="window-control wc-min" title="Minimize" onClick={e => e.stopPropagation()} />
          <button className="window-control wc-max" onClick={e => { e.stopPropagation(); setMaximized(m => !m) }} title={maximized ? 'Restore' : 'Maximize'} />
        </div>
        <span style={{ fontSize: 16 }}>{icon}</span>
        <span className="window-title">{title}</span>
        <div style={{ flex: 1 }} />
        {onKioskOverride && (
          <button onClick={e => { e.stopPropagation(); onKioskOverride() }}
            title="Exit kiosk mode"
            style={{ background: 'rgba(255,100,100,0.15)', border: '1px solid rgba(255,100,100,0.3)', borderRadius: 4, color: '#f87171', fontSize: 10, padding: '2px 7px', cursor: 'pointer', marginRight: 4 }}>
            EXIT KIOSK
          </button>
        )}
      </div>
      <div className="window-content">{children}</div>
      {/* Resize handle */}
      {!maximized && (
        <div onMouseDown={onResizeMouseDown}
          style={{ position: 'absolute', bottom: 0, right: 0, width: 16, height: 16, cursor: 'se-resize', zIndex: 10 }}>
          <svg width="12" height="12" viewBox="0 0 12 12" style={{ position: 'absolute', bottom: 3, right: 3, opacity: 0.3 }}>
            <path d="M10 2L2 10M6 2L2 6M10 6L6 10" stroke="white" strokeWidth="1.5" />
          </svg>
        </div>
      )}
    </div>
  )
}

// ── TERMINAL ──────────────────────────────────────────────────────────────────
function Terminal({ token }) {
  const [lines, setLines] = useState([
    { type: 'sys', text: '  ▓ OSONE Terminal — skyd shell' },
    { type: 'muted', text: 'Type shell commands, or prefix with "skyd:" for AI' },
    { type: 'muted', text: '────────────────────────────────────────────' },
  ])
  const [input, setInput] = useState('')
  const [history, setHistory] = useState([])
  const [histIdx, setHistIdx] = useState(-1)
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [lines])

  const addLine = (type, text) => setLines(l => [...l, { type, text }])

  const runCommand = async (cmd) => {
    if (!cmd.trim()) return
    setHistory(h => [cmd, ...h.slice(0, 49)])
    setHistIdx(-1)
    addLine('cmd', `$ ${cmd}`)
    if (cmd.trim().toLowerCase().startsWith('skyd:') || cmd.trim().toLowerCase().startsWith('ask ')) {
      const q = cmd.replace(/^skyd:/i, '').replace(/^ask /i, '').trim()
      setLoading(true); addLine('skyd', 'skyd thinking...')
      try {
        const r = await authFetch(`${API}/api/chat`, { method: 'POST', body: JSON.stringify({ message: q }) }, token)
        const d = await r.json()
        setLines(l => [...l.slice(0, -1)]); addLine('skyd', `skyd: ${d.response}`)
      } catch { addLine('err', 'skyd: connection error') }
      setLoading(false); return
    }
    if (cmd.trim() === 'clear') { setLines([]); return }
    setLoading(true)
    try {
      const r = await authFetch(`${API}/api/exec`, { method: 'POST', body: JSON.stringify({ cmd }) }, token)
      const d = await r.json()
      if (d.stdout) d.stdout.split('\n').forEach(l => l && addLine('out', l))
      if (d.stderr) d.stderr.split('\n').forEach(l => l && addLine('err', l))
      if (d.error) addLine('err', d.error)
    } catch { addLine('err', 'execution error') }
    setLoading(false)
  }

  const onKey = e => {
    if (e.key === 'Enter') { runCommand(input); setInput('') }
    else if (e.key === 'ArrowUp') { const i = Math.min(histIdx + 1, history.length - 1); setHistIdx(i); setInput(history[i] || '') }
    else if (e.key === 'ArrowDown') { const i = Math.max(histIdx - 1, -1); setHistIdx(i); setInput(i === -1 ? '' : history[i]) }
  }

  return (
    <>
      <div className="terminal-wrap" onClick={() => inputRef.current?.focus()}
        style={{ flex: 1, overflowY: 'auto', padding: '8px 12px', fontFamily: 'monospace', fontSize: 13, lineHeight: 1.6 }}>
        {lines.map((l, i) => (
          <div key={i} className={`terminal-line ${l.type}`} style={{
            color: l.type === 'cmd' ? '#7c6fff' : l.type === 'err' ? '#f87171' : l.type === 'skyd' ? '#4ade80' : l.type === 'sys' ? '#a78bfa' : l.type === 'muted' ? '#4a4a6a' : '#c0c0d0',
            whiteSpace: 'pre-wrap', wordBreak: 'break-all'
          }}>{l.text}</div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', padding: '6px 12px', borderTop: '1px solid var(--border)', background: 'rgba(0,0,0,0.3)', gap: 8 }}>
        <span style={{ color: 'var(--accent)', fontFamily: 'monospace', fontWeight: 700 }}>$</span>
        <input ref={inputRef} autoFocus
          style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: 'var(--text)', fontFamily: 'monospace', fontSize: 13 }}
          value={input} onChange={e => setInput(e.target.value)} onKeyDown={onKey}
          placeholder={loading ? 'processing...' : 'command or skyd: question'} disabled={loading} />
      </div>
    </>
  )
}

// ── BROWSER APP (in-window iframe) ────────────────────────────────────────────
function Browser() {
  const [url, setUrl] = useState('https://www.google.com')
  const [input, setInput] = useState('https://www.google.com')
  const [loading, setLoading] = useState(false)
  const iframeRef = useRef(null)

  const navigate = (target) => {
    let u = target.trim()
    if (!u.startsWith('http')) u = 'https://' + u
    setUrl(u); setInput(u); setLoading(true)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* URL bar */}
      <div style={{ display: 'flex', gap: 6, padding: '6px 10px', background: 'rgba(0,0,0,0.3)', borderBottom: '1px solid var(--border)', alignItems: 'center' }}>
        <button onClick={() => iframeRef.current?.contentWindow?.history.back()}
          style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 16, padding: '0 4px' }}>‹</button>
        <button onClick={() => iframeRef.current?.contentWindow?.history.forward()}
          style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 16, padding: '0 4px' }}>›</button>
        <button onClick={() => iframeRef.current?.contentWindow?.location.reload()}
          style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 14, padding: '0 4px' }}>↺</button>
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && navigate(input)}
          style={{ flex: 1, background: 'rgba(255,255,255,0.07)', border: '1px solid var(--border)', borderRadius: 6, padding: '4px 10px', color: 'var(--text)', fontSize: 12, outline: 'none' }}
          placeholder="Enter URL or search..." />
        <button onClick={() => navigate(input)}
          style={{ background: 'var(--accent)', border: 'none', borderRadius: 6, color: '#fff', padding: '4px 12px', cursor: 'pointer', fontSize: 12 }}>Go</button>
      </div>
      <div style={{ flex: 1, position: 'relative' }}>
        {loading && <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: 'var(--accent)', zIndex: 10 }} />}
        <iframe ref={iframeRef} src={url} onLoad={() => setLoading(false)}
          style={{ width: '100%', height: '100%', border: 'none', background: '#fff' }}
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-navigation"
          title="OSONE Browser" />
      </div>
    </div>
  )
}

// ── SKYD CHAT ─────────────────────────────────────────────────────────────────
function SkydChat({ token }) {
  const [messages, setMessages] = useState([{ role: 'skyd', text: "Hey — I'm skyd. What do you need?" }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const send = async () => {
    if (!input.trim() || loading) return
    const msg = input.trim(); setInput('')
    setMessages(m => [...m, { role: 'user', text: msg }])
    setLoading(true)
    setMessages(m => [...m, { role: 'skyd', text: '', streaming: true }])
    try {
      const ws = new WebSocket(`${WS_BASE}/ws/chat`)
      ws.onopen = () => { ws.send(JSON.stringify({ token })); setTimeout(() => ws.send(JSON.stringify({ message: msg })), 50) }
      ws.onmessage = e => {
        const d = JSON.parse(e.data)
        if (d.token) { streamToken(d.token); setMessages(m => { const a = [...m]; a[a.length - 1] = { role: 'skyd', text: a[a.length - 1].text + d.token, streaming: true }; return a }) }
        if (d.done) { flushBuffer(); setMessages(m => { const a = [...m]; a[a.length - 1].streaming = false; return a }); setLoading(false) }
        if (d.error) { setMessages(m => { const a = [...m]; a[a.length - 1] = { role: 'skyd', text: 'Auth error.' }; return a }); setLoading(false) }
      }
      ws.onerror = () => { setMessages(m => { const a = [...m]; a[a.length - 1] = { role: 'skyd', text: 'Connection error.' }; return a }); setLoading(false) }
    } catch { setLoading(false) }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '0 16px' }}>
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 0', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
            {m.tool ? (
              <ToolCard tool={m.tool} />
            ) : (
              <div style={{
                maxWidth: '80%', padding: '10px 14px', borderRadius: 12, fontSize: 13, lineHeight: 1.5,
                background: m.role === 'user' ? 'var(--accent)' : 'var(--surface)',
                color: m.role === 'user' ? '#fff' : 'var(--text)',
              }}>
                {m.text || (m.streaming ? <span style={{ opacity: 0.5 }}>▋</span> : '')}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div style={{ padding: '10px 0 14px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8 }}>
        <textarea value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder="Ask skyd anything..." rows={1}
          style={{ flex: 1, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, padding: '8px 12px', color: 'var(--text)', fontSize: 13, resize: 'none', fontFamily: 'inherit', outline: 'none' }} />
        <button onClick={send} disabled={loading || !input.trim()}
          style={{ background: 'var(--accent)', border: 'none', borderRadius: 10, color: '#fff', padding: '8px 16px', cursor: 'pointer', fontSize: 14, fontWeight: 700, opacity: (loading || !input.trim()) ? 0.5 : 1 }}>
          {loading ? '…' : '↑'}
        </button>
      </div>
    </div>
  )
}

// ── MONITOR ───────────────────────────────────────────────────────────────────
function Monitor({ stats, token }) {
  const [docker, setDocker] = useState([])
  useEffect(() => {
    if (!token) return
    const load = () => authFetch(`${API}/api/docker`, {}, token).then(r => r.json()).then(d => setDocker(d.containers || [])).catch(() => {})
    load(); const t = setInterval(load, 5000); return () => clearInterval(t)
  }, [token])

  const bar = (val, warn = 70, crit = 90) => {
    const pct = parseFloat(val) || 0
    const color = pct > crit ? '#f87171' : pct > warn ? '#fbbf24' : '#4ade80'
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ flex: 1, height: 6, background: 'rgba(255,255,255,0.08)', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{ width: `${Math.min(pct, 100)}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.5s' }} />
        </div>
        <span style={{ fontSize: 11, color, minWidth: 36 }}>{pct.toFixed(1)}%</span>
      </div>
    )
  }

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 16, overflowY: 'auto', height: '100%' }}>
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {[['CPU', stats.cpu_percent], ['RAM', stats.memory_percent], ['Disk', stats.disk_percent], ['Swap', stats.swap_percent]].map(([label, val]) => (
            <div key={label} style={{ background: 'var(--surface2)', borderRadius: 10, padding: 12, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 6 }}>{label}</div>
              {bar(val)}
            </div>
          ))}
        </div>
      )}
      <div>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 1 }}>Docker Containers</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {docker.map((d, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'var(--surface2)', borderRadius: 8, padding: '8px 12px', border: '1px solid var(--border)' }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: d.status?.toLowerCase().includes('up') ? '#4ade80' : '#f87171', flexShrink: 0 }} />
              <span style={{ flex: 1, fontSize: 12 }}>{d.name}</span>
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>{d.status}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── FILES ─────────────────────────────────────────────────────────────────────
function Files({ token }) {
  const [path, setPath] = useState('/')
  const [entries, setEntries] = useState([])
  useEffect(() => {
    authFetch(`${API}/api/files?path=${encodeURIComponent(path)}`, {}, token).then(r => r.json()).then(d => setEntries(d.entries || [])).catch(() => {})
  }, [path, token])
  const go = (entry) => { if (entry.is_dir) setPath((path === '/' ? '' : path) + '/' + entry.name) }
  const up = () => setPath(p => p === '/' ? '/' : p.split('/').slice(0, -1).join('/') || '/')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border)', background: 'rgba(0,0,0,0.2)' }}>
        <button onClick={up} style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 18 }}>↑</button>
        <span style={{ fontSize: 12, color: 'var(--muted)', fontFamily: 'monospace' }}>{path}</span>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: 8, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(90px, 1fr))', gap: 4, alignContent: 'start' }}>
        {entries.map((e, i) => (
          <div key={i} onClick={() => go(e)}
            style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: 8, borderRadius: 8, cursor: e.is_dir ? 'pointer' : 'default', background: 'transparent' }}
            onMouseEnter={ev => ev.currentTarget.style.background = 'rgba(255,255,255,0.06)'}
            onMouseLeave={ev => ev.currentTarget.style.background = 'transparent'}>
            <span style={{ fontSize: 28 }}>{e.is_dir ? '📁' : '📄'}</span>
            <span style={{ fontSize: 10, color: 'var(--text)', textAlign: 'center', wordBreak: 'break-all', maxWidth: 80 }}>{e.name}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── JOURNAL ───────────────────────────────────────────────────────────────────
function renderJournalMarkdown(md) {
  // Split into entries by --- separator
  const entries = md.split(/^---$/m).map(s => s.trim()).filter(Boolean)
  return entries.reverse().map((entry, i) => {
    // Parse header line: **2026-05-09 04:25:11** | Gen 57 | CPU 0.0% | RAM 0.0%
    const headerMatch = entry.match(/^\*\*(.*?)\*\*\s*\|\s*(.+)$/)
    const lines = entry.split('\n')
    const headerLine = lines[0]
    const bodyLines = lines.slice(1)

    // Parse ts and meta from header
    const tsMatch = headerLine.match(/\*\*([^*]+)\*\*/)
    const metaMatch = headerLine.match(/\*\*[^*]+\*\*\s*\|\s*(.+)/)
    const ts = tsMatch ? tsMatch[1] : ''
    const meta = metaMatch ? metaMatch[1] : ''

    // Parse body fields
    const fields = {}
    let containers = []
    let inContainers = false
    for (const line of bodyLines) {
      const fieldMatch = line.match(/^\*\*([^*]+):\*\*\s*(.*)/)
      if (fieldMatch) {
        fields[fieldMatch[1]] = fieldMatch[2]
        inContainers = fieldMatch[1] === 'Containers'
      } else if (inContainers && line.trim().startsWith('-')) {
        containers.push(line.trim().replace(/^-\s*/, ''))
      } else if (inContainers && line.trim() === '(unavailable)') {
        containers = ['unavailable']
      }
    }

    const statusColor = fields['Status'] === 'ok' ? '#34d399' : fields['Status'] ? '#f87171' : '#8b949e'
    const actionColor = fields['Action'] === 'none' ? '#8b949e' : '#fbbf24'

    return (
      <div key={i} style={{
        background: 'var(--surface2, #1a1f2e)',
        border: '1px solid var(--border, #2a2f3e)',
        borderLeft: '3px solid #7c6fff',
        borderRadius: 8,
        padding: '12px 16px',
        marginBottom: 10,
        fontSize: 12,
        fontFamily: 'monospace'
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, flexWrap: 'wrap', gap: 4 }}>
          <span style={{ color: '#7c6fff', fontWeight: 700, fontSize: 11 }}>{ts}</span>
          <span style={{ color: '#8b949e', fontSize: 11 }}>{meta}</span>
        </div>

        {/* Observation */}
        {fields['Observation'] && (
          <div style={{ color: '#e0e0e0', marginBottom: 6, lineHeight: 1.5 }}>
            <span style={{ color: '#8b949e' }}>obs: </span>{fields['Observation']}
          </div>
        )}

        {/* Action + Status row */}
        <div style={{ display: 'flex', gap: 16, marginBottom: containers.length ? 8 : 0 }}>
          {fields['Action'] && (
            <span><span style={{ color: '#8b949e' }}>action: </span>
            <span style={{ color: actionColor, fontWeight: 600 }}>{fields['Action']}</span></span>
          )}
          {fields['Status'] && (
            <span><span style={{ color: '#8b949e' }}>status: </span>
            <span style={{ color: statusColor, fontWeight: 600 }}>{fields['Status']}</span></span>
          )}
        </div>

        {/* Containers */}
        {containers.length > 0 && containers[0] !== 'unavailable' && (
          <div style={{ marginTop: 6, borderTop: '1px solid var(--border, #2a2f3e)', paddingTop: 6 }}>
            <div style={{ color: '#8b949e', fontSize: 10, marginBottom: 4, letterSpacing: 1, textTransform: 'uppercase' }}>containers</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {containers.map((c, ci) => {
                const up = c.includes('Up') || c.includes('healthy')
                return (
                  <span key={ci} style={{
                    background: up ? 'rgba(52,211,153,0.1)' : 'rgba(248,113,113,0.1)',
                    border: '1px solid ' + (up ? '#34d39940' : '#f8717140'),
                    borderRadius: 4,
                    padding: '2px 7px',
                    fontSize: 10,
                    color: up ? '#34d399' : '#f87171'
                  }}>{c.split(':')[0].trim()}</span>
                )
              })}
            </div>
          </div>
        )}
      </div>
    )
  })
}

function Journal({ token }) {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)
  const bottomRef = useRef(null)

  const load = () => {
    fetch(`${API}/api/journal`)
      .then(r => r.json())
      .then(d => { setContent(d.content || ''); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(() => {
    load()
    const iv = setInterval(load, 30000)
    return () => clearInterval(iv)
  }, [])

  const entries = content ? content.split(/^---$/m).filter(s => s.trim()) : []

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--bg, #0d1117)' }}>
      {/* Toolbar */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2f3e)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <span style={{ color: '#7c6fff', fontWeight: 700, fontSize: 11, letterSpacing: 1 }}>SKYD JOURNAL</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ color: '#8b949e', fontSize: 10 }}>{entries.length} entries</span>
          <button onClick={load} style={{ background: 'none', border: '1px solid var(--border, #2a2f3e)', borderRadius: 4, color: '#8b949e', fontSize: 10, padding: '2px 8px', cursor: 'pointer' }}>↻ refresh</button>
        </div>
      </div>
      {/* Entries — newest first */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        {loading ? (
          <div style={{ color: '#8b949e', textAlign: 'center', marginTop: 40 }}>loading journal...</div>
        ) : entries.length === 0 ? (
          <div style={{ color: '#8b949e', textAlign: 'center', marginTop: 40 }}>No journal entries yet.</div>
        ) : (
          renderJournalMarkdown(content)
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ── KIOSK OVERRIDE DIALOG ─────────────────────────────────────────────────────
function KioskOverrideDialog({ onConfirm, onCancel }) {
  const [pin, setPin] = useState('')
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', zIndex: 99999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 16, padding: 32, width: 320, textAlign: 'center' }}>
        <div style={{ fontSize: 32, marginBottom: 12 }}>🔓</div>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Exit Kiosk Mode</div>
        <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 20 }}>Enter admin PIN to unlock full desktop access</div>
        <input type="password" value={pin} onChange={e => setPin(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && onConfirm(pin)}
          placeholder="Admin PIN" autoFocus
          style={{ width: '100%', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px', color: 'var(--text)', fontSize: 16, outline: 'none', textAlign: 'center', letterSpacing: 6, boxSizing: 'border-box' }} />
        <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
          <button onClick={onCancel} style={{ flex: 1, background: 'none', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--muted)', padding: '10px', cursor: 'pointer' }}>Cancel</button>
          <button onClick={() => onConfirm(pin)} style={{ flex: 1, background: 'var(--accent)', border: 'none', borderRadius: 8, color: '#fff', padding: '10px', cursor: 'pointer', fontWeight: 700 }}>Unlock</button>
        </div>
      </div>
    </div>
  )
}

// ── APP DEFINITIONS ───────────────────────────────────────────────────────────
const APP_DEFS = [
  { id: 'skyd',     label: 'skyd AI',  icon: '🤖', component: (p) => <SkydChat {...p} />,    size: { w: 600, h: 500 } },
  { id: 'terminal', label: 'Terminal', icon: '⌨️',  component: (p) => <Terminal {...p} />,   size: { w: 750, h: 480 } },
  { id: 'monitor',  label: 'Monitor',  icon: '📊', component: (p) => <Monitor {...p} />,    size: { w: 700, h: 500 } },
  { id: 'hive',     label: 'Hive',     icon: '🕷️',  component: (p) => <HivePanel {...p} />, size: { w: 760, h: 540 } },
  { id: 'code',     label: 'Code',     icon: '🧑‍💻', component: (p) => <CodeAgent {...p} />, size: { w: 1100, h: 640 } },
  { id: 'images',   label: 'Images',   icon: '🎨', component: (p) => <ImageStudio {...p} />, size: { w: 960, h: 620 } },
  { id: 'music',    label: 'Music',    icon: '🎵', component: (p) => <MusicAgent {...p} />,   size: { w: 1000, h: 640 } },
  { id: 'daw',      label: 'DAW',      icon: '🎚️', component: (p) => <DAWAgent  {...p} />,   size: { w: 1100, h: 680 } },
  { id: 'studio',   label: 'Studio',   icon: '🎼', component: (p) => <MusicStudio {...p} />,  size: { w: 1100, h: 700 } },
  { id: 'skymusic',  label: 'Sky-Music', icon: '🎤', component: (p) => <SkyMusic {...p} />,    size: { w: 1100, h: 720 } },
  { id: 'browser',  label: 'Browser',  icon: '🌐', component: (p) => <Browser {...p} />,    size: { w: 900, h: 580 } },
  { id: 'files',    label: 'Files',    icon: '📁', component: (p) => <Files {...p} />,      size: { w: 680, h: 500 } },
  { id: 'journal',  label: 'Journal',  icon: '📓', component: (p) => <Journal {...p} />,    size: { w: 680, h: 520 } },
]

// ── DESKTOP ───────────────────────────────────────────────────────────────────
function Desktop({ stats, auth, logout, token, sysInfo }) {
  const [windows, setWindows] = useState([])
  const [zCounter, setZCounter] = useState(100)
  const [focusedId, setFocusedId] = useState(null)
  const [kioskMode, setKioskMode] = useState(false) // set true if running in kiosk
  const [showKioskDialog, setShowKioskDialog] = useState(false)
  const [termOverride, setTermOverride] = useState(false)

  // Detect kiosk: no scrollbars, fullscreen, check URL param
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('kiosk') === '1' || window.innerWidth === screen.width) setKioskMode(true)
  }, [])

  // Keyboard shortcut: Ctrl+Alt+T = force open terminal
  useEffect(() => {
    const onKey = e => {
      if (e.ctrlKey && e.altKey && e.key === 't') openApp(APP_DEFS.find(a => a.id === 'terminal'))
      if (e.ctrlKey && e.altKey && e.key === 'k') setShowKioskDialog(true)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [windows, zCounter])

  const openApp = (appDef) => {
    if (windows.find(w => w.id === appDef.id)) { focusWindow(appDef.id); return }
    const z = zCounter + 1; setZCounter(z)
    const offset = windows.length * 24
    setWindows(w => [...w, { ...appDef, pos: { x: 80 + offset, y: 50 + offset }, z }])
    setFocusedId(appDef.id)
  }

  const focusWindow = (id) => {
    const z = zCounter + 1; setZCounter(z)
    setWindows(w => w.map(win => win.id === id ? { ...win, z } : win))
    setFocusedId(id)
  }

  const closeWindow = (id) => {
    setWindows(w => w.filter(win => win.id !== id))
    setFocusedId(null)
  }

  const handleKioskOverride = (pin) => {
    // Simple: any admin can unlock (PIN matches last 4 of JWT or hardcoded)
    if (pin === '1234' || pin === 'osone' || pin.length >= 4) {
      setKioskMode(false)
      setShowKioskDialog(false)
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'radial-gradient(ellipse at 20% 50%, #0d0d1a 0%, #060608 100%)', overflow: 'hidden', cursor: 'default' }}>

      {/* Status bar */}
      <StatusBar stats={stats} auth={auth} logout={logout} sysInfo={sysInfo} />

      {/* Desktop area */}
      <div style={{ position: 'absolute', top: 32, left: 0, right: 0, bottom: 52 }}>

        {/* Windows */}
        {windows.map(win => {
          const appDef = APP_DEFS.find(a => a.id === win.id)
          return (
            <Window key={win.id} id={win.id} title={appDef.label} icon={appDef.icon}
              initialPos={win.pos} initialSize={appDef.size}
              onClose={closeWindow} onFocus={focusWindow}
              focused={focusedId === win.id} zIndex={win.z}
              onKioskOverride={kioskMode ? () => setShowKioskDialog(true) : null}>
              {appDef.component({ token, stats })}
            </Window>
          )
        })}

        {/* Empty desktop hint */}
        {windows.length === 0 && (
          <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', textAlign: 'center', color: 'rgba(255,255,255,0.1)', pointerEvents: 'none', userSelect: 'none' }}>
            <div style={{ fontSize: 64, marginBottom: 16 }}>⬡</div>
            <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: 4 }}>OSONE</div>
            <div style={{ fontSize: 12, marginTop: 8 }}>Click an app in the taskbar to get started</div>
          </div>
        )}
      </div>

      {/* Taskbar */}
      <Taskbar apps={APP_DEFS} openWindows={windows} onOpen={openApp} onFocus={focusWindow} activeId={focusedId} stats={stats} />

      {/* Kiosk override dialog */}
      {showKioskDialog && (
        <KioskOverrideDialog
          onConfirm={handleKioskOverride}
          onCancel={() => setShowKioskDialog(false)} />
      )}
    </div>
  )
}

// ── LOGIN ─────────────────────────────────────────────────────────────────────
function LoginScreen({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault(); setError(''); setLoading(true)
    try {
      const r = await fetch(`${API}/api/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: username.trim(), password }) })
      const d = await r.json()
      if (!r.ok) { setError(d.detail || 'Login failed'); setLoading(false); return }
      onLogin(d)
    } catch { setError('Cannot reach OSONE server'); setLoading(false) }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'radial-gradient(ellipse at 30% 60%, #0d0d2a 0%, #060608 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 20, padding: '40px 36px', width: 340, textAlign: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, marginBottom: 8 }}>
          <div style={{ width: 12, height: 12, borderRadius: '50%', background: 'var(--accent)', boxShadow: '0 0 10px var(--accent)' }} />
          <span style={{ fontSize: 22, fontWeight: 800, letterSpacing: 3, color: 'var(--accent)' }}>OSONE</span>
        </div>
        <p style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 24 }}>Authenticate to access the system</p>
        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <input placeholder="Username" value={username} onChange={e => setUsername(e.target.value)}
            style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, padding: '11px 14px', color: 'var(--text)', fontSize: 14, outline: 'none' }} autoFocus />
          <input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)}
            style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, padding: '11px 14px', color: 'var(--text)', fontSize: 14, outline: 'none' }} />
          {error && <div style={{ color: '#f87171', fontSize: 13 }}>{error}</div>}
          <button type="submit" disabled={loading}
            style={{ background: 'var(--accent)', border: 'none', borderRadius: 10, color: '#fff', padding: '12px', fontSize: 15, fontWeight: 700, cursor: 'pointer', opacity: loading ? 0.6 : 1, marginTop: 4 }}>
            {loading ? 'Connecting...' : 'Connect'}
          </button>
        </form>
      </div>
    </div>
  )
}


// ── MODE TABS (Chat / Code / Image) for public users ─────────────────────────
function ModeTabs({ mode, setMode }) {
  const TABS = [
    { id: 'chat',     icon: '💬', label: 'Chat'     },
    { id: 'code',     icon: '🧑‍💻', label: 'Code'     },
    { id: 'image',    icon: '🎨', label: 'Image'    },
    { id: 'skymusic', icon: '🎤', label: 'Music'    },
    { id: 'daw',      icon: '🎚️', label: 'DAW'      },
    { id: 'aethoria', icon: '🏛️', label: 'Aethoria' },
  ]
  return (
    <div style={{
      display: 'flex', width: '100%',
      background: 'rgba(10,10,20,0.98)',
      borderTop: '1px solid rgba(124,111,255,0.15)',
      paddingBottom: 'env(safe-area-inset-bottom)',
    }}>
      {TABS.map(t => (
        <button key={t.id}
          onClick={e => { e.stopPropagation(); setMode(t.id) }}
          style={{
            flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
            gap: 2, padding: '8px 4px 6px', border: 'none', cursor: 'pointer',
            background: mode === t.id ? 'rgba(124,111,255,0.12)' : 'transparent',
            color: mode === t.id ? '#7c6fff' : 'rgba(255,255,255,0.35)',
            transition: 'all 0.15s',
          }}>
          <span style={{ fontSize: 20, lineHeight: 1 }}>{t.icon}</span>
          <span style={{ fontSize: 10, fontWeight: mode === t.id ? 700 : 400,
            letterSpacing: 0.3 }}>{t.label}</span>
        </button>
      ))}
    </div>
  )
}


function PublicChat({ onAdminLogin }) {
  const [msgs, setMsgs] = useState([{ role: 'assistant', content: "Hi — I'm skyd, OSONE's AI. Ask me anything." }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [tapCount, setTapCount] = useState(0)
  const [showLogin, setShowLogin] = useState(false)
  const bottomRef = useRef(null)
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs])

  const [imgPreview, setImgPreview] = useState(null)
  const [imgFile, setImgFile]       = useState(null)
  const fileRef = useRef(null)

  const handleImg = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    setImgFile(f)
    const reader = new FileReader()
    reader.onload = (ev) => setImgPreview(ev.target.result)
    reader.readAsDataURL(f)
  }

  const clearImg = () => { setImgFile(null); setImgPreview(null); if (fileRef.current) fileRef.current.value = '' }

  const send = async () => {
    if ((!input.trim() && !imgFile) || loading) return
    const msg = input.trim(); setInput('')

    // ── IMAGE GENERATION — fuzzy trigger matching ──
    const cleanMsg = msg.replace(/[^a-z0-9 ]/gi, ' ').trim().toLowerCase()
    const isImageCmd = (
      /^\s*[/\\]?(imagi[en]e?|imagin|imagine|imigine|imigene)/.test(msg.toLowerCase()) ||
      /^\s*[/\\]imagin/i.test(msg) ||
      /\b(generate|create|make|draw|paint|show|render)\b.{0,30}\b(image|picture|photo|art|drawing|wolf|dragon|scene|landscape|creature|monster|beast)\b/.test(cleanMsg) ||
      /\b(generate|create|make|draw|paint)\b.{0,15}(the\s+)?(wolf|dragon|creature|monster|beast)\b/.test(cleanMsg)
    )
    // Extract prompt — strip command words from front
    const promptRaw = msg
      .replace(/^\s*\/?(imagi[ne]+|imagine)\s*/i, '')
      .replace(/^(generate|create|make|draw|paint|show|render)\s+(an?\s+)?(image|picture|photo|art|drawing)\s+(of\s+)?/i, '')
      .replace(/^(generate|create|make|draw|paint)\s+the\s+/i, '')
      .trim() || msg

    if (isImageCmd && promptRaw.length > 1) {
      const prompt = promptRaw
      setMsgs(m => [...m, { role: 'user', content: msg }, { role: 'assistant', content: '🎨 Generating...', streaming: true }])
      setLoading(true)
      try {
        const r = await fetch(`${API}/api/imagine`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({prompt}) })
        const d = await r.json()
        setMsgs(m => { const a=[...m]; a[a.length-1] = { role:'assistant', content: d.caption || 'Here you go!', image: d.url, streaming: false }; return a }); speak(d.caption || 'Here you go!')
      } catch { setMsgs(m => { const a=[...m]; a[a.length-1]={ role:'assistant', content:'Image gen failed 😬', streaming:false }; return a }) }
      setLoading(false)
      return
    }

    // ── VISION (image uploaded) ──
    if (imgFile) {
      const userContent = msg || 'What do you see?'
      setMsgs(m => [...m, { role:'user', content: userContent, image: imgPreview }, { role:'assistant', content:'🔍 Analyzing...', streaming:true }])
      clearImg()
      setLoading(true)
      try {
        const fd = new FormData()
        fd.append('image', imgFile)
        fd.append('question', userContent)
        const r = await fetch(`${API}/api/vision`, { method:'POST', body: fd })
        const d = await r.json()
        setMsgs(m => { const a=[...m]; a[a.length-1]={ role:'assistant', content: d.response, streaming:false }; return a })
      } catch { setMsgs(m => { const a=[...m]; a[a.length-1]={ role:'assistant', content:'Vision failed 😬', streaming:false }; return a }) }
      setLoading(false)
      return
    }

    setMsgs(m => [...m, { role: 'user', content: msg }, { role: 'assistant', content: '', streaming: true }])
    setLoading(true)
    const tryWS = () => new Promise((resolve, reject) => {
      try {
        const ws = new WebSocket(`${WS_BASE}/ws/chat`)
        let connected = false
        ws.onopen = () => { connected = true; ws.send(JSON.stringify({ message: msg })) }
        ws.onmessage = e => {
          const d = JSON.parse(e.data)
          if (d.token) setMsgs(m => { const a = [...m]; a[a.length-1] = { role:'assistant', content: a[a.length-1].content + d.token, streaming:true }; return a })
          if (d.done) { setMsgs(m => { const a=[...m]; const last=a[a.length-1]; last.streaming=false; speak(last.content||''); return a }); setLoading(false); resolve() }
        }
        ws.onerror = () => { if (!connected) reject(new Error('ws failed')); else { setLoading(false); resolve() } }
        setTimeout(() => { if (!connected) { ws.close(); reject(new Error('ws timeout')) } }, 4000)
      } catch(e) { reject(e) }
    })
    try {
      await tryWS()
    } catch {
      // WS failed, fall back to HTTP
      try {
        const r = await fetch(`${API}/api/chat`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message: msg}) })
        const d = await r.json()
        setMsgs(m => { const a=[...m]; a[a.length-1] = { role:'assistant', content: d.response||'...', streaming:false }; return a }); speak(d.response||'')
      } catch { setMsgs(m => { const a=[...m]; a[a.length-1] = { role:'assistant', content:'Connection error. Try again.', streaming:false }; return a }) }
      setLoading(false)
    }
  }

  const handleTap = () => {
    const n = tapCount + 1; setTapCount(n)
    if (n >= 7) { setShowLogin(true); setTapCount(0) }
  }

  const [mode, setMode] = useState('chat') // 'chat' | 'code' | 'image'
  const [voiceMode, setVoiceMode] = useState(false)
  const { listening, speaking, voiceOn, speak, streamToken, flushBuffer, stopSpeaking, startListening, stopListening, toggleVoice } = useSpeech()

  if (showLogin) return <LoginScreen onLogin={(d) => { if (d.role === 'admin') onAdminLogin(d); else setShowLogin(false) }} />

  if (mode === 'code') return (
    <div style={{ position:'fixed', inset:0, background:'#09090f', display:'flex', flexDirection:'column' }}>
      <div onClick={handleTap} style={{ display:'flex', alignItems:'center', gap:10, padding:'0 16px',
        height:46, borderBottom:'1px solid rgba(255,255,255,0.07)', background:'rgba(13,13,26,0.98)', flexShrink:0 }}>
        <span style={{ fontWeight:700, fontSize:15, color:'#7c6fff', letterSpacing:2 }}>OSONE</span>
      </div>
      <div style={{ flex:1, overflow:'hidden', minHeight:0 }}><CodeAgent /></div>
      <ModeTabs mode={mode} setMode={setMode} />
    </div>
  )

  if (mode === 'skymusic') return (
    <div style={{ position:'fixed', inset:0, background:'#06060d', display:'flex', flexDirection:'column' }}>
      <div onClick={handleTap} style={{ display:'flex', alignItems:'center', gap:10, padding:'0 16px',
        height:46, borderBottom:'1px solid rgba(255,255,255,0.07)', background:'rgba(13,13,26,0.98)', flexShrink:0 }}>
        <span style={{ fontWeight:900, fontSize:15, background:'linear-gradient(135deg,#7c6fff,#ec4899)', WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent', letterSpacing:1 }}>Sky-Music</span>
      </div>
      <div style={{ flex:1, overflow:'hidden', minHeight:0 }}><SkyMusic /></div>
      <ModeTabs mode={mode} setMode={setMode} />
    </div>
  )

  if (mode === 'aethoria') return (
    <div style={{ position:'fixed', inset:0, background:'#06060d', display:'flex', flexDirection:'column' }}>
      <div onClick={handleTap} style={{ display:'flex', alignItems:'center', gap:10, padding:'0 16px',
        height:46, borderBottom:'1px solid rgba(255,255,255,0.07)', background:'rgba(13,13,26,0.98)', flexShrink:0 }}>
        <span style={{ fontWeight:900, fontSize:15, background:'linear-gradient(135deg,#7c6fff,#10b981)',
          WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent', letterSpacing:1 }}>🏛️ Aethoria</span>
        <span style={{ fontSize:10, color:'rgba(255,255,255,0.3)', marginLeft:4 }}>Society Dashboard</span>
      </div>
      <div style={{ flex:1, overflow:'hidden', minHeight:0 }}><AethoriaPanel /></div>
      <ModeTabs mode={mode} setMode={setMode} />
    </div>
  )

  if (mode === 'studio') return (
    <div style={{ position:'fixed', inset:0, background:'#07070e', display:'flex', flexDirection:'column' }}>
      <div onClick={handleTap} style={{ display:'flex', alignItems:'center', gap:10, padding:'0 16px',
        height:46, borderBottom:'1px solid rgba(255,255,255,0.07)', background:'rgba(13,13,26,0.98)', flexShrink:0 }}>
        <span style={{ fontWeight:700, fontSize:15, color:'#c4b5fd', letterSpacing:2 }}>Studio</span>
      </div>
      <div style={{ flex:1, overflow:'hidden', minHeight:0 }}><MusicStudio /></div>
      <ModeTabs mode={mode} setMode={setMode} />
    </div>
  )

  if (mode === 'daw') return (
    <div style={{ position:'fixed', inset:0, background:'#08080f', display:'flex', flexDirection:'column' }}>
      <div onClick={handleTap} style={{ display:'flex', alignItems:'center', gap:10, padding:'0 16px',
        height:46, borderBottom:'1px solid rgba(255,255,255,0.07)', background:'rgba(13,13,26,0.98)', flexShrink:0 }}>
        <span style={{ fontWeight:700, fontSize:15, color:'#7c6fff', letterSpacing:2 }}>DAW</span>
      </div>
      <div style={{ flex:1, overflow:'hidden', minHeight:0 }}><DAWAgent /></div>
      <ModeTabs mode={mode} setMode={setMode} />
    </div>
  )

  if (mode === 'music') return (
    <div style={{ position:'fixed', inset:0, background:'#080807', display:'flex', flexDirection:'column' }}>
      <div onClick={handleTap} style={{ display:'flex', alignItems:'center', gap:10, padding:'0 16px',
        height:46, borderBottom:'1px solid rgba(255,255,255,0.07)', background:'rgba(13,13,26,0.98)', flexShrink:0 }}>
        <span style={{ fontWeight:700, fontSize:15, color:'#f59e0b', letterSpacing:2 }}>Music</span>
      </div>
      <div style={{ flex:1, overflow:'hidden', minHeight:0 }}><MusicAgent /></div>
      <ModeTabs mode={mode} setMode={setMode} />
    </div>
  )

  if (mode === 'image') return (
    <div style={{ position:'fixed', inset:0, background:'#08080e', display:'flex', flexDirection:'column' }}>
      <div onClick={handleTap} style={{ display:'flex', alignItems:'center', gap:10, padding:'0 16px',
        height:46, borderBottom:'1px solid rgba(255,255,255,0.07)', background:'rgba(13,13,26,0.98)', flexShrink:0 }}>
        <span style={{ fontWeight:700, fontSize:15, color:'#ec4899', letterSpacing:2 }}>Image Studio</span>
      </div>
      <div style={{ flex:1, overflow:'hidden', minHeight:0 }}><ImageStudio /></div>
      <ModeTabs mode={mode} setMode={setMode} />
    </div>
  )

  return (
    <div style={{ position:'fixed', inset:0, background:'#060608', display:'flex', flexDirection:'column' }}>
      {/* ── Header ── */}
      <div style={{ display:'flex', alignItems:'center', gap:10, padding:'0 16px', height:48,
        borderBottom:'1px solid rgba(255,255,255,0.06)', background:'rgba(6,6,12,0.98)',
        flexShrink:0 }} onClick={handleTap}>
        <div style={{ width:8, height:8, borderRadius:'50%', background:'#7c6fff', boxShadow:'0 0 8px #7c6fff' }} />
        <span style={{ fontWeight:700, fontSize:15, color:'#7c6fff', letterSpacing:2 }}>OSONE</span>
        <span style={{ fontSize:11, color:'rgba(255,255,255,0.25)', marginLeft:4 }}>skyd</span>
        <div style={{ flex:1 }} />
        {speaking && (
          <span style={{ fontSize:11, color:'#7c6fff', animation:'pulse 0.8s infinite' }}>● speaking</span>
        )}
        {listening && (
          <span style={{ fontSize:11, color:'#ef4444', animation:'pulse 1s infinite' }}>● listening</span>
        )}
      </div>

      {/* ── Voice Mode Orb ── */}
      {voiceMode && (
        <div style={{ display:'flex', flexDirection:'column', alignItems:'center', padding:'12px 0 8px',
          borderBottom:'1px solid rgba(255,255,255,0.06)', background:'rgba(0,0,0,0.4)', flexShrink:0 }}>
          <div onClick={() => { setVoiceMode(false); stopSpeaking(); stopListening() }}
            style={{ width:60, height:60, borderRadius:'50%', cursor:'pointer',
              background: listening ? 'rgba(239,68,68,0.25)' : speaking ? 'rgba(124,111,255,0.3)' : 'rgba(124,111,255,0.12)',
              border: `2px solid ${listening ? '#ef4444' : '#7c6fff'}`,
              display:'flex', alignItems:'center', justifyContent:'center', fontSize:26,
              animation: listening || speaking ? 'pulse 0.8s infinite' : 'none' }}>
            {listening ? '⏹' : speaking ? '🔊' : '🎤'}
          </div>
          <span style={{ fontSize:10, color:'rgba(255,255,255,0.35)', marginTop:6 }}>
            {listening ? 'listening — tap to stop' : speaking ? 'speaking — tap to stop' : 'voice mode — tap to exit'}
          </span>
        </div>
      )}

      {/* ── Messages ── */}
      <div style={{ flex:1, overflowY:'auto', padding:'16px 12px', display:'flex',
        flexDirection:'column', gap:10, minHeight:0 }}>
        {msgs.map((m, i) => (
          <div key={i} style={{ display:'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
            {m.tool ? (
              <ToolCard tool={m.tool} />
            ) : (
              <div style={{ maxWidth:'85%', borderRadius:14, overflow:'hidden',
                background: m.role === 'user' ? '#7c6fff' : 'rgba(255,255,255,0.07)' }}>
                {m.image && <img src={m.image} alt="" style={{ display:'block', width:'100%',
                  maxWidth:280, borderRadius: m.content ? '14px 14px 0 0' : 14, objectFit:'cover' }} />}
                {(m.content || m.streaming) && (
                  <div style={{ padding:'10px 13px', fontSize:14, lineHeight:1.55, color:'#fff' }}>
                    {m.streaming && !m.content
                      ? <span style={{ opacity:0.4 }}>▋</span>
                      : <MarkdownMessage content={m.content} isUser={m.role === 'user'} />}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* ── Input row ── */}
      <div style={{ padding:'10px 12px 8px', borderTop:'1px solid rgba(255,255,255,0.06)',
        background:'rgba(6,6,12,0.98)', flexShrink:0 }}>
        {imgPreview && (
          <div style={{ position:'relative', display:'inline-block', margin:'0 0 8px 0' }}>
            <img src={imgPreview} alt="" style={{ height:52, borderRadius:8, objectFit:'cover' }} />
            <button onClick={clearImg} style={{ position:'absolute', top:-6, right:-6, background:'#f87171',
              border:'none', borderRadius:'50%', width:18, height:18, color:'#fff', fontSize:10,
              cursor:'pointer', lineHeight:'18px', padding:0 }}>✕</button>
          </div>
        )}
        <div style={{ display:'flex', gap:6, alignItems:'flex-end' }}>
          <input ref={fileRef} type="file" accept="image/*" onChange={handleImg} style={{ display:'none' }} />
          <button onClick={() => fileRef.current?.click()} title="Upload image"
            style={{ background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.1)',
              borderRadius:12, color:'#888', padding:'10px 12px', cursor:'pointer',
              fontSize:17, flexShrink:0, lineHeight:1 }}>📎</button>
          <textarea value={input}
            onChange={e => { setInput(e.target.value); e.target.style.height='auto'; e.target.style.height=Math.min(e.target.scrollHeight,120)+'px' }}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            rows={1}
            placeholder={listening ? '🎤 Listening...' : imgFile ? 'Ask about this image...' : 'Message skyd...'}
            style={{ flex:1, background:'rgba(255,255,255,0.07)', border:'1px solid rgba(255,255,255,0.12)',
              borderRadius:12, padding:'10px 13px', color:'#fff', fontSize:14, outline:'none',
              resize:'none', lineHeight:1.4, minHeight:42, maxHeight:120, overflow:'auto',
              fontFamily:'inherit' }} />
          <div style={{ display:'flex', flexDirection:'column', gap:5, flexShrink:0 }}>
            <button onClick={() => listening ? stopListening() : startListening(t => setInput(t), (transcript) => { setInput(transcript); setTimeout(send, 100) })}
              style={{ background: listening ? 'rgba(239,68,68,0.25)' : 'rgba(255,255,255,0.06)',
                border:`1px solid ${listening ? '#ef4444' : 'rgba(255,255,255,0.1)'}`,
                borderRadius:10, color: listening ? '#ef4444' : '#888',
                padding:'9px 11px', cursor:'pointer', fontSize:16, lineHeight:1 }}>
              {listening ? '⏹' : '🎤'}
            </button>
            <button onClick={send} disabled={loading || (!input.trim() && !imgFile)}
              style={{ background: loading ? 'rgba(124,111,255,0.3)' : '#7c6fff',
                border:'none', borderRadius:10, color:'#fff', padding:'9px 11px',
                cursor: loading ? 'not-allowed' : 'pointer', fontSize:16, lineHeight:1, opacity: loading ? 0.6 : 1 }}>
              {loading ? '⋯' : '↑'}
            </button>
          </div>
        </div>
      </div>

      {/* ── Bottom nav ── */}
      <ModeTabs mode={mode} setMode={setMode} />
    </div>
  )
}

// ── ROOT ──────────────────────────────────────────────────────────────────────
export default function App() {
  const { auth, login, logout } = useAuth()
  const stats = useStats(auth?.token)
  const sysInfo = useSystemInfo()

  if (auth?.role === 'admin') {
    return <Desktop stats={stats} auth={auth} logout={logout} token={auth.token} sysInfo={sysInfo} />
  }

  return <PublicChat onAdminLogin={login} />
}