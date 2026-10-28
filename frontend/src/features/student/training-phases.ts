export const PRE_HIRE_MODES = [
  'group_interview',
  'stress_interview',
  'presentation_defense',
  'career_planning',
] as const

export const POST_HIRE_MODES = ['workplace'] as const

export type PreHireMode = (typeof PRE_HIRE_MODES)[number]
export type PostHireMode = (typeof POST_HIRE_MODES)[number]
export type SimulationMode = PreHireMode | PostHireMode

export function isPreHireMode(value: string | null | undefined): value is PreHireMode {
  return Boolean(value && (PRE_HIRE_MODES as readonly string[]).includes(value))
}

export function isPostHireMode(value: string | null | undefined): value is PostHireMode {
  return Boolean(value && (POST_HIRE_MODES as readonly string[]).includes(value))
}

export const phaseLabel = {
  preHire: '入职前 · 求职训练',
  postHire: '入职后 · 职场训练',
} as const
