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
    const onVis = () => {
      if (document.hidden) video.pause()
      else play()
    }
    document.addEventListener('visibilitychange', onVis)
    return () => {
      video.removeEventListener('canplay', play)
      document.removeEventListener('visibilitychange', onVis)
      document.body.classList.remove('xora-home')
    }
  }, [])

  return (
    <div className="xh">
      <header className="xh-nav">
        <a className="xh-brand" href="/" aria-label="XORA">
          <img src="/xtinex-x.png" alt="" width="320" height="205" />
          <span>XORA</span>
        </a>
        <nav>
          <a href="https://www.xtinex.com">XTINEX</a>
          <a href="/charts">Charts</a>
        </nav>
        <a className="xh-pill compact" href="/charts">
          Open Charts
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <path d="M7 17 17 7" />
            <path d="M9 7h8v8" />
          </svg>
        </a>
      </header>

      <section className="xh-stage">
        <div className="xh-media" aria-hidden="true">
          <img src="/xora-scene.jpg" alt="" />
          <video
            ref={videoRef}
            muted
            loop
            playsInline
            autoPlay
            preload="metadata"
            poster="/xora-scene.jpg"
          >
            <source src="/xora-loop.mp4" type="video/mp4" />
          </video>
          <div className="xh-scrim" />
        </div>

        <div className="xh-copy">
          <div className="xh-kicker">
            <i />
            Our first product
          </div>
          <h1>XORA</h1>
          <p className="xh-lead">
            AI that reads the market.
            <br />
            So you can see the opportunity.
          </p>
          <ol>
            <li>
              <i className="swatch noise" /> Losing trades
            </li>
            <li>
              <i className="swatch brain" /> XORA brain
            </li>
            <li>
              <i className="swatch clear" /> Profit
            </li>
          </ol>
          <a className="xh-pill" href="/charts">
            Explore XORA
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <path d="M7 17 17 7" />
              <path d="M9 7h8v8" />
            </svg>
          </a>
        </div>
      </section>
    </div>
  )
}
