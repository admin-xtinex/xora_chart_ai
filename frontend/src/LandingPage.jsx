import { useEffect, useRef } from 'react'

const chartFeatures = [
  ['20-Coin Smart Scan', 'Five gainers, five losers, five movers and five volume leaders — globally unique.'],
  ['10-Pattern Knowledge', 'Visual pattern guides use the same keys as the matcher for a direct learn-and-review loop.'],
  ['AI Match + Confidence', 'Matched structures, reference similarity and evidence stay visible before a trade decision.'],
  ['Risk / Reward Review', 'Entry, invalidation and targets are presented beside the chart, not hidden behind a signal.'],
]

const appFeatures = [
  ['AI Signal Engine', 'Qualified setups with explainable reasoning and confidence.'],
  ['Scout + Chasing', 'Discover, validate and follow opportunities from a mobile-first workspace.'],
  ['Smart Execution', 'Approval, execution and monitoring remain backend-authoritative.'],
  ['Risk Management', 'Capital protection and execution safeguards stay visible at decision time.'],
  ['Portfolio Analytics', 'Active positions, trade history and performance review in one flow.'],
  ['Trade Journal', 'Review outcomes and improve the next decision.'],
]

function ArrowIcon({ className = '' }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12h14"/><path d="m14 7 5 5-5 5"/></svg>
}

function FeatureIcon({ type = 'spark' }) {
  const paths = {
    spark: <><path d="m12 2 1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8L12 2Z"/><path d="m18 15 .9 2.4 2.1.8-2.1.8L18 22l-.9-2-2.1-.8 2.1-.8L18 15Z"/></>,
    shield: <><path d="M12 3 5 6v5c0 5 3 8 7 10 4-2 7-5 7-10V6l-7-3Z"/><path d="m9 12 2 2 4-5"/></>,
    scan: <><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/><path d="M8 11h6M11 8v6"/></>,
    chart: <><path d="M4 19V9M9 15V5M14 19v-7M19 19V3"/><path d="M3 21h18"/></>,
  }
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[type] || paths.spark}</svg>
}

function ChartPreview() {
  const candles = [
    [22,120,145,18],[35,106,130,26],[48,114,139,31],[61,90,123,43],[74,79,112,50],[87,85,108,61],
    [100,65,96,57],[113,71,105,62],[126,55,82,45],[139,49,76,38],[152,58,88,50],[165,46,72,40],
    [178,73,103,63],[191,84,114,76],[204,98,128,90],[217,110,137,99],[230,102,127,94],[243,88,119,80],
    [256,76,106,68],[269,64,94,58],[282,51,83,45],[295,43,72,37],[308,36,65,30],[321,28,57,22],
  ]
  return (
    <div className="landing-chart-wrap" aria-label="Illustrative XORA chart intelligence preview">
      <div className="landing-chart-head">
        <div><span className="live-dot"/>BTC / USDT</div>
        <span>1m · pattern review</span>
      </div>
      <svg className="landing-chart" viewBox="0 0 350 190" preserveAspectRatio="none">
        <defs>
          <linearGradient id="chartArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#00d4ff" stopOpacity=".22"/><stop offset="1" stopColor="#7b2dff" stopOpacity="0"/></linearGradient>
          <filter id="chartGlow"><feGaussianBlur stdDeviation="2.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        </defs>
        {[40,80,120,160].map((y) => <line key={y} x1="0" y1={y} x2="350" y2={y} className="chart-grid-line"/>)}
        {[50,100,150,200,250,300].map((x) => <line key={x} x1={x} y1="0" y2="190" className="chart-grid-line"/>)}
        {candles.map(([x,o,c], i) => {
          const up = c < o
          const hi = Math.max(12, Math.min(o,c)-9)
          const lo = Math.min(178, Math.max(o,c)+12)
          return <g key={i}><line x1={x} x2={x} y1={hi} y2={lo} className={up?'candle-up':'candle-down'}/><rect x={x-3.5} width="7" y={Math.min(o,c)} height={Math.max(4,Math.abs(o-c))} rx="1.5" className={up?'candle-up-fill':'candle-down-fill'}/></g>
        })}
        <path d="M72 58 L141 132 L224 83 L301 58" fill="none" className="pattern-line" filter="url(#chartGlow)"/>
        <path d="M72 58 L301 58 M141 132 L301 58" fill="none" className="pattern-guide"/>
        <path d="M296 60 C315 51 329 37 341 19" fill="none" className="forecast-line" filter="url(#chartGlow)"/>
        <path d="M337 23 342 18 339 28" fill="none" className="forecast-line"/>
      </svg>
      <div className="match-floating-card">
        <span>MATCHED PATTERN</span>
        <strong>Ascending Triangle</strong>
        <div><em>Confidence</em><b>92.4%</b></div>
      </div>
    </div>
  )
}

function AppPhone() {
  return (
    <div className="phone-shell">
      <div className="phone-notch"/>
      <div className="phone-screen">
        <div className="phone-brand"><span className="mini-xora-icon"/><span>XORA</span><i>AI</i></div>
        <div className="phone-top-metrics"><div><small>Market Feed</small><strong className="positive">LIVE</strong></div><div><small>Risk Gate</small><strong>ACTIVE</strong></div></div>
        <div className="phone-signal"><div className="phone-signal-head"><span>AI SIGNAL</span><b>92%</b></div><strong>BTC/USDT</strong><div className="phone-bull">● Bullish <span>High confidence</span></div><button type="button">View signal</button></div>
        <div className="phone-flow">
          {['Discover','Validate','Approve','Execute','Monitor','Review'].map((step,i)=><div key={step}><span>{i<3?'✦':'◇'}</span><small>{step}</small></div>)}
        </div>
      </div>
    </div>
  )
}

function ProductFeature({ children, type }) {
  return <div className="landing-mini-feature"><span><FeatureIcon type={type}/></span><div>{children}</div></div>
}

export default function LandingPage() {
  const rootRef = useRef(null)

  useEffect(() => {
    document.body.classList.add('landing-mode')
    const root = rootRef.current
    if (!root) return () => document.body.classList.remove('landing-mode')
    let raf = 0
    const onMove = (event) => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        root.style.setProperty('--mx', `${event.clientX}px`)
        root.style.setProperty('--my', `${event.clientY}px`)
        root.style.setProperty('--px', `${(event.clientX / Math.max(innerWidth, 1) - .5) * 2}`)
        root.style.setProperty('--py', `${(event.clientY / Math.max(innerHeight, 1) - .5) * 2}`)
      })
    }
    window.addEventListener('pointermove', onMove, { passive: true })
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('pointermove', onMove)
      document.body.classList.remove('landing-mode')
    }
  }, [])

  const scrollToProducts = () => document.getElementById('products')?.scrollIntoView({ behavior: 'smooth', block: 'start' })

  return (
    <div ref={rootRef} className="landing-shell">
      <div className="landing-stars landing-stars-a"/><div className="landing-stars landing-stars-b"/>
      <div className="landing-pointer-glow"/><div className="landing-aurora aurora-left"/><div className="landing-aurora aurora-right"/>
      <header className="landing-nav">
        <a className="landing-brand" href="/" aria-label="XORA home"><span className="landing-logo-image"/><div><strong>XORA</strong><small>AI TRADING INTELLIGENCE</small></div></a>
        <nav className="landing-nav-links" aria-label="Landing navigation">
          <a href="#home">Home</a><button onClick={scrollToProducts}>Products⌄</button><a href="#features">Features</a><a href="#ecosystem">Ecosystem</a><a href="#about">About</a>
        </nav>
        <div className="landing-nav-actions"><a className="landing-ghost-btn" href="/charts">Charts AI</a><a className="landing-primary-btn compact" href="/charts">Get Started <ArrowIcon/></a></div>
      </header>

      <main>
        <section id="home" className="landing-hero landing-container reveal-in">
          <div className="hero-orbit orbit-one"/><div className="hero-orbit orbit-two"/>
          <span className="hero-x-watermark landing-logo-image" aria-hidden="true"/>
          <div className="hero-kicker">ONE INTELLIGENCE ECOSYSTEM · TWO SPECIALIZED EXPERIENCES</div>
          <h1><span>XORA</span></h1>
          <h2>AI INTELLIGENCE FOR <b>EVERY TRADING DECISION</b></h2>
          <p>Analyze smarter with XORA Charts AI. Trade, monitor and review with XORA App AI. One neon intelligence layer built around explainability, risk and control.</p>
          <div className="hero-actions"><a className="landing-primary-btn" href="/charts">Launch XORA Charts AI <ArrowIcon/></a><button className="landing-ghost-btn" onClick={scrollToProducts}>Explore the ecosystem</button></div>
          <div className="hero-scan-line"><span/><i/><b/></div>
        </section>

        <section id="products" className="landing-container product-section">
          <div className="product-grid">
            <article className="product-card product-chart-card">
              <div className="product-glow"/>
              <div className="product-title-row"><span className="product-icon landing-logo-image"/><div><h3><b>XORA</b> CHARTS AI</h3><p>AI Pattern Recognition &amp; Chart Intelligence</p></div></div>
              <div className="product-pill">SEE BEFORE YOU TRADE</div>
              <p className="product-copy">Discover high-probability chart structures with live analysis, matched references, confidence scoring and a direct review workflow.</p>
              <ChartPreview/>
              <div className="chart-feature-strip">
                <ProductFeature type="scan">20-Coin<br/>Smart Scan</ProductFeature><ProductFeature type="chart">10 Pattern<br/>Knowledge</ProductFeature><ProductFeature>AI Match<br/>&amp; Confidence</ProductFeature><ProductFeature type="shield">Risk / Reward<br/>Analysis</ProductFeature>
              </div>
              <div className="product-actions"><a className="landing-primary-btn" href="/charts">Launch XORA Charts AI <ArrowIcon/></a><a className="landing-ghost-btn" href="#charts-details">Explore Charts AI</a></div>
            </article>

            <article id="app-ai" className="product-card product-app-card">
              <div className="product-glow"/>
              <div className="product-title-row"><span className="product-icon landing-logo-image"/><div><h3><b>XORA</b> APP AI</h3><p>AI Trading Assistant for Android</p></div></div>
              <div className="product-pill violet">TRADE. AUTOMATE. GROW.</div>
              <p className="product-copy">A mobile-first AI trading workspace for discovering, validating, approving, executing, monitoring and reviewing opportunities.</p>
              <div className="app-product-body">
                <AppPhone/>
                <div className="app-feature-list">{appFeatures.map(([title,copy],i)=><div key={title}><span className="app-feature-icon"><FeatureIcon type={i===3?'shield':i===4?'chart':'spark'}/></span><div><strong>{title}</strong><small>{copy}</small></div></div>)}</div>
              </div>
              <div className="product-actions"><a className="landing-primary-btn" href="#app-details">Explore XORA App AI <ArrowIcon/></a><a className="landing-ghost-btn" href="#ecosystem">See ecosystem flow</a></div>
            </article>
          </div>
          <div className="product-bridge" aria-hidden="true"><span className="bridge-line left"/><span className="bridge-core landing-logo-image"/><span className="bridge-line right"/></div>
        </section>

        <section id="ecosystem" className="landing-container ecosystem-section">
          <div className="section-heading"><span>ONE <b>ECOSYSTEM.</b> ENDLESS ADVANTAGE.</span><p>Market intelligence flows from discovery to review without hiding the evidence behind the decision.</p></div>
          <div className="ecosystem-flow">
            <div className="eco-label"><span>◈</span><b>Market<br/>Data</b></div><div className="eco-arrow">→</div>
            <div className="eco-card cyan"><strong>XORA CHARTS AI</strong><p>Find &amp; analyze high-probability chart patterns</p><div className="eco-bars"><i/><i/><i/><i/><i/></div></div><div className="eco-arrow cyan-text">→</div>
            <div className="eco-core landing-logo-image"/><div className="eco-arrow violet-text">→</div>
            <div className="eco-card violet"><strong>XORA APP AI</strong><p>Execute, manage &amp; optimize trades seamlessly</p><div className="eco-phone-mini"/></div><div className="eco-arrow violet-text">→</div>
            <div className="eco-label"><span>↗</span><b>Better Process<br/>Stronger Decisions</b></div>
          </div>
          <div className="ecosystem-tags"><span>AI Insights</span><i/> <span>Real-time Data</span><i/> <span>Smart Execution</span><i/> <span>Continuous Review</span></div>
        </section>

        <section id="features" className="landing-container capability-section">
          <div className="capability-grid">
            <div><span>20</span><strong>Unique Coins</strong><small>Four non-overlapping scan cohorts</small></div>
            <div><span>10</span><strong>Pattern Guides</strong><small>Visual Knowledge catalog</small></div>
            <div><span>LIVE</span><strong>Market Feed</strong><small>REST history + WebSocket live data</small></div>
            <div><span>AI</span><strong>Explainable Review</strong><small>Evidence beside the decision</small></div>
            <div><span>RISK</span><strong>Risk-First</strong><small>Guardrails before execution</small></div>
          </div>
        </section>

        <section id="charts-details" className="landing-container details-section">
          <div className="detail-panel detail-panel-cyan">
            <div className="detail-copy"><span>XORA CHARTS AI</span><h3>Pattern intelligence that stays connected to the chart.</h3><p>Matched coins move into a dedicated review experience with pattern geometry, confidence, market analytics, the decision engine and trade plan in one place.</p><a href="/charts" className="landing-primary-btn">Open Charts AI <ArrowIcon/></a></div>
            <div className="detail-feature-grid">{chartFeatures.map(([title,copy])=><div key={title}><strong>{title}</strong><small>{copy}</small></div>)}</div>
          </div>
        </section>

        <section id="app-details" className="landing-container details-section">
          <div className="detail-panel detail-panel-violet">
            <div className="detail-copy"><span>XORA APP AI</span><h3>The broader AI-assisted trading lifecycle in your pocket.</h3><p>Signals, Scout/Chasing, active trade monitoring, history, risk controls and analytics form the mobile workspace around XORA's server-owned trading intelligence.</p><a href="#products" className="landing-primary-btn">View App AI showcase <ArrowIcon/></a></div>
            <div className="detail-feature-grid">{appFeatures.slice(0,4).map(([title,copy])=><div key={title}><strong>{title}</strong><small>{copy}</small></div>)}</div>
          </div>
        </section>

        <section id="about" className="landing-container landing-cta">
          <span className="cta-logo landing-logo-image"/><div><h3>READY TO ELEVATE YOUR TRADING WORKFLOW?</h3><p>Start with XORA Charts AI and move from discovery to evidence-driven review.</p></div><a href="/charts" className="landing-primary-btn">Launch XORA Charts AI <ArrowIcon/></a>
        </section>
      </main>

      <footer className="landing-footer landing-container">
        <div className="footer-brand"><div className="landing-brand"><span className="landing-logo-image"/><div><strong>XORA</strong><small>AI TRADING INTELLIGENCE</small></div></div><p>AI trading intelligence designed to make discovery, analysis and risk decisions easier to understand.</p><small>© 2026 XORA · XTinex</small></div>
        <div><strong>PRODUCTS</strong><a href="/charts">XORA Charts AI</a><a href="#app-details">XORA App AI</a></div>
        <div><strong>PLATFORM</strong><a href="#features">Features</a><a href="#ecosystem">Ecosystem</a><a href="#about">About</a></div>
        <div><strong>RESOURCES</strong><a href="/charts">Knowledge</a><a href="/charts">Analytics</a><a href="/charts">Settings</a></div>
      </footer>
    </div>
  )
}
