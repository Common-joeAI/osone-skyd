
import { useState, useEffect, useRef } from 'react'

const API = `http://${window.location.hostname}:8000`

function fmtLoad(n) { return `${parseFloat(n||0).toFixed(1)}%` }

export default function HivePanel() {
  const [hive, setHive] = useState(null)
  const [task, setTask] = useState("")
  const [taskType, setTaskType] = useState("shell")
  const [target, setTarget] = useState("best")
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)
  const installCmd = `curl http://${window.location.hostname}:8000/agent/install.sh | OSONE_IP=${window.location.hostname} bash`

  useEffect(() => {
    const load = () => fetch(`${API}/api/hive/nodes`).then(r=>r.json()).then(setHive).catch(()=>{})
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [])

  const dispatch = async () => {
    if (!task.trim()) return
    setRunning(true)
    setResult(null)
    try {
      const payload = taskType === "shell" ? {cmd: task} : taskType === "python" ? {code: task} : {url: task}
      const endpoint = target === "all" ? "/api/hive/broadcast" : "/api/hive/dispatch"
      const r = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({task_type: taskType, payload, capability: taskType})
      })
      setResult(await r.json())
    } catch(e) { setResult({error: String(e)}) }
    setRunning(false)
  }

  const nodes = hive?.nodes || []

  return (
    <div style={{display:"flex",flexDirection:"column",height:"100%",overflow:"hidden"}}>
      {/* Header */}
      <div style={{padding:"12px 16px",background:"var(--surface2)",borderBottom:"1px solid var(--border)",display:"flex",alignItems:"center",gap:12}}>
        <span style={{fontSize:20}}>🕷️</span>
        <div>
          <div style={{fontSize:13,fontWeight:600,color:"var(--accent)"}}>OSONE Hive Commander</div>
          <div style={{fontSize:11,color:"var(--muted)"}}>
            {hive ? `${hive.active}/${hive.total} nodes active` : "connecting..."}
          </div>
        </div>
      </div>

      <div style={{flex:1,overflow:"auto",padding:16,display:"flex",flexDirection:"column",gap:16}}>

        {/* Node Grid */}
        <div>
          <div style={{fontSize:11,color:"var(--muted)",textTransform:"uppercase",letterSpacing:"0.5px",marginBottom:10}}>Active Nodes</div>
          {nodes.length === 0 ? (
            <div style={{padding:"20px",background:"var(--surface2)",borderRadius:10,border:"1px dashed var(--border)",textAlign:"center",color:"var(--muted)",fontSize:13}}>
              No underlings connected yet.<br/>
              <span style={{color:"var(--accent)",fontSize:12}}>Install an agent on any machine to join the hive.</span>
            </div>
          ) : (
            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(200px,1fr))",gap:10}}>
              {nodes.map((n,i) => (
                <div key={i} style={{background:"var(--surface2)",border:"1px solid var(--border)",borderRadius:10,padding:12}}>
                  <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:8}}>
                    <div style={{width:8,height:8,borderRadius:"50%",background:"var(--green)",boxShadow:"0 0 6px var(--green)"}} />
                    <span style={{fontSize:13,fontWeight:600}}>{n.name}</span>
                  </div>
                  <div style={{fontSize:11,color:"var(--muted)"}}>Load: <span style={{color:"var(--text)"}}>{fmtLoad(n.load)}</span></div>
                  <div style={{fontSize:11,color:"var(--muted)"}}>Tasks: <span style={{color:"var(--accent)"}}>{n.tasks_completed||0}</span></div>
                  <div style={{marginTop:6,display:"flex",flexWrap:"wrap",gap:4}}>
                    {(n.capabilities||[]).slice(0,3).map(c => (
                      <span key={c} style={{fontSize:10,background:"rgba(124,111,255,0.15)",color:"var(--accent)",padding:"2px 6px",borderRadius:4}}>{c}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Task Dispatcher */}
        <div style={{background:"var(--surface2)",border:"1px solid var(--border)",borderRadius:10,padding:14}}>
          <div style={{fontSize:11,color:"var(--muted)",textTransform:"uppercase",letterSpacing:"0.5px",marginBottom:12}}>Dispatch Task</div>
          <div style={{display:"flex",gap:8,marginBottom:10}}>
            {["shell","python","web_scrape","ping"].map(t => (
              <button key={t} onClick={()=>setTaskType(t)}
                style={{padding:"4px 10px",borderRadius:6,border:"1px solid var(--border)",
                  background:taskType===t?"var(--accent)":"var(--surface)",
                  color:taskType===t?"white":"var(--muted)",fontSize:11,cursor:"pointer"}}>
                {t}
              </button>
            ))}
            <div style={{marginLeft:"auto",display:"flex",alignItems:"center",gap:6,fontSize:11,color:"var(--muted)"}}>
              Target:
              <select value={target} onChange={e=>setTarget(e.target.value)}
                style={{background:"var(--surface)",border:"1px solid var(--border)",color:"var(--text)",borderRadius:6,padding:"3px 8px",fontSize:11}}>
                <option value="best">Best node</option>
                <option value="all">All nodes</option>
              </select>
            </div>
          </div>
          <textarea value={task} onChange={e=>setTask(e.target.value)}
            placeholder={taskType==="shell"?"e.g. uname -a":taskType==="python"?"e.g. print('hello from underling')":taskType==="web_scrape"?"https://...":"ping"}
            style={{width:"100%",height:80,background:"var(--surface)",border:"1px solid var(--border)",
              borderRadius:8,padding:10,color:"var(--text)",fontSize:12,fontFamily:"monospace",resize:"vertical",outline:"none"}} />
          <button onClick={dispatch} disabled={running||nodes.length===0}
            style={{marginTop:8,background:"var(--accent)",border:"none",borderRadius:8,
              padding:"8px 20px",color:"white",fontSize:13,cursor:"pointer",opacity:running||nodes.length===0?0.5:1}}>
            {running ? "Dispatching..." : `${target==="all"?"Broadcast to All":"Dispatch to Best"}`}
          </button>

          {result && (
            <div style={{marginTop:12,background:"#060608",borderRadius:8,padding:12,fontSize:12,fontFamily:"monospace",
              color:"#a0f0a0",whiteSpace:"pre-wrap",maxHeight:200,overflow:"auto"}}>
              {JSON.stringify(result, null, 2)}
            </div>
          )}
        </div>

        {/* Install Instructions */}
        <div style={{background:"var(--surface2)",border:"1px solid rgba(124,111,255,0.3)",borderRadius:10,padding:14}}>
          <div style={{fontSize:11,color:"var(--accent)",textTransform:"uppercase",letterSpacing:"0.5px",marginBottom:10}}>➕ Add a Node to the Hive</div>
          <div style={{fontSize:12,color:"var(--muted)",marginBottom:8}}>Run this on any Linux machine to enlist it as an underling:</div>
          <div style={{background:"#060608",borderRadius:8,padding:10,fontSize:11,fontFamily:"monospace",color:"#4ade80",
            userSelect:"all",wordBreak:"break-all"}}>
            {installCmd}
          </div>
          <div style={{fontSize:11,color:"var(--muted)",marginTop:8}}>
            The node will auto-register, appear above, and await commands.
          </div>
        </div>

      </div>
    </div>
  )
}
