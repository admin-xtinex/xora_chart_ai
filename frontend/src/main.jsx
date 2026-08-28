import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import LandingPage from './LandingPage.jsx'
import './index.css'
import './landing-base.css'
import './landing-products.css'
import './landing-sections.css'
import './dashboard-future.css'
import './xora-home.css'

function RootExperience() {
  const path = window.location.pathname.replace(/\/+$/, '') || '/'
  const isCharts = path === '/charts' || path === '/dashboard' || path.startsWith('/charts/') || path.startsWith('/dashboard/')
  return isCharts ? <App /> : <LandingPage />
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <RootExperience />
  </React.StrictMode>,
)
