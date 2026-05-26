import { StrictMode, Component } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

class ErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null } }
  static getDerivedStateFromError(e) { return { error: e } }
  componentDidCatch(e, info) { console.error('App crash:', e, info) }
  render() {
    if (this.state.error) return (
      <div style={{ background:'#0a0a14', color:'#f87171', padding:30, fontFamily:'monospace',
        minHeight:'100vh', fontSize:13, lineHeight:1.8 }}>
        <div style={{ color:'#ef4444', fontWeight:700, fontSize:18, marginBottom:16 }}>
          ⚠️ App crashed — check browser console (F12) for full trace
        </div>
        <pre style={{ whiteSpace:'pre-wrap', wordBreak:'break-all', 
          background:'rgba(239,68,68,0.1)', padding:16, borderRadius:8 }}>
          {this.state.error?.message}
          {String(this.state.error?.stack || '').slice(0, 800)}
        </pre>
        <button onClick={()=>window.location.reload()}
          style={{ marginTop:20, background:'#7c6fff', border:'none', borderRadius:8,
            color:'#fff', padding:'10px 20px', cursor:'pointer', fontSize:14 }}>
          Reload
        </button>
      </div>
    )
    return this.props.children
  }
}

createRoot(document.getElementById('root')).render(
  <StrictMode><ErrorBoundary><App /></ErrorBoundary></StrictMode>
)
