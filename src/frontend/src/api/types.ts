export type Direction = 'inbound' | 'outbound'
export type EventType = 'ring' | 'call' | 'connect' | 'disconnect'
export type LineStatus = 'idle' | 'ring' | 'call' | 'talking' | 'finished' | 'missed' | 'notReached'
export type CallStatus = 'ringing' | 'dialing' | 'answered' | 'missed' | 'notReached'
export type NumberType = 'private' | 'business' | 'mobile'

export interface DeviceInfo {
  id: string
  extension: string
  name: string
  type: string
}

export interface Call {
  id: string
  connection_id: number
  caller_number: string
  called_number: string
  direction: Direction
  status: CallStatus
  caller_device: DeviceInfo | null
  called_device: DeviceInfo | null
  msn: string | null
  trunk_id: string | null
  line_id: number | null
  is_internal: boolean
  started_at: string
  connected_at: string | null
  finished_at: string | null
  duration_seconds: number | null
  caller_display: string | null
  called_display: string | null
  created_at: string
  updated_at: string
}

export interface CallListResponse {
  items: Call[]
  next_cursor: string | null
  limit: number
}

export interface CallLogEntry {
  id: number
  number: string
  direction: Direction
  event_type: EventType
  source: string
  timestamp: string
}

export interface CallLogResponse {
  items: CallLogEntry[]
  next_cursor: string | null
  limit: number
}

export interface Contact {
  number: string
  name: string
  number_type: NumberType
  tags: string[]
  notes: string | null
  spam_score: number
  source: string | null
  last_seen: string | null
  created_at: string
  updated_at: string
}

export interface ContactCreate {
  number: string
  name: string
  number_type?: NumberType
  tags?: string[]
  notes?: string
  spam_score?: number
}

export interface ContactUpdate {
  name?: string
  number_type?: NumberType
  tags?: string[]
  notes?: string
  spam_score?: number
}

export interface CacheEntry {
  number: string
  adapter: string
  result_name: string | null
  spam_score: number | null
  cached_at: string
  ttl_days: number | null
  expired: boolean
}

export interface CacheResponse {
  entries: CacheEntry[]
}

export interface LineState {
  line_id: number
  status: LineStatus
  connection_id: number | null
  caller_number: string | null
  called_number: string | null
  caller_display: string | null
  called_display: string | null
  direction: Direction | null
  trunk_id: string | null
  caller_device: DeviceInfo | null
  called_device: DeviceInfo | null
  is_internal: boolean
  last_changed: string
}

export interface TrunkStatus {
  id: string
  type: string
  label: string | null
  busy: boolean
}

export interface MsnInfo {
  msn: string
  e164: string
  label: string | null
}

export interface DeviceConfig {
  id: string
  extension: string
  name: string
  type: string
}

export interface PbxStatus {
  lines: LineState[]
  trunks: TrunkStatus[]
  msns: MsnInfo[]
  devices: DeviceConfig[]
}

export interface AdapterConfig {
  type: string
  name: string
  enabled: boolean
  order: number
  config: Record<string, unknown>
}

export interface AppConfig {
  input_adapters: AdapterConfig[]
  resolver_adapters: AdapterConfig[]
  output_adapters: AdapterConfig[]
}

export interface ResolveResult {
  number: string
  name: string | null
  tags: string[]
  notes: string | null
  spam_score: number | null
  source: string | null
  cached: boolean
}
