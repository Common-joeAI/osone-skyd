import { useState, useEffect, useRef, useCallback } from 'react'
import * as Tone from 'tone'

// ─────────────────────────────────────────────────────────────────────────────
//  CONFIG
// ─────────────────────────────────────────────────────────────────────────────
const _isLocal = window.location.port !== ''
const API = _isLocal
  ? `http://${window.location.hostname}:8000`
  : `${window.location.protocol}//${window.location.host}`

const NOTE_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
const midiToNote = m => NOTE_NAMES[m % 12] + (Math.floor(m / 12) - 1)

// ─────────────────────────────────────────────────────────────────────────────
//  INSTRUMENT SAMPLER CACHE
// ─────────────────────────────────────────────────────────────────────────────
const INSTRUMENT_DEFS = {
  piano:    { label:'Grand Piano',     emoji:'🎹', color:'#7c6fff', baseUrl:'https://tonejs.github.io/audio/salamander/', urls:{A0:'A0.mp3',C1:'C1.mp3','D#1':'Ds1.mp3','F#1':'Fs1.mp3',A1:'A1.mp3',C2:'C2.mp3','D#2':'Ds2.mp3','F#2':'Fs2.mp3',A2:'A2.mp3',C3:'C3.mp3','D#3':'Ds3.mp3','F#3':'Fs3.mp3',A3:'A3.mp3',C4:'C4.mp3','D#4':'Ds4.mp3','F#4':'Fs4.mp3',A4:'A4.mp3',C5:'C5.mp3','D#5':'Ds5.mp3','F#5':'Fs5.mp3',A5:'A5.mp3',C6:'C6.mp3'} },
  guitar:   { label:'Acoustic Guitar', emoji:'🎸', color:'#f59e0b', baseUrl:'https://tonejs.github.io/audio/guitar-acoustic/', urls:{E2:'E2.mp3',A2:'A2.mp3',D3:'D3.mp3',G3:'G3.mp3',B3:'B3.mp3',E4:'E4.mp3',A3:'A3.mp3',D4:'D4.mp3',G4:'G4.mp3',B4:'B4.mp3',E5:'E5.mp3'} },
  'e-guitar':{ label:'Electric Guitar',emoji:'⚡', color:'#ef4444', baseUrl:'https://tonejs.github.io/audio/guitar-electric/', urls:{'D#3':'Ds3.mp3','F#3':'Fs3.mp3',A3:'A3.mp3',C4:'C4.mp3','D#4':'Ds4.mp3','F#4':'Fs4.mp3',A4:'A4.mp3',C5:'C5.mp3','D#5':'Ds5.mp3'} },
  bass:     { label:'Electric Bass',   emoji:'🎵', color:'#10b981', baseUrl:'https://tonejs.github.io/audio/bass-electric/', urls:{'A#1':'As1.mp3','A#2':'As2.mp3',C2:'C2.mp3',C3:'C3.mp3',E1:'E1.mp3',E2:'E2.mp3',E3:'E3.mp3',G1:'G1.mp3',G2:'G2.mp3',G3:'G3.mp3'} },
  violin:   { label:'Violin',          emoji:'🎻', color:'#ec4899', baseUrl:'https://tonejs.github.io/audio/violin/', urls:{A3:'A3.mp3',A4:'A4.mp3',A5:'A5.mp3',C4:'C4.mp3',C5:'C5.mp3',C6:'C6.mp3',E4:'E4.mp3',E5:'E5.mp3',G3:'G3.mp3',G4:'G4.mp3',G5:'G5.mp3'} },
  trumpet:  { label:'Trumpet',         emoji:'🎺', color:'#f97316', baseUrl:'https://tonejs.github.io/audio/trumpet/', urls:{C4:'C4.mp3',D4:'D4.mp3','D#4':'Ds4.mp3',F4:'F4.mp3',G4:'G4.mp3',A4:'A4.mp3',C5:'C5.mp3',D5:'D5.mp3',F5:'F5.mp3',G5:'G5.mp3'} },
  flute:    { label:'Flute',           emoji:'🪈', color:'#06b6d4', baseUrl:'https://tonejs.github.io/audio/flute/', urls:{A4:'A4.mp3',C5:'C5.mp3',E5:'E5.mp3',A5:'A5.mp3',C6:'C6.mp3',E6:'E6.mp3'} },
  cello:    { label:'Cello',           emoji:'🎻', color:'#8b5cf6', baseUrl:'https://tonejs.github.io/audio/cello/', urls:{E2:'E2.mp3',A2:'A2.mp3',D3:'D3.mp3',G3:'G3.mp3',C3:'C3.mp3',A3:'A3.mp3',D4:'D4.mp3'} },
  marimba:  { label:'Marimba',         emoji:'🪘', color:'#84cc16', baseUrl:'https://tonejs.github.io/audio/marimba/', urls:{A1:'A1.mp3',C2:'C2.mp3',E2:'E2.mp3',A2:'A2.mp3',C3:'C3.mp3',E3:'E3.mp3',A3:'A3.mp3',C4:'C4.mp3',E4:'E4.mp3',A4:'A4.mp3'} },
  organ:    { label:'Organ',           emoji:'🎹', color:'#a78bfa', baseUrl:'https://tonejs.github.io/audio/organ/', urls:{C2:'C2.mp3',C3:'C3.mp3',C4:'C4.mp3',C5:'C5.mp3','F#2':'Fs2.mp3','F#3':'Fs3.mp3','F#4':'Fs4.mp3',A2:'A2.mp3',A3:'A3.mp3',A4:'A4.mp3'} },
}

const _samplers = {}
function getSampler(key) {
  return new Promise(resolve => {
    if (_samplers[key]) { resolve(_samplers[key]); return }
    const def = INSTRUMENT_DEFS[key]; if (!def) { resolve(null); return }
    const s = new Tone.Sampler({ urls:def.urls, baseUrl:def.baseUrl,
      onload:() => { _samplers[key]=s; resolve(s) } }).toDestination()
  })
}

// Drum synths
let _drums = null
function getDrums() {
  if (_drums) return _drums
  _drums = {
    kick:    new Tone.MembraneSynth({pitchDecay:0.05,octaves:5,envelope:{attack:0.001,decay:0.4,sustain:0,release:0.1}}).toDestination(),
    snare:   new Tone.NoiseSynth({noise:{type:'white'},envelope:{attack:0.001,decay:0.2,sustain:0,release:0.05}}).toDestination(),
    hihat:   new Tone.MetalSynth({frequency:400,envelope:{attack:0.001,decay:0.05,release:0.01},harmonicity:5.1,modulationIndex:32,resonance:4000,octaves:1.5}).toDestination(),
    openhat: new Tone.MetalSynth({frequency:400,envelope:{attack:0.001,decay:0.3,release:0.1},harmonicity:5.1,modulationIndex:32,resonance:4000,octaves:1.5}).toDestination(),
    clap:    new Tone.NoiseSynth({noise:{type:'pink'},envelope:{attack:0.001,decay:0.15,sustain:0,release:0.05}}).toDestination(),
    tom:     new Tone.MembraneSynth({pitchDecay:0.08,octaves:4,envelope:{attack:0.001,decay:0.3,sustain:0,release:0.1}}).toDestination(),
    rim:     new Tone.MetalSynth({frequency:800,envelope:{attack:0.001,decay:0.05,release:0.01},harmonicity:8,modulationIndex:16,resonance:5000,octaves:0.5}).toDestination(),
  }
  _drums.kick.volume.value=-2; _drums.snare.volume.value=-5; _drums.hihat.volume.value=-14
  _drums.openhat.volume.value=-15; _drums.clap.volume.value=-8; _drums.tom.volume.value=-7; _drums.rim.volume.value=-12
  return _drums
}
const DRUM_KEYS = ['kick','snare','hihat','openhat','clap','tom','rim']
function triggerDrum(type, t) {
  const d=getDrums()
  switch(type){
    case 'kick':    d.kick.triggerAttackRelease('C1','8n',t); break
    case 'snare':   d.snare.triggerAttackRelease('8n',t); break
    case 'hihat':   d.hihat.triggerAttackRelease('32n',t); break
    case 'openhat': d.openhat.triggerAttackRelease('8n',t); break
    case 'clap':    d.clap.triggerAttackRelease('16n',t); break
    case 'tom':     d.tom.triggerAttackRelease('A1','8n',t); break
    case 'rim':     d.rim.triggerAttackRelease('32n',t); break
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  MOBILE
// ─────────────────────────────────────────────────────────────────────────────
function useIsMobile() {
  const [m,setM]=useState(()=>/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)||window.innerWidth<=768)
  useEffect(()=>{const c=()=>setM(/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)||window.innerWidth<=768);window.addEventListener('resize',c);return()=>window.removeEventListener('resize',c)},[])
  return m
}

// ─────────────────────────────────────────────────────────────────────────────
//  WAVEFORM
// ─────────────────────────────────────────────────────────────────────────────
function Waveform({ playing, color }) {
  const canvasRef=useRef(null), animRef=useRef(null), analyserRef=useRef(null)
  useEffect(()=>{
    if(!playing){cancelAnimationFrame(animRef.current);const cv=canvasRef.current;if(cv)cv.getContext('2d').clearRect(0,0,cv.width,cv.height);return}
    const toneCtx=Tone.getContext().rawContext
    if(!analyserRef.current){analyserRef.current=toneCtx.createAnalyser();analyserRef.current.fftSize=512;Tone.getDestination().connect(analyserRef.current)}
    const buf=new Uint8Array(analyserRef.current.frequencyBinCount)
    const draw=()=>{
      animRef.current=requestAnimationFrame(draw)
      const cv=canvasRef.current;if(!cv)return
      const ctx=cv.getContext('2d')
      analyserRef.current.getByteTimeDomainData(buf)
      ctx.clearRect(0,0,cv.width,cv.height)
      ctx.strokeStyle=color;ctx.lineWidth=2;ctx.shadowColor=color;ctx.shadowBlur=10
      ctx.beginPath()
      const sw=cv.width/buf.length;let x=0
      for(let i=0;i<buf.length;i++){const v=buf[i]/128-1,y=v*cv.height/2+cv.height/2;i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);x+=sw}
      ctx.stroke()
    }
    draw()
    return()=>cancelAnimationFrame(animRef.current)
  },[playing,color])
  return <canvas ref={canvasRef} width={600} height={56} style={{width:'100%',height:56,display:'block'}}/>
}

// ─────────────────────────────────────────────────────────────────────────────
//  LYRIC KARAOKE VIEW  — shows current syllable highlighted
// ─────────────────────────────────────────────────────────────────────────────
function LyricDisplay({ sections, globalBeat, bpm, isMobile }) {
  const spb = 60 / (bpm || 120)

  // Build flat list of {syllable, globalStart}
  const syllables = []
  let offset = 0
  sections?.forEach(sec => {
    sec.notes?.forEach(n => {
      if (n.syllable && n.syllable.trim()) {
        syllables.push({ syllable: n.syllable, start: offset + n.start, section: sec.name })
      }
    })
    offset += (sec.bars || 4) * 4
  })

  // Find current syllable
  const currentIdx = syllables.reduce((best, s, i) =>
    s.start <= globalBeat ? i : best, -1)

  return (
    <div style={{ padding: isMobile ? '10px 12px' : '14px 20px',
      background:'rgba(0,0,0,0.3)', borderRadius:12, minHeight:80,
      display:'flex', flexWrap:'wrap', gap:'6px 8px', alignContent:'flex-start' }}>
      {syllables.length === 0 ? (
        <span style={{ color:'rgba(255,255,255,0.2)', fontSize:13 }}>
          Lyrics will appear here during playback...
        </span>
      ) : syllables.map((s, i) => (
        <span key={i} style={{
          fontSize: isMobile ? 15 : 18,
          fontWeight: i === currentIdx ? 800 : 400,
          color: i === currentIdx ? '#fff' : i < currentIdx ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.55)',
          textShadow: i === currentIdx ? '0 0 20px rgba(255,255,255,0.8)' : 'none',
          transition: 'all 0.1s',
          transform: i === currentIdx ? 'scale(1.05)' : 'scale(1)',
          display:'inline-block',
          borderBottom: i === currentIdx ? '2px solid #fff' : '2px solid transparent',
        }}>
          {s.syllable}
        </span>
      ))}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  SECTION STRIP  — compact lyric + chord view
// ─────────────────────────────────────────────────────────────────────────────
function SectionStrip({ section, color, isActive, isMobile }) {
  return (
    <div style={{ background: isActive ? `${color}18` : 'rgba(255,255,255,0.03)',
      border:`1px solid ${isActive ? color+'66' : 'rgba(255,255,255,0.08)'}`,
      borderRadius:10, padding:'10px 14px', marginBottom:6,
      transition:'all 0.2s' }}>
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:section.lyrics ? 6 : 0 }}>
        <span style={{ fontSize:10, fontWeight:700, color: isActive ? color : 'rgba(255,255,255,0.4)',
          letterSpacing:1, textTransform:'uppercase', minWidth:70 }}>{section.name}</span>
        <div style={{ display:'flex', gap:4, flexWrap:'wrap' }}>
          {section.chord_progression?.map((c,i) => (
            <span key={i} style={{ background:`${color}20`,border:`1px solid ${color}44`,
              borderRadius:5,padding:'1px 7px',fontSize:10,color:color,fontWeight:600 }}>{c}</span>
          ))}
        </div>
        <span style={{ marginLeft:'auto', fontSize:9, color:'rgba(255,255,255,0.25)' }}>
          {section.bars}b · {section.dynamic}
        </span>
      </div>
      {section.lyrics && (
        <div style={{ fontSize: isMobile ? 12 : 13, color:'rgba(255,255,255,0.6)',
          lineHeight:1.6, fontStyle:'italic', whiteSpace:'pre-wrap' }}>
          {section.lyrics}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  PLAYBACK ENGINE
// ─────────────────────────────────────────────────────────────────────────────
function usePlayback(song) {
  const [playing,  setPlaying]  = useState(false)
  const [beat,     setBeat]     = useState(0)
  const [step,     setStep]     = useState(-1)
  const stepRef=useRef(0), beatRef=useRef(0), nextRef=useRef(0), timerRef=useRef(null)
  const songRef=useRef(song)
  useEffect(()=>{ songRef.current=song },[song])

  const getAllNotes = useCallback(()=>{
    const s=songRef.current; if(!s) return []
    const all=[]; let off=0
    s.sections?.forEach(sec=>{
      sec.notes?.forEach(n=>all.push({...n,start:n.start+off}))
      off+=(sec.bars||4)*4
    })
    return all
  },[])

  const getTotalBeats = useCallback(()=>{
    const s=songRef.current; if(!s) return 32
    return s.sections?.reduce((a,sec)=>a+(sec.bars||4)*4,0)||32
  },[])

  const scheduler = useCallback(()=>{
    const s=songRef.current; if(!s) return
    const bpm=s.bpm||120, spb=60/bpm, sp16=spb/4
    const instr=s.lead_instrument||'piano'
    const drum=s.drum_pattern||{}
    const allNotes=getAllNotes()
    const total=getTotalBeats()

    while(nextRef.current < Tone.now()+0.1){
      const st=stepRef.current, bt=beatRef.current, t=nextRef.current
      const beatPos=bt+(st%4)*0.25

      if(drum && typeof drum === 'object') {
        DRUM_KEYS.forEach(dk=>{ if(Array.isArray(drum[dk]) && drum[dk][st%16]) triggerDrum(dk,t) })
      }

      if(_samplers[instr]){
        allNotes.forEach(n=>{
          if(Math.abs(n.start-beatPos)<0.13){
            const dur=Math.max(0.1,n.len*spb-0.05)
            _samplers[instr].triggerAttackRelease(midiToNote(n.midi),dur,t,n.vel/127)
          }
        })
      }

      setStep(st); setBeat(beatPos)
      stepRef.current=(st+1)%16
      if(st===15){
        const nb=bt+4; beatRef.current=nb>=total?0:nb
      }
      nextRef.current+=sp16
    }
  },[getAllNotes,getTotalBeats])

  const play=useCallback(async()=>{
    const s=songRef.current; if(!s) return
    try {
      // Resume AudioContext — must happen in user gesture handler
      await Tone.start()
      await Tone.getContext().resume()
      // Load sampler — wait for it
      const instr = s.lead_instrument || 'piano'
      await getSampler(instr)
      getDrums()
      // Small buffer before scheduling
      await new Promise(r => setTimeout(r, 80))
      nextRef.current = Tone.now() + 0.1
      stepRef.current = 0
      beatRef.current = 0
      setPlaying(true)
      timerRef.current = setInterval(scheduler, 25)
    } catch(e) {
      console.error('Play error:', e)
    }
  },[scheduler])

  const stop=useCallback(()=>{
    clearInterval(timerRef.current)
    setPlaying(false); setBeat(0); setStep(-1)
    stepRef.current=0; beatRef.current=0
  },[])

  useEffect(()=>()=>clearInterval(timerRef.current),[])
  const totalBeats=song?(song.sections?.reduce((a,s)=>a+(s.bars||4)*4,0)||32):32
  return{playing,play,stop,beat,step,totalBeats}
}

// ─────────────────────────────────────────────────────────────────────────────
//  ADVANCED MODE FORM
// ─────────────────────────────────────────────────────────────────────────────
const GENRE_PRESETS = [
  'Pop','Indie Pop','R&B','Soul','Blues','Blues Rock','Rock','Folk',
  'Country','Hip-Hop','Jazz','Bossa Nova','Cinematic','Orchestral',
  'Electronic','Ambient','Metal','Punk','Reggae','Latin'
]
const EMOTION_PRESETS = [
  'Longing','Heartbreak','Joy','Euphoria','Melancholy','Nostalgia',
  'Anger','Determination','Peace','Fear','Hope','Love','Grief','Wonder'
]
const TEMPO_PRESETS = [
  {label:'Very Slow (40-55)',v:'very slow, around 50 BPM'},
  {label:'Slow (56-75)',    v:'slow, around 65 BPM'},
  {label:'Medium (76-110)', v:'medium, around 95 BPM'},
  {label:'Upbeat (111-140)',v:'upbeat, around 125 BPM'},
  {label:'Fast (141-180)',  v:'fast, around 160 BPM'},
]

function AdvancedForm({ style, setStyle, isMobile }) {
  const Field = ({ label, desc, children }) => (
    <div style={{ marginBottom:16 }}>
      <div style={{ fontSize:12, fontWeight:700, color:'rgba(255,255,255,0.7)', marginBottom:3 }}>{label}</div>
      {desc && <div style={{ fontSize:10, color:'rgba(255,255,255,0.3)', marginBottom:6, lineHeight:1.5 }}>{desc}</div>}
      {children}
    </div>
  )

  const inputStyle = {
    width:'100%', background:'rgba(255,255,255,0.07)', border:'1px solid rgba(255,255,255,0.12)',
    borderRadius:8, color:'#fff', padding:'8px 12px', fontSize:12,
    outline:'none', fontFamily:'inherit', boxSizing:'border-box'
  }

  const ChipRow = ({ options, field }) => (
    <div style={{ display:'flex', flexWrap:'wrap', gap:5, marginTop:5 }}>
      {options.map(o => {
        const val = typeof o === 'string' ? o : o.v
        const lbl = typeof o === 'string' ? o : o.label
        const active = style[field] === val
        return (
          <button key={val} onClick={() => setStyle(s => ({...s, [field]: active ? '' : val}))}
            style={{ background: active ? 'rgba(124,111,255,0.3)' : 'rgba(255,255,255,0.05)',
              border:`1px solid ${active ? '#7c6fff' : 'rgba(255,255,255,0.1)'}`,
              borderRadius:20, color: active ? '#7c6fff' : 'rgba(255,255,255,0.5)',
              fontSize:10, padding:'4px 10px', cursor:'pointer' }}>
            {lbl}
          </button>
        )
      })}
    </div>
  )

  const INSTR_LIST = Object.entries(INSTRUMENT_DEFS)

  return (
    <div style={{ padding:'12px 14px' }}>
      <Field label="🎸 Instruments" desc="What instruments should play? You can pick multiple or write your own.">
        <div style={{ display:'flex', flexWrap:'wrap', gap:5, marginBottom:5 }}>
          {INSTR_LIST.map(([k,d]) => {
            const active = style.instruments?.includes(d.label)
            return (
              <button key={k} onClick={() => setStyle(s => {
                const cur = s.instruments || ''
                const has = cur.includes(d.label)
                return {...s, instruments: has
                  ? cur.replace(d.label,'').replace(/,\s*,/,',').replace(/^,|,$/,'').trim()
                  : cur ? cur+', '+d.label : d.label }
              })}
                style={{ background: active ? `${d.color}30` : 'rgba(255,255,255,0.05)',
                  border:`1px solid ${active ? d.color : 'rgba(255,255,255,0.1)'}`,
                  borderRadius:8, color: active ? d.color : 'rgba(255,255,255,0.45)',
                  fontSize:11, padding:'5px 10px', cursor:'pointer' }}>
                {d.emoji} {d.label}
              </button>
            )
          })}
        </div>
        <input value={style.instruments||''} onChange={e=>setStyle(s=>({...s,instruments:e.target.value}))}
          placeholder="or type: piano, strings, bass drum..." style={inputStyle} />
      </Field>

      <Field label="🎵 Style / Genre" desc="Genre, vibe, artist references are all fair game.">
        <input value={style.genre||''} onChange={e=>setStyle(s=>({...s,genre:e.target.value}))}
          placeholder="e.g. 'dark indie folk', 'early 2000s R&B', 'like Radiohead meets Miles Davis'" style={inputStyle} />
        <ChipRow options={GENRE_PRESETS} field="genre" />
      </Field>

      <Field label="🌆 Scene" desc="Where does this song happen? What does the listener see?">
        <textarea value={style.scene||''} onChange={e=>setStyle(s=>({...s,scene:e.target.value}))}
          placeholder="e.g. 'empty bar at 2am, rain on the window, last call'" rows={2}
          style={{...inputStyle, resize:'none', lineHeight:1.5}} />
      </Field>

      <Field label="💜 Emotion" desc="The core feeling this song must convey.">
        <input value={style.emotion||''} onChange={e=>setStyle(s=>({...s,emotion:e.target.value}))}
          placeholder="e.g. 'the specific grief of missing someone who is still alive'" style={inputStyle} />
        <ChipRow options={EMOTION_PRESETS} field="emotion" />
      </Field>

      <Field label="⏱ Tempo">
        <ChipRow options={TEMPO_PRESETS} field="tempo" />
        {style.tempo && !TEMPO_PRESETS.find(t=>t.v===style.tempo) && (
          <input value={style.tempo||''} onChange={e=>setStyle(s=>({...s,tempo:e.target.value}))}
            placeholder="custom tempo description" style={{...inputStyle, marginTop:6}} />
        )}
      </Field>

      <Field label="📖 Backstory" desc="The story behind this song. Why was it written? What happened? This shapes the entire composition.">
        <textarea value={style.backstory||''} onChange={e=>setStyle(s=>({...s,backstory:e.target.value}))}
          placeholder="e.g. 'Written the night after she left. Not angry, just... empty. Trying to understand how something so real could just stop.'" rows={3}
          style={{...inputStyle, resize:'none', lineHeight:1.6}} />
      </Field>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  PLAY BUTTON
// ─────────────────────────────────────────────────────────────────────────────
function PlayButton({ playing, loading, color, isMobile, onPlay, onStop }) {
  const size  = isMobile ? 50 : 60
  const fsize = isMobile ? 22 : 28
  return (
    <button
      onClick={() => playing ? onStop() : onPlay()}
      disabled={loading}
      style={{ width:size, height:size, borderRadius:'50%',
        background: playing ? 'rgba(239,68,68,0.2)' : loading ? 'rgba(255,255,255,0.08)' : `${color}33`,
        border:`2.5px solid ${playing ? '#ef4444' : loading ? 'rgba(255,255,255,0.2)' : color}`,
        color: playing ? '#ef4444' : loading ? 'rgba(255,255,255,0.4)' : color,
        fontSize:fsize, cursor: loading ? 'wait' : 'pointer',
        flexShrink:0, display:'flex', alignItems:'center', justifyContent:'center',
        boxShadow: playing ? '0 0 24px rgba(239,68,68,0.35)' : loading ? 'none' : `0 0 24px ${color}55`,
        transition:'all 0.2s', animation: loading ? 'pulse 1s infinite' : 'none' }}>
      {loading ? '⏳' : playing ? '⏹' : '▶'}
    </button>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  MAIN SKY-MUSIC
// ─────────────────────────────────────────────────────────────────────────────
export default function SkyMusic() {
  const isMobile = useIsMobile()
  const [mode,      setMode]      = useState('simple')   // 'simple' | 'advanced'
  const [lyrics,    setLyrics]    = useState('')
  const [style,     setStyle]     = useState({})
  const [composing, setComposing] = useState(false)
  const [song,      setSong]      = useState(null)
  const [error,     setError]     = useState(null)
  const [statusMsg, setStatusMsg] = useState('')
  const [viewTab,   setViewTab]   = useState('song')     // 'song' | 'score' | 'studio'
  const [history,   setHistory]   = useState([])

  const { playing, play, stop, beat, totalBeats } = usePlayback(song)
  const [loadingAudio, setLoadingAudio] = useState(false)

  // ── Real audio render via Sky Music engine ──────────────────────────────
  const renderReal = useCallback(async () => {
    if (!song || rendering) return
    setRendering(true)
    setRenderResult(null)
    // Build prompt from song metadata
    const prompt = [
      song.mood_tags?.[0] || 'mysterious',
      song.genre || 'pop',
      'in', song.key || 'C', song.scale || 'minor',
      song.bpm ? `at ${song.bpm} BPM` : '',
      song.title ? `— ${song.title}` : ''
    ].filter(Boolean).join(' ')
    try {
      const r = await fetch(`${API}/api/music/compose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ prompt })
      })
      const d = await r.json()
      if (d.ok && d.audio_url) {
        setRenderResult(d)
        if (realAudioRef.current) {
          realAudioRef.current.src = `${API}${d.audio_url}`
          realAudioRef.current.play()
          setRealPlaying(true)
        }
      } else {
        console.error('render failed', d)
      }
    } catch(e) { console.error(e) }
    setRendering(false)
  }, [song, rendering, token])

  const toggleRealPlay = () => {
    if (!realAudioRef.current) return
    if (realAudioRef.current.paused) { realAudioRef.current.play(); setRealPlaying(true) }
    else { realAudioRef.current.pause(); setRealPlaying(false) }
  }

  const handlePlay = useCallback(async () => {
    if (loadingAudio) return
    setLoadingAudio(true)
    await play()
    setLoadingAudio(false)
  }, [play, loadingAudio])
  const color = INSTRUMENT_DEFS[song?.lead_instrument]?.color || '#7c6fff'

  // Which section is currently playing
  const activeSection = (() => {
    if (!song || !playing) return -1
    let off = 0
    for (let i = 0; i < (song.sections?.length||0); i++) {
      const bars = song.sections[i].bars || 4
      if (beat < off + bars*4) return i
      off += bars*4
    }
    return -1
  })()

  const compose = async () => {
    if (!lyrics.trim() || composing) return
    setComposing(true); setError(null); stop()
    const msgs = [
      'Reading your lyrics...',
      'Finding the key and tempo...',
      'Mapping syllables to melody...',
      'Building chord progressions...',
      'Shaping the dynamic arc...',
      'Writing the drum pattern...',
      'Arranging the sections...',
      'Polishing the composition...',
    ]
    let mi=0
    setStatusMsg(msgs[0])
    const t=setInterval(()=>{ mi=(mi+1)%msgs.length; setStatusMsg(msgs[mi]) },1800)

    try {
      const r = await fetch(`${API}/api/skymusic`,{
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({ lyrics, style: mode==='advanced'?style:{} })
      })
      clearInterval(t)
      const data = await r.json()
      if (data.ok && data.song) {
        setSong(data.song)
        setHistory(h=>[{lyrics:lyrics.slice(0,60),song:data.song,ts:Date.now()},...h.slice(0,7)])
        setViewTab('song')
        getSampler(data.song.lead_instrument||'piano')
      } else {
        setError(data.error||'Composition failed. Try again.')
        if(data.raw) console.warn('Raw:',data.raw)
      }
    } catch(e){ clearInterval(t); setError('Network error: '+e.message) }
    setStatusMsg(''); setComposing(false)
  }

  const lyricCount = lyrics.trim().split(/\s+/).filter(Boolean).length

  // ── RENDER ────────────────────────────────────────────────────────────────
  return (
    <div style={{ display:'flex', flexDirection: isMobile?'column':'row',
      height:'100%', background:'#06060d', fontFamily:'system-ui,sans-serif',
      overflow:'hidden', color:'#fff' }}>

      {/* ── LEFT PANEL: Input ── */}
      <div style={{ width: isMobile?'100%':380, flexShrink:0, display:'flex',
        flexDirection:'column', overflow:'hidden',
        borderRight: isMobile?'none':'1px solid rgba(255,255,255,0.07)',
        borderBottom: isMobile?'1px solid rgba(255,255,255,0.07)':'none',
        maxHeight: isMobile?(mode==='advanced'?'60%':'45%'):'none' }}>

        {/* Header */}
        <div style={{ padding:'10px 14px 8px', background:'rgba(0,0,0,0.5)', flexShrink:0,
          borderBottom:'1px solid rgba(255,255,255,0.07)' }}>
          <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:2 }}>
            <span style={{ fontSize:20 }}>🎤</span>
            <span style={{ fontWeight:900, fontSize:16, background:'linear-gradient(135deg,#7c6fff,#ec4899)',
              WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent' }}>Sky-Music</span>
          </div>
          <div style={{ fontSize:10, color:'rgba(255,255,255,0.35)' }}>
            Your lyrics. Your story. Real music.
          </div>
        </div>

        {/* Mode switcher */}
        <div style={{ display:'flex', background:'#0a0a14', flexShrink:0,
          borderBottom:'1px solid rgba(255,255,255,0.07)' }}>
          {[['simple','⚡ Auto'],['advanced','🎛 Advanced']].map(([m,l])=>(
            <button key={m} onClick={()=>setMode(m)}
              style={{ flex:1, background: mode===m?'rgba(124,111,255,0.15)':'transparent',
                border:'none', borderBottom:`2px solid ${mode===m?'#7c6fff':'transparent'}`,
                color: mode===m?'#7c6fff':'rgba(255,255,255,0.4)',
                fontSize:12, padding:'8px', cursor:'pointer', fontWeight: mode===m?700:400 }}>
              {l}
            </button>
          ))}
        </div>

        {/* Scrollable input area */}
        <div style={{ flex:1, overflowY:'auto' }}>
          {/* Lyrics input — always visible */}
          <div style={{ padding:'12px 14px',
            borderBottom: mode==='advanced'?'1px solid rgba(255,255,255,0.07)':'none' }}>
            <div style={{ fontSize:10, color:'rgba(255,255,255,0.3)', marginBottom:6, letterSpacing:1 }}>
              LYRICS {lyricCount>0&&<span style={{color:'rgba(255,255,255,0.2)'}}>· {lyricCount} words</span>}
            </div>
            <textarea value={lyrics} onChange={e=>setLyrics(e.target.value)}
              placeholder={`Paste your full lyrics here.\n\nTip: Put [Verse], [Chorus], [Bridge] labels and Sky-Music will use them to structure the song.\n\nOr just paste the raw lyrics — it'll figure it out.`}
              rows={isMobile?6:12}
              style={{ width:'100%', background:'rgba(255,255,255,0.06)',
                border:`1px solid ${composing?'#7c6fff':'rgba(255,255,255,0.1)'}`,
                borderRadius:10, padding:'10px 12px', color:'#fff', fontSize:12,
                outline:'none', resize:'none', fontFamily:'inherit', lineHeight:1.7,
                boxSizing:'border-box',
                boxShadow: composing?'0 0 16px rgba(124,111,255,0.3)':'none',
                transition:'all 0.3s' }} />
          </div>

          {/* Advanced form */}
          {mode === 'advanced' && (
            <AdvancedForm style={style} setStyle={setStyle} isMobile={isMobile} />
          )}
        </div>

        {/* Compose button — pinned to bottom */}
        <div style={{ padding:'10px 14px 14px', background:'rgba(0,0,0,0.3)',
          borderTop:'1px solid rgba(255,255,255,0.07)', flexShrink:0 }}>
          {error && (
            <div style={{ marginBottom:8, fontSize:11, color:'#f87171',
              background:'rgba(239,68,68,0.1)', borderRadius:6, padding:'6px 10px' }}>{error}</div>
          )}
          {composing && (
            <div style={{ marginBottom:8, fontSize:11, color:'#7c6fff',
              textAlign:'center', animation:'pulse 1.5s infinite' }}>{statusMsg}</div>
          )}
          <button onClick={compose} disabled={composing||!lyrics.trim()}
            style={{ width:'100%', padding:'12px',
              background: composing
                ? 'rgba(124,111,255,0.2)'
                : 'linear-gradient(135deg,#7c6fff,#ec4899)',
              border:'none', borderRadius:12, color:'#fff',
              fontSize:14, fontWeight:800, cursor: composing?'wait':'pointer',
              opacity: (!lyrics.trim()&&!composing)?0.4:1,
              letterSpacing:0.5, boxShadow: composing?'none':'0 4px 20px rgba(124,111,255,0.4)',
              transition:'all 0.2s' }}>
            {composing ? '🎵 Sky-Music is composing...' : '🎤 Generate Song'}
          </button>
          {!isMobile && history.length>0 && (
            <div style={{ marginTop:10 }}>
              <div style={{ fontSize:9, color:'rgba(255,255,255,0.2)', marginBottom:5, letterSpacing:1 }}>RECENT</div>
              {history.slice(0,4).map((h,i)=>(
                <div key={h.ts} onClick={()=>{setSong(h.song);setViewTab('song')}}
                  style={{ background: song===h.song?'rgba(124,111,255,0.12)':'rgba(255,255,255,0.03)',
                    border:`1px solid ${song===h.song?'rgba(124,111,255,0.4)':'rgba(255,255,255,0.06)'}`,
                    borderRadius:7, padding:'6px 10px', marginBottom:4, cursor:'pointer' }}>
                  <div style={{ fontSize:10, color: INSTRUMENT_DEFS[h.song.lead_instrument]?.color||'#7c6fff',
                    fontWeight:700, marginBottom:1 }}>{h.song.title}</div>
                  <div style={{ fontSize:9, color:'rgba(255,255,255,0.3)',
                    overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                    "{h.lyrics}..."
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── RIGHT PANEL: Song view ── */}
      <div style={{ flex:1, display:'flex', flexDirection:'column', minHeight:0, overflow:'hidden' }}>
        {!song ? (
          <div style={{ flex:1, display:'flex', flexDirection:'column', alignItems:'center',
            justifyContent:'center', gap:14, padding:30, textAlign:'center' }}>
            <div style={{ fontSize:52 }}>🎤</div>
            <div style={{ fontWeight:800, fontSize:20, color:'rgba(255,255,255,0.55)' }}>
              Your lyrics deserve real music
            </div>
            <div style={{ fontSize:13, color:'rgba(255,255,255,0.3)', maxWidth:380, lineHeight:1.8 }}>
              Paste any lyrics — a full song, a verse, even just a few lines.
              Sky-Music reads the words, feels the story, and composes music that fits.
            </div>
            <div style={{ display:'flex', flexWrap:'wrap', gap:6, justifyContent:'center', maxWidth:420, marginTop:4 }}>
              {['Every word matters','Syllables map to melody','Your emotion drives the key',
                'No training on others\' music','Built from theory','Your story, your sound'].map((t,i)=>(
                <span key={i} style={{ background:'rgba(124,111,255,0.08)',
                  border:'1px solid rgba(124,111,255,0.15)', borderRadius:20,
                  padding:'5px 12px', fontSize:11, color:'rgba(255,255,255,0.45)' }}>{t}</span>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ flex:1, display:'flex', flexDirection:'column', minHeight:0 }}>
            {/* Song header */}
            <div style={{ padding:'12px 16px', background:'rgba(0,0,0,0.5)',
              borderBottom:'1px solid rgba(255,255,255,0.07)', flexShrink:0 }}>
              <div style={{ display:'flex', alignItems:'flex-start', gap:12 }}>
                <div style={{ flex:1 }}>
                  <div style={{ fontWeight:900, fontSize: isMobile?17:22, color:color,
                    marginBottom:3, letterSpacing:0.3 }}>{song.title}</div>
                  <div style={{ fontSize:11, color:'rgba(255,255,255,0.45)',
                    lineHeight:1.5, marginBottom:8 }}>{song.story}</div>
                  <div style={{ display:'flex', flexWrap:'wrap', gap:5 }}>
                    {[
                      song.genre,
                      song.key&&`${song.key} ${song.mode}`,
                      song.bpm&&`${song.bpm} BPM`,
                      song.time_signature,
                      INSTRUMENT_DEFS[song.lead_instrument]?.emoji+' '+INSTRUMENT_DEFS[song.lead_instrument]?.label,
                    ].filter(Boolean).map((tag,i)=>(
                      <span key={i} style={{ background:`${color}22`,border:`1px solid ${color}44`,
                        borderRadius:20,padding:'2px 9px',fontSize:10,color:color }}>{tag}</span>
                    ))}
                    {song.mood_tags?.map((t,i)=>(
                      <span key={i} style={{ background:'rgba(255,255,255,0.06)',borderRadius:20,
                        padding:'2px 9px',fontSize:10,color:'rgba(255,255,255,0.4)' }}>{t}</span>
                    ))}
                  </div>
                </div>
                {/* Play button */}
                <PlayButton playing={playing} loading={loadingAudio}
                  color={color} isMobile={isMobile}
                  onPlay={handlePlay} onStop={stop} />
              {/* ── Real Render Button ── */}
              <button
                onClick={renderReal}
                disabled={rendering || !song}
                title="Render real multi-track audio via Sky Music engine"
                style={{
                  background: rendering ? 'rgba(124,111,255,0.2)' : renderResult ? '#16a34a22' : 'rgba(124,111,255,0.15)',
                  border: `1px solid ${renderResult ? '#16a34a66' : 'rgba(124,111,255,0.4)'}`,
                  borderRadius: 10, padding: isMobile ? '5px 10px' : '6px 14px',
                  color: renderResult ? '#4ade80' : '#a78bfa',
                  fontSize: isMobile ? 10 : 11, cursor: rendering||!song ? 'not-allowed' : 'pointer',
                  display:'flex', alignItems:'center', gap:5, marginTop:6, fontWeight:600,
                  opacity: !song ? 0.4 : 1,
                }}>
                {rendering ? <span style={{animation:'spin 1s linear infinite',display:'inline-block'}}>⟳</span>
                  : renderResult ? '✅' : '✦'}
                {rendering ? 'Rendering…' : renderResult ? 'Rendered!' : 'Render Real Audio'}
              </button>
              </div>
              {/* Waveform */}
              <div style={{ marginTop:8 }}>
                <Waveform playing={playing} color={color} />
              </div>
              {/* ── Real Audio Player ── */}
              {renderResult && (
                <div style={{ marginTop:10, background:'rgba(22,163,74,0.08)',
                  border:'1px solid rgba(22,163,74,0.25)', borderRadius:10,
                  padding:'10px 12px' }}>
                  <div style={{ fontSize:10, color:'#4ade80', marginBottom:6, fontWeight:700, letterSpacing:0.5 }}>
                    🎵 SKY MUSIC · REAL RENDER
                  </div>
                  <div style={{ fontSize:11, color:'rgba(255,255,255,0.6)', marginBottom:8 }}>
                    {renderResult.params?.key} {renderResult.params?.scale} ·
                    {renderResult.params?.tempo} BPM · {renderResult.params?.mood}
                  </div>
                  <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                    <button onClick={toggleRealPlay} style={{
                      background:'#16a34a', border:'none', borderRadius:8,
                      width:32, height:32, color:'#fff', fontSize:14,
                      cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center' }}>
                      {realPlaying ? '⏸' : '▶'}
                    </button>
                    <div style={{ flex:1, height:3, background:'rgba(255,255,255,0.1)',
                      borderRadius:2, cursor:'pointer' }}
                      onClick={e => {
                        const r = e.currentTarget.getBoundingClientRect()
                        const pct = (e.clientX-r.left)/r.width
                        if(realAudioRef.current) realAudioRef.current.currentTime = pct * realDuration
                      }}>
                      <div style={{ height:'100%', background:'#4ade80', borderRadius:2,
                        width: realDuration ? `${(realProgress/realDuration)*100}%` : '0%',
                        transition:'width 0.3s' }} />
                    </div>
                    <span style={{ fontSize:9, color:'rgba(255,255,255,0.4)', minWidth:28 }}>
                      {Math.floor(realProgress/60)}:{String(Math.floor(realProgress%60)).padStart(2,'0')}
                    </span>
                  </div>
                  <audio ref={realAudioRef}
                    onTimeUpdate={()=>setRealProgress(realAudioRef.current?.currentTime||0)}
                    onDurationChange={()=>setRealDuration(realAudioRef.current?.duration||0)}
                    onEnded={()=>setRealPlaying(false)} />
                </div>
              )}
            </div>

            {/* View tabs */}
            <div style={{ display:'flex', background:'#09090f',
              borderBottom:'1px solid rgba(255,255,255,0.07)', flexShrink:0 }}>
              {[['song','🎵 Song'],['score','📜 Score'],['studio','🎚 Studio Info']].map(([id,lbl])=>(
                <button key={id} onClick={()=>setViewTab(id)}
                  style={{ flex:1, background: viewTab===id?`${color}15`:'transparent',
                    border:'none', borderBottom:`2px solid ${viewTab===id?color:'transparent'}`,
                    color: viewTab===id?color:'rgba(255,255,255,0.4)',
                    fontSize: isMobile?10:12, padding: isMobile?'7px 4px':'9px',
                    cursor:'pointer', fontWeight: viewTab===id?700:400 }}>
                  {isMobile?lbl.split(' ')[0]:lbl}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div style={{ flex:1, overflowY:'auto' }}>
              {/* SONG TAB — karaoke + sections */}
              {viewTab==='song' && (
                <div style={{ padding: isMobile?'10px':'14px 16px' }}>
                  {/* Karaoke display */}
                  {playing && (
                    <div style={{ marginBottom:14 }}>
                      <div style={{ fontSize:9, color:'rgba(255,255,255,0.3)', marginBottom:6, letterSpacing:1 }}>
                        NOW SINGING
                      </div>
                      <LyricDisplay sections={song.sections} globalBeat={beat}
                        bpm={song.bpm} isMobile={isMobile} />
                    </div>
                  )}
                  {/* Section strips */}
                  <div style={{ fontSize:9, color:'rgba(255,255,255,0.3)', marginBottom:8, letterSpacing:1 }}>
                    STRUCTURE
                  </div>
                  {song.sections?.map((sec,i)=>(
                    <SectionStrip key={i} section={sec} color={color}
                      isActive={i===activeSection} isMobile={isMobile} />
                  ))}
                </div>
              )}

              {/* SCORE TAB — full note breakdown */}
              {viewTab==='score' && (
                <div style={{ padding: isMobile?'10px':'14px 16px' }}>
                  {song.sections?.map((sec,i)=>(
                    <div key={i} style={{ marginBottom:16 }}>
                      <div style={{ fontSize:10, fontWeight:700, color:color,
                        letterSpacing:1, textTransform:'uppercase', marginBottom:6 }}>
                        {sec.name} — {sec.bars} bars
                      </div>
                      <div style={{ display:'flex', gap:4, flexWrap:'wrap', marginBottom:6 }}>
                        {sec.chord_progression?.map((c,j)=>(
                          <span key={j} style={{ background:`${color}22`,border:`1px solid ${color}44`,
                            borderRadius:5,padding:'2px 8px',fontSize:11,color:color,fontWeight:600 }}>{c}</span>
                        ))}
                      </div>
                      {sec.notes?.length>0 && (
                        <div style={{ display:'flex', gap:3, flexWrap:'wrap' }}>
                          {sec.notes.map((n,j)=>(
                            <div key={j} style={{ display:'flex',flexDirection:'column',
                              alignItems:'center', background:`${color}15`,
                              border:`1px solid ${color}33`, borderRadius:6,
                              padding:'4px 7px', minWidth:28 }}>
                              <span style={{ fontSize:9, color:color, fontWeight:700 }}>
                                {NOTE_NAMES[n.midi%12]}{Math.floor(n.midi/12)-1}
                              </span>
                              <span style={{ fontSize:8, color:'rgba(255,255,255,0.5)',marginTop:1 }}>
                                {n.syllable||'—'}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* STUDIO INFO TAB */}
              {viewTab==='studio' && (
                <div style={{ padding: isMobile?'10px':'14px 16px' }}>
                  {song.production_notes && (
                    <div style={{ background:`${color}0d`,border:`1px solid ${color}22`,
                      borderRadius:10,padding:'12px 14px',marginBottom:14,
                      fontSize:13,color:'rgba(255,255,255,0.65)',lineHeight:1.8,fontStyle:'italic' }}>
                      {song.production_notes}
                    </div>
                  )}
                  {/* All instruments */}
                  {song.instruments?.length>0 && (
                    <div style={{ marginBottom:14 }}>
                      <div style={{ fontSize:10, color:'rgba(255,255,255,0.3)', marginBottom:8, letterSpacing:1 }}>
                        FULL ARRANGEMENT
                      </div>
                      <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
                        {song.instruments.map((ins,i)=>(
                          <span key={i} style={{ background:'rgba(255,255,255,0.07)',
                            border:'1px solid rgba(255,255,255,0.12)', borderRadius:8,
                            padding:'5px 12px', fontSize:12, color:'rgba(255,255,255,0.6)' }}>{ins}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {/* Drum pattern visual */}
                  {song.drum_pattern && typeof song.drum_pattern === 'object' && (
                    <div>
                      <div style={{ fontSize:10, color:'rgba(255,255,255,0.3)', marginBottom:8, letterSpacing:1 }}>
                        DRUM PATTERN
                      </div>
                      {DRUM_KEYS.map(dk=>(
                        <div key={dk} style={{ display:'flex', alignItems:'center', gap:4, marginBottom:4 }}>
                          <div style={{ width:52, fontSize:9, color:'rgba(255,255,255,0.4)' }}>
                            {dk.charAt(0).toUpperCase()+dk.slice(1)}
                          </div>
                          {song.drum_pattern[dk]?.map((on,si)=>(
                            <div key={si} style={{ width:14, height:14, borderRadius:3,
                              background: on?color:'rgba(255,255,255,0.05)',
                              border:`1px solid ${on?color+'88':'rgba(255,255,255,0.08)'}`,
                              opacity: on?1:0.5 }} />
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
