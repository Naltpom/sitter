import { useState, useEffect, useCallback } from 'react'
import api from '../../api'
import type { Conversation } from './types'

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(true)

  const fetchConversations = useCallback(async () => {
    try {
      const res = await api.get<{ items: Conversation[] }>('/tts/conversations')
      setConversations(res.data.items)
    } catch (err) {
      console.error('Failed to fetch conversations', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchConversations()
  }, [fetchConversations])

  const create = useCallback(async (title: string, content: string): Promise<Conversation | null> => {
    try {
      const res = await api.post<Conversation>('/tts/conversations', { title, content })
      setConversations((prev) => [res.data, ...prev])
      return res.data
    } catch (err) {
      console.error('Failed to create conversation', err)
      return null
    }
  }, [])

  const update = useCallback(async (uuid: string, data: { title?: string; content?: string }): Promise<Conversation | null> => {
    try {
      const res = await api.put<Conversation>(`/tts/conversations/${uuid}`, data)
      setConversations((prev) => prev.map((c) => (c.uuid === uuid ? res.data : c)))
      return res.data
    } catch (err) {
      console.error('Failed to update conversation', err)
      return null
    }
  }, [])

  const remove = useCallback(async (uuid: string) => {
    try {
      await api.delete(`/tts/conversations/${uuid}`)
      setConversations((prev) => prev.filter((c) => c.uuid !== uuid))
    } catch (err) {
      console.error('Failed to delete conversation', err)
    }
  }, [])

  return { conversations, loading, create, update, remove, refetch: fetchConversations }
}
