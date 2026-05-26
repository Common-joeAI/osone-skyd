import { useState, useRef, useEffect } from 'react'

const _isLocal = window.location.port !== ''
const API = _isLocal
  ? `http://${window.location.hostname}:8000`
  : `${window.location.protocol}//${window.location.host}`

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

export default function ImageStudio({ token }) {
  const isMobile = useIsMobile()
  const [prompt, setPrompt]       = useState('')
  const [loading, setLoading]     = useState(false)
  const [images, setImages]       = useState([])
  const [selected, setSelected]   = useState(null)
  const [style, setStyle]         = useState('cinematic')
  const [refImg, setRefImg]       = useState(null)
  const [refPreview, setRefPreview] = useState(null)
  const fileRef = useRef(null)

  const STYLES = [
    { id: 'cinematic',   label: '🎬 Cinematic' },
    { id: 'anime',       label: '🌸 Anime' },
    { id: 'photorealism',label: '📷 Photo' },
    { id: 'oil-painting',label: '🎨 Oil Paint' },
    { id: 'neon-noir',   label: '🌆 Neon Noir' },
    { id: 'pixel-art',   label: '👾 Pixel Art' },
    { id: 'sketch',      label: '✏️ Sketch' },
    { id: 'cyberpunk',   label: '🤖 Cyberpunk' },
  ]

  const generate = async () => {
    if (!prompt.trim() || loading) return
    setLoading(true)
    const fullPrompt = `${prompt}, ${style} style, highly detailed`
    try {
      const headers = { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }
      const r = await fetch(`${API}/api/imagine`, {
        method: 'POST', headers,
        body: JSON.stringify({ prompt: fullPrompt, reference_image: refImg })
      })
      const d = await r.json()
      if (d.url) {
        const entry = { url: d.url, prompt: fullPrompt, id: Date.now() }
        setImages(prev => [entry, ...prev])
        setSelected(entry)
      }
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  const handleRef = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    const reader = new FileReader()
    reader.onload = ev => { setRefImg(ev.target.result); setRefPreview(ev.target.result) }
    reader.readAsDataURL(f)
  }

  const download = (url, name) => {
    const a = document.createElement('a'); a.href = url; a.download = name || 'osone-image.png'
    a.target = '_blank'; a.click()
  }

  return (
    <div style={{ display:'flex', flexDirection: isMobile ? 'column' : 'row', height:'100%', background:'#09090f', fontFamily:'system-ui,sans-serif', overflow:'hidden' }}>

      {/* Left: Controls */}
      <div style={{ width: isMobile ? '100%' : 280, maxHeight: isMobile ? '44%' : 'none', display:'flex', flexDirection:'column', borderRight: isMobile ? 'none' : '1px solid rgba(255,255,255,0.07)', borderBottom: isMobile ? '1px solid rgba(255,255,255,0.07)' : 'none',
        background:'#0d0d1a', flexShrink:0, overflowY:'auto' }}>
        <div style={{ padding:'14px 14px 10px', borderBottom:'1px solid rgba(255,255,255,0.06)' }}>
          <div style={{ display:'flex', alignItems:'center', gap:8 }}>
            <div style={{ width:7, height:7, borderRadius:'50%', background:'#7c6fff', boxShadow:'0 0 6px #7c6fff' }} />
            <span style={{ fontWeight:700, fontSize:13, color:'#7c6fff', letterSpacing:1 }}>skyd</span>
            <span style={{ fontSize:11, color:'rgba(255,255,255,0.3)' }}>image studio</span>
          </div>
        </div>

        <div style={{ padding:14, display:'flex', flexDirection:'column', gap:14 }}>
          {/* Prompt */}
          <div>
            <label style={{ fontSize:11, color:'rgba(255,255,255,0.4)', display:'block', marginBottom:6 }}>PROMPT</label>
            <textarea
              value={prompt} onChange={e => setPrompt(e.target.value)}
              onKeyDown={e => { if (e.key==='Enter' && e.ctrlKey) generate() }}
              placeholder="Describe the image you want to create..."
              rows={4}
              style={{ width:'100%', background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.1)',
                borderRadius:8, padding:'9px 11px', color:'#fff', fontSize:13, outline:'none',
                resize:'none', fontFamily:'inherit', lineHeight:1.5, boxSizing:'border-box' }}
            />
          </div>

          {/* Style selector */}
          <div>
            <label style={{ fontSize:11, color:'rgba(255,255,255,0.4)', display:'block', marginBottom:6 }}>STYLE</label>
            <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
              {STYLES.map(s => (
                <button key={s.id} onClick={() => setStyle(s.id)}
                  style={{ background: style===s.id ? 'rgba(124,111,255,0.25)' : 'rgba(255,255,255,0.05)',
                    border: `1px solid ${style===s.id ? '#7c6fff' : 'rgba(255,255,255,0.1)'}`,
                    borderRadius:6, color: style===s.id ? '#7c6fff' : 'rgba(255,255,255,0.5)',
                    fontSize:11, padding:'4px 8px', cursor:'pointer' }}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Reference image */}
          <div>
            <label style={{ fontSize:11, color:'rgba(255,255,255,0.4)', display:'block', marginBottom:6 }}>REFERENCE IMAGE (optional)</label>
            <input ref={fileRef} type="file" accept="image/*" onChange={handleRef} style={{ display:'none' }} />
            {refPreview
              ? <div style={{ position:'relative', display:'inline-block' }}>
                  <img src={refPreview} alt="" style={{ height:70, borderRadius:6, objectFit:'cover' }} />
                  <button onClick={() => { setRefImg(null); setRefPreview(null) }}
                    style={{ position:'absolute', top:-6, right:-6, background:'#f87171', border:'none',
                      borderRadius:'50%', width:18, height:18, color:'#fff', fontSize:10,
                      cursor:'pointer', lineHeight:'18px', padding:0 }}>✕</button>
                </div>
              : <button onClick={() => fileRef.current?.click()}
                  style={{ background:'rgba(255,255,255,0.05)', border:'1px dashed rgba(255,255,255,0.15)',
                    borderRadius:8, color:'rgba(255,255,255,0.35)', fontSize:12, padding:'10px 14px',
                    cursor:'pointer', width:'100%' }}>+ Upload reference</button>
            }
          </div>

          {/* Generate button */}
          <button onClick={generate} disabled={loading || !prompt.trim()}
            style={{ background: loading ? 'rgba(124,111,255,0.3)' : '#7c6fff',
              border:'none', borderRadius:10, color:'#fff', padding:'13px',
              fontSize:14, fontWeight:700, cursor: loading?'wait':'pointer',
              opacity: !prompt.trim() ? 0.4 : 1, transition:'all 0.2s' }}>
            {loading ? '✦ Generating...' : '✦ Generate'}
          </button>

          {/* History strip */}
          {images.length > 1 && (
            <div>
              <label style={{ fontSize:11, color:'rgba(255,255,255,0.4)', display:'block', marginBottom:6 }}>HISTORY</label>
              <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
                {images.map(img => (
                  <img key={img.id} src={img.url} alt="" onClick={() => setSelected(img)}
                    style={{ width:56, height:56, borderRadius:6, objectFit:'cover', cursor:'pointer',
                      border: selected?.id===img.id ? '2px solid #7c6fff' : '2px solid transparent',
                      opacity: selected?.id===img.id ? 1 : 0.6 }} />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right: Canvas */}
      <div style={{ flex:1, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center',
        position:'relative', overflow:'hidden' }}>
        {selected ? (
          <>
            <img src={selected.url} alt={selected.prompt}
              style={{ maxWidth:'90%', maxHeight:'85%', borderRadius:12, objectFit:'contain',
                boxShadow:'0 0 60px rgba(124,111,255,0.15)' }} />
            {/* Action bar */}
            <div style={{ position:'absolute', bottom:20, display:'flex', gap:10 }}>
              <button onClick={() => download(selected.url, `osone-${selected.id}.png`)}
                style={{ background:'rgba(0,0,0,0.6)', border:'1px solid rgba(255,255,255,0.15)',
                  borderRadius:8, color:'#fff', fontSize:13, padding:'8px 18px', cursor:'pointer',
                  backdropFilter:'blur(8px)' }}>↓ Download</button>
              <button onClick={() => { setPrompt(selected.prompt.split(',')[0]); setRefImg(selected.url); setRefPreview(selected.url) }}
                style={{ background:'rgba(124,111,255,0.3)', border:'1px solid #7c6fff',
                  borderRadius:8, color:'#fff', fontSize:13, padding:'8px 18px', cursor:'pointer',
                  backdropFilter:'blur(8px)' }}>↺ Remix</button>
            </div>
            {/* Prompt overlay */}
            <div style={{ position:'absolute', top:14, left:'50%', transform:'translateX(-50%)',
              background:'rgba(0,0,0,0.55)', backdropFilter:'blur(8px)',
              borderRadius:20, padding:'5px 14px', fontSize:11, color:'rgba(255,255,255,0.6)',
              maxWidth:'70%', textAlign:'center', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>
              {selected.prompt}
            </div>
          </>
        ) : (
          <div style={{ textAlign:'center', color:'rgba(255,255,255,0.12)', userSelect:'none' }}>
            <div style={{ fontSize:64, marginBottom:16 }}>🎨</div>
            <div style={{ fontSize:16, fontWeight:600, letterSpacing:2 }}>IMAGE STUDIO</div>
            <div style={{ fontSize:12, marginTop:8 }}>Describe something. Hit Generate.</div>
          </div>
        )}
      </div>
    </div>
  )
}
