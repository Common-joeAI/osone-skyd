import { useState, useEffect, useRef, useCallback } from 'react'
import * as Tone from 'tone'

// ─────────────────────────────────────────────────────────────────────────────
//  INSTRUMENT LIBRARY  (free samples via unpkg / CDN)
//  Salamander Grand Piano + freesound-based packs, all MIT/CC0
// ─────────────────────────────────────────────────────────────────────────────

// Note map helpers
const NOTE_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
const midiToNote = (midi) => {
  const oct = Math.floor(midi / 12) - 1
  return NOTE_NAMES[midi % 12] + oct          // e.g. "C4", "F#3"
}

// Each instrument definition: label, Tone.Sampler urls, base url
const INSTRUMENTS = {
  piano: {
    label: '🎹 Grand Piano',
    color: '#7c6fff',
    baseUrl: 'https://tonejs.github.io/audio/salamander/',
    urls: {
      A0:'A0.mp3', C1:'C1.mp3', 'D#1':'Ds1.mp3', 'F#1':'Fs1.mp3',
      A1:'A1.mp3', C2:'C2.mp3', 'D#2':'Ds2.mp3', 'F#2':'Fs2.mp3',
      A2:'A2.mp3', C3:'C3.mp3', 'D#3':'Ds3.mp3', 'F#3':'Fs3.mp3',
      A3:'A3.mp3', C4:'C4.mp3', 'D#4':'Ds4.mp3', 'F#4':'Fs4.mp3',
      A4:'A4.mp3', C5:'C5.mp3', 'D#5':'Ds5.mp3', 'F#5':'Fs5.mp3',
      A5:'A5.mp3', C6:'C6.mp3', 'D#6':'Ds6.mp3', 'F#6':'Fs6.mp3',
      A6:'A6.mp3', C7:'C7.mp3', 'D#7':'Ds7.mp3', 'F#7':'Fs7.mp3',
      A7:'A7.mp3', C8:'C8.mp3',
    }
  },
  guitar: {
    label: '🎸 Acoustic Guitar',
    color: '#f59e0b',
    baseUrl: 'https://tonejs.github.io/audio/guitar-acoustic/',
    urls: {
      E2:'E2.mp3', A2:'A2.mp3', D3:'D3.mp3', G3:'G3.mp3', B3:'B3.mp3', E4:'E4.mp3',
      A3:'A3.mp3', D4:'D4.mp3', G4:'G4.mp3', B4:'B4.mp3', E5:'E5.mp3',
    }
  },
  'e-guitar': {
    label: '⚡ Electric Guitar',
    color: '#ef4444',
    baseUrl: 'https://tonejs.github.io/audio/guitar-electric/',
    urls: {
      'D#3':'Ds3.mp3', 'F#3':'Fs3.mp3', A3:'A3.mp3', C4:'C4.mp3',
      'D#4':'Ds4.mp3', 'F#4':'Fs4.mp3', A4:'A4.mp3', C5:'C5.mp3',
      'D#5':'Ds5.mp3', 'F#5':'Fs5.mp3', A5:'A5.mp3',
    }
  },
  bass: {
    label: '🎵 Electric Bass',
    color: '#10b981',
    baseUrl: 'https://tonejs.github.io/audio/bass-electric/',
    urls: {
      'A#1':'As1.mp3', 'A#2':'As2.mp3', 'A#3':'As3.mp3', 'A#4':'As4.mp3',
      C2:'C2.mp3', C3:'C3.mp3', C4:'C4.mp3',
      E1:'E1.mp3', E2:'E2.mp3', E3:'E3.mp3', E4:'E4.mp3',
      G1:'G1.mp3', G2:'G2.mp3', G3:'G3.mp3', G4:'G4.mp3',
    }
  },
  violin: {
    label: '🎻 Violin',
    color: '#ec4899',
    baseUrl: 'https://tonejs.github.io/audio/violin/',
    urls: {
      A3:'A3.mp3', A4:'A4.mp3', A5:'A5.mp3', A6:'A6.mp3',
      C4:'C4.mp3', C5:'C5.mp3', C6:'C6.mp3', C7:'C7.mp3',
      E4:'E4.mp3', E5:'E5.mp3', E6:'E6.mp3',
      G3:'G3.mp3', G4:'G4.mp3', G5:'G5.mp3', G6:'G6.mp3',
    }
  },
  trumpet: {
    label: '🎺 Trumpet',
    color: '#f97316',
    baseUrl: 'https://tonejs.github.io/audio/trumpet/',
    urls: {
      C4:'C4.mp3', D4:'D4.mp3', 'D#4':'Ds4.mp3', F4:'F4.mp3',
      G4:'G4.mp3', A4:'A4.mp3', 'A#4':'As4.mp3', C5:'C5.mp3',
      D5:'D5.mp3', F5:'F5.mp3', G5:'G5.mp3', A5:'A5.mp3',
    }
  },
  flute: {
    label: '🪈 Flute',
    color: '#06b6d4',
    baseUrl: 'https://tonejs.github.io/audio/flute/',
    urls: {
      A4:'A4.mp3', C5:'C5.mp3', E5:'E5.mp3', A5:'A5.mp3',
      C6:'C6.mp3', E6:'E6.mp3', A6:'A6.mp3',
    }
  },
  cello: {
    label: '🎻 Cello',
    color: '#8b5cf6',
    baseUrl: 'https://tonejs.github.io/audio/cello/',
    urls: {
      E2:'E2.mp3', A2:'A2.mp3', D3:'D3.mp3', G3:'G3.mp3',
      C3:'C3.mp3', F3:'F3.mp3', 'A#3':'As3.mp3', E3:'E3.mp3',
      A3:'A3.mp3', D4:'D4.mp3', G4:'G4.mp3',
    }
  },
  marimba: {
    label: '🪘 Marimba',
    color: '#84cc16',
    baseUrl: 'https://tonejs.github.io/audio/marimba/',
    urls: {
      A1:'A1.mp3', C2:'C2.mp3', E2:'E2.mp3', A2:'A2.mp3',
      C3:'C3.mp3', E3:'E3.mp3', A3:'A3.mp3', C4:'C4.mp3',
      E4:'E4.mp3', A4:'A4.mp3', C5:'C5.mp3', E5:'E5.mp3',
    }
  },
  organ: {
    label: '🎹 Organ',
    color: '#a78bfa',
    baseUrl: 'https://tonejs.github.io/audio/organ/',
    urls: {
      C2:'C2.mp3', C3:'C3.mp3', C4:'C4.mp3', C5:'C5.mp3',
      'F#2':'Fs2.mp3', 'F#3':'Fs3.mp3', 'F#4':'Fs4.mp3',
      A2:'A2.mp3', A3:'A3.mp3', A4:'A4.mp3',
    }
  },
}

// ─────────────────────────────────────────────────────────────────────────────
//  SAMPLER CACHE  — one Tone.Sampler per instrument, loaded on demand
// ─────────────────────────────────────────────────────────────────────────────
const _samplers = {}
const _loading  = {}

function getSampler(instrKey) {
  return new Promise((resolve) => {
    if (_samplers[instrKey]) { resolve(_samplers[instrKey]); return }
    if (_loading[instrKey])  { _loading[instrKey].push(resolve); return }
    _loading[instrKey] = [resolve]
    const def = INSTRUMENTS[instrKey]
    const sampler = new Tone.Sampler({
      urls:    def.urls,
      baseUrl: def.baseUrl,
      onload:  () => {
        _samplers[instrKey] = sampler
        _loading[instrKey].forEach(cb => cb(sampler))
        delete _loading[instrKey]
      }
    }).toDestination()
  })
}

// ─────────────────────────────────────────────────────────────────────────────
//  DRUM SYNTHS  (Tone.js built-in synthesized percussion — no samples needed)
// ─────────────────────────────────────────────────────────────────────────────
let _drumSynths = null
function getDrumSynths() {
  if (_drumSynths) return _drumSynths
  _drumSynths = {
    kick:    new Tone.MembraneSynth({ pitchDecay:0.05, octaves:5, envelope:{attack:0.001,decay:0.4,sustain:0,release:0.1} }).toDestination(),
    snare:   new Tone.NoiseSynth({ noise:{type:'white'}, envelope:{attack:0.001,decay:0.2,sustain:0,release:0.05} }).toDestination(),
    hihat:   new Tone.MetalSynth({ frequency:400, envelope:{attack:0.001,decay:0.05,release:0.01}, harmonicity:5.1, modulationIndex:32, resonance:4000, octaves:1.5 }).toDestination(),
    openhat: new Tone.MetalSynth({ frequency:400, envelope:{attack:0.001,decay:0.3, release:0.1},  harmonicity:5.1, modulationIndex:32, resonance:4000, octaves:1.5 }).toDestination(),
    clap:    new Tone.NoiseSynth({ noise:{type:'pink'}, envelope:{attack:0.001,decay:0.15,sustain:0,release:0.05} }).toDestination(),
    tom:     new Tone.MembraneSynth({ pitchDecay:0.08, octaves:4, envelope:{attack:0.001,decay:0.3,sustain:0,release:0.1} }).toDestination(),
    rim:     new Tone.MetalSynth({ frequency:800, envelope:{attack:0.001,decay:0.05,release:0.01}, harmonicity:8,   modulationIndex:16, resonance:5000, octaves:0.5 }).toDestination(),
  }
  // Set volumes
  _drumSynths.kick.volume.value    = -3
  _drumSynths.snare.volume.value   = -6
  _drumSynths.hihat.volume.value   = -12
  _drumSynths.openhat.volume.value = -14
  _drumSynths.clap.volume.value    = -8
  _drumSynths.tom.volume.value     = -6
  _drumSynths.rim.volume.value     = -10
  return _drumSynths
}

function triggerDrum(type, time) {
  const d = getDrumSynths()
  switch(type) {
    case 'kick':    d.kick.triggerAttackRelease('C1', '8n', time); break
    case 'snare':   d.snare.triggerAttackRelease('8n', time); break
    case 'hihat':   d.hihat.triggerAttackRelease('32n', time); break
    case 'openhat': d.openhat.triggerAttackRelease('8n', time); break
    case 'clap':    d.clap.triggerAttackRelease('16n', time); break
    case 'tom':     d.tom.triggerAttackRelease('A1', '8n', time); break
    case 'rim':     d.rim.triggerAttackRelease('32n', time); break
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  CONSTANTS
// ─────────────────────────────────────────────────────────────────────────────
const MIDI_MIN    = 36
const MIDI_MAX    = 84
const TOTAL_ROWS  = MIDI_MAX - MIDI_MIN + 1
const TOTAL_BEATS = 32

const DRUM_ROWS = [
  { id:'kick',    label:'Kick'   },
  { id:'snare',   label:'Snare'  },
  { id:'hihat',   label:'Hi-Hat' },
  { id:'openhat', label:'O.Hat'  },
  { id:'clap',    label:'Clap'   },
  { id:'tom',     label:'Tom'    },
  { id:'rim',     label:'Rim'    },
]

const SCALES = {
  'Major':      [0,2,4,5,7,9,11],  'Minor':      [0,2,3,5,7,8,10],
  'Dorian':     [0,2,3,5,7,9,10],  'Phrygian':   [0,1,3,5,7,8,10],
  'Lydian':     [0,2,4,6,7,9,11],  'Mixolydian': [0,2,4,5,7,9,10],
  'Pentatonic': [0,2,4,7,9],        'Blues':      [0,3,5,6,7,10],
  'Chromatic':  [0,1,2,3,4,5,6,7,8,9,10,11],
}
const CHORD_SHAPES = {
  'Major':[0,4,7], 'Minor':[0,3,7], 'Dom7':[0,4,7,10],
  'Maj7':[0,4,7,11], 'Min7':[0,3,7,10], 'Sus4':[0,5,7],
}
const ROOTS = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

// ─────────────────────────────────────────────────────────────────────────────
//  MOBILE
// ─────────────────────────────────────────────────────────────────────────────
function useIsMobile() {
  const [m, setM] = useState(() =>
    /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent) || window.innerWidth <= 768)
  useEffect(() => {
    const c = () => setM(/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent) || window.innerWidth <= 768)
    window.addEventListener('resize', c); return () => window.removeEventListener('resize', c)
  }, [])
  return m
}

// ─────────────────────────────────────────────────────────────────────────────
//  PIANO ROLL
// ─────────────────────────────────────────────────────────────────────────────
function PianoRoll({ notes, setNotes, playing, playhead, instrKey, isMobile }) {
  const cellW  = isMobile ? 20 : 26
  const cellH  = isMobile ? 13 : 17
  const labelW = isMobile ? 34 : 46
  const rollRef = useRef(null)
  const [tool, setTool] = useState('draw')
  const [drag, setDrag] = useState(null)
  const color  = INSTRUMENTS[instrKey]?.color || '#7c6fff'

  const rows = []
  for (let midi = MIDI_MAX; midi >= MIDI_MIN; midi--) rows.push(midi)

  const getCell = (e) => {
    const rect = rollRef.current.getBoundingClientRect()
    const cx = (e.touches?.[0]?.clientX ?? e.clientX) - rect.left - labelW
    const cy = (e.touches?.[0]?.clientY ?? e.clientY) - rect.top
    return { beat: Math.floor(cx / cellW), midi: MIDI_MAX - Math.floor(cy / cellH) }
  }

  const onDown = (e) => {
    e.preventDefault()
    const { beat, midi } = getCell(e)
    if (beat < 0 || beat >= TOTAL_BEATS || midi < MIDI_MIN || midi > MIDI_MAX) return

    if (tool === 'erase') {
      setNotes(n => n.filter(x => !(x.midi===midi && beat>=x.start && beat<x.start+x.len)))
      return
    }
    const hit = notes.find(x => x.midi===midi && beat>=x.start && beat<x.start+x.len)
    if (hit) {
      const idx = notes.indexOf(hit)
      const isResize = beat >= hit.start + hit.len - 1
      setDrag({ idx, startX: e.touches?.[0]?.clientX ?? e.clientX,
        origLen: hit.len, origStart: hit.start, mode: isResize ? 'resize' : 'move' })
      return
    }
    // Preview note via Tone.js sampler
    getSampler(instrKey).then(s => s.triggerAttackRelease(midiToNote(midi), '8n'))
    setNotes(n => [...n, { id: Date.now(), midi, start: beat, len: 1, vel: 100 }])
  }

  const onMove = (e) => {
    if (!drag) return
    const dx = ((e.touches?.[0]?.clientX ?? e.clientX) - drag.startX)
    const db = Math.round(dx / cellW)
    setNotes(n => n.map((x, i) => i !== drag.idx ? x : drag.mode === 'resize'
      ? { ...x, len: Math.max(1, drag.origLen + db) }
      : { ...x, start: Math.max(0, Math.min(TOTAL_BEATS - x.len, drag.origStart + db)) }
    ))
  }

  const velColor = (vel) => `hsl(${260},${50 + vel * 0.3}%,${35 + vel * 0.25}%)`

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', minHeight:0 }}>
      <div style={{ display:'flex', gap:6, padding:'5px 8px', background:'#0d0d1a',
        borderBottom:'1px solid rgba(255,255,255,0.07)', alignItems:'center', flexShrink:0 }}>
        <span style={{ fontSize:11, color:'rgba(255,255,255,0.35)' }}>TOOL:</span>
        {['draw','erase'].map(t => (
          <button key={t} onClick={() => setTool(t)}
            style={{ background: tool===t ? `${color}33` : 'rgba(255,255,255,0.05)',
              border:`1px solid ${tool===t ? color : 'rgba(255,255,255,0.1)'}`,
              borderRadius:6, color: tool===t ? color : 'rgba(255,255,255,0.4)',
              fontSize:11, padding:'3px 10px', cursor:'pointer' }}>
            {t === 'draw' ? '✏️ Draw' : '🗑 Erase'}
          </button>
        ))}
        <button onClick={() => setNotes([])}
          style={{ marginLeft:'auto', background:'rgba(239,68,68,0.1)',
            border:'1px solid rgba(239,68,68,0.3)', borderRadius:6,
            color:'#f87171', fontSize:11, padding:'3px 10px', cursor:'pointer' }}>Clear</button>
      </div>
      <div style={{ flex:1, overflow:'auto' }}>
        <div ref={rollRef}
          style={{ position:'relative', width: labelW + TOTAL_BEATS * cellW,
            height: TOTAL_ROWS * cellH, userSelect:'none' }}
          onMouseDown={onDown} onMouseMove={onMove} onMouseUp={() => setDrag(null)}
          onTouchStart={onDown} onTouchMove={onMove} onTouchEnd={() => setDrag(null)}>
          {rows.map((midi, ri) => {
            const name = NOTE_NAMES[midi % 12]
            const isBlack = name.includes('#')
            const isC     = name === 'C'
            return (
              <div key={midi} style={{ position:'absolute', top: ri*cellH, left:0, width:'100%', height:cellH,
                background: isBlack ? 'rgba(0,0,0,0.35)' : isC ? 'rgba(124,111,255,0.04)' : 'transparent',
                borderBottom:`1px solid rgba(255,255,255,${isC?'0.1':'0.03'})` }}>
                <div style={{ position:'absolute', left:0, width:labelW, height:'100%',
                  background: isBlack ? '#111' : '#1c1c2a',
                  borderRight:'1px solid rgba(255,255,255,0.08)',
                  display:'flex', alignItems:'center', paddingLeft:3,
                  fontSize: isMobile ? 7 : 9,
                  color: isC ? color : isBlack ? '#444' : '#333' }}>
                  {isC || (!isMobile && ['E','G','A'].includes(name))
                    ? `${name}${Math.floor(midi/12)-1}` : (isMobile ? '' : name)}
                </div>
              </div>
            )
          })}
          {Array.from({length:TOTAL_BEATS},(_,b) => (
            <div key={b} style={{ position:'absolute', left: labelW+b*cellW, top:0, width:1, height:'100%',
              background: b%4===0 ? 'rgba(255,255,255,0.14)' : b%2===0 ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.02)' }} />
          ))}
          {Array.from({length:TOTAL_BEATS/4},(_,bar) => (
            <div key={bar} style={{ position:'absolute', left: labelW+bar*4*cellW+2, top:2,
              fontSize:8, color:'rgba(255,255,255,0.25)', pointerEvents:'none' }}>{bar+1}</div>
          ))}
          {notes.map((n,i) => (
            <div key={n.id||i} style={{ position:'absolute',
              left: labelW + n.start*cellW + 1, top: (MIDI_MAX-n.midi)*cellH + 1,
              width: Math.max(4, n.len*cellW - 2), height: cellH - 2,
              background: velColor(n.vel), borderRadius:3,
              border:`1px solid ${color}55`,
              boxShadow:`0 0 5px ${color}44`, pointerEvents:'none' }} />
          ))}
          {playing && (
            <div style={{ position:'absolute', left: labelW + playhead*cellW, top:0,
              width:2, height:'100%', background:'#ef4444',
              boxShadow:'0 0 6px rgba(239,68,68,0.7)', pointerEvents:'none' }} />
          )}
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  STEP SEQUENCER
// ─────────────────────────────────────────────────────────────────────────────
function StepSequencer({ pattern, setPattern, currentStep, isMobile }) {
  const STEPS = 16
  const toggle = (row, step) =>
    setPattern(p => p.map((r,ri) => ri===row ? r.map((v,si) => si===step ? !v : v) : r))

  return (
    <div style={{ padding: isMobile ? '8px 6px' : '12px 14px', background:'#0a0a14' }}>
      <div style={{ fontSize:10, color:'rgba(255,255,255,0.3)', marginBottom:10, letterSpacing:1 }}>🥁 DRUM MACHINE</div>
      {DRUM_ROWS.map((drum, ri) => (
        <div key={drum.id} style={{ display:'flex', alignItems:'center', gap: isMobile ? 3 : 4, marginBottom: isMobile ? 4 : 6 }}>
          <div style={{ width: isMobile ? 38 : 50, fontSize: isMobile ? 9 : 10,
            color:'rgba(255,255,255,0.5)', flexShrink:0 }}>{drum.label}</div>
          {Array.from({length:STEPS},(_,s) => {
            const on = pattern[ri]?.[s]
            const cur = currentStep===s
            const down = s%4===0
            return (
              <div key={s} onClick={() => toggle(ri, s)}
                style={{ width: isMobile ? 17 : 23, height: isMobile ? 17 : 23, borderRadius:4,
                  background: on ? (cur ? '#fff' : `hsl(${260+ri*22},65%,58%)`)
                    : cur ? 'rgba(255,255,255,0.15)' : down ? 'rgba(255,255,255,0.07)' : 'rgba(255,255,255,0.04)',
                  border:`1px solid ${on ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.07)'}`,
                  cursor:'pointer', flexShrink:0, transition:'background 0.04s',
                  boxShadow: on&&cur ? '0 0 8px rgba(255,255,255,0.5)' : 'none' }} />
            )
          })}
        </div>
      ))}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  INSTRUMENT PICKER
// ─────────────────────────────────────────────────────────────────────────────
function InstrumentPicker({ instrKey, setInstrKey, loadState, isMobile }) {
  return (
    <div style={{ padding: isMobile ? '8px' : '12px 14px', background:'#0a0a14',
      borderTop:'1px solid rgba(255,255,255,0.07)' }}>
      <div style={{ fontSize:10, color:'rgba(255,255,255,0.3)', marginBottom:10, letterSpacing:1 }}>🎼 INSTRUMENT</div>
      <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
        {Object.entries(INSTRUMENTS).map(([key, def]) => (
          <button key={key} onClick={() => setInstrKey(key)}
            style={{ background: instrKey===key ? `${def.color}22` : 'rgba(255,255,255,0.04)',
              border:`1px solid ${instrKey===key ? def.color : 'rgba(255,255,255,0.1)'}`,
              borderRadius:8, color: instrKey===key ? def.color : 'rgba(255,255,255,0.45)',
              fontSize: isMobile ? 11 : 12, padding: isMobile ? '6px 10px' : '7px 14px',
              cursor:'pointer', fontWeight: instrKey===key ? 700 : 400,
              transition:'all 0.15s' }}>
            {def.label}
            {loadState[key] === 'loading' && instrKey===key && <span style={{ marginLeft:4, opacity:0.6 }}>⏳</span>}
            {loadState[key] === 'ready'   && instrKey===key && <span style={{ marginLeft:4, color:'#10b981' }}>●</span>}
          </button>
        ))}
      </div>
      <div style={{ marginTop:8, fontSize:10, color:'rgba(255,255,255,0.25)', lineHeight:1.6 }}>
        Samples stream from a free CDN. First play takes ~2s to buffer. Subsequent plays are instant.
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  ARIA GENERATOR
// ─────────────────────────────────────────────────────────────────────────────
function AriaGenerator({ onInsertNotes, isMobile }) {
  const [root,      setRoot]      = useState(60)
  const [scale,     setScale]     = useState('Major')
  const [chord,     setChord]     = useState('Major')
  const [pattern,   setPattern]   = useState('ascending')
  const [octaves,   setOctaves]   = useState(1)
  const [startBeat, setStartBeat] = useState(0)
  const [spacing,   setSpacing]   = useState(1)

  const generateScale = () => {
    const ivs = SCALES[scale]
    let notes = []
    for (let oct=0; oct<octaves; oct++)
      ivs.forEach((iv,i) => notes.push({ id:Date.now()+i+oct*100,
        midi: root+oct*12+iv, start: startBeat+(i+oct*ivs.length)*spacing, len:spacing, vel:100 }))
    if (pattern==='descending') notes.reverse().forEach((n,i) => { n.start=startBeat+i*spacing })
    if (pattern==='random')     notes.sort(()=>Math.random()-0.5).forEach((n,i) => { n.start=startBeat+i*spacing })
    onInsertNotes(notes)
  }
  const generateChord = () =>
    onInsertNotes(CHORD_SHAPES[chord].map((iv,i) => ({
      id:Date.now()+i, midi:root+iv, start:startBeat, len:4, vel:90-i*5 })))
  const generateArp = () =>
    onInsertNotes(CHORD_SHAPES[chord].map((iv,i) => ({
      id:Date.now()+i, midi:root+iv, start:startBeat+i*spacing, len:spacing, vel:100 })))

  const S = (label, val, set, opts) => (
    <div style={{ display:'flex', flexDirection:'column', gap:3 }}>
      <label style={{ fontSize:9, color:'rgba(255,255,255,0.35)', letterSpacing:1 }}>{label}</label>
      <select value={val} onChange={e=>set(e.target.value)}
        style={{ background:'rgba(255,255,255,0.08)', border:'1px solid rgba(255,255,255,0.12)',
          borderRadius:6, color:'#fff', padding:'4px 7px', fontSize:11, cursor:'pointer' }}>
        {opts.map(o=><option key={o.v} value={o.v} style={{background:'#1a1a2e'}}>{o.l}</option>)}
      </select>
    </div>
  )

  return (
    <div style={{ padding: isMobile ? '8px' : '12px 14px', background:'#0a0a14',
      borderTop:'1px solid rgba(255,255,255,0.07)' }}>
      <div style={{ fontSize:10, color:'rgba(255,255,255,0.3)', marginBottom:10, letterSpacing:1 }}>✨ ARIA GENERATOR</div>
      <div style={{ display:'flex', flexWrap:'wrap', gap:8, alignItems:'flex-end' }}>
        {S('ROOT',    root,      v=>setRoot(+v),    ROOTS.map((r,i)=>({v:60+i,l:r+'4'})))}
        {S('SCALE',   scale,     setScale,           Object.keys(SCALES).map(s=>({v:s,l:s})))}
        {S('CHORD',   chord,     setChord,           Object.keys(CHORD_SHAPES).map(c=>({v:c,l:c})))}
        {S('PATTERN', pattern,   setPattern,         [{v:'ascending',l:'↑ Asc'},{v:'descending',l:'↓ Desc'},{v:'random',l:'↺ Rand'}])}
        {S('START',   startBeat, v=>setStartBeat(+v),Array.from({length:32},(_,i)=>({v:i,l:String(i+1)})))}
        {S('STEP',    spacing,   v=>setSpacing(+v),  [{v:0.5,l:'½'},{v:1,l:'1'},{v:2,l:'2'},{v:4,l:'4'}])}
        <div style={{ display:'flex', gap:6, marginTop:'auto' }}>
          {[['+ Scale',generateScale],['+ Chord',generateChord],['+ Arp',generateArp]].map(([l,fn])=>(
            <button key={l} onClick={fn}
              style={{ background:'rgba(124,111,255,0.18)', border:'1px solid #7c6fff',
                borderRadius:7, color:'#7c6fff', fontSize:11, padding:'5px 10px', cursor:'pointer' }}>{l}</button>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  TRANSPORT
// ─────────────────────────────────────────────────────────────────────────────
function Transport({ playing, setPlaying, bpm, setBpm, loop, setLoop, onExport, isMobile }) {
  return (
    <div style={{ display:'flex', alignItems:'center', gap: isMobile ? 6 : 12,
      padding: isMobile ? '6px 8px' : '8px 14px', background:'#0d0d1a',
      borderBottom:'1px solid rgba(255,255,255,0.07)', flexShrink:0, flexWrap:'wrap' }}>
      <button onClick={()=>setPlaying(p=>!p)}
        style={{ background: playing ? 'rgba(239,68,68,0.2)' : 'rgba(124,111,255,0.2)',
          border:`1px solid ${playing ? '#ef4444' : '#7c6fff'}`,
          borderRadius:8, color: playing ? '#ef4444' : '#7c6fff',
          fontSize: isMobile ? 16 : 20, padding: isMobile ? '4px 10px' : '5px 14px', cursor:'pointer' }}>
        {playing ? '⏹' : '▶'}
      </button>
      <div style={{ display:'flex', alignItems:'center', gap:6 }}>
        <span style={{ fontSize:10, color:'rgba(255,255,255,0.4)' }}>BPM</span>
        <input type="number" value={bpm} min={40} max={240}
          onChange={e=>setBpm(Math.min(240,Math.max(40,+e.target.value)))}
          style={{ width: isMobile ? 46 : 54, background:'rgba(255,255,255,0.08)',
            border:'1px solid rgba(255,255,255,0.12)', borderRadius:6,
            color:'#fff', padding:'4px 7px', fontSize:13, textAlign:'center' }} />
        <input type="range" min={40} max={240} value={bpm}
          onChange={e=>setBpm(+e.target.value)}
          style={{ width: isMobile ? 55 : 75, accentColor:'#7c6fff' }} />
      </div>
      <button onClick={()=>setLoop(l=>!l)}
        style={{ background: loop ? 'rgba(124,111,255,0.2)' : 'rgba(255,255,255,0.05)',
          border:`1px solid ${loop ? '#7c6fff' : 'rgba(255,255,255,0.1)'}`,
          borderRadius:8, color: loop ? '#7c6fff' : '#555',
          fontSize:13, padding:'5px 12px', cursor:'pointer' }}>🔁 Loop</button>
      <button onClick={onExport}
        style={{ marginLeft:'auto', background:'rgba(16,185,129,0.15)',
          border:'1px solid rgba(16,185,129,0.4)', borderRadius:8,
          color:'#10b981', fontSize: isMobile ? 11 : 12,
          padding: isMobile ? '4px 10px' : '5px 14px', cursor:'pointer' }}>↓ Export WAV</button>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  MAIN DAW
// ─────────────────────────────────────────────────────────────────────────────
export default function DAWAgent() {
  const isMobile = useIsMobile()
  const [tab,         setTab]         = useState('piano')
  const [instrKey,    setInstrKey]    = useState('piano')
  const [playing,     setPlaying]     = useState(false)
  const [bpm,         setBpm]         = useState(120)
  const [loop,        setLoop]        = useState(true)
  const [playhead,    setPlayhead]    = useState(0)
  const [currentStep, setCurrentStep] = useState(-1)
  const [notes,       setNotes]       = useState([])
  const [drumPattern, setDrumPattern] = useState(() => DRUM_ROWS.map(() => Array(16).fill(false)))
  const [loadState,   setLoadState]   = useState({})

  const bpmRef     = useRef(bpm)
  const notesRef   = useRef(notes)
  const patternRef = useRef(drumPattern)
  const instrRef   = useRef(instrKey)
  const loopRef    = useRef(loop)
  const stepRef    = useRef(0)
  const beatRef    = useRef(0.0)
  const nextRef    = useRef(0)
  const timerRef   = useRef(null)

  useEffect(() => { bpmRef.current     = bpm },         [bpm])
  useEffect(() => { notesRef.current   = notes },       [notes])
  useEffect(() => { patternRef.current = drumPattern }, [drumPattern])
  useEffect(() => { instrRef.current   = instrKey },    [instrKey])
  useEffect(() => { loopRef.current    = loop },        [loop])

  // Pre-load instrument when selected
  useEffect(() => {
    setLoadState(s => ({...s, [instrKey]: 'loading'}))
    getSampler(instrKey).then(() =>
      setLoadState(s => ({...s, [instrKey]: 'ready'})))
  }, [instrKey])

  // Sequencer scheduler
  const scheduler = useCallback(() => {
    const now = Tone.now()
    const spb  = 60 / bpmRef.current
    const sp16 = spb / 4

    while (nextRef.current < now + 0.1) {
      const step  = stepRef.current
      const beat  = beatRef.current
      const t     = nextRef.current

      // Drums
      patternRef.current.forEach((row, ri) => {
        if (row[step]) triggerDrum(DRUM_ROWS[ri].id, t)
      })

      // Piano roll — beat-aligned
      const beatPos = beat + (step % 4) * 0.25
      if (_samplers[instrRef.current]) {
        notesRef.current.forEach(n => {
          if (Math.abs(n.start - beatPos) < 0.13) {
            const dur = Math.max(0.1, n.len * spb - 0.05)
            _samplers[instrRef.current].triggerAttackRelease(midiToNote(n.midi), dur, t)
          }
        })
      }

      setCurrentStep(step)
      setPlayhead(beatPos)

      stepRef.current = (step + 1) % 16
      if (step === 15) {
        const nextBeat = beat + 4
        beatRef.current = loopRef.current ? nextBeat % TOTAL_BEATS : nextBeat
        if (!loopRef.current && nextBeat >= TOTAL_BEATS) {
          setPlaying(false)
        }
      }
      nextRef.current += sp16
    }
  }, [])

  useEffect(() => {
    if (playing) {
      Tone.start()
      nextRef.current = Tone.now() + 0.05
      stepRef.current = 0
      beatRef.current = 0
      timerRef.current = setInterval(scheduler, 25)
    } else {
      clearInterval(timerRef.current)
      setCurrentStep(-1)
      setPlayhead(0)
      stepRef.current = 0
      beatRef.current = 0
    }
    return () => clearInterval(timerRef.current)
  }, [playing, scheduler])

  // WAV export
  const exportWav = useCallback(async () => {
    alert('Rendering… this may take a moment.')
    const spb   = 60 / bpm
    const sp16  = spb / 4
    const dur   = TOTAL_BEATS * spb
    const sr    = 44100
    const ctx2  = new OfflineAudioContext(1, Math.ceil(sr * dur), sr)

    // Drum synthesis offline
    const mkDrum = (type, t) => {
      switch(type) {
        case 'kick': {
          const o=ctx2.createOscillator(),g=ctx2.createGain()
          o.connect(g);g.connect(ctx2.destination)
          o.frequency.setValueAtTime(150,t);o.frequency.exponentialRampToValueAtTime(0.01,t+0.5)
          g.gain.setValueAtTime(1,t);g.gain.exponentialRampToValueAtTime(0.001,t+0.5)
          o.start(t);o.stop(t+0.5);break
        }
        case 'snare': case 'hihat': case 'openhat': case 'clap': {
          const b=ctx2.createBuffer(1,Math.ceil(sr*0.15),sr)
          const d=b.getChannelData(0)
          for(let i=0;i<d.length;i++) d[i]=(Math.random()*2-1)*(1-i/d.length)
          const s=ctx2.createBufferSource(),g=ctx2.createGain(),f=ctx2.createBiquadFilter()
          f.type='highpass';f.frequency.value=type==='kick'?200:4000
          s.buffer=b;s.connect(f);f.connect(g);g.connect(ctx2.destination)
          g.gain.setValueAtTime(0.5,t);g.gain.exponentialRampToValueAtTime(0.001,t+0.2)
          s.start(t);break
        }
        default: break
      }
    }

    for (let step=0; step<TOTAL_BEATS*4; step++) {
      const t = step * sp16
      if (t > dur) break
      drumPattern.forEach((row,ri) => { if (row[step%16]) mkDrum(DRUM_ROWS[ri].id, t) })
    }

    // Note events (approximate with tone offline — just schedule raw audio)
    notes.forEach(n => {
      const freq = 440 * Math.pow(2,(n.midi-69)/12)
      const o=ctx2.createOscillator(),g=ctx2.createGain(),f=ctx2.createBiquadFilter()
      f.type='lowpass';f.frequency.value=4000
      o.type='triangle';o.frequency.value=freq
      o.connect(f);f.connect(g);g.connect(ctx2.destination)
      const t=n.start*spb, d=n.len*spb-0.05
      g.gain.setValueAtTime(0,t);g.gain.linearRampToValueAtTime(0.3,t+0.01)
      g.gain.setValueAtTime(0.25,t+d-0.05);g.gain.linearRampToValueAtTime(0,t+d)
      o.start(t);o.stop(t+d)
    })

    const buf = await ctx2.startRendering()
    const wav = new ArrayBuffer(44 + buf.length*4)
    const v   = new DataView(wav)
    const w   = (off,str) => { for(let i=0;i<str.length;i++) v.setUint8(off+i,str.charCodeAt(i)) }
    w(0,'RIFF');v.setUint32(4,36+buf.length*4,true);w(8,'WAVE');w(12,'fmt ')
    v.setUint32(16,16,true);v.setUint16(20,3,true);v.setUint16(22,1,true)
    v.setUint32(24,sr,true);v.setUint32(28,sr*4,true);v.setUint16(32,4,true);v.setUint16(34,32,true)
    w(36,'data');v.setUint32(40,buf.length*4,true)
    const ch=buf.getChannelData(0)
    for(let i=0;i<buf.length;i++) v.setFloat32(44+i*4,ch[i],true)
    const a=document.createElement('a')
    a.href=URL.createObjectURL(new Blob([wav],{type:'audio/wav'}))
    a.download='osone_daw.wav';a.click()
  }, [notes, drumPattern, bpm])

  const TABS = [
    { id:'piano',      label:'🎹 Piano Roll' },
    { id:'drums',      label:'🥁 Drums'      },
    { id:'instrument', label:'🎼 Instruments'},
    { id:'generate',   label:'✨ Generate'   },
  ]

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', background:'#08080f',
      fontFamily:'system-ui,sans-serif', overflow:'hidden', color:'#fff' }}>

      {/* Header */}
      <div style={{ display:'flex', alignItems:'center', gap:10, padding:'0 14px', height:40,
        background:'#0d0d1a', borderBottom:'1px solid rgba(255,255,255,0.07)', flexShrink:0 }}>
        <span style={{ fontSize:16 }}>🎚️</span>
        <span style={{ fontWeight:800, fontSize:13, color: INSTRUMENTS[instrKey].color, letterSpacing:2 }}>OSONE DAW</span>
        <span style={{ fontSize:11, color:'rgba(255,255,255,0.4)', marginLeft:2 }}>
          {INSTRUMENTS[instrKey].label}
        </span>
        <div style={{ flex:1 }} />
        <span style={{ fontSize:10, color:'rgba(255,255,255,0.2)' }}>
          {notes.length} notes · {drumPattern.flat().filter(Boolean).length} hits
        </span>
      </div>

      {/* Transport */}
      <Transport playing={playing} setPlaying={setPlaying} bpm={bpm} setBpm={setBpm}
        loop={loop} setLoop={setLoop} onExport={exportWav} isMobile={isMobile} />

      {/* Tabs */}
      <div style={{ display:'flex', background:'#0a0a14',
        borderBottom:'1px solid rgba(255,255,255,0.07)', flexShrink:0 }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            style={{ flex:1, background: tab===t.id ? `${INSTRUMENTS[instrKey].color}18` : 'transparent',
              border:'none', borderBottom:`2px solid ${tab===t.id ? INSTRUMENTS[instrKey].color : 'transparent'}`,
              color: tab===t.id ? INSTRUMENTS[instrKey].color : 'rgba(255,255,255,0.4)',
              fontSize: isMobile ? 10 : 12, padding: isMobile ? '7px 2px' : '8px 6px',
              cursor:'pointer', fontWeight: tab===t.id ? 700 : 400 }}>
            {isMobile ? t.label.split(' ')[0] : t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex:1, overflow:'hidden', display:'flex', flexDirection:'column', minHeight:0 }}>
        {tab === 'piano' && (
          <PianoRoll notes={notes} setNotes={setNotes} playing={playing}
            playhead={playhead} instrKey={instrKey} isMobile={isMobile} />
        )}
        {tab === 'drums' && (
          <div style={{ flex:1, overflowY:'auto' }}>
            <StepSequencer pattern={drumPattern} setPattern={setDrumPattern}
              currentStep={currentStep} isMobile={isMobile} />
          </div>
        )}
        {tab === 'instrument' && (
          <div style={{ flex:1, overflowY:'auto' }}>
            <InstrumentPicker instrKey={instrKey} setInstrKey={setInstrKey}
              loadState={loadState} isMobile={isMobile} />
          </div>
        )}
        {tab === 'generate' && (
          <div style={{ flex:1, overflowY:'auto' }}>
            <AriaGenerator onInsertNotes={n => setNotes(prev => [...prev, ...n])} isMobile={isMobile} />
            <div style={{ padding:14, color:'rgba(255,255,255,0.3)', fontSize:12, lineHeight:1.9 }}>
              <p>Use <strong style={{color:'#7c6fff'}}>Generate</strong> to fill the piano roll, then switch to <strong style={{color:'#7c6fff'}}>Instruments</strong> to pick what plays it.</p>
              <p>Each instrument streams real samples — piano uses the <em style={{color:'rgba(255,255,255,0.5)'}}>Salamander Grand Piano</em> (free, high quality). Strings, brass, guitar all use matching free libraries.</p>
              <p>Drums are always synthesized locally — no network needed for the beat.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
