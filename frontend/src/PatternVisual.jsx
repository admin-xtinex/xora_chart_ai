const diagrams = {
  breakout_retest: {
    points: '12,82 38,64 62,68 88,42 112,40 130,48 146,39 170,16',
    levels: [{ y: 46, label: 'resistance → support' }],
    marks: [{ x: 126, y: 48, label: 'retest' }],
  },
  breakdown_retest: {
    points: '12,22 38,38 62,34 88,60 112,62 130,52 146,62 170,86',
    levels: [{ y: 55, label: 'support → resistance' }],
    marks: [{ x: 130, y: 52, label: 'retest' }],
  },
  head_and_shoulders: {
    points: '12,78 32,46 54,68 84,18 112,68 138,44 166,82',
    levels: [{ y: 68, label: 'neckline' }],
    marks: [
      { x: 32, y: 46, label: 'LS' },
      { x: 84, y: 18, label: 'H' },
      { x: 138, y: 44, label: 'RS' },
    ],
  },
  double_top: {
    points: '12,80 40,30 62,64 86,32 112,66 142,70 170,88',
    levels: [{ y: 65, label: 'neckline' }],
    marks: [{ x: 40, y: 30, label: 'T1' }, { x: 86, y: 32, label: 'T2' }],
  },
  double_bottom: {
    points: '12,20 40,72 62,40 88,70 112,38 142,30 170,12',
    levels: [{ y: 39, label: 'neckline' }],
    marks: [{ x: 40, y: 72, label: 'B1' }, { x: 88, y: 70, label: 'B2' }],
  },
  cup_and_handle: {
    points: '12,30 34,58 58,76 82,78 106,58 126,30 140,44 152,40 170,16',
    levels: [{ y: 31, label: 'rim' }],
    marks: [{ x: 146, y: 42, label: 'handle' }],
  },
  bull_flag: {
    points: '12,82 42,18 60,34 78,28 96,42 114,36 132,50 150,44 170,16',
    channels: [
      '55,27 151,39',
      '60,43 151,55',
    ],
  },
  bear_flag: {
    points: '12,18 42,82 60,66 78,72 96,58 114,64 132,50 150,56 170,84',
    channels: [
      '55,61 151,45',
      '60,77 151,61',
    ],
  },
  bull_pennant: {
    points: '12,82 42,18 62,38 80,30 98,46 116,38 134,52 150,46 170,16',
    channels: [
      '58,28 150,47',
      '58,52 150,47',
    ],
  },
  bear_pennant: {
    points: '12,18 42,82 62,62 80,70 98,54 116,62 134,48 150,54 170,84',
    channels: [
      '58,72 150,53',
      '58,48 150,53',
    ],
  },
}

export default function PatternVisual({ patternKey, direction = 'bullish', compact = false }) {
  const d = diagrams[patternKey] || diagrams.breakout_retest
  const bullish = direction === 'bullish'
  const stroke = bullish ? '#34d399' : '#fb7185'
  const guide = '#67e8f9'
  const height = compact ? 108 : 180

  return (
    <div className="pattern-visual" style={{ height }} aria-label={`${patternKey} diagram`}>
      <svg viewBox="0 0 184 100" preserveAspectRatio="none" role="img">
        <line x1="8" x2="176" y1="90" y2="90" stroke="rgba(148,163,184,.12)" />
        {(d.levels || []).map((level) => (
          <g key={`${level.y}-${level.label}`}>
            <line x1="10" x2="174" y1={level.y} y2={level.y} stroke={guide} strokeOpacity=".72" strokeDasharray="4 4" />
            {!compact && <text x="12" y={level.y - 4} fill="#94a3b8" fontSize="6">{level.label}</text>}
          </g>
        ))}
        {(d.channels || []).map((points) => {
          const [a, b] = points.split(' ')
          const [x1, y1] = a.split(',')
          const [x2, y2] = b.split(',')
          return <line key={points} x1={x1} y1={y1} x2={x2} y2={y2} stroke={guide} strokeOpacity=".78" strokeDasharray="4 4" />
        })}
        <polyline points={d.points} fill="none" stroke={stroke} strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" />
        {(d.marks || []).map((mark) => (
          <g key={`${mark.x}-${mark.label}`}>
            <circle cx={mark.x} cy={mark.y} r="3.4" fill="#08111f" stroke={stroke} strokeWidth="1.5" />
            {!compact && <text x={mark.x} y={Math.max(8, mark.y - 7)} textAnchor="middle" fill="#cbd5e1" fontSize="6.5">{mark.label}</text>}
          </g>
        ))}
        <path d={bullish ? 'M158 22 L174 10 M174 10 L168 22 M174 10 L162 12' : 'M158 78 L174 90 M174 90 L168 78 M174 90 L162 88'} fill="none" stroke={stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  )
}
