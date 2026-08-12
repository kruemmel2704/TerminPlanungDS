import React, { createContext, useContext, useState, useEffect } from 'react'
import { HashRouter as Router, Routes, Route, Link, useNavigate, useParams } from 'react-router-dom'

// --- TYPES ---
interface User {
  id: number
  discord_id: string
  username: string
  avatar: string | null
  is_admin: boolean
  whatsapp_chat_id: string | null
  whatsapp_chat_name: string | null
  whatsapp_admin_chat_id: string | null
  whatsapp_admin_chat_name: string | null
  google_calendar_id: string | null
  google_token: string | null
}

interface AuthContextType {
  user: User | null
  loading: boolean
  checkAuth: () => Promise<void>
  logout: () => Promise<void>
}

interface Vote {
  id: number
  option_id: number
  user_id: number
  user_name: string
  is_whatsapp: boolean
}

interface Option {
  id: number
  poll_id: number
  start_time: string // ISO string
  end_time: string // ISO string
  votes: Vote[]
}

interface Poll {
  id: number
  title: string
  description: string
  created_at: string
  deadline: string
  is_active: boolean
  status: 'voting' | 'pending' | 'finalized'
  poll_type: 'single' | 'liga'
  winner_option_id: number | null
  war_orga: string | null
  players: string | null
  substitutes: string | null
  options: Option[]
  unique_voter_count: number
  unique_voter_names: string[]
}

interface Group {
  id: string
  name: string
}

interface WhatsAppStatus {
  status: string
  qr_data: string | null
  groups: Group[]
  configured: boolean
}

// --- CONTEXT ---
const AuthContext = createContext<AuthContextType | undefined>(undefined)

const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within an AuthProvider')
  return context
}

// --- UTILS ---
const formatDate = (dateStr: string) => {
  const d = new Date(dateStr)
  return d.toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatDateShort = (dateStr: string) => {
  const d = new Date(dateStr)
  return d.toLocaleDateString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  })
}

// --- APP COMPONENT ---
export default function App() {
  return (
    <AuthProvider>
      <Router>
        <Layout>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<ProtectedRoute><HomePage /></ProtectedRoute>} />
            <Route path="/vote/:id" element={<ProtectedRoute><VotePage /></ProtectedRoute>} />
            <Route path="/results/:id" element={<ProtectedRoute><ResultsPage /></ProtectedRoute>} />
            <Route path="/admin" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
            <Route path="/admin/confirm/:id" element={<AdminRoute><ConfirmPollPage /></AdminRoute>} />
            <Route path="/admin/reset/:id" element={<AdminRoute><ResetPollPage /></AdminRoute>} />
            <Route path="/whatsapp" element={<AdminRoute><WhatsAppDashboard /></AdminRoute>} />
          </Routes>
        </Layout>
      </Router>
    </AuthProvider>
  )
}

// --- AUTH PROVIDER ---
function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const checkAuth = async () => {
    try {
      const res = await fetch('/api/auth/status')
      const data = await res.json()
      if (data.authenticated) {
        setUser(data.user)
      } else {
        setUser(null)
      }
    } catch (err) {
      console.error('Auth check failed:', err)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  const logout = async () => {
    try {
      await fetch('/api/auth/logout')
      setUser(null)
    } catch (err) {
      console.error('Logout failed:', err)
    }
  }

  useEffect(() => {
    checkAuth()
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, checkAuth, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// --- PROTECTED ROUTES ---
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()

  if (loading) return <div className="container text-center"><p>Laden...</p></div>
  if (!user) return <LoginPage />

  return <>{children}</>
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()

  if (loading) return <div className="container text-center"><p>Laden...</p></div>
  if (!user) return <LoginPage />
  if (!user.is_admin) {
    return (
      <div className="container text-center">
        <div className="flash error">Kein Zugriff! Du bist kein Admin.</div>
        <Link to="/" className="btn btn-primary">Zurück zur Startseite</Link>
      </div>
    )
  }

  return <>{children}</>
}

// --- LAYOUT ---
function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async (e: React.MouseEvent) => {
    e.preventDefault()
    await logout()
    navigate('/login')
  }

  return (
    <>
      <nav>
        <Link to="/" className="logo">LIGA PLANER</Link>
        <div className="nav-links">
          <Link to="/">Home</Link>
          {user?.is_admin && (
            <>
              <Link to="/admin">Admin</Link>
              <Link to="/whatsapp">WhatsApp</Link>
            </>
          )}
          {user ? (
            <>
              <span style={{ marginLeft: '1rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                {user.avatar && (
                  <img
                    src={`https://cdn.discordapp.com/avatars/${user.discord_id}/${user.avatar}.png`}
                    alt={user.username}
                    style={{ width: 24, height: 24, borderRadius: '50%' }}
                  />
                )}
                {user.username}
              </span>
              <a href="#" onClick={handleLogout}>Abmelden</a>
            </>
          ) : (
            <a href="/login" className="btn btn-outline" style={{ padding: '0.4rem 1rem' }}>Discord Login</a>
          )}
        </div>
      </nav>
      <div className="container">
        {children}
      </div>
    </>
  )
}

// --- PAGES ---

// 1. Login Page
function LoginPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (user) navigate('/')
  }, [user, navigate])

  const handleDiscordLogin = () => {
    window.location.href = '/login'
  }

  return (
    <div className="auth-container">
      <div className="card login-card">
        <div className="login-icon">📅</div>
        <h2>Liga Termin Planer</h2>
        <p style={{ margin: '1rem 0 2rem 0', color: 'var(--text-muted)' }}>
          Melde dich mit deinem Discord-Account an, um an Terminabstimmungen teilzunehmen.
        </p>
        <button onClick={handleDiscordLogin} className="btn btn-primary" style={{ width: '100%' }}>
          Mit Discord anmelden
        </button>
      </div>
    </div>
  )
}

// 2. Home Page
function HomePage() {
  const [polls, setPolls] = useState<Poll[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/polls')
      .then((res) => res.json())
      .then((data) => {
        setPolls(data)
        setLoading(false)
      })
      .catch(() => {
        setError('Fehler beim Laden der Abstimmungen.')
        setLoading(false)
      })
  }, [])

  if (loading) return <p className="text-center">Abstimmungen werden geladen...</p>
  if (error) return <div className="flash error">{error}</div>

  const activePolls = polls.filter(p => p.is_active)
  const finishedPolls = polls.filter(p => !p.is_active)

  return (
    <div>
      <h1 className="mb-2">Aktive Abstimmungen</h1>
      {activePolls.length === 0 ? (
        <p style={{ color: 'var(--text-muted)', marginBottom: '3rem' }}>Aktuell gibt es keine aktiven Abstimmungen.</p>
      ) : (
        activePolls.map((poll) => (
          <div key={poll.id} className="card poll-card">
            <div>
              <span className={`badge badge-${poll.poll_type}`}>
                {poll.poll_type === 'liga' ? 'Liga' : 'TCW'}
              </span>
              <h3>{poll.title}</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>{poll.description}</p>
              <p style={{ fontSize: '0.85rem', marginTop: '0.5rem' }}>
                ⏳ Deadline: <strong style={{ color: 'var(--primary-color)' }}>{formatDate(poll.deadline)}</strong>
              </p>
            </div>
            <div>
              <Link to={`/vote/${poll.id}`} className="btn btn-primary">Abstimmen</Link>
            </div>
          </div>
        ))
      )}

      {finishedPolls.length > 0 && (
        <>
          <h2 className="mb-2" style={{ marginTop: '3rem' }}>Abgeschlossene Events</h2>
          {finishedPolls.map((poll) => (
            <div key={poll.id} className="card poll-card">
              <div>
                <span className="badge" style={{ backgroundColor: '#555', color: 'white' }}>Inaktiv</span>
                <h3>{poll.title}</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>{poll.description}</p>
              </div>
              <div>
                <Link to={`/results/${poll.id}`} className="btn btn-outline">Ergebnisse sehen</Link>
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  )
}

// 3. Vote Page
function VotePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [poll, setPoll] = useState<Poll | null>(null)
  const [selectedOptionIds, setSelectedOptionIds] = useState<number[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  useEffect(() => {
    fetch(`/api/polls/${id}`)
      .then((res) => {
        if (!res.ok) throw new Error()
        return res.json()
      })
      .then((data) => {
        setPoll(data)
        setLoading(false)
      })
      .catch(() => {
        setMessage({ type: 'error', text: 'Abstimmung konnte nicht geladen werden.' })
        setLoading(false)
      })
  }, [id])

  if (loading) return <p className="text-center">Abstimmung wird geladen...</p>
  if (!poll) return <div className="flash error">{message?.text || 'Abstimmung nicht gefunden.'}</div>

  const handleOptionChange = (optionId: number) => {
    setSelectedOptionIds(prev =>
      prev.includes(optionId) ? prev.filter(oid => oid !== optionId) : [...prev, optionId]
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (selectedOptionIds.length === 0) {
      setMessage({ type: 'error', text: 'Bitte wähle mindestens einen Termin aus!' })
      return
    }
    setSubmitting(true)
    setMessage(null)

    try {
      const res = await fetch(`/api/polls/${poll.id}/vote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ option_ids: selectedOptionIds })
      })
      const result = await res.json()

      if (res.ok) {
        setMessage({ type: 'success', text: result.message })
        setTimeout(() => navigate('/'), 1500)
      } else {
        setMessage({ type: 'error', text: result.message || 'Fehler beim Abstimmen.' })
      }
    } catch {
      setMessage({ type: 'error', text: 'Netzwerkfehler.' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <Link to="/" style={{ color: 'var(--primary-color)', textDecoration: 'none', marginBottom: '1.5rem', display: 'inline-block' }}>
        ← Zurück
      </Link>
      <div className="card">
        <span className={`badge badge-${poll.poll_type}`}>
          {poll.poll_type === 'liga' ? 'Liga' : 'TCW'}
        </span>
        <h1 style={{ marginTop: '0.5rem' }}>{poll.title}</h1>
        <p style={{ color: 'var(--text-muted)', margin: '1rem 0' }}>{poll.description}</p>
        <p style={{ fontSize: '0.9rem', marginBottom: '2rem' }}>
          ⏳ Abgabe bis: <strong>{formatDate(poll.deadline)}</strong>
        </p>

        {message && <div className={`flash ${message.type}`}>{message.text}</div>}

        <form onSubmit={handleSubmit}>
          <p style={{ fontWeight: 600, marginBottom: '1rem' }}>Wähle deine verfügbaren Termine:</p>
          {poll.options.map((opt) => {
            const isChecked = selectedOptionIds.includes(opt.id)
            return (
              <label key={opt.id} className="option-item">
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => handleOptionChange(opt.id)}
                />
                <div>
                  <strong>{formatDateShort(opt.start_time)}</strong>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    {new Date(opt.start_time).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })} - {new Date(opt.end_time).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })} Uhr
                  </div>
                </div>
              </label>
            )
          })}
          <button type="submit" disabled={submitting} className="btn btn-primary" style={{ width: '100%', marginTop: '1.5rem' }}>
            {submitting ? 'Speichern...' : 'Stimme abgeben'}
          </button>
        </form>
      </div>
    </div>
  )
}

// 4. Results Page
function ResultsPage() {
  const { id } = useParams()
  const { user } = useAuth()
  const [poll, setPoll] = useState<Poll | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`/api/polls/${id}`)
      .then((res) => {
        if (!res.ok) throw new Error()
        return res.json()
      })
      .then((data) => {
        setPoll(data)
        setLoading(false)
      })
      .catch(() => {
        setError('Ergebnisse konnten nicht geladen werden.')
        setLoading(false)
      })
  }, [id])

  if (loading) return <p className="text-center">Ergebnisse werden geladen...</p>
  if (!poll) return <div className="flash error">{error || 'Event nicht gefunden.'}</div>

  // Calculate votes count and sorted data
  const resultsData = poll.options.map(opt => ({
    option: opt,
    votesCount: opt.votes.length,
    voters: opt.votes.map(v => v.user_name)
  })).sort((a, b) => b.votesCount - a.votesCount)

  const maxVotes = resultsData[0]?.votesCount || 0
  const winner = resultsData[0] || null

  return (
    <div>
      <Link to="/" style={{ color: 'var(--primary-color)', textDecoration: 'none', marginBottom: '1.5rem', display: 'inline-block' }}>
        ← Zurück zur Übersicht
      </Link>
      <div className="card">
        <h1 className="mb-2">Ergebnisse: {poll.title}</h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>{poll.description}</p>

        {poll.status === 'finalized' && (
          <div style={{ borderLeft: '4px solid var(--primary-color)', paddingLeft: '1rem', marginBottom: '2rem' }}>
            <h3 style={{ color: 'var(--primary-color)' }}>🛡️ Bestätigtes Roster</h3>
            <p style={{ marginTop: '0.5rem' }}><strong>War Orga:</strong> {poll.war_orga}</p>
            <p><strong>Spieler:</strong> {poll.players}</p>
            {poll.substitutes && <p><strong>Ersatz:</strong> {poll.substitutes}</p>}
          </div>
        )}

        {resultsData.map(({ option, votesCount, voters }) => {
          const percentage = maxVotes > 0 ? (votesCount / maxVotes) * 100 : 0
          const isWinner = winner && winner.option.id === option.id
          return (
            <div key={option.id} className="result-row">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <strong>{formatDateShort(option.start_time)}</strong> ({new Date(option.start_time).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })} - {new Date(option.end_time).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })} Uhr) {isWinner && <span className="winner-badge" style={{ marginLeft: '1rem', marginBottom: 0 }}>Gewinner</span>}
                </div>
                <div>
                  <strong>{votesCount} Stimme(n)</strong>
                </div>
              </div>
              <div className="progress-bar-bg">
                <div className="progress-bar-fill" style={{ width: `${percentage}%` }}></div>
              </div>
              {voters.length > 0 && (
                <div className="voters-list">
                  👤 Abgestimmt von: {voters.join(', ')}
                </div>
              )}
            </div>
          )
        })}

        {user?.is_admin && poll.status === 'pending' && (
          <div style={{ marginTop: '3rem' }}>
            <Link to={`/admin/confirm/${poll.id}`} className="btn btn-primary" style={{ marginRight: '1rem' }}>
              Roster erstellen / Kalender eintragen
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}

// 5. Admin Dashboard
function AdminDashboard() {
  const [activePolls, setActivePolls] = useState<Poll[]>([])
  const [finishedPolls, setFinishedPolls] = useState<Poll[]>([])
  const [loading, setLoading] = useState(true)

  // Form states
  const [pollType, setPollType] = useState<'single' | 'liga'>('single')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [deadline, setDeadline] = useState('')
  const [ligaStartDate, setLigaStartDate] = useState('')
  const [singleDates, setSingleDates] = useState<string[]>([''])

  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [googleCalendarId, setGoogleCalendarId] = useState<string | null>(null)
  const [hasGoogleToken, setHasGoogleToken] = useState(false)

  const loadData = async () => {
    try {
      const res = await fetch('/api/polls')
      const pollsData = await res.json()
      setActivePolls(pollsData.filter((p: Poll) => p.is_active))
      setFinishedPolls(pollsData.filter((p: Poll) => !p.is_active))

      const userRes = await fetch('/api/auth/status')
      const userData = await userRes.json()
      if (userData.authenticated) {
        setGoogleCalendarId(userData.user.google_calendar_id)
        setHasGoogleToken(!!userData.user.google_token)
      }
    } catch {
      console.error('Failed to load admin dashboard data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleAddSingleDate = () => {
    setSingleDates([...singleDates, ''])
  }

  const handleSingleDateChange = (index: number, val: string) => {
    const updated = [...singleDates]
    updated[index] = val
    setSingleDates(updated)
  }

  const handleRemoveSingleDate = (index: number) => {
    setSingleDates(singleDates.filter((_, i) => i !== index))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setMessage(null)

    if (!title || !deadline) {
      setMessage({ type: 'error', text: 'Titel und Deadline sind Pflichtfelder.' })
      return
    }

    const payload = {
      poll_type: pollType,
      title,
      description,
      deadline,
      liga_start_date: pollType === 'liga' ? ligaStartDate : null,
      single_dates: pollType === 'single' ? singleDates.filter(d => d) : []
    }

    try {
      const res = await fetch('/api/polls/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const result = await res.json()

      if (res.ok) {
        setMessage({ type: 'success', text: 'Abstimmung erfolgreich erstellt!' })
        setTitle('')
        setDescription('')
        setDeadline('')
        setLigaStartDate('')
        setSingleDates([''])
        loadData()
      } else {
        setMessage({ type: 'error', text: result.message || 'Fehler beim Erstellen.' })
      }
    } catch {
      setMessage({ type: 'error', text: 'Netzwerkfehler.' })
    }
  }

  const handleFinalize = async (pollId: number) => {
    if (!confirm('Möchtest du diese Abstimmung wirklich beenden?')) return
    try {
      const res = await fetch(`/api/polls/${pollId}/finalize`, { method: 'POST' })
      if (res.ok) {
        loadData()
      }
    } catch {
      alert('Fehler beim Beenden der Abstimmung')
    }
  }

  if (loading) return <p className="text-center">Dashboard wird geladen...</p>

  return (
    <div>
      <h1 className="mb-2">Admin Dashboard</h1>

      {/* Google Calendar Connection Status */}
      <div className="card">
        <h3>📅 Google Kalender Integration</h3>
        <p style={{ margin: '0.5rem 0', color: 'var(--text-muted)', fontSize: '0.95rem' }}>
          {hasGoogleToken
            ? `Verbunden! Kalender-ID: ${googleCalendarId || 'Wird beim ersten Event erstellt.'}`
            : 'Aktuell nicht mit Google Kalender verbunden. Roster-Bestätigungen können nicht eingetragen werden.'}
        </p>
        {!hasGoogleToken ? (
          <a href="/admin/connect-google" className="btn btn-outline mt-1">Mit Google verbinden</a>
        ) : (
          <a href="/admin/connect-google" className="btn btn-outline mt-1">Verbindung erneuern</a>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginTop: '2rem' }}>
        {/* Create Poll */}
        <div>
          <h2>Neue Abstimmung erstellen</h2>
          <form onSubmit={handleSubmit} className="card" style={{ marginTop: '1rem' }}>
            {message && <div className={`flash ${message.type}`}>{message.text}</div>}

            <div className="form-group">
              <label>Typ</label>
              <div className="type-selector">
                <div
                  className={`type-btn ${pollType === 'single' ? 'active' : ''}`}
                  onClick={() => setPollType('single')}
                >
                  TCW (Einzeltermine)
                </div>
                <div
                  className={`type-btn ${pollType === 'liga' ? 'active' : ''}`}
                  onClick={() => setPollType('liga')}
                >
                  Liga (5 Tage am Stück)
                </div>
              </div>
            </div>

            <div className="form-group">
              <label>Titel</label>
              <input type="text" value={title} onChange={e => setTitle(e.target.value)} required />
            </div>

            <div className="form-group">
              <label>Beschreibung</label>
              <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} />
            </div>

            <div className="form-group">
              <label>Deadline (Abgabefrist)</label>
              <input type="datetime-local" value={deadline} onChange={e => setDeadline(e.target.value)} required />
            </div>

            {pollType === 'liga' ? (
              <div className="form-group">
                <label>Liga Startdatum (Montag)</label>
                <input type="date" value={ligaStartDate} onChange={e => setLigaStartDate(e.target.value)} required />
              </div>
            ) : (
              <div className="form-group">
                <label>Einzelne Terminvorschläge</label>
                {singleDates.map((date, idx) => (
                  <div key={idx} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <input type="date" value={date} onChange={e => handleSingleDateChange(idx, e.target.value)} required />
                    {singleDates.length > 1 && (
                      <button type="button" onClick={() => handleRemoveSingleDate(idx)} className="btn btn-outline" style={{ padding: '0.5rem 1rem' }}>
                        ✕
                      </button>
                    )}
                  </div>
                ))}
                <button type="button" onClick={handleAddSingleDate} className="btn btn-outline mt-1" style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}>
                  + Termin hinzufügen
                </button>
              </div>
            )}

            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '1rem' }}>
              Abstimmung starten
            </button>
          </form>
        </div>

        {/* Manage Polls */}
        <div>
          <h2>Aktive Abstimmungen</h2>
          <div style={{ marginTop: '1rem' }}>
            {activePolls.length === 0 ? (
              <p style={{ color: 'var(--text-muted)' }}>Keine aktiven Abstimmungen.</p>
            ) : (
              activePolls.map(p => (
                <div key={p.id} className="card" style={{ padding: '1rem' }}>
                  <strong>{p.title}</strong>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: '0.3rem 0' }}>
                    Typ: {p.poll_type.toUpperCase()} | Deadline: {formatDate(p.deadline)}
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                    <Link to={`/vote/${p.id}`} className="btn btn-outline" style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}>Vorschau</Link>
                    <button onClick={() => handleFinalize(p.id)} className="btn btn-primary" style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}>Beenden</button>
                  </div>
                </div>
              ))
            )}
          </div>

          <h2 style={{ marginTop: '2rem' }}>Abgeschlossene Events</h2>
          <div style={{ marginTop: '1rem' }}>
            {finishedPolls.length === 0 ? (
              <p style={{ color: 'var(--text-muted)' }}>Keine beendeten Abstimmungen.</p>
            ) : (
              finishedPolls.map(p => (
                <div key={p.id} className="card" style={{ padding: '1rem' }}>
                  <strong>{p.title}</strong>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: '0.3rem 0' }}>
                    Status: <strong style={{ color: p.status === 'finalized' ? '#4caf50' : '#ff9800' }}>{p.status.toUpperCase()}</strong>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                    <Link to={`/results/${p.id}`} className="btn btn-outline" style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}>Ergebnisse</Link>
                    {p.status === 'pending' && (
                      <Link to={`/admin/confirm/${p.id}`} className="btn btn-primary" style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}>Roster eintragen</Link>
                    )}
                    <Link to={`/admin/reset/${p.id}`} className="btn btn-outline" style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem', color: '#ff9800', borderColor: '#ff9800' }}>Reset</Link>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// 6. Confirm Poll (Roster Creation) Page
function ConfirmPollPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [poll, setPoll] = useState<Poll | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error' | 'warning', text: string } | null>(null)

  // Fields
  const [warOrga, setWarOrga] = useState('')
  const [players, setPlayers] = useState('')
  const [substitutes, setSubstitutes] = useState('')
  const [finalStart, setFinalStart] = useState('')
  const [finalEnd, setFinalEnd] = useState('')

  useEffect(() => {
    fetch(`/api/polls/${id}`)
      .then(res => res.json())
      .then(data => {
        setPoll(data)
        // Pre-fill fields with best option if available
        const optionsSorted = data.options.map((opt: Option) => ({
          opt,
          votesCount: opt.votes.length
        })).sort((a: any, b: any) => b.votesCount - a.votesCount)

        const topOption = optionsSorted[0]?.opt
        if (topOption) {
          // Format ISO to datetime-local string (YYYY-MM-DDTHH:MM)
          const parseTime = (iso: string) => iso.slice(0, 16)
          setFinalStart(parseTime(topOption.start_time))
          setFinalEnd(parseTime(topOption.end_time))
        }

        setLoading(false)
      })
  }, [id])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setMessage(null)

    try {
      const res = await fetch(`/api/polls/${id}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          war_orga: warOrga,
          players,
          substitutes,
          final_start: finalStart,
          final_end: finalEnd
        })
      })
      const result = await res.json()

      if (res.ok) {
        setMessage({
          type: result.calendar_error ? 'warning' : 'success',
          text: result.message
        })
        setTimeout(() => navigate(`/results/${id}`), 2000)
      } else {
        setMessage({ type: 'error', text: result.message || 'Fehler beim Bestätigen.' })
      }
    } catch {
      setMessage({ type: 'error', text: 'Netzwerkfehler.' })
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <p className="text-center">Laden...</p>
  if (!poll) return <div className="flash error">Event nicht gefunden.</div>

  return (
    <div>
      <Link to="/admin" style={{ color: 'var(--primary-color)', textDecoration: 'none', marginBottom: '1.5rem', display: 'inline-block' }}>
        ← Zurück zum Admin Dashboard
      </Link>
      <div className="card" style={{ maxWidth: '600px', margin: '0 auto' }}>
        <h2>🛡️ Roster festlegen: {poll.title}</h2>
        <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
          Trage das endgültige Roster ein und wähle den finalen Spieltermin. Bei aktiver Google-Integration wird das Event in den Google-Kalender eingetragen.
        </p>

        {message && <div className={`flash ${message.type}`}>{message.text}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>War Orga</label>
            <input type="text" value={warOrga} onChange={e => setWarOrga(e.target.value)} placeholder="z.B. Kruemmel" required />
          </div>

          <div className="form-group">
            <label>Spieler (Roster)</label>
            <textarea value={players} onChange={e => setPlayers(e.target.value)} placeholder="z.B. Kruemmel, John, Doe" rows={3} required />
          </div>

          <div className="form-group">
            <label>Ersatzspieler</label>
            <textarea value={substitutes} onChange={e => setSubstitutes(e.target.value)} placeholder="z.B. SpielerA, SpielerB" rows={2} />
          </div>

          <div className="form-group">
            <label>Finaler Starttermin</label>
            <input type="datetime-local" value={finalStart} onChange={e => setFinalStart(e.target.value)} required />
          </div>

          <div className="form-group">
            <label>Finaler Endtermin</label>
            <input type="datetime-local" value={finalEnd} onChange={e => setFinalEnd(e.target.value)} required />
          </div>

          <button type="submit" disabled={submitting} className="btn btn-primary" style={{ width: '100%', marginTop: '1.5rem' }}>
            {submitting ? 'Speichern...' : 'Event bestätigen & in Kalender eintragen'}
          </button>
        </form>
      </div>
    </div>
  )
}

// 7. Reset Poll Page
function ResetPollPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [poll, setPoll] = useState<Poll | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [newDeadline, setNewDeadline] = useState('')
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  useEffect(() => {
    fetch(`/api/polls/${id}`)
      .then(res => res.json())
      .then(data => {
        setPoll(data)
        setLoading(false)
      })
  }, [id])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newDeadline) return

    setSubmitting(true)
    setMessage(null)

    try {
      const res = await fetch(`/api/polls/${id}/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ deadline: newDeadline })
      })
      const result = await res.json()

      if (res.ok) {
        setMessage({ type: 'success', text: 'Abstimmung wurde erfolgreich zurückgesetzt!' })
        setTimeout(() => navigate('/admin'), 1500)
      } else {
        setMessage({ type: 'error', text: result.message || 'Fehler beim Zurücksetzen.' })
      }
    } catch {
      setMessage({ type: 'error', text: 'Netzwerkfehler.' })
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <p className="text-center">Laden...</p>
  if (!poll) return <div className="flash error">Event nicht gefunden.</div>

  return (
    <div>
      <Link to="/admin" style={{ color: 'var(--primary-color)', textDecoration: 'none', marginBottom: '1.5rem', display: 'inline-block' }}>
        ← Zurück zum Admin Dashboard
      </Link>
      <div className="card" style={{ maxWidth: '500px', margin: '0 auto' }}>
        <h2>🔄 Abstimmung zurücksetzen</h2>
        <p style={{ color: 'var(--text-muted)', margin: '1rem 0 2rem 0', fontSize: '0.95rem' }}>
          Setzt die Abstimmung "{poll.title}" zurück. Alle bisherigen Stimmen werden gelöscht und eine neue Deadline wird gesetzt.
        </p>

        {message && <div className={`flash ${message.type}`}>{message.text}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Neue Deadline</label>
            <input type="datetime-local" value={newDeadline} onChange={e => setNewDeadline(e.target.value)} required />
          </div>

          <button type="submit" disabled={submitting} className="btn btn-primary" style={{ width: '100%', marginTop: '1rem', backgroundColor: '#ff9800' }}>
            {submitting ? 'Zurücksetzen...' : 'Abstimmung zurücksetzen & neu starten'}
          </button>
        </form>
      </div>
    </div>
  )
}

// 8. WhatsApp Dashboard
function WhatsAppDashboard() {
  const [statusData, setStatusData] = useState<WhatsAppStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  // Input states
  const [defaultChatId, setDefaultChatId] = useState('')
  const [defaultChatName, setDefaultChatName] = useState('')
  const [adminChatId, setAdminChatId] = useState('')
  const [adminChatName, setAdminChatName] = useState('')

  // Poll sharing
  const [polls, setPolls] = useState<Poll[]>([])
  const [selectedPollId, setSelectedPollId] = useState<string>('')
  const [waMessage, setWaMessage] = useState('')

  const loadStatus = async () => {
    try {
      const res = await fetch('/api/whatsapp/status')
      const data = await res.json()
      setStatusData(data)

      const userRes = await fetch('/api/auth/status')
      const userData = await userRes.json()
      if (userData.authenticated) {
        setDefaultChatId(userData.user.whatsapp_chat_id || '')
        setDefaultChatName(userData.user.whatsapp_chat_name || '')
        setAdminChatId(userData.user.whatsapp_admin_chat_id || '')
        setAdminChatName(userData.user.whatsapp_admin_chat_name || '')
      }

      const pollsRes = await fetch('/api/polls')
      const pollsData = await pollsRes.json()
      setPolls(pollsData.filter((p: Poll) => p.is_active))
    } catch {
      setError('Verbindung zur WhatsApp-API fehlgeschlagen.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  const handleSetDefault = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setMessage(null)
    try {
      const res = await fetch('/api/whatsapp/set_default', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: defaultChatId, chat_name: defaultChatName })
      })
      if (res.ok) {
        setMessage({ type: 'success', text: 'Standard-Chat erfolgreich gespeichert!' })
        loadStatus()
      } else {
        setMessage({ type: 'error', text: 'Fehler beim Speichern.' })
      }
    } catch {
      setMessage({ type: 'error', text: 'Netzwerkfehler.' })
    } finally {
      setSubmitting(false)
    }
  }

  const handleSetAdmin = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setMessage(null)
    try {
      const res = await fetch('/api/whatsapp/set_admin_chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ admin_chat_id: adminChatId, admin_chat_name: adminChatName })
      })
      if (res.ok) {
        setMessage({ type: 'success', text: 'Admin-Chat erfolgreich gespeichert!' })
        loadStatus()
      } else {
        setMessage({ type: 'error', text: 'Fehler beim Speichern.' })
      }
    } catch {
      setMessage({ type: 'error', text: 'Netzwerkfehler.' })
    } finally {
      setSubmitting(false)
    }
  }

  const handleLogout = async () => {
    if (!confirm('Möchtest du dich wirklich abmelden?')) return
    setLoading(true)
    try {
      const res = await fetch('/api/whatsapp/logout', { method: 'POST' })
      if (res.ok) {
        loadStatus()
      }
    } catch {
      alert('Fehler beim Abmelden.')
    } finally {
      setLoading(false)
    }
  }

  const handleSharePoll = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedPollId) return

    setSubmitting(true)
    setMessage(null)
    try {
      const res = await fetch(`/api/whatsapp/share/${selectedPollId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: waMessage })
      })
      if (res.ok) {
        setMessage({ type: 'success', text: 'Abstimmung erfolgreich geteilt!' })
        setWaMessage('')
        setSelectedPollId('')
      } else {
        const d = await res.json()
        setMessage({ type: 'error', text: d.message || 'Fehler beim Teilen.' })
      }
    } catch {
      setMessage({ type: 'error', text: 'Netzwerkfehler.' })
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <p className="text-center">WhatsApp Status wird geladen...</p>
  if (error) return <div className="flash error">{error}</div>
  if (!statusData?.configured) {
    return (
      <div className="card text-center">
        <h3>⚠️ WhatsApp-API unkonfiguriert</h3>
        <p style={{ color: 'var(--text-muted)', marginTop: '0.5rem' }}>
          Bitte stelle sicher, dass die WhatsApp-Credentials in der `.env`-Datei eingetragen sind.
        </p>
      </div>
    )
  }

  const isConnected = statusData.status === 'online' || statusData.status === 'authorized'

  return (
    <div>
      <h1 className="mb-2">WhatsApp Integration</h1>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
        {/* Connection status & config */}
        <div>
          <div className="card">
            <h3>Verbindungsstatus: <span style={{ color: isConnected ? '#4caf50' : '#f44336' }}>{statusData.status.toUpperCase()}</span></h3>
            {statusData.status === 'notAuthorized' && statusData.qr_data && (
              <div style={{ marginTop: '1.5rem', textAlign: 'center' }}>
                <p style={{ marginBottom: '1rem', fontSize: '0.95rem' }}>Scanne diesen QR-Code mit WhatsApp auf deinem Handy:</p>
                <img
                  src={`data:image/png;base64,${statusData.qr_data}`}
                  alt="WhatsApp QR Code"
                  style={{ background: 'white', padding: '1rem', borderRadius: '8px' }}
                />
              </div>
            )}

            {isConnected && (
              <div style={{ marginTop: '1.5rem' }}>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', marginBottom: '1rem' }}>
                  Die Verbindung ist aktiv. Der Bot empfängt Nachrichten und kann Termine teilen.
                </p>
                <button onClick={handleLogout} className="btn btn-outline" style={{ color: '#f44336', borderColor: '#f44336' }}>
                  Abmelden
                </button>
              </div>
            )}
          </div>

          {isConnected && (
            <div className="card">
              <h3>Standard-Chat Gruppen</h3>
              {message && <div className={`flash ${message.type}`}>{message.text}</div>}

              {/* Set Default Chat */}
              <form onSubmit={handleSetDefault} style={{ marginBottom: '2rem', marginTop: '1rem' }}>
                <div className="form-group">
                  <label>Standard-Chat (Gruppe/JID)</label>
                  <select value={defaultChatId} onChange={e => {
                    setDefaultChatId(e.target.value)
                    const selected = statusData.groups.find(g => g.id === e.target.value)
                    if (selected) setDefaultChatName(selected.name)
                  }}>
                    <option value="">-- Wähle eine Gruppe --</option>
                    {statusData.groups.map(g => (
                      <option key={g.id} value={g.id}>{g.name}</option>
                    ))}
                  </select>
                </div>
                <button type="submit" disabled={submitting} className="btn btn-outline" style={{ width: '100%' }}>
                  Standard-Chat speichern
                </button>
              </form>

              {/* Set Admin Chat */}
              <form onSubmit={handleSetAdmin}>
                <div className="form-group">
                  <label>Admin-Chat (Gruppe/JID)</label>
                  <select value={adminChatId} onChange={e => {
                    setAdminChatId(e.target.value)
                    const selected = statusData.groups.find(g => g.id === e.target.value)
                    if (selected) setAdminChatName(selected.name)
                  }}>
                    <option value="">-- Wähle eine Gruppe --</option>
                    {statusData.groups.map(g => (
                      <option key={g.id} value={g.id}>{g.name}</option>
                    ))}
                  </select>
                </div>
                <button type="submit" disabled={submitting} className="btn btn-outline" style={{ width: '100%' }}>
                  Admin-Chat speichern
                </button>
              </form>
            </div>
          )}
        </div>

        {/* Share Poll */}
        {isConnected && (
          <div>
            <h2>Terminabstimmung per WhatsApp teilen</h2>
            <form onSubmit={handleSharePoll} className="card" style={{ marginTop: '1rem' }}>
              <div className="form-group">
                <label>Aktive Abstimmung wählen</label>
                <select value={selectedPollId} onChange={e => setSelectedPollId(e.target.value)} required>
                  <option value="">-- Wähle eine Abstimmung --</option>
                  {polls.map(p => (
                    <option key={p.id} value={p.id}>{p.title}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Zusätzliche Nachricht (Optional)</label>
                <textarea
                  value={waMessage}
                  onChange={e => setWaMessage(e.target.value)}
                  placeholder="z.B. @everyone Bitte zeitnah abstimmen!"
                  rows={4}
                />
              </div>

              <button type="submit" disabled={submitting || !selectedPollId} className="btn btn-primary" style={{ width: '100%' }}>
                Teilen
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  )
}
