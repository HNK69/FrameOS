"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Activity, ArrowDownRight, ArrowRight, AudioLines, Bell, BrainCircuit, Check, CheckCircle2, ChevronDown, CircleHelp, Clock3, FileAudio2, FileText, FolderKanban, LayoutDashboard, LockKeyhole, LogOut, MoreHorizontal, Plus, Radio, Search, ShieldCheck, Sparkles, Upload, UsersRound, WandSparkles, X, Zap } from "lucide-react";
import { api, json } from "@/lib/api";
import { ProductionWorkspace } from "./production-workspace";
import { ProductionAnalytics } from "./production-analytics";

type Page = "overview" | "clients" | "projects" | "production";
type Client = { id:number; name:string; brand:string; industry:string; description:string; memory_status:string; projects_count:number; memories_retained:number };
type Project = { id:number; client_id:number; client_name:string; name:string; description:string; status:string; due_date:string|null };
type Task = { id:number; title:string; category:string; instruction:string; resolve_workflow:string; priority:string; source:string; evidence:string; confidence:number; requires_confirmation:boolean; status:string };
type Run = { id:number; status:string; stage:string; error:string; extractions:any[]; tasks:Task[]; memory_operations:any[] };

const nav = [
  { href:"/", key:"overview", label:"Overview", icon:LayoutDashboard },
  { href:"/clients", key:"clients", label:"Clients", icon:UsersRound },
  { href:"/projects", key:"projects", label:"Projects", icon:FolderKanban },
  { href:"/production", key:"production", label:"Production", icon:AudioLines },
];

function AuthGate({ onReady }: { onReady:()=>void }) {
  const [setup, setSetup] = useState<boolean|null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ email:"", password:"", workspace_name:"" });
  useEffect(() => { api<{setup_required:boolean;auth_ready:boolean}>("/api/auth/status").then(v=>setSetup(v.setup_required)).catch(()=>setError("FRAMEOPS API is offline. Start the backend and refresh.")); }, []);
  async function submit(e:React.FormEvent) {
    e.preventDefault(); setError(""); setBusy(true);
    try { await api(setup ? "/api/auth/setup" : "/api/auth/login", json("POST",form)); onReady(); }
    catch(e:any){setError(e.message)} finally {setBusy(false)}
  }
  return <main className="auth-screen"><div className="auth-card panel"><Logo/><div className="eyebrow">CLIENT INTELLIGENCE PLATFORM</div><h1>{setup ? "Create your workspace" : "Welcome back"}</h1><p>{setup ? "Set up the first owner account to begin." : "Sign in to continue to your client workspace."}</p>
    {setup===null && !error ? <div className="loading-line">Checking secure setup…</div> : <form onSubmit={submit} className="stack-form">
      {setup && <label>Workspace name<input required maxLength={160} value={form.workspace_name} onChange={e=>setForm({...form,workspace_name:e.target.value})} placeholder="Your agency"/></label>}
      <label>Email<input required type="email" autoComplete="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} placeholder="you@studio.com"/></label>
      <label>Password<input required minLength={setup?12:1} type="password" autoComplete={setup?"new-password":"current-password"} value={form.password} onChange={e=>setForm({...form,password:e.target.value})} placeholder={setup?"At least 12 characters":"Your password"}/></label>
      {error && <div className="error-box">{error}</div>}
      <button className="primary-button full" disabled={busy}>{busy?"Working…":setup?"Create workspace":"Sign in"}<ArrowRight size={16}/></button>
      {setup && <small className="muted">The first account becomes the workspace owner. Public sign-up is closed afterward.</small>}
    </form>}</div></main>
}

export function AppShell({page}:{page:Page}) {
  const [authed,setAuthed]=useState(false); const [checking,setChecking]=useState(true);
  const [clients,setClients]=useState<Client[]>([]); const [projects,setProjects]=useState<Project[]>([]); const [tasks,setTasks]=useState<Task[]>([]); const [analytics,setAnalytics]=useState<any>(null); const [readiness,setReadiness]=useState<any>(null); const [user,setUser]=useState<any>(null);
  const [notice,setNotice]=useState(""); const [refresh,setRefresh]=useState(0); const [logoutBusy,setLogoutBusy]=useState(false);
  useEffect(()=>{api("/api/me").then(v=>{setUser(v);setAuthed(true)}).catch(()=>setAuthed(false)).finally(()=>setChecking(false))},[]);
  useEffect(()=>{if(!authed)return; Promise.all([api<Client[]>("/api/clients"),api<Project[]>("/api/projects"),api<Task[]>("/api/tasks"),api("/api/analytics"),api("/api/ready")]).then(([c,p,t,a,r])=>{setClients(c);setProjects(p);setTasks(t);setAnalytics(a);setReadiness(r)}).catch(e=>setNotice(e.message))},[authed,refresh]);
  async function logout(){setLogoutBusy(true);try{await api("/api/auth/logout",json("POST"));setAuthed(false);setUser(null)}finally{setLogoutBusy(false)}}
  if(checking)return <main className="auth-screen"><div className="loading-line">Opening FRAMEOPS…</div></main>;
  if(!authed)return <AuthGate onReady={()=>{setChecking(true);api("/api/me").then(v=>{setUser(v);setAuthed(true)}).finally(()=>setChecking(false))}}/>;
  return <div className="app-frame"><header className="topbar"><Link href="/" className="brand-lockup"><Logo/><span className="brand-name">FRAME<span>OPS</span></span></Link><nav className="top-nav">{nav.map(n=><Link key={n.key} href={n.href} className={page===n.key?"active":""}>{n.label}</Link>)}</nav><div className="top-actions"><div className="service-pip" title="Service readiness"><span className="pip-dot"/> Workspace</div><div className="profile-chip"><div className="avatar">{user?.email?.slice(0,1).toUpperCase()||"F"}</div><span>{user?.email?.split("@")[0]||"Owner"}</span><button onClick={logout} disabled={logoutBusy} aria-label="Sign out" title="Sign out"><LogOut size={15}/></button></div></div></header>
    <div className="workspace"><aside className="side-rail">{nav.map(n=><Link key={n.key} href={n.href} className={page===n.key?"selected":""} title={n.label}><n.icon size={18}/></Link>)}<div className="rail-spacer"/><Link href="/production" title="Client Memory"><BrainCircuit size={18}/></Link><div className="rail-bottom"><ShieldCheck size={17}/></div></aside>
      <main className="main-content"><div className="page-heading"><div><div className="eyebrow">WORKSPACE / {page.toUpperCase()}</div><h1>{page==="overview"?"Client intelligence, in focus":page==="clients"?"Client intelligence":page==="projects"?"Production projects":"Production workspace"}</h1><p>{page==="overview"?"Every decision gets sharper when client history stays close.":page=== "production"?"Turn real feedback into evidence-backed Resolve instructions.":"Keep client context connected to the work it shapes."}</p></div><div className="heading-actions"><button className="quiet-button" onClick={()=>setRefresh(x=>x+1)}><Activity size={15}/> Refresh data</button><Link className="primary-button" href={page==="clients"?"/clients":page==="projects"?"/projects":"/production"}><Plus size={16}/>{page==="clients"?"New client":page==="projects"?"New project":"Process feedback"}</Link></div></div>
        {notice&&<div className="notice"><span>{notice}</span><button onClick={()=>setNotice("")} aria-label="Dismiss"><X size={14}/></button></div>}
        {page==="overview"&&<ProductionAnalytics analytics={analytics} clients={clients} projects={projects} tasks={tasks} readiness={readiness}/>}
        {page==="clients"&&<Clients clients={clients} refresh={()=>setRefresh(x=>x+1)} notify={setNotice}/>}
        {page==="projects"&&<Projects clients={clients} projects={projects} tasks={tasks} refresh={()=>setRefresh(x=>x+1)} notify={setNotice}/>}
        {page==="production"&&<ProductionWorkspace clients={clients} projects={projects} refresh={()=>setRefresh(x=>x+1)} notify={setNotice}/>}
        <footer className="app-footer"><span>FRAMEOPS <i>·</i> Remember Every Client. Perfect Every Project.</span><span>Data shown from this workspace</span></footer>
      </main></div></div>
}

function Logo(){return <div className="logo-mark"><span>F</span></div>}
function CardHead({icon:Icon,title,meta}:{icon:any;title:string;meta?:string}){return <div className="card-head"><div className="card-title"><span className="head-icon"><Icon size={16}/></span><h2>{title}</h2></div>{meta&&<span className="card-meta">{meta}</span>}</div>}
function Empty({title,body,action}:{title:string;body:string;action?:React.ReactNode}){return <div className="empty-state"><div className="empty-orbit"><Sparkles size={19}/></div><b>{title}</b><p>{body}</p>{action}</div>}

function Clients({clients,refresh,notify}:{clients:Client[];refresh:()=>void;notify:(x:string)=>void}){
  const [open,setOpen]=useState(false);const [busy,setBusy]=useState(false);const [editingId,setEditingId]=useState<number|null>(null);const [form,setForm]=useState({name:"",brand:"",industry:"",description:""});const [query,setQuery]=useState("");
  async function save(e:React.FormEvent){e.preventDefault();setBusy(true);try{await api(editingId?`/api/clients/${editingId}`:"/api/clients",json(editingId?"PATCH":"POST",form));setForm({name:"",brand:"",industry:"",description:""});setEditingId(null);setOpen(false);refresh()}catch(e:any){notify(e.message)}finally{setBusy(false)}}
  function edit(c:Client){setForm({name:c.name,brand:c.brand,industry:c.industry,description:c.description});setEditingId(c.id);setOpen(true)}
  async function remove(c:Client){if(!confirm(`Delete ${c.name} and request deletion of its Hindsight bank?`))return;try{await api(`/api/clients/${c.id}`,{method:"DELETE"});refresh()}catch(e:any){notify(e.message)}}
  const shown=clients.filter(c=>(c.name+c.brand+c.industry).toLowerCase().includes(query.toLowerCase()));
  return <section className="panel directory-panel"><div className="toolbar"><div className="search-box"><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search clients"/></div><button className="primary-button" onClick={()=>{setEditingId(null);setForm({name:"",brand:"",industry:"",description:""});setOpen(x=>!x)}}><Plus size={16}/> Add client</button></div>
    {open&&<form className="create-form" onSubmit={save}><div className="form-grid"><label>Client name<input required maxLength={160} value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="Studio or client name"/></label><label>Brand<input maxLength={160} value={form.brand} onChange={e=>setForm({...form,brand:e.target.value})} placeholder="Brand name"/></label><label>Industry<input maxLength={120} value={form.industry} onChange={e=>setForm({...form,industry:e.target.value})} placeholder="Industry"/></label><label>Description<input maxLength={5000} value={form.description} onChange={e=>setForm({...form,description:e.target.value})} placeholder="Context about the client"/></label></div><button className="primary-button" disabled={busy}>{busy?"Saving…":"Save client"}</button></form>}
    {shown.length?<div className="client-grid">{shown.map(c=><article className="client-card" key={c.id}><div className="client-card-top"><div className="client-monogram large">{c.name.slice(0,1).toUpperCase()}</div><button className="icon-button" onClick={()=>edit(c)} title={`Edit ${c.name}`}>Edit</button><button className="icon-button" onClick={()=>remove(c)} title="Delete client and offboard memory"><X size={15}/></button></div><h3>{c.name}</h3><p>{c.brand||c.industry||"Client profile"}</p><div className="client-card-metrics"><span><FolderKanban size={14}/>{c.projects_count} projects</span><span><BrainCircuit size={14}/>{c.memories_retained} memories</span></div><div className="bank-status"><i className={c.memory_status==="ready"?"status-ready":"status-off"}/>{c.memory_status==="ready"?"Hindsight bank connected":"Memory service unavailable"}</div><Link href={`/production?client=${c.id}`} className="outline-action">Start production <ArrowRight size={14}/></Link></article>)}</div>:<Empty title={query?"No matching clients":"Your client intelligence starts here"} body={query?"Try another client or brand name.":"Create a client profile to establish its isolated memory bank and start a project."} action={!query&&<button className="small-action" onClick={()=>setOpen(true)}>Create your first client <ArrowRight size={13}/></button>}/>}
  </section>
}

function Projects({clients,projects,tasks=[],refresh,notify}:{clients:Client[];projects:Project[];tasks?:Task[];refresh:()=>void;notify:(x:string)=>void}){
  const [open,setOpen]=useState(false);const [filter,setFilter]=useState("all");const [form,setForm]=useState({client_id:0,name:"",description:"",status:"active",due_date:""});
  useEffect(()=>{if(clients.length&&!form.client_id)setForm(v=>({...v,client_id:clients[0].id}))},[clients]);
  async function create(e:React.FormEvent){e.preventDefault();try{await api("/api/projects",json("POST",{...form,due_date:form.due_date?new Date(form.due_date).toISOString():null}));setOpen(false);setForm(v=>({...v,name:"",description:"",due_date:""}));refresh()}catch(e:any){notify(e.message)}}
  async function setStatus(p:Project,status:string){try{await api(`/api/projects/${p.id}`,json("PATCH",{client_id:p.client_id,name:p.name,description:p.description,status,due_date:p.due_date}));refresh()}catch(e:any){notify(e.message)}}
  async function remove(p:Project){if(!confirm(`Delete project “${p.name}” and its project records?`))return;try{await api(`/api/projects/${p.id}`,{method:"DELETE"});refresh()}catch(e:any){notify(e.message)}}
  const shown=filter==="all"?projects:projects.filter(p=>p.status===filter);
  return <section className="panel directory-panel"><div className="toolbar"><div className="filter-pills">{["all","active","completed","archived"].map(f=><button key={f} className={filter===f?"chosen":""} onClick={()=>setFilter(f)}>{f}<span>{f==="all"?projects.length:projects.filter(p=>p.status===f).length}</span></button>)}</div><button className="primary-button" onClick={()=>setOpen(x=>!x)} disabled={!clients.length}><Plus size={16}/> Add project</button></div>
    {open&&<form className="create-form" onSubmit={create}><div className="form-grid"><label>Client<select required value={form.client_id||""} onChange={e=>setForm({...form,client_id:Number(e.target.value)})}>{clients.map(c=><option value={c.id} key={c.id}>{c.name}</option>)}</select></label><label>Project name<input required value={form.name} maxLength={180} onChange={e=>setForm({...form,name:e.target.value})} placeholder="Campaign or deliverable"/></label><label>Description<input value={form.description} onChange={e=>setForm({...form,description:e.target.value})} placeholder="Brief project context"/></label><label>Due date<input type="date" value={form.due_date} onChange={e=>setForm({...form,due_date:e.target.value})}/></label></div><button className="primary-button">Save project</button></form>}
    {shown.length?<div className="table-wrap"><div className="table-header project-list-header"><span>Project</span><span>Client</span><span>Status</span><span>Due date</span><span>Actions</span></div>{shown.map(p=>{
      const projTasks = (tasks || []).filter((t: any) => t.project_id === p.id);
      const completed = projTasks.filter((t: any) => t.status === "completed" || t.status === "accepted").length;
      const pending = projTasks.filter((t: any) => t.status === "pending").length;
      const inProg = projTasks.filter((t: any) => t.status === "in_progress").length;
      return <div className="table-row project-list-row" key={p.id}>
        <div>
          <b>{p.name}</b>
          <small>{projTasks.length > 0 ? `${completed}/${projTasks.length} tasks completed · ${pending} pending${inProg > 0 ? ` · ${inProg} in progress` : ""}` : (p.description || "Creative production")}</small>
        </div>
        <span>{p.client_name}</span>
        <span><i className={`status-dot ${p.status}`}/>{p.status}</span>
        <span>{p.due_date?new Date(p.due_date).toLocaleDateString():"—"}</span>
        <div className="row-controls">
          <select value={p.status} onChange={e=>setStatus(p,e.target.value)} aria-label={`Set ${p.name} status`}>
            <option value="active">Active</option>
            <option value="completed">Completed</option>
            <option value="archived">Archived</option>
          </select>
          <Link className="row-link" href={`/production?project=${p.id}`} title="Open production">
            <ArrowRight size={15}/>
          </Link>
          <button className="row-link" onClick={()=>remove(p)} title="Delete project"><X size={14}/></button>
        </div>
      </div>;
    })}</div>:<Empty title={clients.length?"No projects in this view":"Create a client first"} body={clients.length?"Add a project to connect feedback, assets, and production tasks.":"A project must be associated with a workspace client."} action={clients.length?<button className="small-action" onClick={()=>setOpen(true)}>Create project <ArrowRight size={13}/></button>:<Link className="small-action" href="/clients">Add a client <ArrowRight size={13}/></Link>}/>}</section>
}
