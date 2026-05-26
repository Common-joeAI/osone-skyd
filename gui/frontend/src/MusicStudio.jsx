import { useState, useEffect, useRef, useCallback } from 'react'
import * as Tone from 'tone'

// ─────────────────────────────────────────────────────────────────────────────
//  CONFIG
// ─────────────────────────────────────────────────────────────────────────────
const _isLocal = window.location.port !== ''
const API    = _isLocal ? `http://${window.location.hostname}:8000` : `${window.location.protocol}//${window.location.host}`
const WS_BASE= _isLocal ? `ws://${window.location.hostname}:8000`  : `${window.location.protocol==='https:'?'wss':'ws'}://${window.location.host}`

// ─────────────────────────────────────────────────────────────────────────────
//  INSTRUMENTS  (same sampler cache pattern as DAW)
// ─────────────────────────────────────────────────────────────────────────────
const INSTRUMENT_DEFS = {
  piano:    { label:'Grand Piano',     color:'#7c6fff', baseUrl:'https://tonejs.github.io/audio/salamander/', urls:{A0:'A0.mp3',C1:'C1.mp3','D#1':'Ds1.mp3','F#1':'Fs1.mp3',A1:'A1.mp3',C2:'C2.mp3','D#2':'Ds2.mp3','F#2':'Fs2.mp3',A2:'A2.mp3',C3:'C3.mp3','D#3':'Ds3.mp3','F#3':'Fs3.mp3',A3:'A3.mp3',C4:'C4.mp3','D#4':'Ds4.mp3','F#4':'Fs4.mp3',A4:'A4.mp3',C5:'C5.mp3','D#5':'Ds5.mp3','F#5':'Fs5.mp3',A5:'A5.mp3',C6:'C6.mp3'} },
  guitar:   { label:'Acoustic Guitar', color:'#f59e0b', baseUrl:'https://tonejs.github.io/audio/guitar-acoustic/', urls:{E2:'E2.mp3',A2:'A2.mp3',D3:'D3.mp3',G3:'G3.mp3',B3:'B3.mp3',E4:'E4.mp3',A3:'A3.mp3',D4:'D4.mp3',G4:'G4.mp3',B4:'B4.mp3',E5:'E5.mp3'} },
  'e-guitar':{ label:'Electric Guitar',color:'#ef4444', baseUrl:'https://tonejs.github.io/audio/guitar-electric/', urls:{'D#3':'Ds3.mp3','F#3':'Fs3.mp3',A3:'A3.mp3',C4:'C4.mp3','D#4':'Ds4.mp3','F#4':'Fs4.mp3',A4:'A4.mp3',C5:'C5.mp3','D#5':'Ds5.mp3'} },
  bass:     { label:'Electric Bass',   color:'#10b981', baseUrl:'https://tonejs.github.io/audio/bass-electric/', urls:{'A#1':'As1.mp3','A#2':'As2.mp3',C2:'C2.mp3',C3:'C3.mp3',E1:'E1.mp3',E2:'E2.mp3',E3:'E3.mp3',G1:'G1.mp3',G2:'G2.mp3',G3:'G3.mp3'} },
  violin:   { label:'Violin',          color:'#ec4899', baseUrl:'https://tonejs.github.io/audio/violin/', urls:{A3:'A3.mp3',A4:'A4.mp3',A5:'A5.mp3',C4:'C4.mp3',C5:'C5.mp3',C6:'C6.mp3',E4:'E4.mp3',E5:'E5.mp3',G3:'G3.mp3',G4:'G4.mp3',G5:'G5.mp3'} },
  trumpet:  { label:'Trumpet',         color:'#f97316', baseUrl:'https://tonejs.github.io/audio/trumpet/', urls:{C4:'C4.mp3',D4:'D4.mp3','D#4':'Ds4.mp3',F4:'F4.mp3',G4:'G4.mp3',A4:'A4.mp3',C5:'C5.mp3',D5:'D5.mp3',F5:'F5.mp3',G5:'G5.mp3'} },
  flute:    { label:'Flute',           color:'#06b6d4', baseUrl:'https://tonejs.github.io/audio/flute/', urls:{A4:'A4.mp3',C5:'C5.mp3',E5:'E5.mp3',A5:'A5.mp3',C6:'C6.mp3',E6:'E6.mp3'} },
  cello:    { label:'Cello',           color:'#8b5cf6', baseUrl:'https://tonejs.github.io/audio/cello/', urls:{E2:'E2.mp3',A2:'A2.mp3',D3:'D3.mp3',G3:'G3.mp3',C3:'C3.mp3',A3:'A3.mp3',D4:'D4.mp3'} },
  marimba:  { label:'Marimba',         color:'#84cc16', baseUrl:'https://tonejs.github.io/audio/marimba/', urls:{A1:'A1.mp3',C2:'C2.mp3',E2:'E2.mp3',A2:'A2.mp3',C3:'C3.mp3',E3:'E3.mp3',A3:'A3.mp3',C4:'C4.mp3',E4:'E4.mp3',A4:'A4.mp3'} },
  organ:    { label:'Organ',           color:'#a78bfa', baseUrl:'https://tonejs.github.io/audio/organ/', urls:{C2:'C2.mp3',C3:'C3.mp3',C4:'C4.mp3',C5:'C5.mp3','F#2':'Fs2.mp3','F#3':'Fs3.mp3','F#4':'Fs4.mp3',A2:'A2.mp3',A3:'A3.mp3',A4:'A4.mp3'} },
}

const NOTE_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
const midiToNote = m => NOTE_NAMES[m%12] + (Math.floor(m/12)-1)

const _samplers = {}
function getSampler(key) {
  return new Promise(resolve => {
    if (_samplers[key]) { resolve(_samplers[key]); return }
    const def = INSTRUMENT_DEFS[key]
    if (!def) { resolve(null); return }
    const s = new Tone.Sampler({ urls: def.urls, baseUrl: def.baseUrl,
      onload: () => { _samplers[key] = s; resolve(s) } }).toDestination()
  })
}

// Drum synths
let _drums = null
function getDrums() {
  if (_drums) return _drums
  _drums = {
    kick:    new Tone.MembraneSynth({ pitchDecay:0.05,octaves:5,envelope:{attack:0.001,decay:0.4,sustain:0,release:0.1}}).toDestination(),
    snare:   new Tone.NoiseSynth({noise:{type:'white'},envelope:{attack:0.001,decay:0.2,sustain:0,release:0.05}}).toDestination(),
    hihat:   new Tone.MetalSynth({frequency:400,envelope:{attack:0.001,decay:0.05,release:0.01},harmonicity:5.1,modulationIndex:32,resonance:4000,octaves:1.5}).toDestination(),
    openhat: new Tone.MetalSynth({frequency:400,envelope:{attack:0.001,decay:0.3,release:0.1},harmonicity:5.1,modulationIndex:32,resonance:4000,octaves:1.5}).toDestination(),
    clap:    new Tone.NoiseSynth({noise:{type:'pink'},envelope:{attack:0.001,decay:0.15,sustain:0,release:0.05}}).toDestination(),
    tom:     new Tone.MembraneSynth({pitchDecay:0.08,octaves:4,envelope:{attack:0.001,decay:0.3,sustain:0,release:0.1}}).toDestination(),
    rim:     new Tone.MetalSynth({frequency:800,envelope:{attack:0.001,decay:0.05,release:0.01},harmonicity:8,modulationIndex:16,resonance:5000,octaves:0.5}).toDestination(),
  }
  _drums.kick.volume.value=-3; _drums.snare.volume.value=-6; _drums.hihat.volume.value=-14
  _drums.openhat.volume.value=-16; _drums.clap.volume.value=-9; _drums.tom.volume.value=-7; _drums.rim.volume.value=-12
  return _drums
}

const DRUM_KEYS = ['kick','snare','hihat','openhat','clap','tom','rim']

function triggerDrum(type, time) {
  const d = getDrums()
  switch(type) {
    case 'kick':    d.kick.triggerAttackRelease('C1','8n',time); break
    case 'snare':   d.snare.triggerAttackRelease('8n',time); break
    case 'hihat':   d.hihat.triggerAttackRelease('32n',time); break
    case 'openhat': d.openhat.triggerAttackRelease('8n',time); break
    case 'clap':    d.clap.triggerAttackRelease('16n',time); break
    case 'tom':     d.tom.triggerAttackRelease('A1','8n',time); break
    case 'rim':     d.rim.triggerAttackRelease('32n',time); break
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  MOBILE
// ─────────────────────────────────────────────────────────────────────────────
function useIsMobile() {
  const [m,setM] = useState(()=>/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)||window.innerWidth<=768)
  useEffect(()=>{const c=()=>setM(/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)||window.innerWidth<=768);window.addEventListener('resize',c);return()=>window.removeEventListener('resize',c)},[])
  return m
}

// ─────────────────────────────────────────────────────────────────────────────
//  WAVEFORM VISUALIZER  (canvas, draws live amplitude)
// ─────────────────────────────────────────────────────────────────────────────
function Waveform({ playing, color = '#7c6fff' }) {
  const canvasRef = useRef(null)
  const animRef   = useRef(null)
  const analyser  = useRef(null)

  useEffect(() => {
    if (!playing) {
      cancelAnimationFrame(animRef.current)
      const canvas = canvasRef.current; if (!canvas) return
      const ctx = canvas.getContext('2d')
      ctx.clearRect(0,0,canvas.width,canvas.height)
      return
    }
    // Connect analyser to Tone destination
    const toneCtx = Tone.getContext().rawContext
    if (!analyser.current) {
      analyser.current = toneCtx.createAnalyser()
      analyser.current.fftSize = 256
      Tone.getDestination().connect(analyser.current)
    }
    const buf = new Uint8Array(analyser.current.frequencyBinCount)
    const draw = () => {
      animRef.current = requestAnimationFrame(draw)
      const canvas = canvasRef.current; if (!canvas) return
      const ctx = canvas.getContext('2d')
      analyser.current.getByteTimeDomainData(buf)
      ctx.clearRect(0,0,canvas.width,canvas.height)
      ctx.strokeStyle = color
      ctx.lineWidth   = 2
      ctx.shadowColor = color
      ctx.shadowBlur  = 8
      ctx.beginPath()
      const sliceW = canvas.width / buf.length
      let x = 0
      for (let i=0; i<buf.length; i++) {
        const v = buf[i]/128 - 1
        const y = (v * canvas.height/2) + canvas.height/2
        i===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y)
        x += sliceW
      }
      ctx.stroke()
    }
    draw()
    return () => cancelAnimationFrame(animRef.current)
  }, [playing, color])

  return <canvas ref={canvasRef} width={500} height={60}
    style={{ width:'100%', height:60, display:'block' }} />
}

// ─────────────────────────────────────────────────────────────────────────────
//  MINI PIANO ROLL  (read-only visualizer for composition preview)
// ─────────────────────────────────────────────────────────────────────────────
function MiniRoll({ notes, totalBeats, playhead, color, isMobile }) {
  if (!notes || notes.length === 0) return (
    <div style={{ height:80, display:'flex', alignItems:'center', justifyContent:'center',
      color:'rgba(255,255,255,0.2)', fontSize:12 }}>No notes yet</div>
  )
  const midiValues = notes.map(n=>n.midi)
  const midiMin = Math.min(...midiValues) - 2
  const midiMax = Math.max(...midiValues) + 2
  const range   = Math.max(midiMax - midiMin, 8)
  const cellW   = isMobile ? 8 : 14
  const cellH   = isMobile ? 4 : 6
  const height  = range * cellH
  const width   = totalBeats * cellW

  return (
    <div style={{ overflowX:'auto', overflowY:'hidden' }}>
      <div style={{ position:'relative', width, height, background:'rgba(0,0,0,0.3)',
        borderRadius:6, minHeight:60 }}>
        {/* Beat grid */}
        {Array.from({length:totalBeats},(_,b) => (
          <div key={b} style={{ position:'absolute', left:b*cellW, top:0, width:1, height:'100%',
            background: b%4===0 ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.04)' }} />
        ))}
        {/* Notes */}
        {notes.map((n,i) => (
          <div key={i} style={{ position:'absolute',
            left: n.start * cellW,
            top:  (midiMax - n.midi) * cellH,
            width: Math.max(cellW*0.8, n.len * cellW - 1),
            height: cellH - 1,
            background: color,
            borderRadius: 2,
            opacity: 0.85,
            boxShadow: `0 0 4px ${color}88` }} />
        ))}
        {/* Playhead */}
        {playhead > 0 && (
          <div style={{ position:'absolute', left: playhead*cellW, top:0, width:2,
            height:'100%', background:'#ef4444', boxShadow:'0 0 5px rgba(239,68,68,0.7)' }} />
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  SECTION CARD
// ─────────────────────────────────────────────────────────────────────────────
function SectionCard({ section, idx, color, isMobile }) {
  const [open, setOpen] = useState(idx === 0)
  const totalBeats = section.bars * 4

  return (
    <div style={{ background:'rgba(255,255,255,0.04)', border:`1px solid ${color}33`,
      borderRadius:10, marginBottom:8, overflow:'hidden' }}>
      <div onClick={()=>setOpen(o=>!o)}
        style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 14px',
          cursor:'pointer', background: open ? `${color}11` : 'transparent' }}>
        <span style={{ fontSize:10, color: color, fontWeight:700, letterSpacing:1,
          textTransform:'uppercase' }}>{section.name}</span>
        <span style={{ fontSize:10, color:'rgba(255,255,255,0.35)' }}>{section.bars} bars · {section.dynamic}</span>
        <span style={{ fontSize:10, color:'rgba(255,255,255,0.25)', flex:1 }}>{section.melodic_character}</span>
        <span style={{ fontSize:12, color:'rgba(255,255,255,0.3)' }}>{open ? '▲' : '▼'}</span>
      </div>
      {open && (
        <div style={{ padding:'0 14px 12px' }}>
          <div style={{ display:'flex', flexWrap:'wrap', gap:6, marginBottom:8 }}>
            {section.chord_progression?.map((c,i) => (
              <span key={i} style={{ background:`${color}22`, border:`1px solid ${color}44`,
                borderRadius:6, padding:'3px 10px', fontSize:12, color: color, fontWeight:600 }}>{c}</span>
            ))}
          </div>
          <MiniRoll notes={section.notes} totalBeats={totalBeats}
            playhead={0} color={color} isMobile={isMobile} />
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  VOCAL LINE DISPLAY
// ─────────────────────────────────────────────────────────────────────────────
function VocalLine({ vocal_melody, lyric_themes, color }) {
  if (!vocal_melody || vocal_melody.length === 0) return null
  return (
    <div style={{ background:'rgba(255,255,255,0.03)', border:`1px solid ${color}22`,
      borderRadius:10, padding:'12px 14px', marginBottom:12 }}>
      <div style={{ fontSize:10, color:'rgba(255,255,255,0.35)', letterSpacing:1, marginBottom:8 }}>
        🎤 VOCAL MELODY GUIDE
      </div>
      <div style={{ display:'flex', flexWrap:'wrap', gap:4, marginBottom:10 }}>
        {vocal_melody.map((v,i) => (
          <div key={i} style={{ display:'flex', flexDirection:'column', alignItems:'center',
            background:`${color}15`, border:`1px solid ${color}33`,
            borderRadius:6, padding:'4px 8px', minWidth:32 }}>
            <span style={{ fontSize:9, color: color }}>{NOTE_NAMES[v.midi%12]}</span>
            <span style={{ fontSize:8, color:'rgba(255,255,255,0.4)', marginTop:1 }}>{v.syllable || '—'}</span>
          </div>
        ))}
      </div>
      {lyric_themes && lyric_themes.length > 0 && (
        <div>
          <div style={{ fontSize:9, color:'rgba(255,255,255,0.3)', marginBottom:5 }}>LYRIC THEMES</div>
          <div style={{ display:'flex', flexWrap:'wrap', gap:5 }}>
            {lyric_themes.map((t,i) => (
              <span key={i} style={{ background:'rgba(255,255,255,0.06)', borderRadius:20,
                padding:'3px 10px', fontSize:11, color:'rgba(255,255,255,0.55)', fontStyle:'italic' }}>
                "{t}"
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  PLAYBACK ENGINE
// ─────────────────────────────────────────────────────────────────────────────
function usePlayback(composition) {
  const [playing,     setPlaying]  = useState(false)
  const [playhead,    setPlayhead] = useState(0)
  const [currentStep, setStep]     = useState(-1)

  const stepRef   = useRef(0)
  const beatRef   = useRef(0)
  const nextRef   = useRef(0)
  const timerRef  = useRef(null)
  const compRef   = useRef(composition)
  const playingRef= useRef(false)

  useEffect(() => { compRef.current = composition }, [composition])
  useEffect(() => { playingRef.current = playing }, [playing])

  const getAllNotes = useCallback(() => {
    const comp = compRef.current
    if (!comp) return []
    const all = []
    let beatOffset = 0
    comp.sections?.forEach(sec => {
      sec.notes?.forEach(n => all.push({ ...n, start: n.start + beatOffset }))
      beatOffset += (sec.bars || 2) * 4
    })
    return all
  }, [])

  const getTotalBeats = useCallback(() => {
    const comp = compRef.current
    if (!comp) return 32
    return comp.sections?.reduce((s,sec) => s + (sec.bars||2)*4, 0) || 32
  }, [])

  const scheduler = useCallback(() => {
    const comp = compRef.current
    if (!comp) return
    const bpm   = comp.bpm || 120
    const spb   = 60 / bpm
    const sp16  = spb / 4
    const instr = comp.instrument || 'piano'
    const drum  = comp.drum_pattern || {}
    const allNotes = getAllNotes()
    const total = getTotalBeats()

    while (nextRef.current < Tone.now() + 0.1) {
      const step    = stepRef.current
      const beat    = beatRef.current
      const t       = nextRef.current
      const beatPos = beat + (step % 4) * 0.25

      // Drums
      if (drum && typeof drum === 'object') {
        DRUM_KEYS.forEach(dk => {
          if (Array.isArray(drum[dk]) && drum[dk][step % 16]) triggerDrum(dk, t)
        })
      }

      // Melody notes
      if (_samplers[instr]) {
        allNotes.forEach(n => {
          if (Math.abs(n.start - beatPos) < 0.13) {
            const dur = Math.max(0.1, n.len * spb - 0.05)
            _samplers[instr].triggerAttackRelease(midiToNote(n.midi), dur, t)
          }
        })
      }

      setStep(step)
      setPlayhead(beatPos)

      stepRef.current = (step + 1) % 16
      if (step === 15) {
        const next = beat + 4
        beatRef.current = next >= total ? 0 : next   // always loop
      }
      nextRef.current += sp16
    }
  }, [getAllNotes, getTotalBeats])

  const play = useCallback(async () => {
    const comp = compRef.current
    if (!comp) return
    try {
      await Tone.start()
      await Tone.getContext().resume()
      await getSampler(comp.instrument || 'piano')
      getDrums()
      await new Promise(r => setTimeout(r, 80))
      nextRef.current = Tone.now() + 0.1
      stepRef.current = 0
      beatRef.current = 0
      setPlaying(true)
      timerRef.current = setInterval(scheduler, 25)
    } catch(e) { console.error('Play error:', e) }
  }, [scheduler])

  const stop = useCallback(() => {
    clearInterval(timerRef.current)
    setPlaying(false)
    setPlayhead(0)
    setStep(-1)
    stepRef.current = 0
    beatRef.current = 0
  }, [])

  useEffect(() => () => clearInterval(timerRef.current), [])

  const totalBeats = composition ? (composition.sections?.reduce((s,sec)=>s+(sec.bars||2)*4,0)||32) : 32

  return { playing, play, stop, playhead, currentStep, totalBeats }
}

// ─────────────────────────────────────────────────────────────────────────────
//  PROMPT SUGGESTIONS
// ─────────────────────────────────────────────────────────────────────────────
const STORY_PROMPTS = [
  "Driving alone at 3am through empty city streets, streetlights blurring past",
  "The moment you realize you're falling in love but you're terrified",
  "A soldier coming home after years away — joy and grief at once",
  "Exploring a forest just before dawn — everything still, expectant",
  "The last day of summer before everything changes",
  "Dancing alone in your kitchen at midnight, completely free",
  "Standing at the edge of something huge — a decision you can't undo",
  "Grief that's finally softened into something like peace",
  "A child discovering the ocean for the first time",
  "Nostalgia for a place you've never actually been",
]

// ─────────────────────────────────────────────────────────────────────────────
//  MAIN STUDIO
// ─────────────────────────────────────────────────────────────────────────────
export default function MusicStudio() {
  const isMobile = useIsMobile()
  const [prompt,      setPrompt]      = useState('')
  const [composing,   setComposing]   = useState(false)
  const [composition, setComposition] = useState(null)
  const [error,       setError]       = useState(null)
  const [streamText,  setStreamText]  = useState('')
  const [history,     setHistory]     = useState([])    // past compositions
  const [tab,         setTab]         = useState('story') // 'story' | 'score' | 'vocal'
  const { playing, play, stop, playhead, totalBeats } = usePlayback(composition)

  const color = composition
    ? (INSTRUMENT_DEFS[composition.instrument]?.color || '#7c6fff')
    : '#7c6fff'

  const compose = async (overridePrompt) => {
    const p = (overridePrompt || prompt).trim()
    if (!p || composing) return
    setComposing(true)
    setError(null)
    setStreamText('Aria is listening to your story...')
    stop()

    try {
      // Show streaming status messages
      const steps = [
        'Translating emotion to key and tempo...',
        'Building chord progressions...',
        'Shaping the melody...',
        'Writing the drum pattern...',
        'Arranging sections...',
        'Composing vocal guide...',
        'Finalizing the score...',
      ]
      let si = 0
      const statusTimer = setInterval(() => {
        si = (si + 1) % steps.length
        setStreamText(steps[si])
      }, 1800)

      const r = await fetch(`${API}/api/compose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: p })
      })
      clearInterval(statusTimer)

      const data = await r.json()
      if (data.ok && data.composition) {
        setComposition(data.composition)
        setHistory(h => [{ prompt: p, composition: data.composition, ts: Date.now() }, ...h.slice(0,9)])
        setPrompt('')
        setTab('story')
        // Auto-preload the instrument
        getSampler(data.composition.instrument || 'piano')
      } else {
        setError(data.error || 'Composition failed')
        if (data.raw) console.warn('Raw response:', data.raw)
      }
    } catch(e) {
      setError(`Network error: ${e.message}`)
    }
    setStreamText('')
    setComposing(false)
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={{ display:'flex', flexDirection: isMobile ? 'column' : 'row',
      height:'100%', background:'#07070e', fontFamily:'system-ui,sans-serif',
      overflow:'hidden', color:'#fff' }}>

      {/* ── LEFT: Input + History ── */}
      <div style={{ width: isMobile ? '100%' : 340, flexShrink:0, display:'flex',
        flexDirection:'column', borderRight: isMobile ? 'none' : '1px solid rgba(255,255,255,0.07)',
        borderBottom: isMobile ? '1px solid rgba(255,255,255,0.07)' : 'none',
        maxHeight: isMobile ? '42%' : 'none', overflowY: isMobile ? 'auto' : 'visible' }}>

        {/* Header */}
        <div style={{ padding:'12px 14px 8px', borderBottom:'1px solid rgba(255,255,255,0.06)',
          background:'rgba(0,0,0,0.3)', flexShrink:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:2 }}>
            <span style={{ fontSize:18 }}>🎼</span>
            <span style={{ fontWeight:800, fontSize:14, color:'#c4b5fd', letterSpacing:1 }}>OSONE Studio</span>
          </div>
          <div style={{ fontSize:10, color:'rgba(255,255,255,0.3)', lineHeight:1.5 }}>
            Tell a story. Aria composes the music.
          </div>
        </div>

        {/* Prompt input */}
        <div style={{ padding:'12px 14px', borderBottom:'1px solid rgba(255,255,255,0.06)', flexShrink:0 }}>
          <textarea value={prompt} onChange={e=>setPrompt(e.target.value)}
            onKeyDown={e => { if (e.key==='Enter' && e.metaKey) compose() }}
            placeholder="Describe a feeling, a moment, a story..."
            rows={isMobile ? 2 : 4}
            style={{ width:'100%', background:'rgba(255,255,255,0.06)',
              border:`1px solid ${composing ? color : 'rgba(255,255,255,0.12)'}`,
              borderRadius:10, padding:'10px 12px', color:'#fff', fontSize:13,
              outline:'none', resize:'none', fontFamily:'inherit', lineHeight:1.6,
              boxSizing:'border-box',
              transition:'border-color 0.3s',
              boxShadow: composing ? `0 0 12px ${color}44` : 'none' }} />
          <button onClick={() => compose()} disabled={composing || !prompt.trim()}
            style={{ marginTop:8, width:'100%', background: composing
              ? `${color}33` : `linear-gradient(135deg, ${color}, #a78bfa)`,
              border:'none', borderRadius:10, color:'#fff',
              fontSize:13, fontWeight:700, padding:'10px',
              cursor: composing ? 'wait' : 'pointer',
              opacity: (!prompt.trim() && !composing) ? 0.5 : 1,
              transition:'all 0.2s' }}>
            {composing ? '♪ Composing...' : '🎼 Compose'}
          </button>
          {composing && (
            <div style={{ marginTop:6, fontSize:11, color: color,
              textAlign:'center', opacity:0.8, animation:'pulse 1.5s infinite' }}>
              {streamText}
            </div>
          )}
          {error && (
            <div style={{ marginTop:6, fontSize:11, color:'#f87171',
              background:'rgba(239,68,68,0.1)', borderRadius:6, padding:'6px 10px' }}>
              {error}
            </div>
          )}
        </div>

        {/* Story prompts */}
        <div style={{ padding:'8px 14px', borderBottom:'1px solid rgba(255,255,255,0.05)', flexShrink:0 }}>
          <div style={{ fontSize:9, color:'rgba(255,255,255,0.25)', marginBottom:6, letterSpacing:1 }}>
            STORY STARTERS
          </div>
          <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
            {STORY_PROMPTS.slice(0, isMobile ? 3 : 6).map((sp,i) => (
              <button key={i} onClick={() => { setPrompt(sp); }}
                style={{ background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.08)',
                  borderRadius:7, color:'rgba(255,255,255,0.5)', fontSize:10,
                  padding:'6px 10px', cursor:'pointer', textAlign:'left', lineHeight:1.4 }}>
                "{sp.slice(0,55)}{sp.length>55?'...':''}"
              </button>
            ))}
          </div>
        </div>

        {/* History */}
        {history.length > 0 && !isMobile && (
          <div style={{ flex:1, overflowY:'auto', padding:'8px 14px' }}>
            <div style={{ fontSize:9, color:'rgba(255,255,255,0.25)', marginBottom:6, letterSpacing:1 }}>
              HISTORY
            </div>
            {history.map((h,i) => (
              <div key={h.ts} onClick={() => { setComposition(h.composition); setTab('story') }}
                style={{ background: composition===h.composition ? 'rgba(124,111,255,0.15)' : 'rgba(255,255,255,0.03)',
                  border:`1px solid ${composition===h.composition ? '#7c6fff44' : 'rgba(255,255,255,0.06)'}`,
                  borderRadius:8, padding:'8px 10px', marginBottom:5, cursor:'pointer' }}>
                <div style={{ fontSize:10, color: INSTRUMENT_DEFS[h.composition.instrument]?.color || '#7c6fff',
                  fontWeight:700, marginBottom:2 }}>{h.composition.title}</div>
                <div style={{ fontSize:9, color:'rgba(255,255,255,0.35)',
                  overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                  "{h.prompt.slice(0,45)}{h.prompt.length>45?'...':''}"
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── RIGHT: Composition view ── */}
      <div style={{ flex:1, display:'flex', flexDirection:'column', minHeight:0, overflow:'hidden' }}>
        {!composition ? (
          /* Empty state */
          <div style={{ flex:1, display:'flex', flexDirection:'column',
            alignItems:'center', justifyContent:'center', gap:16, padding:30, textAlign:'center' }}>
            <div style={{ fontSize:48, marginBottom:4 }}>🎼</div>
            <div style={{ fontWeight:700, fontSize:18, color:'rgba(255,255,255,0.6)' }}>
              Every piece of music tells a story
            </div>
            <div style={{ fontSize:13, color:'rgba(255,255,255,0.3)', maxWidth:360, lineHeight:1.7 }}>
              Describe a feeling, a moment, or a scene. Aria will translate it into a full
              composition — melody, harmony, rhythm, arrangement — built from first principles
              of music theory. No samples, no training on other people's music. Just pure
              musical thinking.
            </div>
            <div style={{ display:'flex', flexWrap:'wrap', gap:6, justifyContent:'center', maxWidth:400 }}>
              {['Lonely','Triumphant','Mysterious','Driving','Peaceful','Nostalgic'].map(m => (
                <span key={m} style={{ background:'rgba(196,181,253,0.08)',
                  border:'1px solid rgba(196,181,253,0.15)', borderRadius:20,
                  padding:'5px 12px', fontSize:11, color:'rgba(255,255,255,0.5)', cursor:'pointer' }}
                  onClick={() => setPrompt(`Something that feels ${m.toLowerCase()}`)}>
                  {m}
                </span>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ flex:1, display:'flex', flexDirection:'column', minHeight:0 }}>

            {/* Composition header */}
            <div style={{ padding:'12px 16px', background:'rgba(0,0,0,0.4)',
              borderBottom:'1px solid rgba(255,255,255,0.07)', flexShrink:0 }}>
              <div style={{ display:'flex', alignItems:'flex-start', gap:12 }}>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ fontWeight:800, fontSize: isMobile ? 16 : 20,
                    color: color, letterSpacing:0.5, marginBottom:3 }}>
                    {composition.title}
                  </div>
                  <div style={{ fontSize:11, color:'rgba(255,255,255,0.45)', lineHeight:1.5 }}>
                    {composition.story}
                  </div>
                  <div style={{ display:'flex', flexWrap:'wrap', gap:6, marginTop:8 }}>
                    {[
                      composition.key && `${composition.key} ${composition.mode}`,
                      composition.bpm && `${composition.bpm} BPM`,
                      composition.time_signature,
                      INSTRUMENT_DEFS[composition.instrument]?.label,
                    ].filter(Boolean).map((tag,i) => (
                      <span key={i} style={{ background:`${color}22`,
                        border:`1px solid ${color}44`, borderRadius:20,
                        padding:'2px 9px', fontSize:10, color: color }}>
                        {tag}
                      </span>
                    ))}
                    {composition.mood_tags?.map((t,i) => (
                      <span key={i} style={{ background:'rgba(255,255,255,0.06)',
                        borderRadius:20, padding:'2px 9px', fontSize:10,
                        color:'rgba(255,255,255,0.4)' }}>
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
                {/* Play controls */}
                <div style={{ display:'flex', flexDirection:'column', gap:6, flexShrink:0 }}>
                  <button onClick={() => playing ? stop() : play()}
                    style={{ background: playing ? 'rgba(239,68,68,0.2)' : `${color}33`,
                      border:`2px solid ${playing ? '#ef4444' : color}`,
                      borderRadius:50, color: playing ? '#ef4444' : color,
                      fontSize: isMobile ? 20 : 26, width: isMobile ? 44 : 54, height: isMobile ? 44 : 54,
                      cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center',
                      boxShadow: playing ? '0 0 20px rgba(239,68,68,0.3)' : `0 0 20px ${color}44`,
                      transition:'all 0.2s' }}>
                    {playing ? '⏹' : '▶'}
                  </button>
                </div>
              </div>

              {/* Waveform */}
              <div style={{ marginTop:10 }}>
                <Waveform playing={playing} color={color} />
              </div>
            </div>

            {/* Tabs */}
            <div style={{ display:'flex', background:'#0a0a14',
              borderBottom:'1px solid rgba(255,255,255,0.07)', flexShrink:0 }}>
              {[
                { id:'story', label:'📖 Story'    },
                { id:'score', label:'🎵 Score'    },
                { id:'vocal', label:'🎤 Vocal'    },
              ].map(t => (
                <button key={t.id} onClick={()=>setTab(t.id)}
                  style={{ flex:1, background: tab===t.id ? `${color}15` : 'transparent',
                    border:'none', borderBottom:`2px solid ${tab===t.id ? color : 'transparent'}`,
                    color: tab===t.id ? color : 'rgba(255,255,255,0.4)',
                    fontSize: isMobile ? 11 : 13, padding: isMobile ? '7px 4px' : '9px 8px',
                    cursor:'pointer', fontWeight: tab===t.id ? 700 : 400 }}>
                  {isMobile ? t.label.split(' ')[0] : t.label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div style={{ flex:1, overflowY:'auto', padding: isMobile ? '10px' : '14px 16px' }}>
              {tab === 'story' && (
                <div>
                  <div style={{ background:`${color}0d`, border:`1px solid ${color}22`,
                    borderRadius:10, padding:'12px 14px', marginBottom:14,
                    fontSize:13, color:'rgba(255,255,255,0.7)', lineHeight:1.8, fontStyle:'italic' }}>
                    "{composition.story}"
                  </div>
                  {composition.arrangement_notes && (
                    <div style={{ marginBottom:14, fontSize:12, color:'rgba(255,255,255,0.45)',
                      lineHeight:1.7, padding:'0 2px' }}>
                      {composition.arrangement_notes}
                    </div>
                  )}
                  <div style={{ fontSize:10, color:'rgba(255,255,255,0.3)', marginBottom:10, letterSpacing:1 }}>
                    STRUCTURE
                  </div>
                  {composition.sections?.map((sec,i) => (
                    <SectionCard key={i} section={sec} idx={i} color={color} isMobile={isMobile} />
                  ))}
                </div>
              )}

              {tab === 'score' && (
                <div>
                  <div style={{ fontSize:10, color:'rgba(255,255,255,0.3)', marginBottom:10, letterSpacing:1 }}>
                    FULL SCORE VIEW
                  </div>
                  {(() => {
                    // Flatten all notes with global beat offset
                    const allNotes = []
                    let offset = 0
                    composition.sections?.forEach(sec => {
                      sec.notes?.forEach(n => allNotes.push({...n, start: n.start+offset}))
                      offset += (sec.bars||2)*4
                    })
                    return (
                      <div style={{ marginBottom:16 }}>
                        <MiniRoll notes={allNotes} totalBeats={totalBeats}
                          playhead={playhead} color={color} isMobile={isMobile} />
                      </div>
                    )
                  })()}
                  {composition.sections?.map((sec,i) => (
                    <SectionCard key={i} section={sec} idx={i} color={color} isMobile={isMobile} />
                  ))}
                </div>
              )}

              {tab === 'vocal' && (
                <div>
                  <VocalLine vocal_melody={composition.vocal_melody}
                    lyric_themes={composition.lyric_themes} color={color} />
                  <div style={{ background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.08)',
                    borderRadius:10, padding:'12px 14px', fontSize:12,
                    color:'rgba(255,255,255,0.4)', lineHeight:1.9 }}>
                    <p>The vocal guide shows suggested note pitches and syllable placements that fit
                    the melody and chord structure. This is a starting point — the story you told
                    should drive what words you choose.</p>
                    <p style={{marginTop:8}}>Lyric themes are extracted from the emotional core of your prompt.
                    Build from them, contradict them, or use them as rhythm anchors.</p>
                    <p style={{marginTop:8, color: color, fontStyle:'italic'}}>
                      "Music is the shorthand of emotion." — Tolstoy
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
