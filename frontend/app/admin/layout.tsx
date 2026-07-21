"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    const userData = localStorage.getItem("user");
    if (!token || !userData) { router.push("/login"); return; }
    const parsed = JSON.parse(userData);
    if (parsed.role !== "admin") { router.push("/dashboard"); return; }
    setUser(parsed);
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/login");
  };

  if (!user) return <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}><span className="spinner spinner-lg" /></div>;

  return (
    <div className="dashboard-layout">
      <aside className="sidebar">
        <Link href="/" className="sidebar-logo">Arooohi</Link>
        <nav className="sidebar-nav">
          <div className="sidebar-section">Admin Panel</div>
          <Link href="/admin" className={`sidebar-link ${pathname === "/admin" ? "active" : ""}`}>📊 Dashboard</Link>
          <Link href="/admin/complaints" className={`sidebar-link ${pathname === "/admin/complaints" ? "active" : ""}`}>🛡️ Complaints</Link>
          <Link href="/admin/drivers" className={`sidebar-link ${pathname === "/admin/drivers" ? "active" : ""}`}>📄 Driver Verification</Link>
          <Link href="/admin/sos" className={`sidebar-link ${pathname === "/admin/sos" ? "active" : ""}`}>🆘 SOS Alerts</Link>

          <div className="sidebar-section" style={{ marginTop: 16 }}>User Views</div>
          <Link href="/dashboard" className={`sidebar-link`}>🗺️ Map & Tracking</Link>
        </nav>
        <div className="sidebar-bottom">
          <div style={{ fontSize: "0.8rem", color: "var(--text-tertiary)", marginBottom: 4 }}>{user.name}</div>
          <span className="badge badge-accent">Admin</span>
          <button onClick={handleLogout} className="btn btn-ghost btn-sm" style={{ width: "100%", marginTop: 12 }}>Logout</button>
        </div>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  );
}
