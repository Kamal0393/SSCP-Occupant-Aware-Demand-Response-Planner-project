const apiUrl = (process.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const token = process.env.DEMO_OVERRIDE_TOKEN;

async function request(path, options = {}) {
  const response = await fetch(`${apiUrl}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || body);
    throw new Error(`${options.method || 'GET'} ${path} returned ${response.status}: ${detail}`);
  }
  return body;
}

function assert(condition, message) {
  if (!condition) throw new Error(`Integration assertion failed: ${message}`);
}

const health = await request('/health');
assert(health.status === 'ok', 'API health');
const [transformers, buildings, occupants, appliances, tariffs, events, comfortRanges, profiles] = await Promise.all([
  request('/api/transformers'), request('/api/buildings'), request('/api/occupants'),
  request('/api/appliances'), request('/api/tariffs'), request('/api/dr-events'),
  request('/api/comfort-ranges'), request('/api/load-profiles'),
]);
assert(buildings.length && occupants.length && appliances.length, 'resource retrieval');

const transformer = transformers.find((item) => {
  if (item.current_load_kw <= item.rated_capacity_kw) return false;
  const ids = new Set(buildings.filter((building) => building.transformer_id === item.id).map((building) => building.id));
  const activeEvent = events.find((candidate) => candidate.transformer_id === item.id && candidate.status === 'active');
  if (!ids.size || !activeEvent) return false;
  const hasOptOut = occupants.some((occupant) => ids.has(occupant.building_id) && occupant.opted_out);
  const hasSchedulable = appliances.some((appliance) => ids.has(appliance.building_id)
    && appliance.is_flexible && !appliance.is_running && appliance.max_shift_slots > 0);
  const startsAt = new Date(activeEvent.start_time);
  const first = startsAt.getUTCHours() * 4 + Math.floor(startsAt.getUTCMinutes() / 15);
  const count = Math.max(1, Math.ceil((new Date(activeEvent.end_time) - startsAt) / 900000));
  const hasHighTariff = tariffs.some((candidate) => Array.from({ length: count }, (_, i) => candidate.rate_per_slot[String((first + i) % 96)] || 0).some((rate) => rate >= 18));
  return hasOptOut && hasSchedulable && hasHighTariff;
});
assert(transformer, 'an overloaded transformer with connected buildings exists');
const selectedBuildings = buildings.filter((item) => item.transformer_id === transformer.id);
const buildingIds = new Set(selectedBuildings.map((item) => item.id));
const selectedOccupants = occupants.filter((item) => buildingIds.has(item.building_id));
const comfortById = Object.fromEntries(comfortRanges
  .filter((item) => selectedOccupants.some((occupant) => occupant.comfort_range_id === item.id))
  .map((item) => [item.id, item]));
assert(selectedOccupants.every((item) => comfortById[item.comfort_range_id]), 'comfort ranges join to occupants');
const event = events.find((item) => item.transformer_id === transformer.id && item.status === 'active');
assert(event, 'an active event exists for the overloaded transformer');
const eventStart = new Date(event.start_time);
const firstSlot = eventStart.getUTCHours() * 4 + Math.floor(eventStart.getUTCMinutes() / 15);
const slotCount = Math.max(1, Math.ceil((new Date(event.end_time) - eventStart) / 900000));
const tariff = tariffs.slice().sort((a, b) => {
  const average = (item) => Array.from({ length: slotCount }, (_, i) => item.rate_per_slot[String((firstSlot + i) % 96)] || 0)
    .reduce((sum, rate) => sum + rate, 0) / slotCount;
  return average(b) - average(a);
})[0];
const selectedAppliances = appliances.filter((item) => buildingIds.has(item.building_id));
const profile = profiles.find((item) => item.entity_id === transformer.id);
const input = {
  dr_event: event, transformer, buildings: selectedBuildings, occupants: selectedOccupants,
  comfort_ranges: comfortById, tariff: tariff || null, appliances: selectedAppliances,
  objective_weights: { peak_reduction: 0.55, comfort: 0.35, energy_cost: 0.1 },
  ...(profile ? { transformer_load_profile_kw: profile.values_kw } : {}),
};

console.log(`Inputs: ${transformer.id} at ${transformer.current_load_kw}/${transformer.rated_capacity_kw} kW, ${selectedBuildings.length} buildings, ${selectedOccupants.length} occupants, event ${event.id}, tariff ${tariff?.id || 'none'}`);
assert(selectedOccupants.some((item) => item.opted_out), 'demo scenario includes opted-out occupants');
assert(selectedAppliances.some((item) => item.is_flexible && !item.is_running && item.max_shift_slots > 0), 'demo scenario includes shiftable loads');
assert(tariff && Math.max(...Object.values(tariff.rate_per_slot)) >= 18, 'overloaded scenario includes a high evening tariff');

const comparison = await request('/api/planning/compare', { method: 'POST', body: JSON.stringify(input) });
assert(comparison.first_strategy === 'baseline' && comparison.second_strategy === 'optimized', 'baseline and optimized strategies executed');
assert(comparison.metrics && Number.isFinite(comparison.metrics.peak_reduction_kw), 'comparison metrics are numeric');
console.log(`Comparison: baseline peak ${comparison.metrics.baseline_peak_load_kw.toFixed(2)} kW, optimized peak ${comparison.metrics.optimized_peak_load_kw.toFixed(2)} kW, reduction ${comparison.metrics.peak_reduction_kw.toFixed(2)} kW (${comparison.changed_decision_count} changed decisions)`);

const plan = await request('/api/planning/generate', { method: 'POST', body: JSON.stringify(input) });
assert(plan.planning_result_id && plan.decisions.length, 'optimized plan persisted decisions');
assert(Math.abs(plan.metrics.baseline_peak_load_kw - plan.metrics.optimized_peak_load_kw - plan.metrics.peak_reduction_kw) < 1e-8, 'peak metrics reconcile');
const optedOutBuildings = new Set(selectedOccupants.filter((item) => item.opted_out).map((item) => item.building_id));
const optedOutDecisions = plan.decisions.filter((item) => optedOutBuildings.has(item.building_id));
assert(optedOutDecisions.length && optedOutDecisions.every((item) => item.estimated_reduction_kw === 0 && item.reasoning_tags.includes('OPTED_OUT')),
  'optimized decisions preserve opted-out loads');
assert(plan.decisions.some((item) => item.action === 'defer_appliance'), 'optimizer shifted an eligible appliance');
const explanations = await request(`/api/planning/results/${plan.planning_result_id}/explanations`);
const history = await request(`/api/planning/history/${plan.planning_result_id}`);
assert(explanations.length === plan.decisions.length && explanations.every((item) => item.text), 'persisted deterministic explanations returned');
assert(history.some((item) => item.action === 'planning_run_generated'), 'planning history was persisted');
console.log(`Plan: ${plan.planning_result_id}; ${plan.decisions.length} decisions; ${optedOutDecisions.length} opt-out protections; ${plan.decisions.filter((item) => item.action === 'defer_appliance').length} appliance shifts; ${explanations.length} explanations; ${history.length} history entries`);

const emergencyTransformer = transformers.find((item) => item.current_load_kw > item.rated_capacity_kw
  && events.some((candidate) => candidate.transformer_id === item.id && candidate.status === 'active')
  && occupants.some((occupant) => occupant.opted_out && occupant.allow_override
    && buildings.some((building) => building.id === occupant.building_id && building.transformer_id === item.id)));
assert(emergencyTransformer, 'demo data includes an overloaded emergency transformer with opted-in override consent');
const emergencyBuildings = buildings.filter((item) => item.transformer_id === emergencyTransformer.id);
const emergencyIds = new Set(emergencyBuildings.map((item) => item.id));
const emergencyOccupants = occupants.filter((item) => emergencyIds.has(item.building_id));
const emergencyEvent = events.find((item) => item.transformer_id === emergencyTransformer.id && item.status === 'active');
const emergencyProfile = profiles.find((item) => item.entity_id === emergencyTransformer.id);
const emergencyInput = {
  ...input, transformer: emergencyTransformer, dr_event: emergencyEvent, buildings: emergencyBuildings,
  occupants: emergencyOccupants,
  comfort_ranges: Object.fromEntries(comfortRanges.filter((item) => emergencyOccupants.some((occupant) => occupant.comfort_range_id === item.id)).map((item) => [item.id, item])),
  appliances: appliances.filter((item) => emergencyIds.has(item.building_id)),
  ...(emergencyProfile ? { transformer_load_profile_kw: emergencyProfile.values_kw } : {}),
};
if (token) {
  const override = await request('/api/planning/emergency-override', {
    method: 'POST', headers: { 'X-Override-Token': token },
    body: JSON.stringify({ ...emergencyInput, emergency_override: {
      operator_id: 'live-demo-operator', justification: 'Prevent immediate thermal overload on emergency feeder',
    } }),
  });
  assert(override.decisions.some((item) => item.is_override), 'authorized emergency override was applied');
  const overrideHistory = await request(`/api/planning/history/${override.planning_result_id}`);
  assert(overrideHistory.some((item) => item.action === 'emergency_override_applied'), 'override audit history was persisted');
  console.log(`Emergency override: authorized and audited (${override.planning_result_id})`);
} else {
  const denied = await fetch(`${apiUrl}/api/planning/emergency-override`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
      ...emergencyInput, emergency_override: { operator_id: 'live-demo-operator', justification: 'Prevent immediate thermal overload on emergency feeder' },
    }),
  });
  assert(denied.status === 403, `missing override token is rejected (got ${denied.status})`);
  console.log('Emergency override: unauthorized request correctly rejected (set DEMO_OVERRIDE_TOKEN and OVERRIDE_AUTH_TOKEN to verify authorized path)');
}

console.log('LIVE BACKEND INTEGRATION PASSED');
