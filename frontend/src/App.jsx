import React, { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api, getToken, setToken, inr } from "./api.js";
import Dashboard from "./pages/Dashboard.jsx";
import Invoices from "./pages/Invoices.jsx";
import InvoiceForm from "./pages/InvoiceForm.jsx";
import InvoiceView from "./pages/InvoiceView.jsx";
import Masters from "./pages/Masters.jsx";
import Returns from "./pages/Returns.jsx";
import Reconcile from "./pages/Reconcile.jsx";
import Settings from "./pages/Settings.jsx";
import Reports from "./pages/Reports.jsx";
import Purchases from "./pages/Purchases.jsx";

export const Ctx = React.createContext(null);

function Login() {
  const [email, setEmail] = useState("owner@aarohi.example");
  const [password, setPassword] = useState("Owner@123");
  const [err, setErr] = useState("");
  async function submit(e) {
    e.preventDefault();
    setErr("");
    try {
      const r = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      setToken(r.token);
      window.location.href = "/";
    } catch (ex) {
      setErr(ex.message);
    }
  }
  return (
    <div className="login">
      <form className="box" onSubmit={submit}>
        <h2 style={{ marginTop: 0 }}>GST Invoice Platform</h2>
        <p className="hint">GST-compliant invoicing, e-invoice sandbox, GSTR-1 / 3B drafts and ITC reconciliation for Indian businesses.</p>
        {err && <div className="error">{err}</div>}
        <div className="field"><label>Email</label><input className="edit" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
        <div className="field" style={{ marginTop: 8 }}><label>Password</label><input className="edit" type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
        <button className="btn" style={{ marginTop: 14, width: "100%" }}>Sign in</button>
        <p className="hint" style={{ marginTop: 12 }}>
          Demo owner: owner@aarohi.example / Owner@123<br />
          Accountant: accounts@aarohi.example / Acct@123
        </p>
      </form>
    </div>
  );
}

function Shell({ children }) {
  const { me, gstinId, setGstinId, gstins } = React.useContext(Ctx);
  const nav = useNavigate();
  const links = [
    ["/", "Dashboard"],
    ["/invoices", "Invoices"],
    ["/invoices/new", "New invoice"],
    ["/purchases", "Purchases"],
    ["/masters", "Masters"],
    ["/returns", "Returns"],
    ["/reconcile", "Reconciliation"],
    ["/reports", "Reports"],
    ["/settings", "Organisation"],
  ];
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <h1>Aarohi GST</h1>
          <small>{me?.company?.trade_name}</small>
        </div>
        <nav className="nav">
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "active" : "")}>{label}</NavLink>
          ))}
        </nav>
        <div style={{ marginTop: "auto", padding: 10, fontSize: 12, color: "#9cb8ad" }}>
          {me?.user?.name} · {me?.user?.role}
        </div>
      </aside>
      <div className="main">
        <div className="topbar">
          <div>
            <b>{me?.company?.legal_name}</b>
            <div className="hint">PAN {me?.company?.pan} · {me?.company?.scheme === "COMPOSITION" ? "Composition" : "Regular"} · AATO {inr(me?.company?.aato)}</div>
          </div>
          <div className="toolbar" style={{ margin: 0 }}>
            <select className="gstin-select" value={gstinId} onChange={(e) => setGstinId(e.target.value)}>
              <option value="">All GSTINs</option>
              {(gstins || []).map((g) => (
                <option key={g.id} value={g.id}>{g.gstin} · {g.city}</option>
              ))}
            </select>
            <button className="btn secondary" onClick={() => { setToken(""); nav("/login"); }}>Sign out</button>
          </div>
        </div>
        <div className="content">{children}</div>
      </div>
    </div>
  );
}

function Guard({ children }) {
  const { me } = React.useContext(Ctx);
  if (!getToken()) return <Navigate to="/login" replace />;
  if (!me) return <div className="content">Loading workspace...</div>;
  return children;
}

export default function App() {
  const [me, setMe] = useState(null);
  const [meta, setMeta] = useState({ states: [], presets: [] });
  const [gstins, setGstins] = useState([]);
  const [gstinId, setGstinId] = useState("");
  useEffect(() => {
    api("/api/meta").then(setMeta).catch(() => {});
  }, []);
  useEffect(() => {
    if (!getToken()) return;
    Promise.all([api("/api/me"), api("/api/gstins")])
      .then(([m, g]) => {
        setMe(m);
        setGstins(g);
        const primary = g.find((x) => x.is_primary) || g[0];
        if (primary) setGstinId(String(primary.id));
      })
      .catch(() => setMe(null));
  }, []);
  return (
    <Ctx.Provider value={{ me, setMe, meta, gstins, gstinId, setGstinId }}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={
          <Guard>
            <Shell>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/invoices" element={<Invoices />} />
                <Route path="/invoices/new" element={<InvoiceForm />} />
                <Route path="/invoices/:id/edit" element={<InvoiceForm />} />
                <Route path="/invoices/:id" element={<InvoiceView />} />
                <Route path="/purchases" element={<Purchases />} />
                <Route path="/masters" element={<Masters />} />
                <Route path="/returns" element={<Returns />} />
                <Route path="/reconcile" element={<Reconcile />} />
                <Route path="/reports" element={<Reports />} />
                <Route path="/settings" element={<Settings />} />
              </Routes>
            </Shell>
          </Guard>
        } />
      </Routes>
    </Ctx.Provider>
  );
}
