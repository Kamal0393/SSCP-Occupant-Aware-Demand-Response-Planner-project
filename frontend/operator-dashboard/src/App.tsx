import type { Page } from './types';
import { Dashboard, EmptyPanel, ExplanationScreen, HistoryScreen, LoadingPanel, OverrideScreen, pageSubtitle, PlanningScreen, ComparisonScreen, ResourceTable, ResultsScreen, TariffScreen } from './pages/screens';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, BarChart3, Building2, CalendarClock, Check, ChevronDown, CircleHelp, Clock3, Gauge, Home, Info, LoaderCircle, Menu, PlugZap, RefreshCw, ShieldCheck, SlidersHorizontal, Users, X } from 'lucide-react';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, get, compare, runPlan, type Appliance, type Building, type Comparison, type ComfortRange, type Decision, type DREvent, type Metrics, type Occupant, type PlanInput, type PlanResponse, type PlanningHistory, type PlanningResult, type Tariff, type Transformer } from './api';

type LoadProfile = { entity_id: string; values_kw: number[] };
const nav: { label: Page; icon: typeof Home; group: string }[] = [
  { label:'Dashboard',icon:Home,group:'Overview' },{ label:'Buildings',icon:Building2,group:'Network' },{ label:'Occupants',icon:Users,group:'Network' },{ label:'Transformers',icon:Gauge,group:'Network' },{ label:'Appliances',icon:PlugZap,group:'Network' },{ label:'Tariffs',icon:Activity,group:'Network' },{ label:'DR Planning',icon:SlidersHorizontal,group:'Operations' },{ label:'Optimization Results',icon:BarChart3,group:'Operations' },{ label:'Comparison',icon:ArrowDownRight,group:'Operations' },{ label:'Explanations',icon:CircleHelp,group:'Operations' },{ label:'Emergency Override',icon:AlertTriangle,group:'Operations' },{ label:'Planning History',icon:CalendarClock,group:'Operations' },
];
const fmt = (n?: number | null, digits=1) => n == null || !Number.isFinite(n) ? '—' : n.toLocaleString(undefined,{ maximumFractionDigits:digits });
const time = (s?: string) => s ? new Date(s).toLocaleString() : '—';

export default function App() {
  const [page,setPage] = useState<Page>('Dashboard');
  const [busy,setBusy] = useState(true);
  const [error,setError] = useState<{message:string;kind:string;status:number}|null>(null);
  const [transformers,setTransformers] = useState<Transformer[]>([]);
  const [buildings,setBuildings] = useState<Building[]>([]);
  const [occupants,setOccupants] = useState<Occupant[]>([]);
  const [appliances,setAppliances] = useState<Appliance[]>([]);
  const [tariffs,setTariffs] = useState<Tariff[]>([]);
  const [events,setEvents] = useState<DREvent[]>([]);
  const [comfort,setComfort] = useState<ComfortRange[]>([]);
  const [profiles,setProfiles] = useState<LoadProfile[]>([]);
  const [results,setResults] = useState<PlanningResult[]>([]);
  const [history,setHistory] = useState<PlanningHistory[]>([]);
  const [transformerId,setTransformerId] = useState('');
  const [eventId,setEventId] = useState('');
  const [tariffId,setTariffId] = useState('');
  const [plan,setPlan] = useState<PlanResponse|null>(null);
  const [comparison,setComparison] = useState<Comparison|null>(null);
  const [working,setWorking] = useState(false);
  const [weights,setWeights] = useState({peak_reduction:0.55,comfort:0.35,energy_cost:0.1});
  const [overrideToken,setOverrideToken] = useState('');
  const [operator,setOperator] = useState('');
  const [justification,setJustification] = useState('');
  const [mobileOpen,setMobileOpen] = useState(false);

  const refresh = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const [tx,bld,occ,appData,tar,eventData,comfortData,profileData,resultData,historyData] = await Promise.all([
        get<Transformer[]>('/api/transformers'),get<Building[]>('/api/buildings'),get<Occupant[]>('/api/occupants'),get<Appliance[]>('/api/appliances'),get<Tariff[]>('/api/tariffs'),get<DREvent[]>('/api/dr-events'),get<ComfortRange[]>('/api/comfort-ranges'),get<LoadProfile[]>('/api/load-profiles'),get<PlanningResult[]>('/api/planning/results'),get<PlanningHistory[]>('/api/planning/history'),
      ]);
      setTransformers(tx);setBuildings(bld);setOccupants(occ);setAppliances(appData);setTariffs(tar);setEvents(eventData);setComfort(comfortData);setProfiles(profileData);setResults(resultData.slice().sort((a,b)=>new Date(b.created_at).getTime()-new Date(a.created_at).getTime()));setHistory(historyData.slice().sort((a,b)=>new Date(b.occurred_at).getTime()-new Date(a.occurred_at).getTime()));
      const viable=tx.filter(t=>{const bs=bld.filter(b=>b.transformer_id===t.id);const ids=new Set(bs.map(b=>b.id));const os=occ.filter(o=>ids.has(o.building_id));return bs.length>0&&os.every(o=>comfortData.some(c=>c.id===o.comfort_range_id));});
      const preferred=viable.find(t=>t.current_load_kw>t.rated_capacity_kw)||viable[0]||tx[0];
      setTransformerId(current=>tx.some(v=>v.id===current)?current:preferred?.id||'');
      const preferredEvents=eventData.filter(e=>e.transformer_id===(tx.some(v=>v.id===transformerId)?transformerId:preferred?.id));
      setEventId(current=>preferredEvents.some(v=>v.id===current)?current:preferredEvents.find(v=>v.status==='active')?.id||preferredEvents[0]?.id||'');
      const defaultEvent=preferredEvents.find(v=>v.id===eventId)||preferredEvents.find(v=>v.status==='active')||preferredEvents[0];
      const eventStart=defaultEvent?new Date(defaultEvent.start_time):null;
      const firstSlot=eventStart?eventStart.getUTCHours()*4+Math.floor(eventStart.getUTCMinutes()/15):0;
      const slots=defaultEvent?Math.max(1,Math.ceil((new Date(defaultEvent.end_time).getTime()-new Date(defaultEvent.start_time).getTime())/900000)):1;
      const eventTariff=tar.slice().sort((a,b)=>{
        const mean=(item:Tariff)=>Array.from({length:slots},(_,i)=>item.rate_per_slot[String((firstSlot+i)%96)]??0).reduce((sum,value)=>sum+value,0)/slots;
        return mean(b)-mean(a);
      })[0];
      setTariffId(current=>tar.some(v=>v.id===current)?current:eventTariff?.id||'');
    } catch(e) { const x=e as {message:string;kind?:string;status?:number}; setError({message:x.message,kind:x.kind||'API Error',status:x.status||0}); }
    finally { setBusy(false); }
  },[]);
  useEffect(()=>{ void refresh(); },[refresh]);

  const transformer = transformers.find(x=>x.id===transformerId);
  const event = events.find(x=>x.id===eventId);
  const tariff = tariffs.find(x=>x.id===tariffId)||null;
  const scopedBuildings = buildings.filter(x=>x.transformer_id===transformerId);
  const buildingIds = new Set(scopedBuildings.map(x=>x.id));
  const scopedOccupants = occupants.filter(x=>buildingIds.has(x.building_id));
  const scopedAppliances = appliances.filter(x=>buildingIds.has(x.building_id));
  const scopedEvents = events.filter(x=>x.transformer_id===transformerId);
  const selectTransformer=(id:string)=>{setTransformerId(id);setPlan(null);setComparison(null);const related=events.filter(e=>e.transformer_id===id);setEventId(related.find(e=>e.status==='active')?.id||related[0]?.id||'');};
  const latestResult = results[0];
  const activeMetrics = plan?.metrics || latestResult?.metrics;
  const loadProfile = profiles.find(x=>x.entity_id===transformerId)?.values_kw;
  const loadSeries = useMemo(()=>loadProfile?.length ? loadProfile.map((kw,i)=>({slot:i,kw})) : transformer ? [{slot:0,kw:transformer.current_load_kw}] : [],[loadProfile,transformer]);

  useEffect(()=>{
    if(plan||!latestResult||(page!=='Optimization Results'&&page!=='Explanations'))return;
    let cancelled=false;
    Promise.all([
      get<Decision[]>(`/api/planning/results/${latestResult.id}/decisions`),
      get<{decision_id:string;text:string}[]>(`/api/planning/results/${latestResult.id}/explanations`),
    ]).then(([decisions,explanations])=>{
      if(cancelled)return;
      const textById=new Map(explanations.map(item=>[item.decision_id,item.text]));
      setPlan({planning_result_id:latestResult.id,metrics:latestResult.metrics,decisions:decisions.map(d=>({...d,explanation:textById.get(d.id)||d.explanation}))});
    }).catch(e=>{if(!cancelled){const x=e as {message:string;kind?:string;status?:number};setError({message:x.message,kind:x.kind||'Results error',status:x.status||0});}});
    return ()=>{cancelled=true;};
  },[page,latestResult,plan]);

  const planInput = (): PlanInput | null => {
    if (!transformer||!event) return null;
    const missingComfort=scopedOccupants.filter(o=>!comfort.some(c=>c.id===o.comfort_range_id));
    if (missingComfort.length) { setError({message:`Comfort preferences are missing for ${missingComfort.map(o=>o.display_name).join(', ')}. Add their comfort ranges to the database before planning.`,kind:'Incomplete planning data',status:422}); return null; }
    const comfortRanges=Object.fromEntries(scopedOccupants.map(o=>o.comfort_range_id).map(id=>[id,comfort.find(c=>c.id===id)!]));
    return {dr_event:event,transformer,buildings:scopedBuildings,occupants:scopedOccupants,comfort_ranges:comfortRanges,tariff,appliances:scopedAppliances,objective_weights:weights,transformer_load_profile_kw:profiles.find(p=>p.entity_id===transformer.id)?.values_kw};
  };
  const execute=async (emergency=false) => {
    const input=planInput(); if(!input)return;
    if(emergency&&(!overrideToken.trim()||!operator.trim()||justification.trim().length<12)){setError({message:'Enter the operator token, operator ID, and a justification of at least 12 characters.',kind:'ValidationError',status:422});return;}
    setWorking(true);setError(null);setComparison(null);
    try { const next=await runPlan(input,emergency?{token:overrideToken,operator,justification}:undefined);setPlan(next);setPage('Optimization Results'); await refresh();
      const compared=await compare(input);setComparison(compared);
    } catch(e) {const x=e as {message:string;kind?:string;status?:number};setError({message:x.message,kind:x.kind||'Planning error',status:x.status||0});}
    finally {setWorking(false);}
  };
  const runComparison=async()=>{const input=planInput();if(!input)return;setWorking(true);setError(null);try{setComparison(await compare(input));setPage('Comparison');}catch(e){const x=e as {message:string;kind?:string;status?:number};setError({message:x.message,kind:x.kind||'Comparison error',status:x.status||0});}finally{setWorking(false);}};

  const metric=activeMetrics;
  const utilization=transformer?transformer.current_load_kw/transformer.rated_capacity_kw*100:0;
  const overload=Boolean(transformer&&transformer.current_load_kw>transformer.rated_capacity_kw);
  const peakChart=metric?[{name:'Baseline',peak:metric.baseline_peak_load_kw},{name:'Optimized',peak:metric.optimized_peak_load_kw}]:[];
  const energyChart=metric?[{name:'Baseline',energy:metric.baseline_energy_kwh},{name:'Optimized',energy:metric.optimized_energy_kwh}]:[];
  const expenseChart=metric?.estimated_cost_difference!=null?[{name:'Estimated cost change',cost:metric.estimated_cost_difference}]:[];
  const protectedIds=new Set((plan?.decisions||[]).filter(d=>d.reasoning_tags.includes('OPTED_OUT')||d.reasoning_tags.includes('COMFORT_PROTECTED')).map(d=>d.building_id));

  const pageContent=()=>{
    if(busy&&!transformers.length)return <LoadingPanel/>;
    if(error&&!transformers.length)return <EmptyPanel title="Backend data unavailable" detail={error.message} action={<button className="button primary" onClick={()=>void refresh()}><RefreshCw size={15}/> Retry connection</button>}/>;
    switch(page){
      case 'Dashboard': return <Dashboard transformer={transformer} event={event} buildings={scopedBuildings} occupants={scopedOccupants} appliances={scopedAppliances} results={results} metrics={metric} currency={tariff?.currency||tariffs[0]?.currency} loadSeries={loadSeries} utilization={utilization} overload={overload} onNavigate={setPage}/>;
      case 'Buildings': return <ResourceTable title="Buildings" subtitle="Building load and transformer associations" icon={<Building2/>} rows={scopedBuildings.map(b=>({Name:b.name,Type:b.building_type,Transformer:b.transformer_id,'Floor area':`${fmt(b.floor_area_sqm,0)} m²`,'Fixed load':`${fmt(b.fixed_load_kw)} kW`,'Flexible load':`${fmt(b.flexible_load_kw)} kW`,Occupants:b.occupant_ids.length}))}/>;
      case 'Occupants': return <ResourceTable title="Occupants" subtitle="Comfort participation and opt-out preferences" icon={<Users/>} rows={scopedOccupants.map(o=>({Occupant:o.display_name,Building:scopedBuildings.find(b=>b.id===o.building_id)?.name||o.building_id,Preference:comfort.find(c=>c.id===o.comfort_range_id)?`${comfort.find(c=>c.id===o.comfort_range_id)!.min_value}–${comfort.find(c=>c.id===o.comfort_range_id)!.max_value} °C`:'Missing',Participation:o.opted_out?'Opted out':'Participating', 'Emergency consent':o.allow_override?'Allowed':'Not allowed'}))}/>;
      case 'Transformers': return <ResourceTable title="Transformers" subtitle="Live capacity and loading from the API" icon={<Gauge/>} rows={transformers.map(t=>({Transformer:t.name,ID:t.id,Load:`${fmt(t.current_load_kw)} kW`,Capacity:`${fmt(t.rated_capacity_kw)} kW`,Utilization:`${fmt(t.current_load_kw/t.rated_capacity_kw*100)}%`,Status:t.current_load_kw>t.rated_capacity_kw?'Overloaded':'Normal'}))}/>;
      case 'Appliances': return <ResourceTable title="Appliances" subtitle="Flexible and non-flexible assets available to the plan" icon={<PlugZap/>} rows={scopedAppliances.map(a=>({Appliance:a.name,Building:scopedBuildings.find(b=>b.id===a.building_id)?.name||a.building_id,Type:a.appliance_type,Power:`${fmt(a.rated_power_kw)} kW`,Flexibility:a.is_flexible?'Flexible':'Fixed',State:a.is_running?'Running':'Scheduled','Shift window':`${a.max_shift_slots} slots`}))}/>;
      case 'Tariffs': return <TariffScreen tariffs={tariffs}/>;
      case 'DR Planning': return <PlanningScreen transformers={transformers} events={scopedEvents} tariffs={tariffs} tariffId={tariffId} setTariff={setTariffId} buildings={scopedBuildings} occupants={scopedOccupants} appliances={scopedAppliances} transformerId={transformerId} eventId={eventId} setTransformer={selectTransformer} setEvent={setEventId} weights={weights} setWeights={setWeights} working={working} onRun={()=>void execute(false)} onCompare={()=>void runComparison()} onEmergency={()=>setPage('Emergency Override')}/>;
      case 'Emergency Override': return <OverrideScreen event={event} transformer={transformer} optedOut={scopedOccupants.filter(o=>o.opted_out)} token={overrideToken} setToken={setOverrideToken} operator={operator} setOperator={setOperator} justification={justification} setJustification={setJustification} working={working} onExecute={()=>void execute(true)}/>;
      case 'Optimization Results': return <ResultsScreen plan={plan} metrics={metric} buildings={scopedBuildings} appliances={scopedAppliances} onCompare={()=>void runComparison()} onPlan={()=>setPage('DR Planning')}/>;
      case 'Comparison': return <ComparisonScreen comparison={comparison} working={working} onRun={()=>void runComparison()}/>;
      case 'Explanations': return <ExplanationScreen decisions={plan?.decisions||[]} buildings={scopedBuildings}/>;
      case 'Planning History': return <HistoryScreen results={results} history={history}/>;
    }
  };
  return <div className="shell">
    <aside className={`sidebar ${mobileOpen?'mobile-open':''}`}><div className="brand"><span className="brand-mark"><Activity size={20}/></span><span><b>GRIDWISE</b><small>DEMAND RESPONSE</small></span><button className="mobile-close icon-button" onClick={()=>setMobileOpen(false)}><X size={18}/></button></div>
      <div className="workspace"><span className="workspace-dot"/><span>Utility operations</span><ChevronDown size={14}/></div>
      {['Overview','Network','Operations'].map(group=><div className="nav-group" key={group}><p>{group}</p>{nav.filter(i=>i.group===group).map(item=>{const Icon=item.icon;return <button key={item.label} onClick={()=>{setPage(item.label);setMobileOpen(false);}} className={`nav-item ${page===item.label?'selected':''}`}><Icon size={17}/><span>{item.label}</span>{item.label==='Emergency Override'&&<span className="nav-alert"/>}</button>})}</div>)}
      <div className="sidebar-foot"><div className="connection"><span className={`connection-dot ${error?'offline':''}`}/><span>{error?'API disconnected':'API connected'}</span></div><div className="version">Planning console <span>v1.0</span></div></div>
    </aside>
    <main className="main"><header className="topbar"><button className="icon-button mobile-menu" onClick={()=>setMobileOpen(true)}><Menu size={20}/></button><div className="breadcrumbs">Utility operations <span>/</span> <b>{page}</b></div><div className="top-actions"><label className="select-wrap top-transformer"><span>Transformer</span><select value={transformerId} onChange={e=>{selectTransformer(e.target.value);setPlan(null);setComparison(null);}}>{transformers.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select><ChevronDown size={14}/></label><button className="icon-button" aria-label="Refresh data" onClick={()=>void refresh()}><RefreshCw size={17}/></button><div className="avatar">OP</div></div></header>
      <section className="page-wrap"><div className="page-heading"><div><div className="eyebrow">{new Date().toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric'})}</div><h1>{page}</h1><p>{pageSubtitle(page)}</p></div>{page==='Dashboard'&&<button className="button primary" onClick={()=>setPage('DR Planning')}><SlidersHorizontal size={15}/> New planning run</button>}</div>
        {error&&<div className={`alert ${error.status>=500?'danger':'warning'}`}><AlertTriangle size={17}/><div><b>{error.kind}{error.status?` · HTTP ${error.status}`:''}</b><p>{error.message}</p></div><button className="icon-button" onClick={()=>setError(null)}><X size={16}/></button></div>}
        {pageContent()}
      </section>
    </main>
  </div>;
}
