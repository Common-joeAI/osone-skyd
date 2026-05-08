import { useState, useEffect, useRef } from 'react'
import './index.css'
import HivePanel from './HivePanel.jsx'

// Auto-detect: if accessed via Cloudflare (no explicit port), use same origin
const _isLocal = window.location.port !== ''
const API = _isLocal
  ? `http://${window.location.hostname}:8000`
  : `${window.location.protocol}//${window.location.host}`
const WS_BASE = _isLocal
  ? `ws://${window.location.hostname}:8000`
  : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`

// ── Auth store ────────────────────────────────────────────────────────────────
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
    /Android|iPhone|iPad|iPod|Mobile|OSONE-Android/i.test(navigator.userAgent) || window.innerWidth <= 768
  )
  useEffect(() => {
    const check = () => setMobile(/Android|iPhone|iPad|iPod|Mobile|OSONE-Android/i.test(navigator.userAgent) || window.innerWidth <= 768)
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])
  return mobile
}

function useStats(token) {
  const [stats, setStats] = useState(null)
  useEffect(() => {
    if (!token) return
    const fetch_ = () => authFetch(`${API}/api/stats`, {}, token).then(r=>r.json()).then(setStats).catch(()=>{})
    fetch_()
    const t = setInterval(fetch_, 3000)
    return () => clearInterval(t)
  }, [token])
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

// ── Login Screen ──────────────────────────────────────────────────────────────
function LoginScreen({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      const r = await fetch(`${API}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password })
      })
      const d = await r.json()
      if (!r.ok) { setError(d.detail || 'Login failed'); setLoading(false); return }
      onLogin(d)
    } catch { setError('Cannot reach OSONE server'); setLoading(false) }
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <div className="login-logo">
          <div className="taskbar-dot" style={{width:12,height:12}} />
          <span className="login-title">OSONE</span>
        </div>
        <p className="login-sub">Authenticate to access the system</p>
        <form onSubmit={submit} className="login-form">
          <input className="login-input" placeholder="Username" value={username}
            onChange={e=>setUsername(e.target.value)} autoComplete="username" autoFocus />
          <input className="login-input" type="password" placeholder="Password" value={password}
            onChange={e=>setPassword(e.target.value)} autoComplete="current-password" />
          {error && <div className="login-error">{error}</div>}
          <button className="login-btn" type="submit" disabled={loading}>
            {loading ? 'Connecting...' : 'Connect'}
          </button>
        </form>
      </div>
    </div>
  )
}

// ── Desktop Window ────────────────────────────────────────────────────────────
function Window({ id, title, icon, children, initialPos, initialSize, onClose, onFocus, focused, zIndex }) {
  const [pos, setPos] = useState(initialPos || { x: 100, y: 60 })
  const [size] = useState(initialSize || { w: 700, h: 500 })
  const [maximized, setMaximized] = useState(false)
  const dragging = useRef(false), dragOffset = useRef(null)
  const onMouseDown = e => { onFocus(id); dragging.current = true; dragOffset.current = { x: e.clientX - pos.x, y: e.clientY - pos.y } }
  useEffect(() => {
    const move = e => { if (dragging.current && !maximized) setPos({ x: e.clientX - dragOffset.current.x, y: e.clientY - dragOffset.current.y }) }
    const up = () => { dragging.current = false }
    window.addEventListener('mousemove', move); window.addEventListener('mouseup', up)
    return () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }
  }, [maximized])
  const style = maximized ? { left:0, top:0, width:'100vw', height:'calc(100vh - 52px)', borderRadius:0, zIndex } : { left: pos.x, top: pos.y, width: size.w, height: size.h, zIndex }
  return (
    <div className={`window ${focused?'focused':''}`} style={style} onMouseDown={() => onFocus(id)}>
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

// ── Terminal (admin only) ─────────────────────────────────────────────────────
function Terminal({ mobile, token }) {
  const [lines, setLines] = useState([
    { type: 'sys', text: '  ▓ OSONE Terminal' },
    { type: 'skyd', text: 'Type commands or ask skyd anything' },
    { type: 'muted', text: 'Prefix with "skyd:" for AI queries' },
    { type: 'muted', text: '────────────────────────────────' },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [lines])
  const addLine = (type, text) => setLines(l => [...l, { type, text }])
  const runCommand = async (cmd) => {
    if (!cmd.trim()) return
    addLine('cmd', `# ${cmd}`)
    if (cmd.trim().toLowerCase().startsWith('skyd:') || cmd.trim().toLowerCase().startsWith('ask ')) {
      const q = cmd.replace(/^skyd:/i,'').replace(/^ask /i,'').trim()
      setLoading(true); addLine('skyd', 'skyd thinking...')
      try {
        const r = await authFetch(`${API}/api/chat`, { method:'POST', body:JSON.stringify({message:q}) }, token)
        const d = await r.json()
        setLines(l => [...l.slice(0,-1)]); addLine('skyd', `skyd: ${d.response}`)
      } catch { addLine('err', 'skyd: connection error') }
      setLoading(false); return
    }
    setLoading(true)
    try {
      const r = await authFetch(`${API}/api/exec`, { method:'POST', body:JSON.stringify({cmd}) }, token)
      const d = await r.json()
      if (d.stdout) d.stdout.split('\n').forEach(l => l && addLine('out', l))
      if (d.stderr) d.stderr.split('\n').forEach(l => l && addLine('err', l))
      if (d.error) addLine('err', d.error)
    } catch { addLine('err', 'execution error') }
    setLoading(false)
  }
  const onKey = e => { if (e.key === 'Enter') { runCommand(input); setInput('') } }
  return (
    <>
      <div className="terminal-wrap" onClick={() => inputRef.current?.focus()}>
        {lines.map((l,i) => <div key={i} className={`terminal-line ${l.type}`}>{l.text}</div>)}
        <div ref={bottomRef} />
      </div>
      <div className="terminal-input-row">
        <span className="terminal-prompt">#</span>
        <input ref={inputRef} autoFocus className="terminal-input" value={input}
          onChange={e=>setInput(e.target.value)} onKeyDown={onKey}
          placeholder={loading?'processing...':'command or skyd: question'} disabled={loading}
          style={mobile?{fontSize:16}:{}} />
      </div>
    </>
  )
}

// ── skyd Chat (users just type naturally) ─────────────────────────────────────
function SkydChat({ mobile, token }) {
  const [messages, setMessages] = useState([{ role: 'skyd', text: "Hey — I'm skyd. Ask me anything." }])
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
      // Send token first
      ws.onopen = () => {
        ws.send(JSON.stringify({ token }))
        setTimeout(() => ws.send(JSON.stringify({ message: msg })), 50)
      }
      ws.onmessage = e => {
        const d = JSON.parse(e.data)
        if (d.error) { setMessages(m => { const a=[...m]; a[a.length-1]={role:'skyd',text:'Auth error.'}; return a }); setLoading(false); return }
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
            <span className="chat-label">{m.role==='skyd'?'🤖 skyd':'👤 you'}</span>
            <div className="chat-bubble">
              {m.text || (m.streaming?<div className="typing"><span/><span/><span/></div>:'')}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="chat-input-row">
        <input className="chat-input" value={input} onChange={e=>setInput(e.target.value)}
          onKeyDown={e=>e.key==='Enter'&&send()} placeholder="Ask skyd anything..."
          style={mobile?{fontSize:16}:{}} />
        <button className="chat-send" onClick={send} disabled={loading}>{mobile?'↑':'Send'}</button>
      </div>
    </>
  )
}

// ── System Monitor ────────────────────────────────────────────────────────────
function SysMonitor({ stats, mobile }) {
  if (!stats) return <div style={{padding:16,color:'var(--muted)'}}>Loading...</div>
  const svcs = Object.entries(stats.services||{})
  return (
    <div className={`stats-grid ${mobile?'stats-grid-mobile':''}`}>
      <div className="stat-card"><div className="stat-label">skyd Generation</div><div className="stat-value">Gen {stats.gen}</div><div className="stat-sub">{stats.rules} SkyLang rules</div></div>
      <div className="stat-card"><div className="stat-label">Uptime</div><div className="stat-value">{fmtUptime(stats.uptime)}</div><div className="stat-sub">{stats.hostname}</div></div>
      <div className="stat-card"><div className="stat-label">CPU</div><div className="stat-value">{stats.cpu?.toFixed(1)}%</div><div className="progress-bar"><div className={`progress-fill ${stats.cpu>80?'danger':stats.cpu>60?'warn':''}`} style={{width:`${stats.cpu}%`}} /></div></div>
      <div className="stat-card"><div className="stat-label">Memory</div><div className="stat-value">{stats.mem_pct?.toFixed(1)}%</div><div className="stat-sub">{fmt(stats.mem_used)} / {fmt(stats.mem_total)}</div><div className="progress-bar"><div className={`progress-fill ${stats.mem_pct>85?'danger':stats.mem_pct>65?'warn':''}`} style={{width:`${stats.mem_pct}%`}} /></div></div>
      {svcs.length > 0 && <div className="stat-card" style={{gridColumn:'1/-1'}}>
        <div className="stat-label" style={{marginBottom:10}}>Services</div>
        <div className="services-list">
          {svcs.map(([name,status]) => (<div key={name} className="svc-row"><span className={`svc-dot ${status==='active'?'green':status==='inactive'?'red':'yellow'}`} /><span className="svc-name">{name}</span><span className={`svc-status ${status}`}>{status}</span></div>))}
        </div>
      </div>}
    </div>
  )
}

// ── Journal ───────────────────────────────────────────────────────────────────
function Journal({ token }) {
  const [content, setContent] = useState('')
  useEffect(() => {
    authFetch(`${API}/api/journal`, {}, token).then(r=>r.json()).then(d=>setContent(d.content||'No journal yet')).catch(()=>setContent('Access denied'))
  }, [token])
  return <div style={{padding:16,overflow:'auto',flex:1,fontFamily:'monospace',fontSize:13,lineHeight:1.7,color:'var(--text)',whiteSpace:'pre-wrap'}}>{content}</div>
}

// ── Files ─────────────────────────────────────────────────────────────────────
function Files({ token }) {
  const [path, setPath] = useState('/')
  const [entries, setEntries] = useState([])
  useEffect(() => {
    authFetch(`${API}/api/files?path=${encodeURIComponent(path)}`, {}, token).then(r=>r.json()).then(d=>setEntries(d.entries||[])).catch(()=>{})
  }, [path, token])
  const nav = (entry) => { if (entry.is_dir) setPath(path.replace(/\/$/,'')+'/'+entry.name) }
  const up = () => { const p=path.split('/').filter(Boolean); p.pop(); setPath('/'+p.join('/')) }
  return (
    <>
      <div className="files-path">{path!=='/'&&<span style={{cursor:'pointer',marginRight:8,color:'var(--accent)'}} onClick={up}>↑ ..</span>}{path}</div>
      <div className="files-list">{entries.map((e,i)=>(<div key={i} className="file-row" onClick={()=>nav(e)}><span className="file-icon">{e.is_dir?'📁':'📄'}</span><span className="file-name">{e.name}</span>{!e.is_dir&&<span className="file-size">{fmt(e.size)}</span>}</div>))}</div>
    </>
  )
}

// ── Admin: User Manager ───────────────────────────────────────────────────────
function UserManager({ token }) {
  const [users, setUsers] = useState([])
  const [newUser, setNewUser] = useState({ username:'', password:'', role:'user' })
  const [msg, setMsg] = useState('')

  const load = () => authFetch(`${API}/api/auth/users`, {}, token).then(r=>r.json()).then(setUsers).catch(()=>{})
  useEffect(() => { load() }, [token])

  const create = async () => {
    const r = await authFetch(`${API}/api/auth/register`, { method:'POST', body:JSON.stringify(newUser) }, token)
    const d = await r.json()
    setMsg(r.ok ? `✅ Created ${d.username}` : `❌ ${d.detail}`)
    if (r.ok) { setNewUser({username:'',password:'',role:'user'}); load() }
  }

  const del = async (username) => {
    if (!confirm(`Delete ${username}?`)) return
    await authFetch(`${API}/api/auth/users/${username}`, { method:'DELETE' }, token)
    load()
  }

  return (
    <div style={{padding:16,overflow:'auto',flex:1}}>
      <div className="stat-label" style={{marginBottom:12}}>Registered Users</div>
      <div className="services-list" style={{marginBottom:20}}>
        {users.map(u => (
          <div key={u.username} className="svc-row">
            <span className={`svc-dot ${u.role==='admin'?'yellow':'green'}`} />
            <span className="svc-name">{u.username}</span>
            <span className={`svc-status ${u.role}`} style={{marginLeft:'auto'}}>{u.role}</span>
            <button onClick={()=>del(u.username)} style={{marginLeft:12,background:'var(--red)',border:'none',borderRadius:6,color:'#fff',padding:'2px 8px',cursor:'pointer',fontSize:11}}>remove</button>
          </div>
        ))}
      </div>
      <div className="stat-label" style={{marginBottom:8}}>Add User</div>
      <div style={{display:'flex',flexDirection:'column',gap:8,maxWidth:320}}>
        <input className="chat-input" placeholder="Username" value={newUser.username} onChange={e=>setNewUser(u=>({...u,username:e.target.value}))} />
        <input className="chat-input" type="password" placeholder="Password" value={newUser.password} onChange={e=>setNewUser(u=>({...u,password:e.target.value}))} />
        <select className="chat-input" value={newUser.role} onChange={e=>setNewUser(u=>({...u,role:e.target.value}))}>
          <option value="user">User (chat only)</option>
          <option value="admin">Admin (full access)</option>
        </select>
        <button className="chat-send" style={{alignSelf:'flex-start',padding:'8px 20px'}} onClick={create}>Create User</button>
        {msg && <span style={{fontSize:12,color:'var(--green)'}}>{msg}</span>}
      </div>
    </div>
  )
}

// ── Clock ─────────────────────────────────────────────────────────────────────
function Clock() {
  const [t, setT] = useState(new Date())
  useEffect(() => { const i = setInterval(()=>setT(new Date()),1000); return ()=>clearInterval(i) }, [])
  return <span className="taskbar-clock">{t.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</span>
}

// ── App registry ──────────────────────────────────────────────────────────────
const ADMIN_APPS = [
  { id:'chat',    title:'skyd AI',  icon:'🤖', initialPos:{x:80,y:40},  initialSize:{w:520,h:560} },
  { id:'terminal',title:'Terminal', icon:'⌨️', initialPos:{x:200,y:80}, initialSize:{w:750,h:520} },
  { id:'monitor', title:'Monitor',  icon:'📊', initialPos:{x:300,y:60}, initialSize:{w:520,h:500} },
  { id:'hive',    title:'Hive',     icon:'🕷️', initialPos:{x:180,y:60}, initialSize:{w:680,h:580} },
  { id:'journal', title:'Journal',  icon:'📓', initialPos:{x:150,y:100},initialSize:{w:600,h:500} },
  { id:'files',   title:'Files',    icon:'📁', initialPos:{x:250,y:80}, initialSize:{w:480,h:500} },
  { id:'users',   title:'Users',    icon:'👥', initialPos:{x:160,y:70}, initialSize:{w:480,h:500} },
]
const USER_APPS = [
  { id:'chat',    title:'skyd AI',  icon:'🤖', initialPos:{x:80,y:40},  initialSize:{w:520,h:560} },
  { id:'monitor', title:'Monitor',  icon:'📊', initialPos:{x:300,y:60}, initialSize:{w:520,h:500} },
]

// ── Mobile Layout ─────────────────────────────────────────────────────────────
function MobileApp({ stats, auth, logout, token }) {
  const isAdmin = auth.role === 'admin'
  const [activeTab, setActiveTab] = useState('chat')
  const tabs = isAdmin
    ? [{id:'chat',icon:'🤖',label:'skyd'},{id:'terminal',icon:'⌨️',label:'Term'},{id:'monitor',icon:'📊',label:'Stats'},{id:'hive',icon:'🕷️',label:'Hive'},{id:'files',icon:'📁',label:'Files'}]
    : [{id:'chat',icon:'🤖',label:'skyd'},{id:'monitor',icon:'📊',label:'Stats'}]

  const renderContent = () => {
    switch(activeTab) {
      case 'chat':     return <SkydChat mobile token={token} />
      case 'terminal': return <Terminal mobile token={token} />
      case 'monitor':  return <SysMonitor stats={stats} mobile />
      case 'hive':     return <HivePanel />
      case 'files':    return <Files token={token} />
    }
  }

  const active = [...ADMIN_APPS].find(a=>a.id===activeTab)
  return (
    <div className="mobile-shell">
      <div className="mobile-header">
        <div className="mobile-header-left">
          <div className="taskbar-dot" />
          <span className="mobile-title">OSONE</span>
          <span style={{fontSize:10,color:'var(--muted)',marginLeft:4}}>{isAdmin?'admin':'user'}</span>
        </div>
        <div className="mobile-header-right">
          {stats && <span className="mobile-gen">Gen {stats.gen}</span>}
          <Clock />
          <button onClick={logout} style={{background:'none',border:'1px solid var(--border)',borderRadius:6,color:'var(--muted)',padding:'3px 8px',fontSize:10,cursor:'pointer'}}>out</button>
        </div>
      </div>
      <div className="mobile-page-title"><span>{active?.icon}</span><span>{active?.title}</span></div>
      <div className="mobile-content">{renderContent()}</div>
      <div className="mobile-nav">
        {tabs.map(t => (
          <button key={t.id} className={`mobile-nav-btn ${activeTab===t.id?'active':''}`} onClick={()=>setActiveTab(t.id)}>
            <span className="mobile-nav-icon">{t.icon}</span>
            <span className="mobile-nav-label">{t.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Desktop Layout ────────────────────────────────────────────────────────────
function DesktopApp({ stats, auth, logout, token }) {
  const isAdmin = auth.role === 'admin'
  const APPS = isAdmin ? ADMIN_APPS : USER_APPS
  const [openWindows, setOpenWindows] = useState([])
  const [focusStack, setFocusStack] = useState([])
  const openApp = (appId) => { if (!openWindows.find(w=>w.id===appId)) setOpenWindows(w=>[...w,APPS.find(a=>a.id===appId)]); setFocusStack(s=>[...s.filter(x=>x!==appId),appId]) }
  const closeWindow = (id) => { setOpenWindows(w=>w.filter(x=>x.id!==id)); setFocusStack(s=>s.filter(x=>x!==id)) }
  const focusWindow = (id) => setFocusStack(s=>[...s.filter(x=>x!==id),id])
  const renderContent = (app) => {
    switch(app.id) {
      case 'terminal': return <Terminal token={token} />
      case 'chat':     return <SkydChat token={token} />
      case 'monitor':  return <SysMonitor stats={stats} />
      case 'journal':  return <Journal token={token} />
      case 'files':    return <Files token={token} />
      case 'hive':     return <HivePanel />
      case 'users':    return <UserManager token={token} />
    }
  }
  return (
    <div className="desktop">
      <div className="wallpaper-grid" />
      <div className="desktop-icons">
        {APPS.map(app=>(<div key={app.id} className="desktop-icon" onDoubleClick={()=>openApp(app.id)}><span className="icon-img">{app.icon}</span><span className="icon-label">{app.title}</span></div>))}
      </div>
      {openWindows.map(app => {
        const zi = 100 + focusStack.indexOf(app.id)
        return (<Window key={app.id} {...app} zIndex={zi} focused={focusStack[focusStack.length-1]===app.id} onClose={closeWindow} onFocus={focusWindow}>{renderContent(app)}</Window>)
      })}
      <div className="taskbar">
        <div className="taskbar-dot" />
        <span style={{fontSize:13,fontWeight:600,color:'var(--accent)',marginRight:4}}>OSONE</span>
        <span style={{fontSize:10,color:'var(--muted)',marginRight:8,border:'1px solid var(--border)',borderRadius:4,padding:'1px 5px'}}>{auth.role}</span>
        {APPS.map(app=>(<button key={app.id} className={`taskbar-btn ${openWindows.find(w=>w.id===app.id)?'active':''}`} onClick={()=>openApp(app.id)}>{app.icon} {app.title}</button>))}
        {stats && <span style={{fontSize:12,color:'var(--muted)',marginLeft:8}}>Gen {stats.gen} · {stats.rules} rules</span>}
        <Clock />
        <button onClick={logout} style={{marginLeft:8,background:'none',border:'1px solid var(--border)',borderRadius:6,color:'var(--muted)',padding:'4px 10px',fontSize:11,cursor:'pointer'}}>logout</button>
      </div>
    </div>
  )
}

// ── Admin Login Modal ────────────────────────────────────────────────────────
function AdminLoginModal({ onLogin, onClose }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      const r = await fetch(`${API}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password })
      })
      if (!r.ok) { setError('Invalid credentials'); setLoading(false); return }
      const data = await r.json()
      if (data.role !== 'admin') { setError('Admin access only'); setLoading(false); return }
      onLogin(data)
    } catch { setError('Connection error'); setLoading(false) }
  }

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.8)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:9999}} onClick={onClose}>
      <div style={{background:'var(--surface)',border:'1px solid var(--border)',borderRadius:12,padding:32,width:320}} onClick={e=>e.stopPropagation()}>
        <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:24}}>
          <span style={{fontSize:22}}>🔐</span>
          <span style={{fontWeight:700,fontSize:18,color:'var(--accent)'}}>Admin Access</span>
        </div>
        <form onSubmit={submit} style={{display:'flex',flexDirection:'column',gap:12}}>
          <input autoFocus value={username} onChange={e=>setUsername(e.target.value)}
            placeholder="Username" style={{background:'var(--surface2)',border:'1px solid var(--border)',borderRadius:8,padding:'10px 14px',color:'var(--text)',fontSize:14}} />
          <input type="password" value={password} onChange={e=>setPassword(e.target.value)}
            placeholder="Password" style={{background:'var(--surface2)',border:'1px solid var(--border)',borderRadius:8,padding:'10px 14px',color:'var(--text)',fontSize:14}} />
          {error && <div style={{color:'#ff6b6b',fontSize:13}}>{error}</div>}
          <div style={{display:'flex',gap:8,marginTop:4}}>
            <button type="button" onClick={onClose} style={{flex:1,padding:'10px',background:'none',border:'1px solid var(--border)',borderRadius:8,color:'var(--muted)',cursor:'pointer',fontSize:14}}>Cancel</button>
            <button type="submit" disabled={loading} style={{flex:1,padding:'10px',background:'var(--accent)',border:'none',borderRadius:8,color:'#fff',cursor:'pointer',fontSize:14,fontWeight:600}}>
              {loading ? '...' : 'Login'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Public Chat (no auth needed) ──────────────────────────────────────────────
function PublicChat({ mobile, onAdminLogin }) {
  const [msgs, setMsgs] = useState([{ role: 'assistant', content: "Hey. I'm skyd — the AI core of OSONE. What do you want to know?" }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [showAdminModal, setShowAdminModal] = useState(false)
  const [adminClickCount, setAdminClickCount] = useState(0)
  const bottomRef = useRef(null)
  const wsRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs])

  // Secret admin trigger: click OSONE title 5 times
  const handleTitleClick = () => {
    const next = adminClickCount + 1
    setAdminClickCount(next)
    if (next >= 5) { setShowAdminModal(true); setAdminClickCount(0) }
  }

  const send = async () => {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setMsgs(m => [...m, { role: 'user', content: userMsg }])
    setLoading(true)

    // Use WebSocket for streaming
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.port ? `${window.location.hostname}:8000` : window.location.host
    const ws = new WebSocket(`${proto}://${host}/ws/chat`)
    wsRef.current = ws

    let reply = ''
    setMsgs(m => [...m, { role: 'assistant', content: '' }])

    ws.onopen = () => ws.send(JSON.stringify({ message: userMsg }))
    ws.onmessage = (e) => {
      const d = JSON.parse(e.data)
      if (d.token) {
        reply += d.token
        setMsgs(m => { const a = [...m]; a[a.length-1] = { role:'assistant', content: reply }; return a })
      }
      if (d.done) { ws.close(); setLoading(false) }
      if (d.error) { ws.close(); setLoading(false) }
    }
    ws.onerror = () => { setLoading(false) }
    ws.onclose = () => { if (!reply) setLoading(false) }
  }

  const containerStyle = mobile ? {
    display:'flex', flexDirection:'column', height:'100vh',
    background:'var(--bg)', fontFamily:'inherit'
  } : {
    display:'flex', flexDirection:'column', height:'100vh',
    background:'var(--bg)', maxWidth:800, margin:'0 auto', padding:'0 16px'
  }

  return (
    <div style={containerStyle}>
      {showAdminModal && <AdminLoginModal onLogin={onAdminLogin} onClose={()=>setShowAdminModal(false)} />}

      {/* Header */}
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'16px 0',borderBottom:'1px solid var(--border)',flexShrink:0}}>
        <div style={{display:'flex',alignItems:'center',gap:10,cursor:'default'}} onClick={handleTitleClick}>
          <div style={{width:10,height:10,borderRadius:'50%',background:'var(--accent)',boxShadow:'0 0 8px var(--accent)'}} />
          <span style={{fontWeight:700,fontSize:18,color:'var(--accent)'}}>OSONE</span>
          <span style={{fontSize:11,color:'var(--muted)',border:'1px solid var(--border)',borderRadius:4,padding:'1px 6px'}}>skyd</span>
        </div>
        <div style={{fontSize:12,color:'var(--muted)'}}>AI Core · Public</div>
      </div>

      {/* Messages */}
      <div style={{flex:1,overflowY:'auto',padding:'16px 0',display:'flex',flexDirection:'column',gap:12}}>
        {msgs.map((m,i) => (
          <div key={i} style={{display:'flex',justifyContent:m.role==='user'?'flex-end':'flex-start'}}>
            <div style={{
              maxWidth:'80%', padding:'10px 14px', borderRadius:12,
              background: m.role==='user' ? 'var(--accent)' : 'var(--surface)',
              color: m.role==='user' ? '#fff' : 'var(--text)',
              fontSize:14, lineHeight:1.5,
              borderBottomRightRadius: m.role==='user' ? 4 : 12,
              borderBottomLeftRadius: m.role==='assistant' ? 4 : 12,
            }}>
              {m.content || (loading && i===msgs.length-1 ? <span style={{color:'var(--muted)'}}>▋</span> : '')}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{padding:'12px 0 20px',borderTop:'1px solid var(--border)',flexShrink:0}}>
        <div style={{display:'flex',gap:8,alignItems:'flex-end'}}>
          <textarea
            value={input} onChange={e=>setInput(e.target.value)}
            onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}}
            placeholder="Ask skyd anything..."
            rows={1}
            style={{
              flex:1, background:'var(--surface)', border:'1px solid var(--border)',
              borderRadius:10, padding:'10px 14px', color:'var(--text)',
              fontSize:14, resize:'none', fontFamily:'inherit', outline:'none',
              lineHeight:1.5
            }}
          />
          <button onClick={send} disabled={loading || !input.trim()} style={{
            background:'var(--accent)', border:'none', borderRadius:10,
            color:'#fff', padding:'10px 18px', cursor:'pointer', fontSize:14,
            fontWeight:600, flexShrink:0, opacity: (loading||!input.trim()) ? 0.5 : 1
          }}>
            {loading ? '...' : '↑'}
          </button>
        </div>
        <div style={{fontSize:11,color:'var(--muted)',marginTop:6,textAlign:'center'}}>
          OSONE · Decentralized AI · osone.org
        </div>
      </div>
    </div>
  )
}

// ── Root ──────────────────────────────────────────────────────────────────────
export default function App() {
  const { auth, login, logout } = useAuth()
  const mobile = useIsMobile()
  const stats = useStats(auth?.token)

  // If admin is logged in, show full OS shell
  if (auth && auth.role === 'admin') {
    return mobile
      ? <MobileApp stats={stats} auth={auth} logout={logout} token={auth.token} />
      : <DesktopApp stats={stats} auth={auth} logout={logout} token={auth.token} />
  }

  // Everyone else: public chat, with hidden admin login trigger
  return <PublicChat mobile={mobile} onAdminLogin={login} />
}
