import Link from "next/link";

const features = [
  {
    icon: "🎓",
    title: "BRACU Student Verification",
    desc: "Only verified @g.bracu.ac.bd emails can register. Your campus, your community.",
    color: "var(--primary-muted)",
  },
  {
    icon: "📄",
    title: "Driver Vehicle Verification",
    desc: "Drivers upload NID, license, and vehicle registration — reviewed by campus moderators.",
    color: "var(--accent-muted)",
  },
  {
    icon: "📍",
    title: "Live GPS Ride Tracking",
    desc: "Real-time location sharing with trusted contacts. Know where your ride is, always.",
    color: "var(--info-muted)",
  },
  {
    icon: "🆘",
    title: "In-App SOS Button",
    desc: "Instant alert to campus security and your emergency contacts with one tap.",
    color: "var(--danger-muted)",
  },
  {
    icon: "🛡️",
    title: "Admin Complaint Panel",
    desc: "Report misconduct directly. Campus moderators review and take action swiftly.",
    color: "var(--warning-muted)",
  },
];

export default function HomePage() {
  return (
    <>
      {/* Header */}
      <header className="header">
        <div className="header-inner">
          <div className="header-logo">Arooohi</div>
          <nav className="header-nav">
            <a href="#features" className="header-link">Features</a>
            <Link href="/login" className="header-link">Login</Link>
            <Link href="/register" className="btn btn-primary btn-sm">Get Started</Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="hero">
        <div className="hero-content">
          <div className="hero-badge">🔒 Exclusive to BRACU Students</div>
          <h1 className="hero-title">
            Safe Rides.<br />
            <span className="hero-gradient">Student-Powered.</span>
          </h1>
          <p className="hero-desc">
            Arooohi is the exclusive ride-sharing network built for BRAC University students.
            Verified riders, trusted drivers, real-time tracking, and instant SOS — all in one platform.
          </p>
          <div className="hero-buttons">
            <Link href="/register" className="btn btn-primary btn-lg">
              🎓 Register with BRACU Email
            </Link>
            <Link href="/login" className="btn btn-secondary btn-lg">
              Sign In
            </Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="features-section" id="features">
        <h2 className="section-title">Built for Campus Safety</h2>
        <p className="section-subtitle">
          Every feature designed with student safety and convenience at its core.
        </p>
        <div className="features-grid">
          {features.map((f, i) => (
            <div key={i} className="glass-card feature-card">
              <div className="feature-icon" style={{ background: f.color }}>
                {f.icon}
              </div>
              <h3 className="feature-title">{f.title}</h3>
              <p className="feature-desc">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="footer">
        <p>© 2026 Arooohi — An exclusive ride-sharing network for BRACU students.</p>
        <p style={{ marginTop: 8 }}>
          Built by Ahnaf, Mujtahidul, Aminul & Sayed | BRAC University
        </p>
      </footer>
    </>
  );
}
