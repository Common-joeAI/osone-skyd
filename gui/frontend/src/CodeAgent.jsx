import { useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { EditorView, keymap, lineNumbers, highlightActiveLine } from '@codemirror/view'
import { EditorState } from '@codemirror/state'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { javascript } from '@codemirror/lang-javascript'
import { python } from '@codemirror/lang-python'
import { html } from '@codemirror/lang-html'
import { css } from '@codemirror/lang-css'
import { json } from '@codemirror/lang-json'
import { markdown } from '@codemirror/lang-markdown'
import { oneDark as cmOneDark } from '@codemirror/theme-one-dark'
import { autocompletion, closeBrackets } from '@codemirror/autocomplete'
import { bracketMatching, indentOnInput, syntaxHighlighting, defaultHighlightStyle } from '@codemirror/language'

const _isLocal = window.location.port !== ''
const API = _isLocal
  ? `http://${window.location.hostname}:8000`
  : `${window.location.protocol}//${window.location.host}`
const WS_BASE = _isLocal
  ? `ws://${window.location.hostname}:8000`
  : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`

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

// ── Language helpers ──────────────────────────────────────────────────────────
function detectLang(filename) {
  const ext = filename?.split('.').pop()?.toLowerCase() || ''
  const map = { js:'javascript', jsx:'javascript', ts:'javascript', tsx:'javascript',
                py:'python', html:'html', htm:'html', css:'css',
                json:'json', md:'markdown', sh:'shell', bash:'shell' }
  return map[ext] || 'javascript'
}
function getLangExtension(lang) {
  switch (lang) {
    case 'python':   return python()
    case 'html':     return html()
    case 'css':      return css()
    case 'json':     return json()
    case 'markdown': return markdown()
    default:         return javascript({ jsx: true, typescript: true })
  }
}

// ── CodeMirror editor ─────────────────────────────────────────────────────────
function CodeEditor({ value, onChange, lang = 'javascript' }) {
  const editorRef = useRef(null)
  const viewRef   = useRef(null)

  useEffect(() => {
    if (!editorRef.current) return
    const updateListener = EditorView.updateListener.of(update => {
      if (update.docChanged && onChange) onChange(update.state.doc.toString())
    })
    const state = EditorState.create({
      doc: value || '',
      extensions: [
        lineNumbers(), history(), highlightActiveLine(),
        bracketMatching(), closeBrackets(), indentOnInput(),
        autocompletion(), syntaxHighlighting(defaultHighlightStyle),
        getLangExtension(lang), cmOneDark,
        keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
        updateListener,
        EditorView.theme({
          '&': { height:'100%', fontSize:'13px', fontFamily:"'JetBrains Mono','Fira Code',monospace" },
          '.cm-scroller': { overflow:'auto', height:'100%' },
          '.cm-content': { minHeight:'100%' },
          '&.cm-focused': { outline:'none' },
        }),
      ]
    })
    const view = new EditorView({ state, parent: editorRef.current })
    viewRef.current = view
    return () => view.destroy()
  }, [lang])

  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    const current = view.state.doc.toString()
    if (current !== value) {
      view.dispatch({ changes: { from:0, to:current.length, insert: value||'' } })
    }
  }, [value])

  return <div ref={editorRef} style={{ height:'100%', width:'100%', overflow:'hidden' }} />
}

// ── Markdown renderer ─────────────────────────────────────────────────────────
function MsgMarkdown({ content }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
      code({ inline, className, children, ...props }) {
        const match = /language-(\w+)/.exec(className || '')
        const codeStr = String(children).replace(/\n$/, '')
        if (!inline && match) {
          return (
            <div style={{ position:'relative', margin:'8px 0', borderRadius:8, overflow:'hidden' }}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
                background:'#1a1a2e', padding:'3px 10px', fontSize:11, color:'#7c6fff',
                borderBottom:'1px solid rgba(255,255,255,0.08)' }}>
                <span>{match[1]}</span>
                <button onClick={() => navigator.clipboard?.writeText(codeStr)}
                  style={{ background:'none', border:'1px solid rgba(124,111,255,0.3)', color:'#7c6fff',
                    borderRadius:4, padding:'1px 7px', cursor:'pointer', fontSize:10 }}>copy</button>
              </div>
              <SyntaxHighlighter style={oneDark} language={match[1]} PreTag="div"
                customStyle={{ margin:0, borderRadius:0, fontSize:12, padding:'12px' }}>{codeStr}</SyntaxHighlighter>
            </div>
          )
        }
        return <code style={{ background:'rgba(124,111,255,0.15)', color:'#c4b5fd',
          borderRadius:4, padding:'1px 5px', fontSize:'0.88em', fontFamily:'monospace' }} {...props}>{children}</code>
      },
      p({ children })      { return <p style={{ margin:'3px 0 7px', lineHeight:1.6 }}>{children}</p> },
      strong({ children }) { return <strong style={{ color:'#c4b5fd', fontWeight:700 }}>{children}</strong> },
      ul({ children })     { return <ul style={{ margin:'4px 0 8px', paddingLeft:18, lineHeight:1.7 }}>{children}</ul> },
      ol({ children })     { return <ol style={{ margin:'4px 0 8px', paddingLeft:18, lineHeight:1.7 }}>{children}</ol> },
      li({ children })     { return <li style={{ marginBottom:2 }}>{children}</li> },
      h1({ children })     { return <h1 style={{ color:'#7c6fff', fontSize:17, margin:'8px 0 5px', fontWeight:700 }}>{children}</h1> },
      h2({ children })     { return <h2 style={{ color:'#7c6fff', fontSize:15, margin:'7px 0 4px', fontWeight:700 }}>{children}</h2> },
      h3({ children })     { return <h3 style={{ color:'#a78bfa', fontSize:13, margin:'5px 0 3px', fontWeight:600 }}>{children}</h3> },
      a({ href, children }){ return <a href={href} target="_blank" rel="noopener noreferrer"
        style={{ color:'#7c6fff', textDecoration:'underline' }}>{children}</a> },
    }}>{content}</ReactMarkdown>
  )
}

// ── File tabs ─────────────────────────────────────────────────────────────────
function FileTabs({ files, activeFile, onSelect, onAdd, onClose, compact }) {
  return (
    <div style={{ display:'flex', alignItems:'center', background:'#0d0d1a',
      borderBottom:'1px solid rgba(255,255,255,0.07)', overflowX:'auto', flexShrink:0 }}>
      {files.map(f => (
        <div key={f.name} onClick={() => onSelect(f.name)}
          style={{ display:'flex', alignItems:'center', gap:4, padding: compact ? '5px 10px' : '6px 14px',
            borderRight:'1px solid rgba(255,255,255,0.06)', cursor:'pointer', flexShrink:0,
            background: f.name===activeFile ? 'rgba(124,111,255,0.12)' : 'transparent',
            borderBottom: f.name===activeFile ? '2px solid #7c6fff' : '2px solid transparent',
            color: f.name===activeFile ? '#fff' : 'rgba(255,255,255,0.45)',
            fontSize: compact ? 11 : 12 }}>
          <span style={{ maxWidth: compact ? 70 : 120, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{f.name}</span>
          <span onClick={e => { e.stopPropagation(); onClose(f.name) }}
            style={{ opacity:0.4, fontSize:9, lineHeight:1, padding:'0 2px', borderRadius:3, cursor:'pointer' }}>✕</span>
        </div>
      ))}
      <button onClick={onAdd}
        style={{ background:'none', border:'none', color:'rgba(255,255,255,0.3)',
          fontSize:16, padding:'0 12px', cursor:'pointer', flexShrink:0 }}>+</button>
    </div>
  )
}

// ── Live preview ──────────────────────────────────────────────────────────────
function LivePreview({ files, activeFile }) {
  const active = files.find(f => f.name === activeFile)
  const lang   = active ? detectLang(active.name) : 'javascript'

  if (lang === 'html') {
    const blob = new Blob([active?.content||''], { type:'text/html' })
    return <iframe src={URL.createObjectURL(blob)} sandbox="allow-scripts"
      style={{ width:'100%', height:'100%', border:'none', background:'#fff' }} title="preview" />
  }
  if (lang === 'javascript') {
    const runCode = `<!DOCTYPE html><html><head><style>body{background:#0d0d1a;color:#e2e8f0;font-family:monospace;padding:16px}pre{margin:0;white-space:pre-wrap}.err{color:#f87171}.ok{color:#4ade80}</style></head><body><pre id="out"></pre><script>
const out=document.getElementById('out');
console.log=(...a)=>{out.innerHTML+='<span class=ok>'+a.map(x=>typeof x==='object'?JSON.stringify(x,null,2):String(x)).join(' ')+'</span>\\n'};
console.error=(...a)=>{out.innerHTML+='<span class=err>'+a.join(' ')+'</span>\\n'};
window.onerror=(m,_,l)=>{out.innerHTML+='<span class=err>Error: '+m+' (line '+l+')</span>\\n';return true};
try{${active?.content||''}}catch(e){console.error(e.message)}<\/script></body></html>`
    const blob = new Blob([runCode], { type:'text/html' })
    return <iframe src={URL.createObjectURL(blob)} sandbox="allow-scripts"
      style={{ width:'100%', height:'100%', border:'none' }} title="js-run" />
  }
  return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center',
      height:'100%', color:'rgba(255,255,255,0.3)', gap:8, fontSize:13 }}>
      <span style={{ fontSize:32 }}>🐍</span>
      <span>No live preview for {lang}</span>
      <span style={{ fontSize:11 }}>Ask skyd to run it</span>
    </div>
  )
}

// ── Chat panel (shared between mobile+desktop) ────────────────────────────────
function ChatPanel({ msgs, input, setInput, send, loading, bottomRef, onSwitchToEditor, isMobile }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', minHeight:0 }}>
      {/* Header */}
      <div style={{ padding:'8px 14px', borderBottom:'1px solid rgba(255,255,255,0.07)',
        display:'flex', alignItems:'center', gap:8, background:'#0d0d1a', flexShrink:0 }}>
        <div style={{ width:7, height:7, borderRadius:'50%', background:'#7c6fff', boxShadow:'0 0 6px #7c6fff' }} />
        <span style={{ fontWeight:700, fontSize:13, color:'#7c6fff', letterSpacing:1 }}>skyd</span>
        <span style={{ fontSize:11, color:'rgba(255,255,255,0.3)' }}>coding agent</span>
        {isMobile && (
          <button onClick={onSwitchToEditor}
            style={{ marginLeft:'auto', background:'rgba(124,111,255,0.15)', border:'1px solid rgba(124,111,255,0.3)',
              borderRadius:8, color:'#7c6fff', fontSize:11, padding:'4px 10px', cursor:'pointer' }}>
            {'</>'} Editor
          </button>
        )}
      </div>

      {/* Messages */}
      <div style={{ flex:1, overflowY:'auto', padding:'12px 10px', display:'flex', flexDirection:'column', gap:8, minHeight:0 }}>
        {msgs.map((m, i) => (
          <div key={i} style={{ display:'flex', justifyContent: m.role==='user' ? 'flex-end' : 'flex-start' }}>
            <div style={{ maxWidth:'90%', borderRadius:10, overflow:'hidden',
              background: m.role==='user' ? '#7c6fff' : 'rgba(255,255,255,0.05)',
              border: m.role==='skyd' ? '1px solid rgba(255,255,255,0.07)' : 'none' }}>
              <div style={{ padding:'8px 12px', fontSize:13, lineHeight:1.5, color:'#fff' }}>
                {m.streaming && !m.content
                  ? <span style={{ opacity:0.4 }}>▋</span>
                  : <MsgMarkdown content={m.content} />}
              </div>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ padding:'8px 10px 12px', borderTop:'1px solid rgba(255,255,255,0.06)', flexShrink:0 }}>
        <div style={{ display:'flex', gap:6, alignItems:'flex-end' }}>
          <textarea value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            placeholder="Describe what to build, paste code, ask to fix..."
            rows={isMobile ? 2 : 3}
            style={{ flex:1, background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.1)',
              borderRadius:10, padding:'8px 12px', color:'#fff', fontSize:13, outline:'none',
              resize:'none', fontFamily:'inherit', lineHeight:1.5 }} />
          <button onClick={send} disabled={loading || !input.trim()}
            style={{ background:'#7c6fff', border:'none', borderRadius:10, color:'#fff',
              padding:'0 16px', cursor:'pointer', fontSize:18, height:40,
              opacity:(loading||!input.trim()) ? 0.5 : 1, flexShrink:0 }}>↑</button>
        </div>
      </div>
    </div>
  )
}

// ── Editor panel (shared between mobile+desktop) ──────────────────────────────
function EditorPanel({ files, activeFile, setActive, addFile, closeFile, updateContent, isMobile, onSwitchToChat, showPreview, setShowPreview }) {
  const activeLang = detectLang(activeFile)
  const copyAll    = () => navigator.clipboard?.writeText(files.find(f => f.name===activeFile)?.content||'')
  const download   = () => {
    const f = files.find(x => x.name===activeFile)
    if (!f) return
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([f.content],{type:'text/plain'}))
    a.download = f.name; a.click()
  }

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', minHeight:0 }}>
      {/* Toolbar */}
      <div style={{ display:'flex', alignItems:'center', gap:4, padding:'0 8px',
        background:'#0d0d1a', borderBottom:'1px solid rgba(255,255,255,0.07)',
        height:36, flexShrink:0 }}>
        {isMobile && (
          <button onClick={onSwitchToChat}
            style={{ background:'rgba(124,111,255,0.15)', border:'1px solid rgba(124,111,255,0.3)',
              borderRadius:8, color:'#7c6fff', fontSize:11, padding:'3px 9px', cursor:'pointer', marginRight:4 }}>
            💬 Chat
          </button>
        )}
        <span style={{ fontSize:10, color:'rgba(255,255,255,0.3)', flex:1 }}>{activeLang}</span>
        <button onClick={copyAll}
          style={{ background:'none', border:'1px solid rgba(255,255,255,0.1)', borderRadius:5,
            color:'rgba(255,255,255,0.5)', fontSize:10, padding:'2px 8px', cursor:'pointer' }}>copy</button>
        <button onClick={download}
          style={{ background:'none', border:'1px solid rgba(255,255,255,0.1)', borderRadius:5,
            color:'rgba(255,255,255,0.5)', fontSize:10, padding:'2px 8px', cursor:'pointer' }}>↓</button>
        <button onClick={() => setShowPreview(p => !p)}
          style={{ background: showPreview ? 'rgba(124,111,255,0.25)' : 'none',
            border:'1px solid rgba(124,111,255,0.3)', borderRadius:5,
            color: showPreview ? '#7c6fff' : 'rgba(255,255,255,0.4)',
            fontSize:10, padding:'2px 8px', cursor:'pointer' }}>
          {showPreview ? '⬛' : '▶'}
        </button>
      </div>

      {/* File tabs */}
      <FileTabs files={files} activeFile={activeFile}
        onSelect={setActive} onAdd={addFile} onClose={closeFile} compact={isMobile} />

      {/* Editor area */}
      <div style={{ flex:1, overflow:'hidden', minHeight:0 }}>
        {showPreview
          ? <LivePreview files={files} activeFile={activeFile} />
          : <CodeEditor key={activeFile}
              value={files.find(f => f.name===activeFile)?.content||''}
              onChange={updateContent} lang={activeLang} />
        }
      </div>
    </div>
  )
}

// ── Main CodeAgent ────────────────────────────────────────────────────────────
export default function CodeAgent({ token }) {
  const isMobile  = useIsMobile()
  const [mobileTab, setMobileTab] = useState('chat') // 'chat' | 'editor'

  // Chat state
  const [msgs, setMsgs]         = useState([{ role:'skyd', content:"Hey — I'm skyd's coding agent. Tell me what to build and I'll put the code straight in the editor." }])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const bottomRef               = useRef(null)

  // Editor state
  const [files, setFiles]       = useState([{ name:'main.js', content:'// Start coding here\n' }])
  const [activeFile, setActive] = useState('main.js')
  const [showPreview, setShowPreview] = useState(false)

  // Desktop drag-split
  const [splitPos, setSplitPos] = useState(42)
  const dragging = useRef(false)
  useEffect(() => {
    const onMove = e => { if (!dragging.current) return
      setSplitPos(Math.min(75, Math.max(25, (e.clientX / window.innerWidth) * 100))) }
    const onUp   = () => { dragging.current = false }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup',   onUp)
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  }, [])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:'smooth' }) }, [msgs])

  // Pull code blocks from AI response → push into editor
  const extractAndPushCode = useCallback((text) => {
    const re = /```(\w+)?\n([\s\S]*?)```/g
    let match
    while ((match = re.exec(text)) !== null) {
      const lang = match[1] || 'js'
      const code = match[2]
      const extMap = { javascript:'js', js:'js', jsx:'jsx', typescript:'ts', ts:'ts',
                       python:'py', py:'py', html:'html', css:'css', json:'json', sh:'sh', bash:'sh' }
      const ext = extMap[lang] || lang
      setFiles(prev => {
        const existing = prev.find(f => f.name.endsWith('.'+ext))
        if (existing) return prev.map(f => f.name===existing.name ? {...f, content:code} : f)
        const name = `skyd_${Date.now()}.${ext}`
        setActive(name)
        // On mobile, auto-switch to editor when code arrives
        if (isMobile) setMobileTab('editor')
        return [...prev, { name, content:code }]
      })
    }
  }, [isMobile])

  const send = async () => {
    const msg = input.trim()
    if (!msg || loading) return
    setInput('')
    setLoading(true)

    const activeContent = files.find(f => f.name===activeFile)?.content || ''
    const contextMsg = activeContent.trim()
      ? `${msg}\n\n[Current file: ${activeFile}]\n\`\`\`\n${activeContent.slice(0,2000)}\n\`\`\``
      : msg

    setMsgs(m => [...m, { role:'user', content:msg }, { role:'skyd', content:'', streaming:true }])

    try {
      const r = await fetch(`${API}/api/chat`, {
        method:'POST',
        headers:{ 'Content-Type':'application/json', ...(token ? { Authorization:`Bearer ${token}` } : {}) },
        body: JSON.stringify({
          message: contextMsg, mode:'ensemble', session_id: sessionId,
          system_override:`You are skyd's coding agent. Always wrap code in fenced code blocks with the correct language tag. Write complete working code. Explain AFTER the code block. If editing, return the FULL updated file.`
        })
      })
      const d = await r.json()
      const resp = d.response || d.final || ''
      if (d.session_id && !sessionId) setSessionId(d.session_id)
      extractAndPushCode(resp)
      setMsgs(m => { const a=[...m]; a[a.length-1]={ role:'skyd', content:resp, streaming:false }; return a })
    } catch(e) {
      setMsgs(m => { const a=[...m]; a[a.length-1]={ role:'skyd', content:`Error: ${e.message}`, streaming:false }; return a })
    }
    setLoading(false)
  }

  const addFile = () => {
    const name = prompt('File name (e.g. utils.py):')
    if (!name) return
    setFiles(f => [...f, { name, content:'' }])
    setActive(name)
  }
  const closeFile = (name) => {
    setFiles(f => {
      const next = f.filter(x => x.name!==name)
      if (activeFile===name) setActive(next[0]?.name||'')
      return next.length ? next : [{ name:'main.js', content:'' }]
    })
  }
  const updateContent = (content) => setFiles(f => f.map(x => x.name===activeFile ? {...x, content} : x))

  // ── MOBILE LAYOUT: full-screen tabs ───────────────────────────────────────
  if (isMobile) {
    return (
      <div style={{ display:'flex', flexDirection:'column', height:'100%', width:'100%',
        background:'#09090f', overflow:'hidden' }}>
        {mobileTab === 'chat'
          ? <ChatPanel msgs={msgs} input={input} setInput={setInput} send={send}
              loading={loading} bottomRef={bottomRef} isMobile={true}
              onSwitchToEditor={() => setMobileTab('editor')} />
          : <EditorPanel files={files} activeFile={activeFile} setActive={setActive}
              addFile={addFile} closeFile={closeFile} updateContent={updateContent}
              isMobile={true} showPreview={showPreview} setShowPreview={setShowPreview}
              onSwitchToChat={() => setMobileTab('chat')} />
        }
      </div>
    )
  }

  // ── DESKTOP LAYOUT: side-by-side split ────────────────────────────────────
  return (
    <div style={{ display:'flex', height:'100%', width:'100%', overflow:'hidden', background:'#09090f' }}>
      {/* Chat */}
      <div style={{ width:`${splitPos}%`, minWidth:280, overflow:'hidden' }}>
        <ChatPanel msgs={msgs} input={input} setInput={setInput} send={send}
          loading={loading} bottomRef={bottomRef} isMobile={false} />
      </div>

      {/* Drag handle */}
      <div onMouseDown={() => { dragging.current = true }}
        style={{ width:4, background:'rgba(124,111,255,0.15)', cursor:'col-resize', flexShrink:0 }}
        onMouseEnter={e => e.currentTarget.style.background='rgba(124,111,255,0.5)'}
        onMouseLeave={e => e.currentTarget.style.background='rgba(124,111,255,0.15)'} />

      {/* Editor */}
      <div style={{ flex:1, minWidth:0, overflow:'hidden' }}>
        <EditorPanel files={files} activeFile={activeFile} setActive={setActive}
          addFile={addFile} closeFile={closeFile} updateContent={updateContent}
          isMobile={false} showPreview={showPreview} setShowPreview={setShowPreview} />
      </div>
    </div>
  )
}
