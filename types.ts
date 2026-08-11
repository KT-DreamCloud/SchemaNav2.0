export type SpecLanguage = 'yaml' | 'json'

/** Which half of the sidebar a spec belongs to. Chosen when the file is opened. */
export type SpecKind = 'frontend' | 'csm'

export type SpecTab = {
  id: string
  name: string
  language: SpecLanguage
  content: string
  updatedAt: number
  dirty: boolean
  kind: SpecKind
  /** Set when the section was chosen by hand; blocks auto-detection */
  pinnedKind?: boolean
}

export type YamlHistoryEntry = {
  id: string
  name: string
  content: string
  viewedAt: number
  /** Short fingerprint for dedupe (name + content length + hash prefix) */
  fingerprint: string
  /** Dedupe identity: microservice name + version */
  specKey?: string
  /** OpenAPI info.title — microservice / API display name */
  msName?: string
  /** OpenAPI info.version */
  msVersion?: string
  /** e.g. OAS 3.0 */
  oasLabel?: string | null
  /** Frontend spec or backend CSM service */
  kind?: SpecKind
  /** Set when the section was chosen by hand; blocks auto-detection */
  pinnedKind?: boolean
}
