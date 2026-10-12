export const functionKey = (inline, cdp) => `${Number(inline)}:${Number(cdp)}`

export function validatePick(pick) {
  if (!Number.isFinite(pick.time_ms) || pick.time_ms < 0 || pick.time_ms > 1e6 ||
      !Number.isFinite(pick.velocity_mps) || pick.velocity_mps <= 0 || pick.velocity_mps > 30000) {
    throw new Error('Pick requires a nonnegative time and velocity in (0, 30000] m/s')
  }
  return pick
}

export function addPick(picks, pick, toleranceMs = 0.001) {
  validatePick(pick)
  return [...picks.filter(p => Math.abs(p.time_ms - pick.time_ms) > toleranceMs), { ...pick }]
    .sort((a, b) => a.time_ms - b.time_ms)
}

export function editPick(picks, index, patch) {
  const updated = validatePick({ ...picks[index], ...patch })
  if (picks.some((p, i) => i !== index && Math.abs(p.time_ms - updated.time_ms) < 0.001)) {
    throw new Error('Two picks cannot have the same time')
  }
  return picks.map((p, i) => i === index ? updated : p).sort((a, b) => a.time_ms - b.time_ms)
}

export function toFunctions(map) {
  return Object.entries(map).filter(([, picks]) => picks.length).map(([key, picks]) => {
    const [inline, cdp] = key.split(':').map(Number)
    return { inline, cdp, picks }
  }).sort((a, b) => a.inline - b.inline || a.cdp - b.cdp)
}

export function fromFunctions(functions) {
  return Object.fromEntries(functions.map(f => [functionKey(f.inline, f.cdp), f.picks.map(p => ({ ...p }))]))
}

export function historyReducer(state, action) {
  if (action.type === 'reset') return { past: [], present: action.value, future: [] }
  if (action.type === 'commit') return { past: [...state.past.slice(-99), state.present], present: action.value, future: [] }
  if (action.type === 'undo' && state.past.length) return {
    past: state.past.slice(0, -1), present: state.past.at(-1), future: [state.present, ...state.future],
  }
  if (action.type === 'redo' && state.future.length) return {
    past: [...state.past, state.present], present: state.future[0], future: state.future.slice(1),
  }
  return state
}
