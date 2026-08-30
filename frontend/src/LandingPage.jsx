import { useEffect, useRef } from 'react'

function Arrow() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M7 17 17 7" />
      <path d="M9 7h8v8" />
    </svg>
  )
}

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
      <div className="xh-film" aria-hidden="true">
        <img src="/xora-scene.jpg" alt="" />
        <video ref={videoRef} muted loop playsInline autoPlay preload="metadata" poster="/xora-scene.jpg">
          <source src="/xora-loop.mp4" type="video/mp4" />
        </video>
        <div className="xh-grade" />
        <div className="xh-scrim" />
      </div>

      <header className="xh-nav">
        <a className="xh-brand" href="/" aria-label="XORA">
          <img src="/xtinex-x.png" alt="" width="320" height="205" />
          <span>XORA</span>
        </a>
        <nav>
          <a href="#products">Products</a>
          <a href="https://www.xtinex.com">XTINEX</a>
        </nav>
        <a className="xh-pill compact" href="/charts">
          Launch Charts AI <Arrow />
        </a>
      </header>

      <section className="xh-hero" id="home">
        <p className="xh-kicker">XORA · First product of XTINEX</p>
        <h1>XORA</h1>
        <p className="xh-lead">
          AI that reads the market.
          <br />
          So you can see the opportunity.
        </p>
        <ol className="xh-flow">
          <li><i className="dot loss" /> Losing trades</li>
          <li><i className="dot brain" /> XORA brain</li>
          <li><i className="dot win" /> Profit</li>
        </ol>
        <div className="xh-actions">
          <a className="xh-pill" href="/charts">Launch Charts AI <Arrow /></a>
          <a className="xh-ghost" href="/app/">Open App AI</a>
        </div>
      </section>

      <section className="xh-products" id="products">
        <article className="xh-card">
          <span>XORA CHARTS AI</span>
          <h2>See the structure before you trade.</h2>
          <p>Pattern intelligence, matched references and confidence on the chart.</p>
          <a className="xh-pill compact" href="/charts">Launch Charts AI <Arrow /></a>
        </article>
        <article className="xh-card">
          <span>XORA APP AI</span>
          <h2>Trade, monitor and review.</h2>
          <p>A mobile workspace around the same intelligence layer.</p>
          <a className="xh-ghost" href="/app/">Open App AI</a>
        </article>
      </section>

      <footer className="xh-foot">
        <p>Built by <a href="https://www.xtinex.com">XTINEX</a></p>
      </footer>
    </div>
  )
}
