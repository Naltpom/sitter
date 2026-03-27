import { useState, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import api from '../../api'
import type { Voice } from './types'

interface Props {
  voice: Voice
  onDelete?: (uuid: string) => void
  onEdit?: (uuid: string) => void
}

export default function VoiceCard({ voice, onDelete, onEdit }: Props) {
  const { t } = useTranslation('tts')
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const audioRef = useRef<HTMLAudioElement>(null)

  const handlePreview = async () => {
    setLoading(true)
    try {
      const res = await api.post(
        `/tts/voices/${voice.uuid}/preview`,
        { text: 'Bonjour, ceci est un test de synthese vocale.' },
        { responseType: 'blob' },
      )
      const url = URL.createObjectURL(res.data)
      setPreviewUrl(url)
      setTimeout(() => audioRef.current?.play(), 100)
    } catch (err) {
      console.error('Preview failed', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="tts-voice-card" style={{ '--voice-color': voice.color } as React.CSSProperties}>
      <div className="tts-voice-card-header">
        <span className="tts-voice-card-dot" style={{ '--voice-dot-bg': voice.color } as React.CSSProperties} />
        <span className="tts-voice-card-name">{voice.name}</span>
        <div className="tts-voice-card-badges">
          <span className="tts-voice-card-badge">
            {voice.voice_type === 'custom' ? t('custom') : t('generic')}
          </span>
          <span className="tts-voice-card-badge">{voice.engine}</span>
        </div>
      </div>

      <div className="tts-voice-card-actions">
        <button
          type="button"
          className="btn btn-sm btn-secondary"
          onClick={handlePreview}
          disabled={loading}
        >
          {loading ? '...' : t('preview')}
        </button>
        {voice.voice_type === 'custom' && onEdit && (
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={() => onEdit(voice.uuid)}
          >
            {t('edit_voice')}
          </button>
        )}
        {voice.voice_type === 'custom' && onDelete && (
          <button
            type="button"
            className="btn btn-sm btn-danger"
            onClick={() => onDelete(voice.uuid)}
          >
            {t('delete_voice')}
          </button>
        )}
      </div>

      {previewUrl && <audio ref={audioRef} src={previewUrl} controls className="tts-voice-card-audio" />}
    </div>
  )
}
