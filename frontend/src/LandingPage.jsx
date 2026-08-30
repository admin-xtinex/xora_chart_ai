import { useEffect, useRef } from 'react'

export default function LandingPage() {
  const videoRef = useRef(null)

  useEffect(() => {
    document.body.classList.add('xora-home')
    const video = videoRef.current
    if (!video) return () => document.body.classList.remove('xora-home')
    const play = () => video.play().catch(() => undefined)
    play()
    video.addEventListener('canplay', play)
    const onVis = () => (document.hidden ? video.pause() : play())
    document.addEventListener('visibilitychange', onVis)
    return () => {
      video.removeEventListener('canplay', play)
      document.removeEventListener('visibilitychange', onVis)
      document.body.classList.remove('xora-home')
    }
  }, [])

  return (
    <div className="xh">
      {/* Animated Background */}
      <div className="xh-background" aria-hidden="true">
        <div className="xh-background-video">
          <video ref={videoRef} muted loop playsInline autoPlay preload="metadata" poster="/xora-scene.jpg">
            <source src="/xora-loop.mp4" type="video/mp4" />
          </video>
        </div>
        <div className="xh-background-overlay">
          {/* Red bearish market flow (left) */}
          <div className="xh-flow bearish"></div>
          {/* Blue bullish market flow (right) */}
          <div className="xh-flow bullish"></div>
          {/* Subtle moving particles */}
          <div className="xh-particles"></div>
          {/* Animated chart lines / candlesticks */}
          <div className="xh-charts"></div>
          {/* Glowing AI brain / neural network feel */}
          <div className="xh-neural"></div>
        </div>
        <div className="xh-grade" />
        <div className="xh-scrim" />
      </div>

      {/* Header / Navigation */}
      <header className="xh-nav">
        <div className="xh-brand">
          <img src="/xtinex-x.png" alt="XTINEX" width="32" height="32" />
          <div>
            <span className="xh-brand-main">XORA</span>
            <span className="xh-brand-sub">by XTINEX</span>
          </div>
        </div>
        <nav>
          <a href="#features">Features</a>
          <a href="#how-it-works">How It Works</a>
          <a href="#capabilities">Capabilities</a>
          <a href="https://www.xtinex.com" target="_blank" rel="noopener noreferrer">XTINEX</a>
        </nav>
        <a className="xh-pill" href="/charts">
          Launch Charts AI
        </a>
      </header>

      {/* Hero Section */}
      <section className="xh-hero" id="home">
        <p className="xh-kicker">XORA · First product of XTINEX</p>
        <h1>AI-Powered Trading Intelligence</h1>
        <p className="xh-lead">
          Advanced pattern recognition and market analysis that reads the market
          so you can see the opportunity.
        </p>
        <div className="xh-actions">
          <a className="xh-pill" href="/charts">
            Launch Charts AI
          </a>
          <a className="xh-ghost" href="#capabilities">
            Learn More
          </a>
        </div>
      </section>

      {/* Short Feature Strip */}
      <section className="xh-strip">
        <div className="xh-strip-item">
          <h3>Pattern Intelligence</h3>
          <p>Advanced AI that detects chart patterns with reference-verified accuracy.</p>
        </div>
        <div className="xh-strip-item">
          <h3>Real-Time Analysis</h3>
          <p>Live market data processing with sub-second pattern recognition.</p>
        </div>
        <div className="xh-strip-item">
          <h3>Risk Management</h3>
          <p>Built-in risk/reward calculations and position sizing guidance.</p>
        </div>
      </section>

      {/* 3 Core Feature Cards */}
      <section className="xh-features">
        <div className="xh-feature-card">
          <div className="xh-feature-icon">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <h3>Pattern Recognition</h3>
          <p>AI-powered pattern detection with reference-verified accuracy for reliable trading signals.</p>
        </div>
        <div className="xh-feature-card">
          <div className="xh-feature-icon">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 2v2M12 20v2M2 12h2M20 12h2"/>
              <path d="M5.64 5.64l1.42 1.42M16.95 16.95l1.42 1.42M5.64 18.36l1.42-1.42M16.95 5.64l1.42-1.42"/>
            </svg>
          </div>
          <h3>Live Market Analysis</h3>
          <p>Real-time processing of market data streams for instant pattern recognition and analysis.</p>
        </div>
        <div className="xh-feature-card">
          <div className="xh-feature-icon">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 11l3 3m0 0l3-3m-3 3V3"/>
              <path d="M3 3h18"/>
            </svg>
          </div>
          <h3>Trade Execution</h3>
          <p>Seamless trade execution with demo and live modes, risk management, and position tracking.</p>
        </div>
      </section>

      {/* How XORA Works Section */}
      <section className="xh-how-it-works" id="how-it-works">
        <h2>How XORA Works</h2>
        <div className="xh-how-grid">
          <div className="xh-how-step">
            <h3>1. Market Scan</h3>
            <p>XORA continuously scans multiple timeframes and symbols to identify potential trading opportunities using advanced pattern recognition algorithms.</p>
          </div>
          <div className="xh-how-step">
            <h3>2. Pattern Match</h3>
            <p>Detected patterns are matched against a library of reference patterns with verification to ensure accuracy and reliability.</p>
          </div>
          <div className="xh-how-step">
            <h3>3. Analysis & Decision</h3>
            <p>Technical analysis, market evidence scoring, and decision engine evaluate the opportunity for actionable trading setups.</p>
          </div>
          <div className="xh-how-step">
            <h3>4. Trade Execution</h3>
            <p>Approved setups can be executed as demo trades for testing or live trades with proper risk management and position sizing.</p>
          </div>
        </div>
      </section>

      {/* Capabilities / Benefits Section */}
      <section className="xh-capabilities" id="capabilities">
        <h2>Key Capabilities</h2>
        <div className="xh-capabilities-grid">
          <div className="xh-capability">
            <h3>Multi-Timeframe Analysis</h3>
            <p>Analyzes patterns across multiple timeframes from 1-minute to 4-hour charts for comprehensive market view.</p>
          </div>
          <div className="xh-capability">
            <h3>Reference-Verified Patterns</h3>
            <p>Every pattern match is verified against reference charts to ensure accuracy and reduce false signals.</p>
          </div>
          <div className="xh-capability">
            <h3>Risk/Reward Optimization</h3>
            <p>Automatic calculation of optimal stop loss and take profit levels based on pattern structure and market volatility.</p>
          </div>
          <div className="xh-capability">
            <h3>Real-Time Alerts</h3>
            <p>Instant notifications when high-probability patterns are detected matching your criteria.</p>
          </div>
          <div className="xh-capability">
            <h3>Performance Tracking</h3>
            <p>Comprehensive trade journaling and analytics to track performance and improve trading decisions.</p>
          </div>
          <div className="xh-capability">
            <h3>Educational Resources</h3>
            <p>Access to pattern guides, trading education, and market analysis resources to improve your skills.</p>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="xh-cta">
        <h2>Ready to Trade with AI Intelligence?</h2>
        <p>Join traders who are using XORA to see market opportunities more clearly and trade with greater confidence.</p>
        <div className="xh-cta-actions">
          <a className="xh-pill" href="/charts">
            Launch XORA Charts AI
          </a>
          <a className="xh-ghost" href="https://www.xtinex.com" target="_blank" rel="noopener noreferrer">
            Learn About XTINEX
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className="xh-foot">
        <div className="xh-foot-content">
          <p>
            XORA is a product of <a href="https://www.xtinex.com" target="_blank" rel="noopener noreferrer">XTINEX</a>,
            a company dedicated to developing advanced financial technology solutions.
          </p>
          <p className="xh-foot-disclaimer">
            Trading involves risk. Past performance is not indicative of future results.
            Please trade responsibly and consider seeking advice from financial professionals.
          </p>
        </div>
      </footer>
    </div>
  )
}