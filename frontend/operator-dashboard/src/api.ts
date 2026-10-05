export type Transformer = { id: string; name: string; rated_capacity_kw: number; current_load_kw: number; connected_building_ids: string[]; safety_margin_pct: number };
export type Building = { id: string; name: string; transformer_id: string; building_type: string; floor_area_sqm: number; fixed_load_kw: number; flexible_load_kw: number; occupant_ids: string[] };
export type Occupant = { id: string; building_id: string; display_name: string; comfort_range_id: string; opted_out: boolean; allow_override: boolean };
export type Appliance = { id: string; building_id: string; name: string; appliance_type: string; rated_power_kw: number; is_flexible: boolean; is_running: boolean; preferred_slot: number | null; max_shift_slots: number; duration_slots: number };
export type Tariff = { id: string; name: string; currency: string; rate_per_slot: Record<string, number> };
export type DREvent = { id: string; transformer_id: string; start_time: string; end_time: string; target_reduction_kw: number; status: string };
export type ComfortRange = { id: string; variable: string; min_value: number; max_value: number; preferred_value: number };
export type Decision = { id: string; dr_event_id: string; building_id: string; occupant_id?: string | null; slot_index: number; action: string; target_variable?: string | null; before_value?: number | null; after_value?: number | null; triggering_constraint: string; objective_weights_used: Record<string, number>; reasoning_tags: string[]; is_override: boolean; estimated_reduction_kw: number; comfort_score?: number | null; delta?: number | null; explanation?: string | null };
export type Metrics = { baseline_peak_load_kw: number; optimized_peak_load_kw: number; peak_reduction_kw: number; peak_reduction_pct: number; baseline_energy_kwh: number; optimized_energy_kwh: number; energy_difference_kwh: number; estimated_cost_difference?: number | null; comfort_impact?: number | null; modified_decision_count: number; protected_decision_count: number; opted_out_decision_count: number; infeasible: boolean };
export type PlanningResult = { id: string; dr_event_id: string; strategy_name: string; status: string; objective_weights: Record<string, number>; metrics: Metrics; created_at: string };
export type PlanningHistory = { id: number; planning_result_id: string; action: string; actor: string; details: Record<string, unknown>; occurred_at: string };
export type PlanResponse = { decisions: Decision[]; metrics: Metrics; planning_result_id: string };
export type Comparison = { first_strategy: string; first_decisions: Decision[]; second_strategy: string; second_decisions: Decision[]; changed_decision_count: number; metrics: Metrics | null };

const API = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || 'http://localhost:8000';
export class ApiError extends Error { constructor(message: string, public status: number, public kind: string) { super(message); } }
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try { response = await fetch(`${API}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } }); }
  catch { throw new ApiError('Cannot reach the planning API. Check that the backend is running and VITE_API_URL is correct.', 0, 'ConnectionError'); }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? body.detail.map((e: { msg?: string }) => e.msg).join('; ') : body.detail || 'Request failed';
    throw new ApiError(String(detail), response.status, body.error_type || (response.status >= 500 ? 'ServerError' : 'ValidationError'));
  }
  return body as T;
}
export const get = <T,>(path: string) => api<T>(path);

export async function runPlan(input: PlanInput, override?: { token: string; operator: string; justification: string }): Promise<PlanResponse> {
  return api<PlanResponse>(override ? '/api/planning/emergency-override' : '/api/planning/generate', {
    method: 'POST', headers: override ? { 'X-Override-Token': override.token } : undefined,
    body: JSON.stringify({ ...input, emergency_override: override ? { operator_id: override.operator, justification: override.justification } : null }),
  });
}
export async function compare(input: PlanInput): Promise<Comparison> {
  return api<Comparison>('/api/planning/compare', { method: 'POST', body: JSON.stringify(input) });
}
export type PlanInput = { dr_event: DREvent; transformer: Transformer; buildings: Building[]; occupants: Occupant[]; comfort_ranges: Record<string, ComfortRange>; tariff: Tariff | null; appliances: Appliance[]; objective_weights: { peak_reduction: number; comfort: number; energy_cost: number }; transformer_load_profile_kw?: number[] };
