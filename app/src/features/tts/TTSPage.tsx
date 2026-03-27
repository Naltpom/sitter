import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import Layout from '../../core/Layout'
import ConversationEditor from './ConversationEditor'
import ConversationList from './ConversationList'
import AudioPlayer from './AudioPlayer'
import GenerationProgress from './GenerationProgress'
import { useVoices } from './useVoices'
import { useConversations } from './useConversations'
import { useGeneration } from './useGeneration'
import './tts.scss'

export default function TTSPage() {
  const { t } = useTranslation('tts')
  const { voices } = useVoices()
  const { conversations, create, update, remove } = useConversations()
  const { generation, audioUrl, startGeneration, reset, restoreFromConversation } = useGeneration()

  const [activeUuid, setActiveUuid] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSelect = useCallback((uuid: string) => {
    const conv = conversations.find((c) => c.uuid === uuid)
    if (conv) {
      setActiveUuid(uuid)
      setTitle(conv.title)
      setContent(conv.content)
      // Restore audio if conversation has a completed generation
      restoreFromConversation(conv)
    }
  }, [conversations, restoreFromConversation])

  const handleCreate = useCallback(async () => {
    const conv = await create(t('new_conversation'), '<p></p>')
    if (conv) {
      setActiveUuid(conv.uuid)
      setTitle(conv.title)
      setContent(conv.content)
      reset()
    }
  }, [create, reset, t])

  const handleDelete = useCallback(async (uuid: string) => {
    if (!confirm(t('delete_conversation_confirm'))) return
    await remove(uuid)
    if (activeUuid === uuid) {
      setActiveUuid(null)
      setTitle('')
      setContent('')
      reset()
    }
  }, [remove, activeUuid, reset, t])

  const handleSave = useCallback(async () => {
    if (!activeUuid) return
    setSaving(true)
    await update(activeUuid, { title, content })
    setSaving(false)
  }, [activeUuid, title, content, update])

  const handleGenerate = useCallback(async () => {
    if (!activeUuid) return
    await update(activeUuid, { title, content })
    await startGeneration(activeUuid)
  }, [activeUuid, title, content, update, startGeneration])

  const isGenerating = generation?.status === 'pending' || generation?.status === 'processing'

  const breadcrumb = [{ label: t('page_title') }]

  return (
    <Layout breadcrumb={breadcrumb} title={t('page_title')}>
      <div className="unified-card page-header-card">
        <div className="unified-page-header">
          <div className="unified-page-header-info">
            <h1>{t('page_title')}</h1>
            <p>{t('page_subtitle')}</p>
          </div>
          <div className="unified-page-header-actions">
            <Link to="/tts/voices" className="btn btn-secondary btn-sm">
              {t('nav_voices')}
            </Link>
          </div>
        </div>
      </div>

      <div className="tts-page">
        <div className="tts-sidebar">
          <div className="unified-card tts-sidebar-card">
            <div className="unified-card-header">
              <h2>{t('conversations')}</h2>
              <div className="unified-card-header-actions">
                <button type="button" className="btn btn-sm btn-primary" onClick={handleCreate}>+</button>
              </div>
            </div>
            <div className="tts-sidebar-body">
              <ConversationList
                conversations={conversations}
                activeUuid={activeUuid}
                onSelect={handleSelect}
                onDelete={handleDelete}
              />
            </div>
          </div>
        </div>

        <div className="tts-main">
          {activeUuid ? (
            <>
              <div className="unified-card">
                <div className="tts-editor-card-body">
                  <div className="form-group">
                    <label>{t('conversation_title')}</label>
                    <input
                      type="text"
                      className="form-control"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder={t('conversation_title_placeholder')}
                    />
                  </div>

                  <ConversationEditor
                    content={content}
                    onChange={setContent}
                    voices={voices}
                  />

                  <div className="form-actions">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={handleSave}
                      disabled={saving}
                    >
                      {saving ? '...' : t('save')}
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={handleGenerate}
                      disabled={isGenerating || !content.trim()}
                    >
                      {isGenerating ? t('generating') : t('generate')}
                    </button>
                  </div>
                </div>
              </div>

              {generation && generation.status !== 'done' && (
                <GenerationProgress generation={generation} />
              )}

              {audioUrl && (
                <AudioPlayer src={audioUrl} />
              )}
            </>
          ) : (
            <div className="unified-card">
              <div className="unified-empty">{t('no_conversations')}</div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
