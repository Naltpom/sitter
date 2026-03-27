import { useState, useRef, useCallback, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import AudioEditorPanel from './AudioEditorPanel'

interface Props {
  onRecorded: (blob: Blob) => void
}

export default function VoiceRecorder({ onRecorded }: Props) {
  const { t } = useTranslation('tts')
  const [isRecording, setIsRecording] = useState(false)
  const [duration, setDuration] = useState(0)
  const [rawBlob, setRawBlob] = useState<Blob | null>(null)
  const [showEditor, setShowEditor] = useState(false)

  const mediaRecorder = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])
  const timerRef = useRef<number | null>(null)

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
      mediaRecorder.current = recorder
      chunks.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data)
      }

      recorder.onstop = () => {
        const blob = new Blob(chunks.current, { type: 'audio/webm' })
        setRawBlob(blob)
        setShowEditor(true)
        stream.getTracks().forEach((track) => track.stop())
      }

      recorder.start()
      setIsRecording(true)
      setDuration(0)
      setRawBlob(null)
      setShowEditor(false)

      timerRef.current = window.setInterval(() => {
        setDuration((d) => d + 1)
      }, 1000)
    } catch (err) {
      console.error('Microphone access denied', err)
    }
  }, [])

  const stopRecording = useCallback(() => {
    if (mediaRecorder.current && mediaRecorder.current.state === 'recording') {
      mediaRecorder.current.stop()
    }
    setIsRecording(false)
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const handleEditorConfirm = useCallback((processedBlob: Blob) => {
    onRecorded(processedBlob)
    setShowEditor(false)
    setRawBlob(null)
  }, [onRecorded])

  const handleEditorCancel = useCallback(() => {
    setShowEditor(false)
    setRawBlob(null)
    setDuration(0)
  }, [])

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60)
    const s = secs % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  // Show audio editor after recording
  if (showEditor && rawBlob) {
    return (
      <AudioEditorPanel
        audioBlob={rawBlob}
        onConfirm={handleEditorConfirm}
        onCancel={handleEditorCancel}
      />
    )
  }

  return (
    <div className="tts-voice-recorder">
      <button
        type="button"
        className={`tts-record-btn ${isRecording ? 'is-recording' : ''}`}
        onClick={isRecording ? stopRecording : startRecording}
      >
        <span className="tts-record-indicator" />
      </button>

      <span className="tts-record-timer">{formatTime(duration)}</span>

      {isRecording && (
        <span className="tts-voice-card-badge">{t('recording')}</span>
      )}

      {!isRecording && !rawBlob && (
        <span className="tts-upload-zone-hint">{t('min_duration')}</span>
      )}
    </div>
  )
}
