import { useState, useCallback, useRef } from 'react'
import { useRealtimeEvent } from '../../core/realtime/useRealtimeEvent'
import api from '../../api'
import type { GenerationStatus, AudioGeneration, Conversation } from './types'

interface SSEProgressData {
  generation_uuid: string
  status: string
  progress?: number
  current_segment?: number
  total_segments?: number
  duration_seconds?: number
  file_size_bytes?: number
  error?: string
}

export function useGeneration() {
  const [generation, setGeneration] = useState<GenerationStatus | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const genUuidRef = useRef<string | null>(null)

  const handleSSE = useCallback((raw: unknown) => {
    const data = raw as SSEProgressData
    if (!genUuidRef.current || data.generation_uuid !== genUuidRef.current) return

    setGeneration({
      uuid: data.generation_uuid,
      status: data.status as GenerationStatus['status'],
      progress: data.progress ?? 0,
      current_segment: data.current_segment ?? 0,
      total_segments: data.total_segments ?? 0,
      duration_seconds: data.duration_seconds ?? null,
      file_size_bytes: data.file_size_bytes ?? null,
      error_message: data.error ?? null,
    })

    if (data.status === 'done') {
      setAudioUrl(`/tts/generations/${data.generation_uuid}/download`)
    }
  }, [])

  useRealtimeEvent('tts_progress', handleSSE)

  const startGeneration = useCallback(async (conversationUuid: string): Promise<AudioGeneration | null> => {
    setAudioUrl(null)
    setGeneration(null)

    try {
      const res = await api.post<AudioGeneration>(`/tts/conversations/${conversationUuid}/generate`)
      const gen = res.data
      genUuidRef.current = gen.uuid

      setGeneration({
        uuid: gen.uuid,
        status: gen.status,
        progress: gen.progress,
        current_segment: gen.current_segment,
        total_segments: gen.total_segments,
        duration_seconds: gen.duration_seconds,
        file_size_bytes: gen.file_size_bytes,
        error_message: gen.error_message,
      })

      return gen
    } catch (err) {
      console.error('Failed to start generation', err)
      return null
    }
  }, [])

  const restoreFromConversation = useCallback((conv: Conversation) => {
    const lg = conv.latest_generation
    if (lg && lg.status === 'done') {
      genUuidRef.current = lg.uuid
      setGeneration({
        uuid: lg.uuid,
        status: lg.status,
        progress: 100,
        current_segment: lg.total_segments,
        total_segments: lg.total_segments,
        duration_seconds: lg.duration_seconds,
        file_size_bytes: lg.file_size_bytes,
        error_message: null,
      })
      setAudioUrl(`/tts/generations/${lg.uuid}/download`)
    } else if (lg && (lg.status === 'pending' || lg.status === 'processing')) {
      genUuidRef.current = lg.uuid
      setGeneration({
        uuid: lg.uuid,
        status: lg.status,
        progress: lg.progress,
        current_segment: lg.current_segment,
        total_segments: lg.total_segments,
        duration_seconds: null,
        file_size_bytes: null,
        error_message: null,
      })
      setAudioUrl(null)
    } else {
      reset()
    }
  }, [])

  const reset = useCallback(() => {
    setGeneration(null)
    setAudioUrl(null)
    genUuidRef.current = null
  }, [])

  return { generation, audioUrl, startGeneration, reset, restoreFromConversation }
}
