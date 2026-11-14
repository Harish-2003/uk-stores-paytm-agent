import { useEffect, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";
const api = (p, o) => fetch(`${API_BASE}/api${p}`, o).then((r) => r.json());
const post = (p, b) => api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
const inr = (n) => "₹" + Number(n).toLocaleString("en-IN");

const PAYTM = [
  { q: "Show today's settlement summary and tell me if anything looks short.", label: "Today's settlement summary" },
  { q: "Show my last 10 transactions.", label: "Last 10 transactions" },
  { q: "Export today's orders to Excel.", label: "Export orders to Excel" },
  { q: "Refund ₹120 on the last order.", label: "Refund ₹120 on last order" },
];
const STORE = [
  { q: "Generate this week's sales report and give me a short spoken summary.", label: "Generate sales data" },
  { q: "Create a 10% discount for regular customers valid for 7 days and announce it on the Soundbox.", label: "10% off for regular customers" },
  { q: "Give 50 Paytm Coins to regular customers as a thank-you and announce it on the Soundbox.", label: "50 Paytm Coins to regulars", coin: true },
  { q: "Give 25 Paytm Coins to new customers as a welcome reward and announce it.", label: "Welcome coins for new customers", coin: true },
];

function Dashboard({ d }) {
  if (!d) return <p className="muted">Loading store data…</p>;
  const max = Math.max(...d.daily.map((x) => x.sales));
  return (
    <>
      <section className="kpis">
        <div className="kpi hero"><span>This week</span><b>{inr(d.kpis.week_sales)}</b></div>
        <div className="kpi"><span>Today</span><b>{inr(d.kpis.today)}</b></div>
        <div className="kpi"><span>Orders this week</span><b>{d.kpis.orders}</b></div>
        <div className="kpi"><span>Average bill</span><b>{inr(d.kpis.avg_bill)}</b></div>
      </section>
      <div className="grid2">
        <div className="card"><h2>Daily sales</h2>
          <div className="bars">{d.daily.map((x) => (<div key={x.date} title={inr(x.sales)}><i style={{ height: (x.sales / max) * 140 }} />{x.date}</div>))}</div></div>
        <div className="card"><h2>Top items this week</h2>
          <table><tbody>{d.top.map((t) => (<tr key={t.item}><td>{t.item}</td><td>{t.units} sold</td></tr>))}</tbody></table></div>
      </div>
      <div className="grid2">
        <div className="card"><h2>Recent orders</h2>
          <table><thead><tr><th>Order</th><th>Customer</th><th>Paid by</th><th>Amount</th></tr></thead>
            <tbody>{d.orders.slice(0, 8).map((o) => (<tr key={o.id}><td>{o.id}</td><td>{o.customer}</td><td>{o.mode}</td><td>{inr(o.amount)}</td></tr>))}</tbody></table></div>
        <div className="card"><h2>Offers and rewards running</h2>
          {!d.discounts.length && !d.coins.length && <p className="muted">Nothing running. Open the Voice agent and create a discount or reward.</p>}
          {d.discounts.map((x, i) => <p key={"d" + i}>{x.percent}% off for {x.segment} customers ({x.customers}) for {x.valid_days} days. Code {x.code}</p>)}
          {d.coins.map((x, i) => <p key={"c" + i}>{x.coins_each} Paytm Coins to {x.segment} customers ({x.customers})</p>)}
          <p className="muted">Customer groups: {Object.entries(d.segments).map(([k, v]) => `${k} ${v}`).join(", ")}</p></div>
      </div>
      <div className="card"><h2>Settlement today <span className="tag demo">demo data</span></h2>
        <p className="muted">Gross {inr(d.settlement.gross)}, refunds {inr(d.settlement.refunds)}, fees {inr(d.settlement.fees)}, payout {inr(d.settlement.payout)}. Bills say {inr(d.settlement.expected_from_bills)}.</p></div>
    </>
  );
}

function Agent({ st, d, onChange }) {
  const [log, setLog] = useState([{ r: "a", t: "Namaste, I'm Lakshmi. Pick an action or ask me anything about UK Stores." }]);
  const [text, setText] = useState(""), [busy, setBusy] = useState(false), [pending, setPending] = useState(null);
  const [talking, setTalking] = useState(false), [voice, setVoice] = useState(true), end = useRef();
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [log]);

  const speak = (t) => {
    if (!voice || !window.speechSynthesis) return;
    const u = new SpeechSynthesisUtterance(t); u.lang = "en-IN";
    u.onstart = () => setTalking(true); u.onend = () => setTalking(false);
    window.speechSynthesis.cancel(); window.speechSynthesis.speak(u);
  };
  async function send(q, scope, confirmed = false) {
    if (!q.trim() || busy) return;
    if (!confirmed) setLog((l) => [...l, { r: "u", t: q }]);
    setText(""); setBusy(true);
    const res = await post("/agent", { message: q, scope, confirmed }).catch(() => ({ reply: "Can't reach the backend. Is uvicorn running on port 8000?", actions: [] }));
    setBusy(false);
    if (res.needs_confirmation) return setPending({ q, scope });
    setLog((l) => [...l, { r: "a", t: res.reply, actions: res.actions, mode: res.mode }]);
    speak(res.reply); onChange();
  }
  const last = [...log].reverse().find((m) => m.r === "a")?.t;
  return (
    <div className="agent">
      <div>
        <div className={"box " + (talking ? "talking" : "")}>
          <div className="led" /><div className="grille" /><p>{busy ? "Thinking…" : last}</p>
        </div>
        <label className="sw"><input type="checkbox" checked={voice} onChange={(e) => setVoice(e.target.checked)} /> Speak replies aloud</label>
        <p className="muted">Groq model: {st?.model || "…"}<br />Brain {st?.groq ? "connected" : "needs GROQ_API_KEY"}. Paytm MCP is {st?.mcp ? "live" : "in demo mode (no credentials yet)"}.</p>
        {d?.voice?.length > 0 && <div className="card"><h2>Soundbox queue</h2>{d.voice.map((v, i) => <p key={i} className="muted">{v.at} {v.text}</p>)}</div>}
      </div>
      <div className="card">
        <h2>Paytm payments {st?.mcp ? <span className="tag live">MCP live</span> : <span className="tag demo">MCP demo</span>}</h2>
        <div className="chips">{PAYTM.map((c) => <button key={c.label} onClick={() => send(c.q, "mcp")}>{c.label}</button>)}</div>
        <h2 style={{ marginTop: 18 }}>Soundbox settings</h2>
        <div className="chips">{STORE.map((c) => <button key={c.label} className={c.coin ? "coin" : ""} onClick={() => send(c.q, "store")}>{c.label}</button>)}</div>
        <div className="log" style={{ marginTop: 16 }}>
          {log.map((m, i) => (<div key={i} className={"msg " + m.r}>{m.t}
            {m.actions?.length > 0 && <small>Ran: {m.actions.map((a) => a.tool).join(", ")}{m.mode ? ` (${m.mode})` : ""}</small>}</div>))}
          <div ref={end} />
        </div>
        <form className="ask" onSubmit={(e) => { e.preventDefault(); send(text, /refund|settle|transaction|order|payment|export/i.test(text) ? "mcp" : "store"); }}>
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask Lakshmi, e.g. why was my payout lower?" aria-label="Ask Lakshmi" />
          <button disabled={busy}>Ask</button>
        </form>
      </div>
      {pending && (<div className="modal"><div><h2>Approve this money action?</h2><p>{pending.q}</p>
        <p className="muted">Lakshmi only moves money after you confirm.</p>
        <div className="row"><button className="primary" onClick={() => { const p = pending; setPending(null); send(p.q, p.scope, true); }}>Confirm refund</button>
          <button onClick={() => setPending(null)}>Cancel</button></div></div></div>)}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("dash"), [d, setD] = useState(null), [st, setSt] = useState(null);
  const load = () => api("/dashboard").then(setD).catch(() => {});
  useEffect(() => { load(); api("/status").then(setSt).catch(() => {}); }, []);
  return (
    <>
      <header className="top">
        <h1>UK Stores<small>Srikakulam, Andhra Pradesh</small></h1>
        <nav><button className={tab === "dash" ? "on" : ""} onClick={() => setTab("dash")}>Dashboard</button>
          <button className={tab === "ai" ? "on" : ""} onClick={() => setTab("ai")}>Voice agent</button></nav>
      </header>
      <main>{tab === "dash" ? <Dashboard d={d} /> : <Agent st={st} d={d} onChange={load} />}</main>
    </>
  );
}
