import { useTranslation } from 'react-i18next'
import type { GenerationStatus } from './types'

interface Props {
  generation: GenerationStatus
}

export default function GenerationProgress({ generation }: Props) {
  const { t } = useTranslation('tts')
  const { status, progress, current_segment, total_segments, error_message } = generation

  const statusLabel = {
    pending: t('status_pending'),
    processing: t('status_processing'),
    done: t('status_done'),
    error: t('status_error'),
  }[status] || status

  const statusClass = {
    pending: '',
    processing: '',
    done: 'badge-success',
    error: 'badge-danger',
  }[status] || ''

  return (
    <div className="tts-generation-progress">
      <div className="tts-progress-label">
        <span className={`tts-voice-card-badge ${statusClass}`}>{statusLabel}</span>
        {total_segments > 0 && (
          <span>{t('segment_progress', { current: current_segment, total: total_segments })}</span>
        )}
      </div>

      <div className="tts-progress-bar">
        <div className="tts-progress-bar-fill" style={{ width: `${progress}%` }} />
      </div>

      {error_message && (
        <p className="text-danger">{error_message}</p>
      )}
    </div>
  )
}
