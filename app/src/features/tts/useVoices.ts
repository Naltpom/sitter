import { useState, useEffect, useCallback } from 'react'
import api from '../../api'
import type { Voice } from './types'

export function useVoices() {
  const [voices, setVoices] = useState<Voice[]>([])
  const [loading, setLoading] = useState(true)

  const fetchVoices = useCallback(async () => {
    try {
      const res = await api.get<Voice[]>('/tts/voices')
      setVoices(res.data)
    } catch (err) {
      console.error('Failed to fetch voices', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchVoices()
  }, [fetchVoices])

  const genericVoices = voices.filter((v) => v.voice_type === 'generic')
  const customVoices = voices.filter((v) => v.voice_type === 'custom')

  return { voices, genericVoices, customVoices, loading, refetch: fetchVoices }
}
