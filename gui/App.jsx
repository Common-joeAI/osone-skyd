
import { useState, useEffect, useRef, useCallback } from 'react'
import './index.css'

const API = `http://${window.location.hostname}:8000`
const WS_BASE = `ws://${window.location.hostname}:8000`

function useStats() {
  const [stats, setStats] = useState(null)
  useEffect(() => {
    const fetch_ = () => fetch(`${API}/api/stats`).then(r=>r.json()).then(setStats).catch(()=>{})
    fetch_()
    const t = setInterval(fetch_, 3000)
    return () => clearInterval(t)
  }, [])
  return stats
}

function fmt(bytes) {
  if (bytes > 1e9) return (bytes/1e9).toFixed(1)+'GB'
  if (bytes > 1e6) return (bytes/1e6).toFixed(0)+'MB'
  return (bytes/1e3).toFixed(0)+'KB'
}
function fmtUptime(s) {
  const h = Math.floor(s/3600), m = Math.floor((s%3600)/60)
  return `${h}h ${m}m`
}

// Draggable Window
function Window({ id, title, icon, children, initialPos, initialSize, onClose, onFocus, focused, zIndex }) {
  const [pos, setPos] = useState(initialPos || { x: 100, y: 60 })
  const [size, setSize] = useState(initialSize || { w: 700, h: 500 })
  const [maximized, setMaximized] = useState(false)
  const dragging = useRef(false), dragOffset = useRef(null)

  const onMouseDown = e => {
    onFocus(id)
    dragging.current = true
    dragOffset.current = { x: e.clientX - pos.x, y: e.clientY - pos.y }
  }
  useEffect(() => {
    const move = e => { if (dragging.current && !maximized) setPos({ x: e.clientX - dragOffset.current.x, y: e.clientY - dragOffset.current.y }) }
    const up = () => { dragging.current = false }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
    return () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }
  }, [maximized])

  const style = maximized
    ? { left:0, top:0, width:'100vw', height:'calc(100vh - 52px)', borderRadius:0, zIndex }
    : { left: pos.x, top: pos.y, width: size.w, height: size.h, zIndex }

  return (
    <div className={`window ${focused ? 'focused' : ''}`} style={style} onMouseDown={() => onFocus(id)}>
      <div className="window-titlebar" onMouseDown={onMouseDown}>
        <div className="window-controls">
          <button className="window-control wc-close" onClick={() => onClose(id)} />
          <button className="window-control wc-min" />
          <button className="window-control wc-max" onClick={() => setMaximized(m=>!m)} />
        </div>
        <span style={{fontSize:16}}>{icon}</span>
        <span className="window-title">{title}</span>
      </div>
      <div className="window-content">{children}</div>
    </div>
  )
}

// TERMINAL APP
function Terminal() {
  const [lines, setLines] = useState([
    { type: 'sys', text: '  ███████╗██╗  ██╗██╗   ██╗██████╗ ' },
    { type: 'sys', text: '  ██╔════╝██║ ██╔╝╚██╗ ██╔╝██╔══██╗' },
    { type: 'sys', text: '  ███████╗█████╔╝  ╚████╔╝ ██║  ██║' },
    { type: 'sys', text: '  ╚════██║██╔═██╗   ╚██╔╝  ██║  ██║' },
    { type: 'sys', text: '  ███████║██║  ██╗   ██║   ██████╔╝' },
    { type: 'sys', text: '  ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═════╝ ' },
    { type: 'skyd', text: 'OSONE Terminal — type commands or ask skyd anything' },
    { type: 'muted', text: 'Prefix with "skyd:" to query the AI. e.g.  skyd: what is my CPU temp?' },
    { type: 'muted', text: '─────────────────────────────────────────────────────' },
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
    setHistory(h => [cmd, ...h])
    setHistIdx(-1)
    addLine('cmd', `root@osone:~# ${cmd}`)

    if (cmd.trim().toLowerCase().startsWith('skyd:') || cmd.trim().toLowerCase().startsWith('ask ')) {
      const q = cmd.replace(/^skyd:/i,'').replace(/^ask /i,'').trim()
      setLoading(true)
      addLine('skyd', 'skyd thinking...')
      try {
        const r = await fetch(`${API}/api/chat`, {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ message: q })
        })
        const d = await r.json()
        setLines(l => [...l.slice(0,-1)])
        addLine('skyd', `skyd: ${d.response}`)
      } catch { addLine('err', 'skyd: connection error') }
      setLoading(false)
      return
    }

    // Run shell command
    setLoading(true)
    try {
      const r = await fetch(`${API}/api/exec`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ cmd })
      })
      const d = await r.json()
      if (d.stdout) d.stdout.split('\n').forEach(l => l && addLine('out', l))
      if (d.stderr) d.stderr.split('\n').forEach(l => l && addLine('err', l))
      if (d.error) addLine('err', d.error)
    } catch { addLine('err', 'execution error') }
    setLoading(false)
  }

  const onKey = e => {
    if (e.key === 'Enter') { runCommand(input); setInput('') }
    else if (e.key === 'ArrowUp') { const i = Math.min(histIdx+1, history.length-1); setHistIdx(i); setInput(history[i]||'') }
    else if (e.key === 'ArrowDown') { const i = Math.max(histIdx-1, -1); setHistIdx(i); setInput(i<0?'':history[i]||'') }
  }

  return (
    <>
      <div className="terminal-wrap" onClick={() => inputRef.current?.focus()}>
        {lines.map((l,i) => <div key={i} className={`terminal-line ${l.type}`}>{l.text}</div>)}
        <div ref={bottomRef} />
      </div>
      <div className="terminal-input-row">
        <span className="terminal-prompt">root@osone:~#</span>
        <input ref={inputRef} autoFocus className="terminal-input" value={input}
          onChange={e => setInput(e.target.value)} onKeyDown={onKey}
          placeholder={loading ? 'processing...' : 'command or skyd: question'} disabled={loading} />
      </div>
    </>
  )
}

// SKYD CHAT APP
function SkydChat() {
  const [messages, setMessages] = useState([
    { role: 'skyd', text: "I'm skyd — the OSONE daemon. I manage this system and I think. What do you need?" }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const send = async () => {
    if (!input.trim() || loading) return
    const msg = input.trim()
    setInput('')
    setMessages(m => [...m, { role: 'user', text: msg }])
    setLoading(true)
    setMessages(m => [...m, { role: 'skyd', text: '', streaming: true }])
    try {
      const ws = new WebSocket(`${WS_BASE}/ws/chat`)
      ws.onopen = () => ws.send(JSON.stringify({ message: msg }))
      ws.onmessage = e => {
        const d = JSON.parse(e.data)
        if (d.token) setMessages(m => { const a=[...m]; a[a.length-1]={role:'skyd',text:a[a.length-1].text+d.token,streaming:true}; return a })
        if (d.done) { setMessages(m => { const a=[...m]; a[a.length-1].streaming=false; return a }); setLoading(false); ws.close() }
      }
      ws.onerror = () => { setMessages(m => { const a=[...m]; a[a.length-1]={role:'skyd',text:'Connection error.'}; return a }); setLoading(false) }
    } catch { setLoading(false) }
  }

  return (
    <>
      <div className="chat-messages">
        {messages.map((m,i) => (
          <div key={i} className={`chat-msg ${m.role}`}>
            <span className="chat-label">{m.role === 'skyd' ? '🤖 skyd' : '👤 you'}</span>
            <div className="chat-bubble">
              {m.text || (m.streaming ? <div className="typing"><span/><span/><span/></div> : '')}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="chat-input-row">
        <input className="chat-input" value={input} onChange={e=>setInput(e.target.value)}
          onKeyDown={e=>e.key==='Enter'&&send()} placeholder="Talk to skyd..." />
        <button className="chat-send" onClick={send} disabled={loading}>Send</button>
      </div>
    </>
  )
}

// SYSTEM MONITOR
function SysMonitor({ stats }) {
  if (!stats) return <div style={{padding:16,color:'var(--muted)'}}>Loading...</div>
  const svcs = Object.entries(stats.services||{})
  return (
    <div className="stats-grid">
      <div className="stat-card">
        <div className="stat-label">skyd Generation</div>
        <div className="stat-value">Gen {stats.gen}</div>
        <div className="stat-sub">{stats.rules} SkyLang rules</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">Uptime</div>
        <div className="stat-value">{fmtUptime(stats.uptime)}</div>
        <div className="stat-sub">{stats.hostname} · {stats.kernel?.split('-')[0]}</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">CPU Usage</div>
        <div className="stat-value">{stats.cpu?.toFixed(1)}%</div>
        <div className="progress-bar"><div className={`progress-fill ${stats.cpu>80?'danger':stats.cpu>60?'warn':''}`} style={{width:`${stats.cpu}%`}} /></div>
      </div>
      <div className="stat-card">
        <div className="stat-label">Memory</div>
        <div className="stat-value">{stats.mem_pct?.toFixed(1)}%</div>
        <div className="stat-sub">{fmt(stats.mem_used)} / {fmt(stats.mem_total)}</div>
        <div className="progress-bar"><div className={`progress-fill ${stats.mem_pct>85?'danger':stats.mem_pct>65?'warn':''}`} style={{width:`${stats.mem_pct}%`}} /></div>
      </div>
      <div className="stat-card" style={{gridColumn:'1/-1'}}>
        <div className="stat-label" style={{marginBottom:10}}>Services</div>
        <div className="services-list">
          {svcs.map(([name,status]) => (
            <div key={name} className="svc-row">
              <span>{name}</span>
              <div style={{display:'flex',alignItems:'center',gap:6}}>
                <div className={`svc-dot ${status==='active'?'active':'inactive'}`} />
                <span style={{color:status==='active'?'var(--green)':'var(--red)',fontSize:11}}>{status}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="stat-card" style={{gridColumn:'1/-1'}}>
        <div className="stat-label">Disk</div>
        <div className="stat-sub" style={{marginBottom:6}}>{fmt(stats.disk_used)} / {fmt(stats.disk_total)}</div>
        <div className="progress-bar"><div className={`progress-fill ${stats.disk_pct>85?'danger':stats.disk_pct>65?'warn':''}`} style={{width:`${stats.disk_pct}%`}} /></div>
      </div>
    </div>
  )
}

// JOURNAL
function Journal() {
  const [content, setContent] = useState('Loading...')
  useEffect(() => {
    fetch(`${API}/api/journal`).then(r=>r.json()).then(d=>setContent(d.content)).catch(()=>setContent('Error loading journal'))
  }, [])
  return <div className="journal-content">{content}</div>
}

// FILES
function Files() {
  const [path, setPath] = useState('/')
  const [entries, setEntries] = useState([])
  useEffect(() => {
    fetch(`${API}/api/files?path=${encodeURIComponent(path)}`).then(r=>r.json()).then(d=>setEntries(d.entries||[]))
  }, [path])
  const nav = (entry) => { if (entry.is_dir) setPath(path.replace(/\/$/,'')+'/'+entry.name) }
  const up = () => { const p=path.split('/').filter(Boolean); p.pop(); setPath('/'+p.join('/')) }
  return (
    <>
      <div className="files-path">
        {path !== '/' && <span style={{cursor:'pointer',marginRight:8,color:'var(--accent)'}} onClick={up}>↑ ..</span>}
        {path}
      </div>
      <div className="files-list">
        {entries.map((e,i) => (
          <div key={i} className="file-row" onClick={()=>nav(e)}>
            <span className="file-icon">{e.is_dir ? '📁' : '📄'}</span>
            <span className="file-name">{e.name}</span>
            {!e.is_dir && <span className="file-size">{fmt(e.size)}</span>}
          </div>
        ))}
      </div>
    </>
  )
}

// CLOCK
function Clock() {
  const [t, setT] = useState(new Date())
  useEffect(() => { const i = setInterval(()=>setT(new Date()),1000); return ()=>clearInterval(i) }, [])
  return <span className="taskbar-clock">{t.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</span>
}

const APPS = [
  { id: 'terminal', title: 'Terminal', icon: '⌨️', initialPos:{x:80,y:40}, initialSize:{w:750,h:520} },
  { id: 'chat', title: 'skyd AI', icon: '🤖', initialPos:{x:200,y:80}, initialSize:{w:520,h:560} },
  { id: 'monitor', title: 'System Monitor', icon: '📊', initialPos:{x:300,y:60}, initialSize:{w:520,h:500} },
  { id: 'journal', title: 'Evolution Journal', icon: '📓', initialPos:{x:150,y:100}, initialSize:{w:600,h:500} },
  { id: 'files', title: 'File Manager', icon: '📁', initialPos:{x:250,y:80}, initialSize:{w:480,h:500} },
]

export default function App() {
  const [openWindows, setOpenWindows] = useState([])
  const [focusStack, setFocusStack] = useState([])
  const stats = useStats()

  const openApp = (appId) => {
    if (!openWindows.find(w=>w.id===appId)) setOpenWindows(w=>[...w, APPS.find(a=>a.id===appId)])
    setFocusStack(s=>[...s.filter(x=>x!==appId), appId])
  }
  const closeWindow = (id) => { setOpenWindows(w=>w.filter(x=>x.id!==id)); setFocusStack(s=>s.filter(x=>x!==id)) }
  const focusWindow = (id) => setFocusStack(s=>[...s.filter(x=>x!==id), id])

  const renderContent = (app) => {
    switch(app.id) {
      case 'terminal': return <Terminal />
      case 'chat': return <SkydChat />
      case 'monitor': return <SysMonitor stats={stats} />
      case 'journal': return <Journal />
      case 'files': return <Files />
    }
  }

  return (
    <div className="desktop">
      <div className="wallpaper-grid" />

      <div className="desktop-icons">
        {APPS.map(app => (
          <div key={app.id} className="desktop-icon" onDoubleClick={()=>openApp(app.id)}>
            <span className="icon-img">{app.icon}</span>
            <span className="icon-label">{app.title}</span>
          </div>
        ))}
      </div>

      {openWindows.map(app => {
        const zi = 100 + focusStack.indexOf(app.id)
        return (
          <Window key={app.id} {...app} zIndex={zi}
            focused={focusStack[focusStack.length-1]===app.id}
            onClose={closeWindow} onFocus={focusWindow}>
            {renderContent(app)}
          </Window>
        )
      })}

      <div className="taskbar">
        <div className="taskbar-dot" />
        <span style={{fontSize:13,fontWeight:600,color:'var(--accent)',marginRight:8}}>OSONE</span>
        {APPS.map(app => (
          <button key={app.id} className={`taskbar-btn ${openWindows.find(w=>w.id===app.id)?'active':''}`}
            onClick={()=>openApp(app.id)}>
            {app.icon} {app.title}
          </button>
        ))}
        {stats && <span style={{fontSize:12,color:'var(--muted)',marginLeft:8}}>Gen {stats.gen} · {stats.rules} rules</span>}
        <Clock />
      </div>
    </div>
  )
}

