import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from './App';

const metrics = {baseline_peak_load_kw:110,optimized_peak_load_kw:100,peak_reduction_kw:10,peak_reduction_pct:9.09,baseline_energy_kwh:110,optimized_energy_kwh:100,energy_difference_kwh:-10,estimated_cost_difference:-4,comfort_impact:0,modified_decision_count:1,protected_decision_count:1,opted_out_decision_count:0,infeasible:false};
const decision = {id:'d-1',dr_event_id:'event-1',building_id:'building-1',slot_index:72,action:'reduce_setpoint',target_variable:'flexible_load_kw',before_value:10,after_value:0,triggering_constraint:'transformer_capacity_protection',objective_weights_used:{peak_reduction:.55,comfort:.35,energy_cost:.1},reasoning_tags:['TRANSFORMER_PEAK_PROTECTION'],is_override:false,estimated_reduction_kw:10,comfort_score:.9,delta:-10,explanation:'Load was reduced to protect transformer capacity.'};
const transformer = {id:'tx-1',name:'Demo Transformer',rated_capacity_kw:100,current_load_kw:110,connected_building_ids:['building-1'],safety_margin_pct:.1};
const event = {id:'event-1',transformer_id:'tx-1',start_time:'2026-10-05T18:00:00Z',end_time:'2026-10-05T19:00:00Z',target_reduction_kw:10,status:'active'};

function mockApi(fail=false) {
  globalThis.fetch=vi.fn(async (input:RequestInfo|URL,init?:RequestInit)=>{
    const url=String(input);
    if(fail&&init?.method!=='POST')return new Response(JSON.stringify({error_type:'DatabaseUnavailable',detail:'Database temporarily unavailable'}),{status:503,headers:{'Content-Type':'application/json'}});
    let body:unknown=[];
    if(url.endsWith('/api/transformers'))body=[transformer];
    else if(url.endsWith('/api/buildings'))body=[{id:'building-1',name:'North House',transformer_id:'tx-1',building_type:'residential',floor_area_sqm:120,fixed_load_kw:4,flexible_load_kw:10,occupant_ids:['occupant-1']}];
    else if(url.endsWith('/api/occupants'))body=[{id:'occupant-1',building_id:'building-1',display_name:'Household 1',comfort_range_id:'comfort-1',opted_out:false,allow_override:false}];
    else if(url.endsWith('/api/appliances'))body=[];
    else if(url.endsWith('/api/tariffs'))body=[];
    else if(url.endsWith('/api/dr-events'))body=[event];
    else if(url.endsWith('/api/comfort-ranges'))body=[{id:'comfort-1',variable:'temperature_c',min_value:19,max_value:25,preferred_value:22}];
    else if(url.endsWith('/api/load-profiles'))body=[{entity_id:'tx-1',values_kw:[80,90,110,105]}];
    else if(url.endsWith('/api/planning/results'))body=[];
    else if(url.endsWith('/api/planning/history'))body=[];
    else if(url.endsWith('/api/planning/generate'))body={decisions:[decision],metrics,planning_result_id:'run-1'};
    else if(url.endsWith('/api/planning/compare'))body={first_strategy:'baseline',first_decisions:[decision],second_strategy:'optimized',second_decisions:[decision],changed_decision_count:0,metrics};
    return new Response(JSON.stringify(body),{status:200,headers:{'Content-Type':'application/json'}});
  }) as typeof fetch;
}

describe('operator console',()=>{
  beforeEach(()=>mockApi());
  afterEach(()=>{cleanup();vi.restoreAllMocks();});

  it('loads live transformer values and runs the planning workflow through FastAPI',async()=>{
    render(<App/>);
    expect(await screen.findByText('Transformer overload detected')).toBeTruthy();
    expect(screen.getByText(/110 kW of 100 kW rated capacity/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'DR Planning'}));
    fireEvent.click(screen.getByRole('button',{name:/Run optimized plan/}));
    expect(await screen.findByText('Optimization complete')).toBeTruthy();
    expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining('/api/planning/generate'),expect.objectContaining({method:'POST'}));
    expect(screen.getAllByText('10 kW').length).toBeGreaterThan(0);
  });

  it('shows a useful empty state when the API cannot load data',async()=>{
    mockApi(true);
    render(<App/>);
    expect(await screen.findByText('Backend data unavailable')).toBeTruthy();
    expect(screen.getAllByText(/Database temporarily unavailable/).length).toBeGreaterThan(0);
  });
});
