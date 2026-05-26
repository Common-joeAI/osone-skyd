import { useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const _isLocal = window.location.port !== ''
const API_BASE = _isLocal ? `http://${window.location.hostname}:8000` : `${window.location.protocol}//${window.location.host}`
const WS_BASE = _isLocal
  ? `ws://${window.location.hostname}:8000`
  : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`

// ── Mobile detection ──────────────────────────────────────────────────────────
function useIsMobile() {
  const [m, setM] = useState(() =>
    /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent) || window.innerWidth <= 768)
  useEffect(() => {
    const c = () => setM(/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent) || window.innerWidth <= 768)
    window.addEventListener('resize', c); return () => window.removeEventListener('resize', c)
  }, [])
  return m
}

// ── Web Audio context (singleton) ─────────────────────────────────────────────
let _audioCtx = null
function getAudio() {
  if (!_audioCtx) _audioCtx = new (window.AudioContext || window.webkitAudioContext)()
  if (_audioCtx.state === 'suspended') _audioCtx.resume()
  return _audioCtx
}

// ── Play a note via Web Audio API ─────────────────────────────────────────────
function playNote(midiNote, duration = 0.8, type = 'triangle', delay = 0) {
  const ctx = getAudio()
  const freq = 440 * Math.pow(2, (midiNote - 69) / 12)
  const osc  = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain); gain.connect(ctx.destination)
  osc.type      = type
  osc.frequency.setValueAtTime(freq, ctx.currentTime + delay)
  gain.gain.setValueAtTime(0, ctx.currentTime + delay)
  gain.gain.linearRampToValueAtTime(0.3, ctx.currentTime + delay + 0.01)
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + duration)
  osc.start(ctx.currentTime + delay)
  osc.stop(ctx.currentTime + delay + duration + 0.05)
}

// ── Play chord (array of midi notes) ─────────────────────────────────────────
function playChord(notes, duration = 1.2) {
  notes.forEach(n => playNote(n, duration))
}

// ── Play scale ────────────────────────────────────────────────────────────────
function playScale(rootMidi, intervals, ascending = true) {
  const notes = intervals.map(i => rootMidi + i)
  if (!ascending) notes.reverse()
  notes.forEach((n, i) => playNote(n, 0.5, 'triangle', i * 0.18))
}

// ── Music theory data ─────────────────────────────────────────────────────────
const NOTE_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
const SCALES = {
  'Major':           { intervals:[0,2,4,5,7,9,11,12], color:'#7c6fff' },
  'Natural Minor':   { intervals:[0,2,3,5,7,8,10,12], color:'#ef4444' },
  'Dorian':          { intervals:[0,2,3,5,7,9,10,12], color:'#3b82f6' },
  'Phrygian':        { intervals:[0,1,3,5,7,8,10,12], color:'#f59e0b' },
  'Lydian':          { intervals:[0,2,4,6,7,9,11,12], color:'#10b981' },
  'Mixolydian':      { intervals:[0,2,4,5,7,9,10,12], color:'#8b5cf6' },
  'Locrian':         { intervals:[0,1,3,5,6,8,10,12], color:'#ec4899' },
  'Harmonic Minor':  { intervals:[0,2,3,5,7,8,11,12], color:'#f97316' },
  'Whole Tone':      { intervals:[0,2,4,6,8,10,12],   color:'#06b6d4' },
  'Pentatonic Maj':  { intervals:[0,2,4,7,9,12],       color:'#84cc16' },
  'Blues':           { intervals:[0,3,5,6,7,10,12],    color:'#6366f1' },
  'Chromatic':       { intervals:[0,1,2,3,4,5,6,7,8,9,10,11,12], color:'#94a3b8' },
}
const CHORDS = {
  'Major':      [0,4,7],   'Minor':      [0,3,7],
  'Dim':        [0,3,6],   'Aug':        [0,4,8],
  'Maj7':       [0,4,7,11],'Min7':       [0,3,7,10],
  'Dom7':       [0,4,7,10],'Dim7':       [0,3,6,9],
  'Sus2':       [0,2,7],   'Sus4':       [0,5,7],
  'Add9':       [0,4,7,14],'Maj9':       [0,4,7,11,14],
}
const ROOTS = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

// ── Piano keyboard ────────────────────────────────────────────────────────────
function Piano({ highlightedNotes = [], onNotePlay, startOctave = 4, octaves = 2 }) {
  const totalKeys = octaves * 12
  const startMidi = (startOctave + 1) * 12  // midi 60 = C4

  const keys = []
  for (let i = 0; i < totalKeys; i++) {
    const midi  = startMidi + i
    const name  = NOTE_NAMES[i % 12]
    const isBlack = name.includes('#')
    keys.push({ midi, name, isBlack })
  }

  const whites = keys.filter(k => !k.isBlack)
  const keyW = 36

  return (
    <div style={{ position:'relative', display:'flex', userSelect:'none',
      height:120, marginBottom:8, overflowX:'auto' }}>
      {whites.map((k, wi) => {
        const isHighlighted = highlightedNotes.includes(k.midi)
        return (
          <div key={k.midi} onPointerDown={() => { playNote(k.midi); onNotePlay?.(k) }}
            style={{ position:'relative', width:keyW, height:110, background: isHighlighted ? '#7c6fff' : '#f0f0f0',
              border:'1px solid #333', borderRadius:'0 0 4px 4px', cursor:'pointer', flexShrink:0,
              boxShadow: isHighlighted ? '0 0 10px rgba(124,111,255,0.8)' : 'none',
              transition:'background 0.1s', zIndex:1 }}>
            {wi % 12 === 0 && (
              <span style={{ position:'absolute', bottom:4, left:'50%', transform:'translateX(-50%)',
                fontSize:9, color: isHighlighted ? '#fff' : '#666' }}>
                C{startOctave + Math.floor(wi/7)}
              </span>
            )}
          </div>
        )
      })}
      {/* Black keys overlay */}
      {keys.filter(k => k.isBlack).map(k => {
        const noteIdx = k.midi - startMidi
        const octave  = Math.floor(noteIdx / 12)
        const posInOct = noteIdx % 12
        // White key positions within octave: 0,2,4,5,7,9,11
        const whitesBefore = [0,2,4,5,7,9,11].filter(w => w < posInOct).length + octave * 7
        const isHighlighted = highlightedNotes.includes(k.midi)
        return (
          <div key={k.midi} onPointerDown={e => { e.stopPropagation(); playNote(k.midi); onNotePlay?.(k) }}
            style={{ position:'absolute', left: whitesBefore * keyW + keyW * 0.6,
              top:0, width: keyW * 0.6, height:70,
              background: isHighlighted ? '#a78bfa' : '#1a1a1a',
              border:'1px solid #000', borderRadius:'0 0 3px 3px', cursor:'pointer', zIndex:2,
              boxShadow: isHighlighted ? '0 0 10px rgba(167,139,250,0.8)' : 'none',
              transition:'background 0.1s' }} />
        )
      })}
    </div>
  )
}

// ── Chord/Scale visualizer panel ──────────────────────────────────────────────
function Visualizer({ isMobile }) {
  const [rootIdx,    setRootIdx]    = useState(0)   // index into ROOTS
  const [scaleKey,   setScaleKey]   = useState('Major')
  const [chordKey,   setChordKey]   = useState('Major')
  const [tab,        setTab]        = useState('scale') // 'scale' | 'chord'
  const [playing,    setPlaying]    = useState(false)

  const rootMidi  = 60 + rootIdx  // C4 = 60
  const scaleData = SCALES[scaleKey]
  const chordInts = CHORDS[chordKey]

  const highlightedNotes = tab === 'scale'
    ? scaleData.intervals.map(i => rootMidi + i)
    : chordInts.map(i => rootMidi + i)

  const doPlay = () => {
    if (playing) return
    setPlaying(true)
    if (tab === 'scale') {
      playScale(rootMidi, scaleData.intervals)
      setTimeout(() => setPlaying(false), scaleData.intervals.length * 180 + 600)
    } else {
      playChord(chordInts.map(i => rootMidi + i))
      setTimeout(() => setPlaying(false), 1400)
    }
  }

  const noteNames = highlightedNotes.map(m => NOTE_NAMES[m % 12])

  return (
    <div style={{ background:'#0d0d1a', borderRadius:12, padding:14,
      border:'1px solid rgba(255,255,255,0.07)' }}>
      {/* Tab switcher */}
      <div style={{ display:'flex', gap:6, marginBottom:12 }}>
        {['scale','chord'].map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{ background: tab===t ? 'rgba(124,111,255,0.25)' : 'rgba(255,255,255,0.05)',
              border:`1px solid ${tab===t ? '#7c6fff' : 'rgba(255,255,255,0.1)'}`,
              borderRadius:8, color: tab===t ? '#7c6fff' : 'rgba(255,255,255,0.5)',
              fontSize:12, padding:'4px 14px', cursor:'pointer', fontWeight: tab===t ? 700 : 400 }}>
            {t === 'scale' ? '🎵 Scale' : '🎹 Chord'}
          </button>
        ))}
      </div>

      {/* Controls */}
      <div style={{ display:'flex', flexWrap:'wrap', gap:8, marginBottom:12, alignItems:'center' }}>
        {/* Root selector */}
        <select value={rootIdx} onChange={e => setRootIdx(+e.target.value)}
          style={{ background:'rgba(255,255,255,0.08)', border:'1px solid rgba(255,255,255,0.15)',
            borderRadius:8, color:'#fff', padding:'5px 10px', fontSize:13, cursor:'pointer' }}>
          {ROOTS.map((r, i) => <option key={i} value={i} style={{ background:'#1a1a2e' }}>{r}</option>)}
        </select>

        {/* Scale / chord type */}
        <select value={tab==='scale' ? scaleKey : chordKey}
          onChange={e => tab==='scale' ? setScaleKey(e.target.value) : setChordKey(e.target.value)}
          style={{ background:'rgba(255,255,255,0.08)', border:'1px solid rgba(255,255,255,0.15)',
            borderRadius:8, color:'#fff', padding:'5px 10px', fontSize:13, cursor:'pointer', flex:1, minWidth:120 }}>
          {Object.keys(tab==='scale' ? SCALES : CHORDS).map(k => (
            <option key={k} value={k} style={{ background:'#1a1a2e' }}>{k}</option>
          ))}
        </select>

        {/* Play button */}
        <button onClick={doPlay} disabled={playing}
          style={{ background: playing ? 'rgba(124,111,255,0.2)' : '#7c6fff',
            border:'none', borderRadius:8, color:'#fff',
            padding:'5px 16px', cursor: playing ? 'wait' : 'pointer', fontSize:13, fontWeight:700 }}>
          {playing ? '♪ playing...' : '▶ Play'}
        </button>
      </div>

      {/* Note badges */}
      <div style={{ display:'flex', flexWrap:'wrap', gap:6, marginBottom:12 }}>
        {noteNames.map((n, i) => (
          <span key={i} onPointerDown={() => playNote(highlightedNotes[i])}
            style={{ background: `${tab==='scale' ? scaleData.color : '#7c6fff'}22`,
              border:`1px solid ${tab==='scale' ? scaleData.color : '#7c6fff'}55`,
              borderRadius:6, padding:'3px 10px', fontSize:12,
              color: tab==='scale' ? scaleData.color : '#a78bfa', cursor:'pointer' }}>
            {n}
          </span>
        ))}
      </div>

      {/* Piano */}
      <Piano highlightedNotes={highlightedNotes} startOctave={4} octaves={isMobile ? 1 : 2} />
    </div>
  )
}

// ── Markdown renderer ─────────────────────────────────────────────────────────
function MsgMD({ content }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
      p({ children })      { return <p style={{ margin:'3px 0 8px', lineHeight:1.7 }}>{children}</p> },
      strong({ children }) { return <strong style={{ color:'#c4b5fd', fontWeight:700 }}>{children}</strong> },
      em({ children })     { return <em style={{ color:'#a5f3fc' }}>{children}</em> },
      ul({ children })     { return <ul style={{ margin:'4px 0 8px', paddingLeft:18, lineHeight:1.8 }}>{children}</ul> },
      ol({ children })     { return <ol style={{ margin:'4px 0 8px', paddingLeft:18, lineHeight:1.8 }}>{children}</ol> },
      li({ children })     { return <li style={{ marginBottom:3 }}>{children}</li> },
      h1({ children })     { return <h1 style={{ color:'#c4b5fd', fontSize:17, margin:'10px 0 5px', fontWeight:700 }}>{children}</h1> },
      h2({ children })     { return <h2 style={{ color:'#a78bfa', fontSize:15, margin:'8px 0 4px', fontWeight:700 }}>{children}</h2> },
      h3({ children })     { return <h3 style={{ color:'#818cf8', fontSize:13, margin:'6px 0 3px', fontWeight:600 }}>{children}</h3> },
      blockquote({ children }) { return <blockquote style={{ borderLeft:'3px solid #a78bfa', paddingLeft:10, margin:'8px 0', color:'rgba(255,255,255,0.6)', fontStyle:'italic' }}>{children}</blockquote> },
      code({ inline, children }) {
        return inline
          ? <code style={{ background:'rgba(124,111,255,0.15)', color:'#c4b5fd', borderRadius:4, padding:'1px 5px', fontFamily:'monospace', fontSize:'0.9em' }}>{children}</code>
          : <pre style={{ background:'#1a1a2e', borderRadius:8, padding:12, overflowX:'auto', fontSize:12, margin:'8px 0' }}><code>{children}</code></pre>
      },
    }}>{content}</ReactMarkdown>
  )
}

// ── Quick topic buttons ───────────────────────────────────────────────────────
const TOPICS = [
  { label:'🎵 What is a note?',          q:'Explain what a musical note actually is — from physics all the way to why we hear it as music.' },
  { label:'🔢 Overtone series',          q:'Explain the overtone series and why it is the foundation of all music theory.' },
  { label:'🎸 Why does minor sound sad?', q:'Why does minor sound sad and major sound happy? Is it physics, culture, or both?' },
  { label:'🌍 Indian ragas',             q:'Explain Indian classical music — ragas, talas, and how they differ from Western music.' },
  { label:'🎲 John Cage & chance music', q:'Who was John Cage and what is chance music? Why is 4\'33" considered a masterpiece?' },
  { label:'⚗️ Serialism explained',      q:'Explain serialism and 12-tone technique — why Schoenberg invented it and what it sounds like.' },
  { label:'🌊 Spectral music',           q:'What is spectral music and how does it differ from traditional composition?' },
  { label:'🎹 Modal jazz',               q:'Explain modal jazz — what Miles Davis did on Kind of Blue and why it changed everything.' },
  { label:'🔬 Microtones',               q:'What are microtones? Explain equal temperament vs just intonation and why it matters.' },
  { label:'⚡ Synthesizers',             q:'How do synthesizers work — from oscillators, filters, and envelopes to modern synthesis.' },
]

// ── Main MusicAgent ───────────────────────────────────────────────────────────
export default function MusicAgent() {
  const isMobile = useIsMobile()
  const [msgs,  setMsgs]  = useState([{
    role:'aria',
    content:`Hello. I'm **Aria** — a music intelligence built into OSONE.\n\nI know music from its deepest roots — the physics of vibration, the mathematics of harmony, the history of every tradition — all the way to the experimental edge where music breaks its own rules.\n\nWhat do you want to explore?`
  }])
  const [input,   setInput]   = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])
  const [showViz, setShowViz] = useState(!isMobile)
  const [composePrompt, setComposePrompt] = useState('')
  const [composing, setComposing] = useState(false)
  const [composition, setComposition] = useState(null)
  const [showCompose, setShowCompose] = useState(false)
  const [listening,  setListening]  = useState(false)
  const [speaking,   setSpeaking]   = useState(false)
  const [voiceOn,    setVoiceOn]    = useState(true)
  const [voiceMode,  setVoiceMode]  = useState(false)

  const bottomRef      = useRef(null)
  const synthRef       = useRef(window.speechSynthesis)
  const voiceRef       = useRef(null)
  const sentenceBuffer = useRef('')
  const voiceModeRef   = useRef(false)
  const recRef         = useRef(null)

  useEffect(() => { voiceModeRef.current = voiceMode }, [voiceMode])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:'smooth' }) }, [msgs])

  // Pick best voice
  useEffect(() => {
    const pick = () => {
      const voices = synthRef.current.getVoices()
      const want = ['Google US English','Samantha','Google UK English Female','Microsoft Zira','en-US']
      for (const n of want) {
        const v = voices.find(v => v.name.includes(n) || v.lang.includes(n))
        if (v) { voiceRef.current = v; return }
      }
      voiceRef.current = voices.find(v => v.lang.startsWith('en')) || voices[0] || null
    }
    pick()
    synthRef.current.addEventListener('voiceschanged', pick)
    return () => synthRef.current.removeEventListener('voiceschanged', pick)
  }, [])

  const cleanTTS = t => t
    .replace(/```[\s\S]*?```/g,'code block.')
    .replace(/`[^`]+`/g,'')
    .replace(/[*_#>\[\]]/g,'')
    .replace(/https?:\/\/\S+/g,'link')
    .replace(/\s+/g,' ').trim()

  const speakChunk = useCallback((text) => {
    if (!voiceOn || !text.trim()) return
    const utt = new SpeechSynthesisUtterance(text.trim())
    utt.voice  = voiceRef.current
    utt.rate   = 1.0
    utt.pitch  = 1.05
    utt.volume = 1
    utt.onstart = () => setSpeaking(true)
    utt.onend   = () => {
      setSpeaking(false)
      // Voice mode — auto listen again after speaking
      if (voiceModeRef.current) {
        setTimeout(() => { if (voiceModeRef.current) startListening() }, 500)
      }
    }
    synthRef.current.speak(utt)
  }, [voiceOn])

  const streamToken = useCallback((token) => {
    if (!voiceOn) return
    sentenceBuffer.current += token
    const re = /[^.!?]*[.!?]+(\s|$)/g
    let match, last = 0
    while ((match = re.exec(sentenceBuffer.current)) !== null) {
      const s = cleanTTS(match[0])
      if (s.length > 3) speakChunk(s)
      last = re.lastIndex
    }
    sentenceBuffer.current = sentenceBuffer.current.slice(last)
  }, [voiceOn, speakChunk])

  const flushBuffer = useCallback(() => {
    const r = cleanTTS(sentenceBuffer.current)
    if (r.length > 2) speakChunk(r)
    sentenceBuffer.current = ''
  }, [speakChunk])

  const stopSpeaking = () => { synthRef.current.cancel(); setSpeaking(false); sentenceBuffer.current = '' }

  const startListening = useCallback((onTranscript) => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return
    synthRef.current.cancel()
    const rec = new SR()
    rec.lang = 'en-US'; rec.continuous = false; rec.interimResults = true
    rec.onresult = (e) => {
      const t = Array.from(e.results).map(r => r[0].transcript).join(' ').trim()
      setInput(t)
      if (e.results[e.results.length-1].isFinal) {
        if (onTranscript) onTranscript(t)
        else setTimeout(() => sendMsg(t), 100)
      }
    }
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    recRef.current = rec
    rec.start()
    setListening(true)
  }, [])

  const sendMsg = async (overrideMsg) => {
    const msg = (overrideMsg || input).trim()
    if (!msg || loading) return
    setInput('')
    setLoading(true)

    const newHistory = [...history, { role:'user', content: msg }]
    setHistory(newHistory)
    setMsgs(m => [...m, { role:'user', content:msg }, { role:'aria', content:'', streaming:true }])

    try {
      const ws = new WebSocket(`${WS_BASE}/ws/music`)
      let full = ''
      ws.onopen  = () => ws.send(JSON.stringify({ message: msg, history: newHistory }))
      ws.onmessage = e => {
        const d = JSON.parse(e.data)
        if (d.token) {
          full += d.token
          streamToken(d.token)
          setMsgs(m => { const a=[...m]; a[a.length-1]={ role:'aria', content:full, streaming:true }; return a })
        }
        if (d.done) {
          flushBuffer()
          setMsgs(m => { const a=[...m]; a[a.length-1].streaming=false; return a })
          setHistory(h => [...h, { role:'assistant', content:full }])
          setLoading(false)
        }
      }
      ws.onerror = () => { setLoading(false) }
    } catch(e) { setLoading(false) }
  }


  const composeMusic = async () => {
    const prompt = composePrompt.trim()
    if (!prompt || composing) return
    setComposing(true)
    setComposition(null)
    try {
      const r = await fetch(`${API_BASE}/api/compose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      })
      // Read raw text first — avoids "Expecting value" crash on empty/HTML responses
      const text = await r.text()
      if (!text || !text.trim().startsWith('{')) {
        setComposition({ error: `Server returned unexpected response (HTTP ${r.status}). Try again.` })
        setComposing(false)
        return
      }
      let d
      try { d = JSON.parse(text) }
      catch { setComposition({ error: 'Could not parse server response. Try again.' }); setComposing(false); return }

      if (d.ok && d.composition) {
        setComposition(d.composition)
      } else {
        setComposition({ error: d.error || 'Composition failed — try a different prompt' })
      }
    } catch (e) {
      const msg = String(e)
      if (msg.includes('fetch') || msg.includes('network') || msg.includes('Failed')) {
        setComposition({ error: 'Network error — check your connection and try again' })
      } else {
        setComposition({ error: msg })
      }
    }
    setComposing(false)
  }

  return (
    <div style={{ display:'flex', flexDirection: isMobile ? 'column' : 'row',
      height:'100%', background:'#08080f', fontFamily:'system-ui,sans-serif', overflow:'hidden' }}>

      {/* ── LEFT / TOP: Chat ── */}
      <div style={{ flex:1, display:'flex', flexDirection:'column', minHeight:0,
        borderRight: isMobile ? 'none' : '1px solid rgba(255,255,255,0.07)',
        borderBottom: isMobile ? '1px solid rgba(255,255,255,0.07)' : 'none' }}>

        {/* Header */}
        <div style={{ padding:'10px 14px', borderBottom:'1px solid rgba(255,255,255,0.07)',
          background:'rgba(0,0,0,0.4)', display:'flex', alignItems:'center', gap:10, flexShrink:0 }}>
          <div style={{ fontSize:20 }}>🎵</div>
          <div>
            <div style={{ fontWeight:700, fontSize:13, color:'#c4b5fd', letterSpacing:1 }}>Aria</div>
            <div style={{ fontSize:10, color:'rgba(255,255,255,0.3)' }}>music intelligence</div>
          </div>
          <div style={{ flex:1 }} />
          {/* Voice controls */}
          <button onClick={() => { if (voiceMode) { setVoiceMode(false); stopSpeaking(); recRef.current?.stop() } else { setVoiceMode(true); startListening() }}}
            title={voiceMode ? 'Exit voice mode' : 'Voice mode'}
            style={{ background: voiceMode ? 'rgba(196,181,253,0.2)' : 'rgba(255,255,255,0.06)',
              border:`1px solid ${voiceMode ? '#c4b5fd' : 'rgba(255,255,255,0.1)'}`,
              borderRadius:8, color: voiceMode ? '#c4b5fd' : '#666',
              padding:'5px 10px', cursor:'pointer', fontSize:14 }}>🎙️</button>
          <button onClick={() => setVoiceOn(v => !v)} title={voiceOn ? 'Mute Aria' : 'Unmute Aria'}
            style={{ background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.1)',
              borderRadius:8, color: voiceOn ? '#c4b5fd' : '#444',
              padding:'5px 10px', cursor:'pointer', fontSize:14 }}>
            {voiceOn ? '🔊' : '🔇'}
          </button>
          {!isMobile && (
            <button onClick={() => setShowViz(v => !v)}
              style={{ background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.1)',
                borderRadius:8, color:'rgba(255,255,255,0.4)',
                padding:'5px 10px', cursor:'pointer', fontSize:11 }}>
              {showViz ? '⬛ hide' : '🎹 visualizer'}
            </button>
          )}
        </div>

        {/* Voice mode orb */}
        {voiceMode && (
          <div style={{ display:'flex', flexDirection:'column', alignItems:'center', padding:'12px',
            background:'rgba(196,181,253,0.05)', borderBottom:'1px solid rgba(255,255,255,0.06)' }}>
            <div onClick={() => { setVoiceMode(false); stopSpeaking(); recRef.current?.stop() }}
              style={{ width:60, height:60, borderRadius:'50%', cursor:'pointer',
                background: listening ? 'radial-gradient(circle,#ef4444,rgba(239,68,68,0.2))'
                  : speaking ? 'radial-gradient(circle,#c4b5fd,rgba(196,181,253,0.2))'
                  : 'radial-gradient(circle,rgba(196,181,253,0.4),rgba(196,181,253,0.05))',
                boxShadow: listening ? '0 0 25px rgba(239,68,68,0.5)'
                  : speaking ? '0 0 25px rgba(196,181,253,0.6)' : '0 0 10px rgba(196,181,253,0.2)',
                display:'flex', alignItems:'center', justifyContent:'center', fontSize:24,
                animation:(listening||speaking) ? 'pulse 1s infinite' : 'none', transition:'all 0.3s' }}>
              {listening ? '🎤' : speaking ? '🎵' : '🎙️'}
            </div>
            <span style={{ fontSize:10, color:'rgba(255,255,255,0.4)', marginTop:6 }}>
              {listening ? 'Listening...' : speaking ? 'Aria is speaking...' : 'Tap to stop'}
            </span>
          </div>
        )}

        {/* Messages */}
        <div style={{ flex:1, overflowY:'auto', padding:'14px 12px',
          display:'flex', flexDirection:'column', gap:10, minHeight:0 }}>
          {msgs.map((m, i) => (
            <div key={i} style={{ display:'flex', justifyContent: m.role==='user' ? 'flex-end' : 'flex-start' }}>
              {m.role==='aria' && <div style={{ fontSize:18, marginRight:8, marginTop:4, flexShrink:0 }}>🎵</div>}
              <div style={{ maxWidth:'88%', borderRadius:12, overflow:'hidden',
                background: m.role==='user'
                  ? 'linear-gradient(135deg, #7c6fff, #a78bfa)'
                  : 'rgba(196,181,253,0.06)',
                border: m.role==='aria' ? '1px solid rgba(196,181,253,0.1)' : 'none' }}>
                <div style={{ padding:'9px 13px', fontSize:13, lineHeight:1.6, color:'#fff' }}>
                  {m.streaming && !m.content
                    ? <span style={{ opacity:0.4 }}>♪</span>
                    : <MsgMD content={m.content} />}
                </div>
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Quick topics */}
        {msgs.length <= 2 && (
          <div style={{ padding:'0 12px 8px', display:'flex', flexWrap:'wrap', gap:6 }}>
            {TOPICS.slice(0, isMobile ? 4 : 6).map((t, i) => (
              <button key={i} onClick={() => sendMsg(t.q)}
                style={{ background:'rgba(196,181,253,0.08)', border:'1px solid rgba(196,181,253,0.15)',
                  borderRadius:20, color:'rgba(255,255,255,0.6)', fontSize:11,
                  padding:'5px 12px', cursor:'pointer' }}>{t.label}</button>
            ))}
          </div>
        )}

        {/* Input */}
        <div style={{ padding:'8px 12px 12px', borderTop:'1px solid rgba(255,255,255,0.06)', flexShrink:0 }}>
          {speaking && (
            <button onClick={stopSpeaking}
              style={{ display:'block', width:'100%', background:'rgba(196,181,253,0.1)',
                border:'1px solid rgba(196,181,253,0.3)', borderRadius:8,
                color:'#c4b5fd', fontSize:12, padding:'5px', cursor:'pointer', marginBottom:6,
                animation:'pulse 0.8s infinite' }}>⏸ Stop Aria speaking</button>
          )}
          <div style={{ display:'flex', gap:6, alignItems:'flex-end' }}>
            <textarea value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); sendMsg() }}}
              placeholder={listening ? '🎤 Listening...' : 'Ask Aria anything about music...'}
              rows={2}
              style={{ flex:1, background:'rgba(255,255,255,0.06)', border:'1px solid rgba(196,181,253,0.15)',
                borderRadius:10, padding:'8px 12px', color:'#fff', fontSize:13,
                outline:'none', resize:'none', fontFamily:'inherit', lineHeight:1.5 }} />
            <button onClick={() => listening ? recRef.current?.stop() : startListening()}
              style={{ background: listening ? 'rgba(239,68,68,0.2)' : 'rgba(255,255,255,0.06)',
                border:`1px solid ${listening ? '#ef4444' : 'rgba(255,255,255,0.1)'}`,
                borderRadius:10, color: listening ? '#ef4444' : '#666',
                padding:'0 12px', cursor:'pointer', fontSize:16, height:40, flexShrink:0 }}>
              {listening ? '⏹' : '🎤'}
            </button>
            <button onClick={() => sendMsg()} disabled={loading || !input.trim()}
              style={{ background:'linear-gradient(135deg,#7c6fff,#a78bfa)', border:'none',
                borderRadius:10, color:'#fff', padding:'0 16px', cursor:'pointer',
                fontSize:18, height:40, opacity:(loading||!input.trim())?0.5:1, flexShrink:0 }}>♪</button>
          </div>
        </div>
      </div>

      {/* ── RIGHT / BOTTOM: Compose + Visualizer ── */}
      <div style={{ width: isMobile ? '100%' : 380, flexShrink:0, display:'flex',
        flexDirection:'column', overflowY:'auto',
        maxHeight: isMobile ? '52%' : 'none',
        background:'rgba(0,0,0,0.3)', borderLeft: isMobile ? 'none' : '1px solid rgba(255,255,255,0.07)',
        borderTop: isMobile ? '1px solid rgba(255,255,255,0.07)' : 'none' }}>

        {/* ── TAB SWITCHER: Compose vs Explorer ── */}
        <div style={{ display:'flex', borderBottom:'1px solid rgba(255,255,255,0.07)', flexShrink:0 }}>
          {[['compose','🎼 Generate'],['explore','🎹 Explorer']].map(([id,label]) => (
            <button key={id} onClick={() => setShowCompose(id === 'compose')}
              style={{ flex:1, padding:'10px 0', border:'none', cursor:'pointer', fontSize:12, fontWeight:700,
                background: (id==='compose') === showCompose ? 'rgba(124,111,255,0.15)' : 'transparent',
                color: (id==='compose') === showCompose ? '#7c6fff' : 'rgba(255,255,255,0.35)',
                borderBottom: (id==='compose') === showCompose ? '2px solid #7c6fff' : '2px solid transparent' }}>
              {label}
            </button>
          ))}
        </div>

        <div style={{ flex:1, overflowY:'auto', padding:14 }}>
          {showCompose ? (
            /* ── COMPOSE PANEL ── */
            <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
              <div style={{ fontSize:11, color:'rgba(255,255,255,0.3)', letterSpacing:1, textTransform:'uppercase' }}>
                Describe your song
              </div>
              <textarea
                value={composePrompt}
                onChange={e => setComposePrompt(e.target.value)}
                onKeyDown={e => { if (e.key==='Enter' && e.metaKey) composeMusic() }}
                placeholder={"e.g. 'melancholy jazz ballad about 3am' or 'epic cinematic battle theme'"}
                rows={3}
                style={{ background:'rgba(255,255,255,0.07)', border:'1px solid rgba(124,111,255,0.25)',
                  borderRadius:10, padding:'10px 12px', color:'#fff', fontSize:13,
                  outline:'none', resize:'none', fontFamily:'inherit', lineHeight:1.5, width:'100%' }}
              />
              <button onClick={composeMusic} disabled={composing || !composePrompt.trim()}
                style={{ background: composing ? 'rgba(124,111,255,0.3)' : 'linear-gradient(135deg,#7c6fff,#a78bfa)',
                  border:'none', borderRadius:10, color:'#fff', padding:'12px',
                  cursor: composing ? 'wait' : 'pointer', fontSize:14, fontWeight:700,
                  opacity: !composePrompt.trim() ? 0.4 : 1, letterSpacing:0.5 }}>
                {composing ? '🎵 Composing...' : '🎼 Generate Song'}
              </button>

              {/* Quick mood buttons */}
              <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
                {['melancholy jazz','epic cinematic','lo-fi chill','angry punk','romantic waltz','dark ambient','upbeat pop','blues at midnight'].map(p => (
                  <button key={p} onClick={() => setComposePrompt(p)}
                    style={{ background:'rgba(124,111,255,0.08)', border:'1px solid rgba(124,111,255,0.2)',
                      borderRadius:20, color:'rgba(255,255,255,0.55)', fontSize:11,
                      padding:'4px 10px', cursor:'pointer' }}>{p}</button>
                ))}
              </div>

              {/* ── Result card ── */}
              {composition && !composition.error && (
                <div style={{ borderRadius:12, padding:14, marginTop:4,
                  background:'rgba(124,111,255,0.08)', border:'1px solid rgba(124,111,255,0.25)' }}>
                  <div style={{ fontWeight:800, fontSize:16, color:'#c4b5fd', marginBottom:6 }}>
                    {composition.title}
                  </div>
                  <div style={{ fontSize:12, color:'rgba(255,255,255,0.5)', fontStyle:'italic',
                    lineHeight:1.6, marginBottom:10 }}>{composition.story}</div>
                  <div style={{ display:'flex', flexWrap:'wrap', gap:6, marginBottom:10 }}>
                    {[
                      composition.key && `${composition.key} ${composition.mode}`,
                      composition.bpm && `${composition.bpm} BPM`,
                      composition.instrument,
                      composition.genre
                    ].filter(Boolean).map((tag,i) => (
                      <span key={i} style={{ background:'rgba(124,111,255,0.15)',
                        border:'1px solid rgba(124,111,255,0.3)', borderRadius:20,
                        padding:'3px 10px', fontSize:11, color:'#a78bfa' }}>{tag}</span>
                    ))}
                  </div>
                  {composition.lyrics && (
                    <div style={{ background:'rgba(0,0,0,0.3)', borderRadius:8, padding:10,
                      fontSize:12, color:'rgba(255,255,255,0.55)', lineHeight:1.8,
                      whiteSpace:'pre-wrap', maxHeight:180, overflowY:'auto', marginBottom:8 }}>
                      {composition.lyrics}
                    </div>
                  )}
                  <div style={{ fontSize:11, color:'rgba(124,111,255,0.5)' }}>
                    ✓ Composition ready — open Sky-Music to play
                  </div>
                </div>
              )}
              {composition?.error && (
                <div style={{ background:'rgba(239,68,68,0.1)', border:'1px solid rgba(239,68,68,0.3)',
                  borderRadius:8, padding:10, fontSize:12, color:'#f87171' }}>
                  {composition.error}
                </div>
              )}
            </div>
          ) : (
            /* ── EXPLORER PANEL ── */
            <div>
              <div style={{ fontSize:11, color:'rgba(255,255,255,0.3)', marginBottom:10,
                letterSpacing:1, textTransform:'uppercase' }}>Interactive Explorer</div>
              <Visualizer isMobile={isMobile} />
              {!isMobile && (
                <div style={{ marginTop:14 }}>
                  <div style={{ fontSize:11, color:'rgba(255,255,255,0.3)', marginBottom:8,
                    letterSpacing:1, textTransform:'uppercase' }}>Explore Topics</div>
                  <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
                    {TOPICS.map((t, i) => (
                      <button key={i} onClick={() => sendMsg(t.q)}
                        style={{ background:'rgba(196,181,253,0.06)', border:'1px solid rgba(196,181,253,0.1)',
                          borderRadius:8, color:'rgba(255,255,255,0.55)', fontSize:12,
                          padding:'7px 12px', cursor:'pointer', textAlign:'left' }}>{t.label}</button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
