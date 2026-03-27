export interface Voice {
  id: number
  uuid: string
  name: string
  slug: string
  voice_type: 'generic' | 'custom'
  engine: 'piper' | 'xtts'
  piper_model_name: string | null
  color: string
  language: string
  is_active: boolean
  user_id: number | null
  created_at: string
}

export interface Conversation {
  id: number
  uuid: string
  title: string
  content: string
  user_id: number
  created_at: string
  updated_at: string
  latest_generation: AudioGeneration | null
}

export interface AudioGeneration {
  id: number
  uuid: string
  conversation_id: number
  status: 'pending' | 'processing' | 'done' | 'error'
  progress: number
  current_segment: number
  total_segments: number
  output_format: string
  duration_seconds: number | null
  file_size_bytes: number | null
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export interface GenerationStatus {
  uuid: string
  status: 'pending' | 'processing' | 'done' | 'error'
  progress: number
  current_segment: number
  total_segments: number
  duration_seconds: number | null
  file_size_bytes: number | null
  error_message: string | null
}

export interface TextSegment {
  voice_slug: string
  text: string
}
