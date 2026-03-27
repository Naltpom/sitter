import { useTranslation } from 'react-i18next'
import type { Conversation } from './types'

interface Props {
  conversations: Conversation[]
  activeUuid: string | null
  onSelect: (uuid: string) => void
  onDelete: (uuid: string) => void
}

export default function ConversationList({ conversations, activeUuid, onSelect, onDelete }: Props) {
  const { t } = useTranslation('tts')

  if (conversations.length === 0) {
    return <div className="unified-empty">{t('no_conversations')}</div>
  }

  return (
    <div className="tts-conv-list">
      {conversations.map((c) => (
        <div
          key={c.uuid}
          className={`tts-conv-item ${c.uuid === activeUuid ? 'is-active' : ''}`}
          onClick={() => onSelect(c.uuid)}
        >
          <div>
            <div className="tts-conv-item-title">{c.title}</div>
            <div className="tts-conv-item-date">
              {new Date(c.updated_at).toLocaleDateString()}
            </div>
          </div>
          <button
            type="button"
            className="btn btn-sm btn-icon tts-conv-item-delete"
            onClick={(e) => {
              e.stopPropagation()
              onDelete(c.uuid)
            }}
          >
            &times;
          </button>
        </div>
      ))}
    </div>
  )
}
