import { useState, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import Layout from '../../core/Layout'
import api from '../../api'
import VoiceCard from './VoiceCard'
import VoiceRecorder from './VoiceRecorder'
import { useVoices } from './useVoices'
import type { Voice } from './types'
import './tts.scss'

export default function VoicesPage() {
  const { t } = useTranslation('tts')
  const { genericVoices, customVoices, refetch } = useVoices()

  // Create voice state
  const [activeTab, setActiveTab] = useState<'record' | 'upload'>('record')
  const [name, setName] = useState('')
  const [color, setColor] = useState('#6366f1')
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null)
  const [creating, setCreating] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Edit voice state
  const [editingVoice, setEditingVoice] = useState<Voice | null>(null)
  const [editName, setEditName] = useState('')
  const [editColor, setEditColor] = useState('')
  const [editAudioBlob, setEditAudioBlob] = useState<Blob | null>(null)
  const [editTab, setEditTab] = useState<'record' | 'upload'>('upload')
  const [saving, setSaving] = useState(false)
  const editFileInputRef = useRef<HTMLInputElement>(null)

  // ── Create handlers ──────────────────────────────────────
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) setAudioBlob(file)
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file && file.type.startsWith('audio/')) setAudioBlob(file)
  }, [])

  const handleCreate = async () => {
    if (!audioBlob || !name.trim()) return
    setCreating(true)
    try {
      const formData = new FormData()
      formData.append('file', audioBlob, 'recording.webm')
      formData.append('name', name.trim())
      formData.append('color', color)
      await api.post('/tts/voices', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setName('')
      setAudioBlob(null)
      refetch()
    } catch (err) {
      console.error('Failed to create voice', err)
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (uuid: string) => {
    if (!confirm(t('delete_voice_confirm'))) return
    try {
      await api.delete(`/tts/voices/${uuid}`)
      if (editingVoice?.uuid === uuid) setEditingVoice(null)
      refetch()
    } catch (err) {
      console.error('Failed to delete voice', err)
    }
  }

  // ── Edit handlers ────────────────────────────────────────
  const handleStartEdit = (uuid: string) => {
    const voice = customVoices.find((v) => v.uuid === uuid)
    if (!voice) return
    setEditingVoice(voice)
    setEditName(voice.name)
    setEditColor(voice.color)
    setEditAudioBlob(null)
    setEditTab('upload')
  }

  const handleCancelEdit = () => {
    setEditingVoice(null)
    setEditAudioBlob(null)
  }

  const handleEditFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) setEditAudioBlob(file)
  }

  const handleEditDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file && file.type.startsWith('audio/')) setEditAudioBlob(file)
  }, [])

  const handleSaveEdit = async () => {
    if (!editingVoice || !editName.trim()) return
    setSaving(true)
    try {
      const formData = new FormData()
      formData.append('name', editName.trim())
      formData.append('color', editColor)
      if (editAudioBlob) {
        formData.append('file', editAudioBlob, 'recording.wav')
      }
      await api.put(`/tts/voices/${editingVoice.uuid}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setEditingVoice(null)
      setEditAudioBlob(null)
      refetch()
    } catch (err) {
      console.error('Failed to update voice', err)
    } finally {
      setSaving(false)
    }
  }

  const breadcrumb = [
    { label: t('nav_tts'), path: '/tts' },
    { label: t('voices_title') },
  ]

  return (
    <Layout breadcrumb={breadcrumb} title={t('voices_title')}>
      {/* Page header */}
      <div className="unified-card page-header-card">
        <div className="unified-page-header">
          <div className="unified-page-header-info">
            <h1>{t('voices_title')}</h1>
            <p>{t('voices_subtitle')}</p>
          </div>
          <div className="page-header-stats">
            <div className="page-header-stat">
              <span className="page-header-stat-value">{genericVoices.length}</span>
              <span className="page-header-stat-label">{t('generic_voices')}</span>
            </div>
            <div className="page-header-stat">
              <span className="page-header-stat-value">{customVoices.length}</span>
              <span className="page-header-stat-label">{t('custom_voices')}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Generic voices */}
      <div className="unified-card">
        <div className="unified-card-header">
          <h2>{t('generic_voices')}</h2>
        </div>
        <div className="tts-card-content">
          <div className="tts-voice-grid">
            {genericVoices.map((v) => (
              <VoiceCard key={v.uuid} voice={v} />
            ))}
          </div>
        </div>
      </div>

      {/* Custom voices */}
      <div className="unified-card">
        <div className="unified-card-header">
          <h2>{t('custom_voices')}</h2>
        </div>
        <div className="tts-card-content">
          {customVoices.length === 0 ? (
            <div className="unified-empty">{t('no_custom_voices')}</div>
          ) : (
            <div className="tts-voice-grid">
              {customVoices.map((v) => (
                <VoiceCard
                  key={v.uuid}
                  voice={v}
                  onDelete={handleDelete}
                  onEdit={handleStartEdit}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Edit voice panel ─────────────────────────────── */}
      {editingVoice && (
        <div className="unified-card">
          <div className="unified-card-header">
            <h2>{t('edit_voice_title')} — {editingVoice.name}</h2>
          </div>
          <div className="tts-card-content">
            <div className="form-row">
              <div className="form-group tts-form-group-grow">
                <label>{t('voice_name')}</label>
                <input
                  type="text"
                  className="form-control"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>{t('voice_color')}</label>
                <input
                  type="color"
                  value={editColor}
                  onChange={(e) => setEditColor(e.target.value)}
                />
              </div>
            </div>

            <div className="tts-create-voice-tabs">
              <button
                type="button"
                className={`tts-create-voice-tab ${editTab === 'record' ? 'is-active' : ''}`}
                onClick={() => setEditTab('record')}
              >
                {t('tab_record')}
              </button>
              <button
                type="button"
                className={`tts-create-voice-tab ${editTab === 'upload' ? 'is-active' : ''}`}
                onClick={() => setEditTab('upload')}
              >
                {t('tab_upload')}
              </button>
            </div>

            {editTab === 'record' ? (
              <VoiceRecorder onRecorded={setEditAudioBlob} />
            ) : (
              <div
                className="tts-upload-zone"
                onClick={() => editFileInputRef.current?.click()}
                onDrop={handleEditDrop}
                onDragOver={(e) => e.preventDefault()}
              >
                <span className="tts-upload-zone-label">
                  {editAudioBlob
                    ? (editAudioBlob as File).name || t('record_preview')
                    : t('upload_audio')}
                </span>
                <span className="tts-upload-zone-hint">
                  {editAudioBlob ? '' : t('upload_formats')}
                </span>
                <input
                  ref={editFileInputRef}
                  type="file"
                  accept="audio/*"
                  className="hidden-input"
                  onChange={handleEditFileChange}
                />
              </div>
            )}

            <div className="form-actions">
              <button type="button" className="btn btn-secondary" onClick={handleCancelEdit}>
                {t('record_retry')}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleSaveEdit}
                disabled={saving || !editName.trim()}
              >
                {saving ? '...' : t('save')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Create voice ─────────────────────────────────── */}
      <div className="unified-card">
        <div className="unified-card-header">
          <h2>{t('create_voice')}</h2>
        </div>
        <div className="tts-card-content">
          <div className="form-row">
            <div className="form-group tts-form-group-grow">
              <label>{t('voice_name')}</label>
              <input
                type="text"
                className="form-control"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('voice_name_placeholder')}
              />
            </div>
            <div className="form-group">
              <label>{t('voice_color')}</label>
              <input
                type="color"
                value={color}
                onChange={(e) => setColor(e.target.value)}
              />
            </div>
          </div>

          <div className="tts-create-voice-tabs">
            <button
              type="button"
              className={`tts-create-voice-tab ${activeTab === 'record' ? 'is-active' : ''}`}
              onClick={() => setActiveTab('record')}
            >
              {t('tab_record')}
            </button>
            <button
              type="button"
              className={`tts-create-voice-tab ${activeTab === 'upload' ? 'is-active' : ''}`}
              onClick={() => setActiveTab('upload')}
            >
              {t('tab_upload')}
            </button>
          </div>

          {activeTab === 'record' && (
            <>
              <div className="form-group">
                <label>{t('reference_text_title')}</label>
                <p className="tts-upload-zone-hint">{t('reference_text_hint')}</p>
              </div>
              <div className="tts-reference-text">
                {t('reference_text')}
              </div>
              <VoiceRecorder onRecorded={setAudioBlob} />
            </>
          )}

          {activeTab === 'upload' && (
            <div
              className="tts-upload-zone"
              onClick={() => fileInputRef.current?.click()}
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
            >
              <span className="tts-upload-zone-label">
                {audioBlob ? (audioBlob as File).name || t('record_preview') : t('upload_audio')}
              </span>
              <span className="tts-upload-zone-hint">{t('upload_formats')}</span>
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*"
                className="hidden-input"
                onChange={handleFileChange}
              />
            </div>
          )}

          {audioBlob && (
            <div className="form-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleCreate}
                disabled={creating || !name.trim()}
              >
                {creating ? '...' : t('create_btn')}
              </button>
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
