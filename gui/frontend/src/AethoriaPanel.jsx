import { useState, useEffect, useCallback } from 'react'

const _isLocal = window.location.port !== ''
const API = _isLocal
  ? `http://${window.location.hostname}:8000`
  : `${window.location.protocol}//${window.location.host}`

const C = {
  bg:'#06060d', panel:'rgba(255,255,255,0.04)', border:'rgba(255,255,255,0.08)',
  accent:'#7c6fff', green:'#10b981', red:'#ef4444', yellow:'#f59e0b',
  blue:'#38bdf8', pink:'#ec4899', text:'rgba(255,255,255,0.85)', muted:'rgba(255,255,255,0.35)',
}

// Safe helpers
const safeNum  = (v, fallback=0) => (typeof v === 'number' && isFinite(v)) ? v : fallback
const safePct  = (v, fallback=100) => { const n = safeNum(v, fallback/100); return Math.max(0, Math.min(100, n <= 1 ? n*100 : n)) }
const isTruthy = (v) => v === true || v === 1 || v === '1'

function StatCard({ icon, label, value, sub, color }) {
  return (
    <div style={{ background:C.panel, border:`1px solid ${color||C.border}33`,
      borderRadius:14, padding:'14px 16px', flex:1, minWidth:110 }}>
      <div style={{ fontSize:20, marginBottom:4 }}>{icon}</div>
      <div style={{ fontSize:20, fontWeight:800, color:color||C.text, lineHeight:1 }}>{value ?? '—'}</div>
      {sub && <div style={{ fontSize:10, color:C.muted, marginTop:2 }}>{sub}</div>}
      <div style={{ fontSize:10, color:C.muted, marginTop:4, textTransform:'uppercase', letterSpacing:1 }}>{label}</div>
    </div>
  )
}

function NeedBar({ val, color }) {
  const pct = safePct(val, 100)
  const bg  = pct < 25 ? C.red : pct < 60 ? C.yellow : color
  return (
    <div style={{ display:'flex', alignItems:'center', gap:3 }}>
      <div style={{ width:36, height:4, background:'rgba(255,255,255,0.08)', borderRadius:99 }}>
        <div style={{ height:'100%', width:`${pct}%`, background:bg, borderRadius:99 }} />
      </div>
      <span style={{ fontSize:9, color:C.muted, width:24 }}>{Math.round(pct)}%</span>
    </div>
  )
}

function AgentRow({ a }) {
  const isChild = isTruthy(a.is_child)
  const isDead  = isTruthy(a.is_dead)
  const gen     = safeNum(a.generation, 1)
  const bal     = safeNum(a.balance, 0)
  const moodClr = { content:C.green, happy:C.green, desperate:C.red, neutral:C.muted, curious:C.blue }[a.mood] || C.muted

  // hunger/thirst/shelter may not exist — show full bar if missing
  const hunger  = a.hunger  !== undefined ? a.hunger  : 1
  const thirst  = a.thirst  !== undefined ? a.thirst  : 1
  const shelter = a.shelter !== undefined ? a.shelter : 1

  return (
    <div style={{ display:'grid', gridTemplateColumns:'1fr 74px 60px repeat(3,48px) 56px',
      gap:4, alignItems:'center', padding:'7px 0',
      borderBottom:'1px solid rgba(255,255,255,0.04)', opacity:isDead?0.35:1 }}>
      <div>
        <span style={{ fontWeight:600, fontSize:12, color:isDead?'#666':C.text }}>
          {isDead?'☠️ ':isChild?'👶 ':''}{a.name||'?'}
        </span>
        {gen > 1 && <span style={{ fontSize:9, color:C.accent, marginLeft:4 }}>g{gen}</span>}
      </div>
      <span style={{ fontSize:10, color:C.muted, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{a.role||'—'}</span>
      <span style={{ fontSize:11, color:C.yellow, textAlign:'right' }}>{Math.round(bal)}A</span>
      <NeedBar val={hunger}  color={C.yellow} />
      <NeedBar val={thirst}  color={C.blue}   />
      <NeedBar val={shelter} color={C.accent} />
      <span style={{ fontSize:10, color:moodClr }}>{a.mood||'—'}</span>
    </div>
  )
}

function MarketRow({ item }) {
  const supply = safeNum(item.supply, 0)
  const price  = safeNum(item.buy_price, 0)
  const pct    = Math.min(100, (supply / 200) * 100)
  const barClr = supply < 15 ? C.red : supply < 50 ? C.yellow : C.green
  return (
    <div style={{ display:'grid', gridTemplateColumns:'1fr 54px 54px 72px',
      gap:4, alignItems:'center', padding:'7px 0',
      borderBottom:'1px solid rgba(255,255,255,0.04)' }}>
      <div style={{ display:'flex', alignItems:'center', gap:6 }}>
        {item._is_new && <span style={{ fontSize:9, background:`${C.green}22`, border:`1px solid ${C.green}44`,
          color:C.green, borderRadius:10, padding:'1px 6px' }}>NEW</span>}
        <span style={{ fontSize:12, color:C.text }}>{item.item}</span>
      </div>
      <span style={{ fontSize:11, color:C.muted, textAlign:'right' }}>{supply}</span>
      <span style={{ fontSize:11, color:C.green, textAlign:'right' }}>{price.toFixed(0)}A</span>
      <div style={{ height:4, background:'rgba(255,255,255,0.06)', borderRadius:99 }}>
        <div style={{ height:'100%', borderRadius:99, width:`${pct}%`, background:barClr }} />
      </div>
    </div>
  )
}

function TechCard({ tech, onStart, treasury }) {
  const sc     = { unlocked:C.green, researching:C.yellow, available:C.blue, locked:C.muted }[tech.status] || C.muted
  const si     = { unlocked:'✅', researching:'🔬', available:'💡', locked:'🔒' }[tech.status] || '❓'
  const cost   = safeNum(tech.cost, 0)
  const prog   = safeNum(tech.progress, 0)
  const canStart = tech.status === 'available' && treasury >= cost * 0.5
  return (
    <div style={{ background:C.panel, border:`1px solid ${sc}33`, borderRadius:12,
      padding:'12px 14px', display:'flex', flexDirection:'column', gap:6,
      opacity:tech.status==='locked'?0.4:1 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <span style={{ fontWeight:700, fontSize:13, color:C.text }}>{si} {tech.name}</span>
        <span style={{ fontSize:10, color:sc, fontWeight:700, textTransform:'uppercase', letterSpacing:1 }}>{tech.status}</span>
      </div>
      <div style={{ fontSize:11, color:C.muted, lineHeight:1.5 }}>{tech.description}</div>
      {tech.status==='researching' && (
        <div>
          <div style={{ height:4, background:'rgba(255,255,255,0.08)', borderRadius:99, overflow:'hidden' }}>
            <div style={{ height:'100%', width:`${prog}%`,
              background:`linear-gradient(90deg,${C.yellow},${C.accent})`, borderRadius:99 }} />
          </div>
          <div style={{ fontSize:10, color:C.yellow, marginTop:3 }}>{prog}% complete</div>
        </div>
      )}
      <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
        {tech.unlocks_item && <span style={{ fontSize:10, background:`${C.green}18`, border:`1px solid ${C.green}44`,
          color:C.green, borderRadius:20, padding:'2px 8px' }}>🆕 {tech.unlocks_item}</span>}
        <span style={{ fontSize:10, background:`${C.accent}18`, border:`1px solid ${C.accent}44`,
          color:C.accent, borderRadius:20, padding:'2px 8px' }}>💰 {cost}A</span>
        {tech.researcher_role && <span style={{ fontSize:10, background:'rgba(255,255,255,0.05)', color:C.muted,
          borderRadius:20, padding:'2px 8px' }}>👤 {tech.researcher_role}</span>}
      </div>
      {tech.requires?.length > 0 && (
        <div style={{ fontSize:10, color:C.muted }}>Needs: {tech.requires.join(' + ')}</div>
      )}
      {canStart && (
        <button onClick={() => onStart(tech.tech_id)} style={{ marginTop:4, padding:'7px 14px',
          background:`${C.accent}22`, border:`1px solid ${C.accent}66`, borderRadius:8,
          color:C.accent, fontSize:12, fontWeight:700, cursor:'pointer' }}>
          Start Research ({Math.ceil(cost*0.5)}A)
        </button>
      )}
      {tech.status==='available' && !canStart && (
        <div style={{ fontSize:10, color:C.red }}>Need {Math.ceil(cost*0.5)}A in treasury</div>
      )}
    </div>
  )
}

export default function AethoriaPanel() {
  const [tab,     setTab]    = useState('overview')
  const [status,  setStatus] = useState(null)
  const [inv,     setInv]    = useState(null)
  const [market,  setMarket] = useState([])
  const [agents,  setAgents] = useState([])
  const [famTree, setFam]    = useState([])
  const [tickMsg, setMsg]    = useState('')
  const [ticking, setBusy]   = useState(false)
  const [filter,  setFilter] = useState('')
  const [error,   setError]  = useState(null)
  const base = `${API}/society`

  const load = useCallback(async () => {
    setError(null)
    try {
      const [st, snap, innovations, nm, ft] = await Promise.all([
        fetch(`${API}/status`).then(r=>r.ok?r.json():null).catch(()=>null),
        fetch(`${base}/snapshot`).then(r=>r.ok?r.json():null).catch(()=>null),
        fetch(`${base}/innovations`).then(r=>r.ok?r.json():null).catch(()=>null),
        fetch(`${base}/market/new`).then(r=>r.ok?r.json():null).catch(()=>null),
        fetch(`${base}/family_tree`).then(r=>r.ok?r.json():null).catch(()=>null),
      ])
      if (st) setStatus(st)
      if (innovations) setInv(innovations)
      if (ft) setFam(ft.family_tree || [])
      if (snap) {
        const base_items = snap.market ? Object.entries(snap.market).map(([item,v])=>({
          item,
          buy_price:  typeof v==='object' ? safeNum(v?.buy_price,0)  : safeNum(v,0),
          sell_price: typeof v==='object' ? safeNum(v?.sell_price,0) : safeNum(v,0),
          supply:     typeof v==='object' ? safeNum(v?.supply,100)   : 100,
          _is_new: false
        })) : []
        const new_items = (nm?.new_items || []).map(i=>({...i, _is_new:true}))
        const newKeys   = new Set(new_items.map(i=>i.item))
        setMarket([...new_items, ...base_items.filter(i=>!newKeys.has(i.item))])
        setAgents(snap.agents || [])
      }
    } catch(e) {
      setError(e.message)
    }
  }, [base])

  useEffect(()=>{ load() }, [load])
  useEffect(()=>{ const id=setInterval(load,30000); return()=>clearInterval(id) }, [load])

  const advance = async (n) => {
    setBusy(true); setMsg(`Running ${n} day${n>1?'s':''}...`)
    try {
      const r = await fetch(`${base}/fast_forward`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ticks:n, mc_day_speed:1, announce:n<=7})
      })
      const d = await r.json()
      const delta = safeNum(d.treasury_delta, 0)
      setMsg(`${n}d done — Treasury: ${safeNum(d.treasury_end,0).toFixed(0)}A (${delta>=0?'+':''}${delta.toFixed(0)}A) · Pop: ${d.population||'?'} · Deaths: ${d.total_deaths||0}`)
      load()
    } catch(e) { setMsg('Error: '+e.message) }
    setBusy(false)
  }

  const startResearch = async (techId) => {
    try {
      const r = await fetch(`${base}/research/start`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({tech_id:techId, proposed_by:'player'})
      })
      const d = await r.json()
      setMsg(d.ok ? `✅ ${d.tech_name} → ${d.researcher} (ETA ${d.eta_days}d)` : `⚠️ ${d.error}`)
      if(d.ok) load()
    } catch(e) { setMsg('Failed: '+e.message) }
  }

  const treas   = safeNum(status?.treasury, 0)
  const pop     = safeNum(status?.agents, 0)
  const tick    = safeNum(status?.tick, 0)
  const dead    = agents.filter(a=>isTruthy(a.is_dead)).length
  const desp    = agents.filter(a=>a.mood==='desperate').length
  const kids    = agents.filter(a=>isTruthy(a.is_child)).length
  const gen2    = famTree.filter(a=>safeNum(a.generation,1)>1).length
  const maxGen  = famTree.length > 0 ? Math.max(...famTree.map(a=>safeNum(a.generation,1))) : 1
  const allT    = inv ? [...(inv.tier1||[]), ...(inv.tier2||[]), ...(inv.tier3||[])] : []
  const TABS    = ['overview','agents','market','tech','family']

  if (error) return (
    <div style={{ padding:32, color:C.red, fontFamily:'monospace', fontSize:13 }}>
      ❌ {error}<br/><br/>
      <button onClick={load} style={{ padding:'8px 16px', background:`${C.accent}22`,
        border:`1px solid ${C.accent}`, borderRadius:8, color:C.accent, cursor:'pointer' }}>
        Retry
      </button>
    </div>
  )

  return (
    <div style={{ height:'100%', display:'flex', flexDirection:'column',
      background:C.bg, color:C.text, fontFamily:"'Inter',sans-serif", overflow:'hidden' }}>

      {/* Sub-nav */}
      <div style={{ display:'flex', borderBottom:`1px solid ${C.border}`,
        background:'rgba(10,10,20,0.95)', flexShrink:0, overflowX:'auto' }}>
        {TABS.map(t=>(
          <button key={t} onClick={()=>setTab(t)} style={{
            padding:'10px 14px', border:'none', cursor:'pointer',
            background:tab===t?`${C.accent}18`:'transparent',
            color:tab===t?C.accent:C.muted, fontWeight:tab===t?700:400,
            fontSize:12, textTransform:'capitalize',
            borderBottom:tab===t?`2px solid ${C.accent}`:'2px solid transparent',
            whiteSpace:'nowrap' }}>{t}</button>
        ))}
        <button onClick={load} style={{ marginLeft:'auto', padding:'10px 14px',
          border:'none', background:'transparent', color:C.muted, cursor:'pointer', fontSize:14 }}>⟳</button>
      </div>

      {/* Status ticker */}
      {tickMsg && (
        <div style={{ padding:'6px 16px', fontSize:11, flexShrink:0,
          background:tickMsg.startsWith('Error')||tickMsg.startsWith('⚠️')?`${C.red}18`:`${C.accent}12`,
          color:tickMsg.startsWith('Error')||tickMsg.startsWith('⚠️')?C.red:C.accent,
          borderBottom:`1px solid ${C.border}` }}>
          {ticking?'⏳ ':''}{tickMsg}
        </div>
      )}

      <div style={{ flex:1, overflowY:'auto', padding:14 }}>

        {/* ── OVERVIEW ── */}
        {tab==='overview' && (
          <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
            {/* Tick indicator */}
            <div style={{ fontSize:11, color:C.muted, textAlign:'right' }}>
              Day {tick} · {pop} citizens · {treas.toFixed(0)}A treasury
            </div>

            <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
              <StatCard icon="👥" label="Population" value={pop}                   color={C.green}  />
              <StatCard icon="💰" label="Treasury"   value={`${treas.toFixed(0)}A`} color={C.yellow} />
              <StatCard icon="🧬" label="Max Gen"    value={`Gen ${maxGen}`} sub={`${gen2} descendants`} color={C.accent} />
              <StatCard icon="👶" label="Children"   value={kids}                  color={C.blue}   />
            </div>
            <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
              <StatCard icon="🔬" label="Researching" value={inv?.in_research??0} sub={`${inv?.total_unlocked??0} unlocked`} color={C.yellow} />
              <StatCard icon="🆕" label="New Items"   value={market.filter(i=>i._is_new).length} color={C.green} />
              <StatCard icon="😰" label="Desperate"   value={desp} color={desp>0?C.red:C.muted} />
              <StatCard icon="☠️" label="Deaths"      value={dead} color={dead>0?C.red:C.muted} />
            </div>

            {/* Time controls */}
            <div style={{ background:C.panel, border:`1px solid ${C.border}`, borderRadius:14, padding:'14px 16px' }}>
              <div style={{ fontWeight:700, fontSize:13, marginBottom:10 }}>⏩ Advance Time</div>
              <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
                {[1,7,30,90,365].map(n=>(
                  <button key={n} onClick={()=>advance(n)} disabled={ticking} style={{
                    padding:'8px 16px', border:`1px solid ${C.accent}55`, borderRadius:8,
                    background:`${C.accent}15`, color:ticking?C.muted:C.accent,
                    fontWeight:700, fontSize:13, cursor:ticking?'default':'pointer' }}>+{n}d</button>
                ))}
              </div>
            </div>

            {/* Active research */}
            <div style={{ background:C.panel, border:`1px solid ${C.border}`, borderRadius:14, padding:'14px 16px' }}>
              <div style={{ fontWeight:700, fontSize:13, marginBottom:10 }}>🔬 Active Research</div>
              {allT.filter(t=>t.status==='researching').length===0
                ? <div style={{ color:C.muted, fontSize:12 }}>No active research — go to Tech tab</div>
                : allT.filter(t=>t.status==='researching').map(t=>(
                  <div key={t.tech_id} style={{ marginBottom:10 }}>
                    <div style={{ display:'flex', justifyContent:'space-between', marginBottom:3 }}>
                      <span style={{ fontSize:12, fontWeight:600 }}>🔬 {t.name}</span>
                      <span style={{ fontSize:11, color:C.yellow }}>{safeNum(t.progress)}% → {t.unlocks_item}</span>
                    </div>
                    <div style={{ height:5, background:'rgba(255,255,255,0.08)', borderRadius:99 }}>
                      <div style={{ height:'100%', width:`${safeNum(t.progress)}%`,
                        background:`linear-gradient(90deg,${C.yellow},${C.accent})`, borderRadius:99 }} />
                    </div>
                  </div>
                ))
              }
            </div>

            {/* New items */}
            {market.filter(i=>i._is_new).length>0 && (
              <div style={{ background:`${C.green}10`, border:`1px solid ${C.green}33`,
                borderRadius:14, padding:'14px 16px' }}>
                <div style={{ fontWeight:700, fontSize:13, color:C.green, marginBottom:8 }}>🆕 Innovation Unlocks</div>
                <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
                  {market.filter(i=>i._is_new).map(i=>(
                    <div key={i.item} style={{ background:`${C.green}15`, border:`1px solid ${C.green}44`,
                      borderRadius:10, padding:'8px 12px' }}>
                      <div style={{ fontWeight:700, fontSize:13 }}>{i.item}</div>
                      <div style={{ fontSize:11, color:C.green }}>{safeNum(i.buy_price).toFixed(0)}A · {safeNum(i.supply)} in stock</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Food warning */}
            {market.filter(i=>['bread','food_ration'].includes(i.item) && safeNum(i.supply)<20).length>0 && (
              <div style={{ background:`${C.red}15`, border:`1px solid ${C.red}44`,
                borderRadius:12, padding:'12px 14px' }}>
                <span style={{ fontSize:13, fontWeight:700, color:C.red }}>⚠️ Food shortage! Citizens may starve.</span>
              </div>
            )}
          </div>
        )}

        {/* ── AGENTS ── */}
        {tab==='agents' && (
          <div>
            <input placeholder="Filter name or role..." value={filter}
              onChange={e=>setFilter(e.target.value)} style={{
                width:'100%', marginBottom:12, padding:'9px 14px',
                background:C.panel, border:`1px solid ${C.border}`, borderRadius:10,
                color:C.text, fontSize:13, boxSizing:'border-box', outline:'none' }} />
            <div style={{ display:'grid', gridTemplateColumns:'1fr 74px 60px repeat(3,48px) 56px',
              gap:4, padding:'0 0 6px', borderBottom:`1px solid ${C.border}`, marginBottom:2 }}>
              {['Name','Role','Bal','🍞','💧','🏠','Mood'].map(h=>(
                <span key={h} style={{ fontSize:10, color:C.muted, textTransform:'uppercase', letterSpacing:1 }}>{h}</span>
              ))}
            </div>
            {agents
              .filter(a => !filter ||
                (a.name||'').toLowerCase().includes(filter.toLowerCase()) ||
                (a.role||'').toLowerCase().includes(filter.toLowerCase()))
              .sort((a,b)=>safeNum(b.balance)-safeNum(a.balance))
              .map((a,i)=><AgentRow key={a.agent_id||a.name||i} a={a} />)
            }
            {agents.length===0 && <div style={{ color:C.muted, fontSize:12, textAlign:'center', marginTop:32 }}>Loading agents...</div>}
          </div>
        )}

        {/* ── MARKET ── */}
        {tab==='market' && (
          <div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 54px 54px 72px',
              gap:4, padding:'0 0 8px', borderBottom:`1px solid ${C.border}`, marginBottom:4 }}>
              {['Item','Supply','Buy','Stock'].map(h=>(
                <span key={h} style={{ fontSize:10, color:C.muted, textTransform:'uppercase', letterSpacing:1 }}>{h}</span>
              ))}
            </div>
            {market
              .sort((a,b)=>(b._is_new?1:0)-(a._is_new?1:0)||a.item.localeCompare(b.item))
              .map(i=><MarketRow key={i.item} item={i} />)
            }
            {market.length===0 && <div style={{ color:C.muted, fontSize:12, textAlign:'center', marginTop:32 }}>Loading market...</div>}
          </div>
        )}

        {/* ── TECH ── */}
        {tab==='tech' && (
          <div style={{ display:'flex', flexDirection:'column', gap:18 }}>
            {inv && (
              <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
                {[['✅','Unlocked',inv.total_unlocked,C.green],
                  ['🔬','Researching',inv.in_research,C.yellow],
                  ['💡','Available',inv.total_available,C.blue]].map(([icon,lbl,val,clr])=>(
                  <div key={lbl} style={{ background:C.panel, border:`1px solid ${clr}33`,
                    borderRadius:12, padding:'10px 16px', display:'flex', gap:8, alignItems:'center' }}>
                    <span style={{ fontSize:18 }}>{icon}</span>
                    <div>
                      <div style={{ fontWeight:800, fontSize:18, color:clr }}>{val??0}</div>
                      <div style={{ fontSize:10, color:C.muted }}>{lbl}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {!inv && <div style={{ color:C.muted, fontSize:12 }}>Loading tech tree...</div>}
            {inv && [['🔨 Tier 1 — Foundations', inv.tier1||[]],
                     ['⚙️  Tier 2 — Industrial',  inv.tier2||[]],
                     ['✨  Tier 3 — Advanced',     inv.tier3||[]]].map(([title,techs])=>(
              <div key={title}>
                <div style={{ fontWeight:700, fontSize:12, color:C.muted,
                  textTransform:'uppercase', letterSpacing:1, marginBottom:10 }}>{title}</div>
                <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(240px,1fr))', gap:10 }}>
                  {techs.map(t=><TechCard key={t.tech_id} tech={t} onStart={startResearch} treasury={treas} />)}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── FAMILY ── */}
        {tab==='family' && (
          <div>
            <div style={{ marginBottom:12, fontSize:12, color:C.muted }}>
              {famTree.length} agents · {gen2} descendants · Max gen {maxGen}
            </div>
            {famTree.length===0 && <div style={{ color:C.muted, fontSize:12 }}>Loading family tree...</div>}
            {[...new Set(famTree.map(a=>safeNum(a.generation,1)))].sort().map(gen=>{
              const g = famTree.filter(a=>safeNum(a.generation,1)===gen)
              return (
                <div key={gen} style={{ marginBottom:18 }}>
                  <div style={{ fontWeight:700, fontSize:12, color:C.accent,
                    textTransform:'uppercase', letterSpacing:1, marginBottom:8 }}>
                    Generation {gen} ({g.length})
                  </div>
                  <div style={{ display:'flex', flexWrap:'wrap', gap:8 }}>
                    {g.map((a,i)=>(
                      <div key={a.agent_id||a.name||i} style={{ background:C.panel,
                        border:`1px solid ${isTruthy(a.is_child)?C.blue:C.border}44`,
                        borderRadius:10, padding:'8px 12px', minWidth:120 }}>
                        <div style={{ fontWeight:700, fontSize:13 }}>
                          {isTruthy(a.is_child)?'👶 ':''}{a.name||'?'}
                        </div>
                        <div style={{ fontSize:11, color:C.muted }}>{a.role||'citizen'}</div>
                        {(a.parent1_name||a.parent2_name) && (
                          <div style={{ fontSize:10, color:C.muted, marginTop:4 }}>
                            ← {a.parent1_name||'?'} + {a.parent2_name||'?'}
                          </div>
                        )}
                        {a.partner_name && (
                          <div style={{ fontSize:10, color:C.pink, marginTop:2 }}>💑 {a.partner_name}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        )}

      </div>
    </div>
  )
}
