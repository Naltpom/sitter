import { useState, useRef, useCallback, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  type AudioSettings,
  DEFAULT_SETTINGS,
  decodeBlob,
  processAudio,
  audioBufferToWavBlob,
  drawWaveform,
} from './audioProcessor'

interface Props {
  audioBlob: Blob
  onConfirm: (processedBlob: Blob) => void
  onCancel: () => void
}

export default function AudioEditorPanel({ audioBlob, onConfirm, onCancel }: Props) {
  const { t } = useTranslation('tts')
  const [settings, setSettings] = useState<AudioSettings>({ ...DEFAULT_SETTINGS })
  const [originalBuffer, setOriginalBuffer] = useState<AudioBuffer | null>(null)
  const [processedBuffer, setProcessedBuffer] = useState<AudioBuffer | null>(null)
  const [processing, setProcessing] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  const originalCanvasRef = useRef<HTMLCanvasElement>(null)
  const processedCanvasRef = useRef<HTMLCanvasElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)

  // Decode original blob on mount
  useEffect(() => {
    decodeBlob(audioBlob).then((buf) => {
      setOriginalBuffer(buf)
      setProcessedBuffer(buf)
    })
  }, [audioBlob])

  // Draw waveforms when buffers change
  useEffect(() => {
    if (originalBuffer && originalCanvasRef.current) {
      drawWaveform(originalCanvasRef.current, originalBuffer, 'var(--primary)')
    }
  }, [originalBuffer])

  useEffect(() => {
    if (processedBuffer && processedCanvasRef.current) {
      drawWaveform(processedCanvasRef.current, processedBuffer, '#10b981')
    }
  }, [processedBuffer])

  // Apply processing when settings change (debounced)
  useEffect(() => {
    if (!originalBuffer) return
    const timeout = setTimeout(async () => {
      setProcessing(true)
      try {
        const result = await processAudio(originalBuffer, settings)
        setProcessedBuffer(result)
        // Generate preview URL
        const blob = audioBufferToWavBlob(result)
        if (previewUrl) URL.revokeObjectURL(previewUrl)
        setPreviewUrl(URL.createObjectURL(blob))
      } catch (err) {
        console.error('Audio processing error', err)
      }
      setProcessing(false)
    }, 300)
    return () => clearTimeout(timeout)
  }, [settings, originalBuffer])

  const handleConfirm = useCallback(() => {
    if (!processedBuffer) return
    const blob = audioBufferToWavBlob(processedBuffer)
    onConfirm(blob)
  }, [processedBuffer, onConfirm])

  const updateSetting = useCallback(<K extends keyof AudioSettings>(key: K, value: AudioSettings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }))
  }, [])

  const handlePreview = useCallback(() => {
    if (audioRef.current && previewUrl) {
      audioRef.current.src = previewUrl
      audioRef.current.play()
    }
  }, [previewUrl])

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [])

  if (!originalBuffer) {
    return <div className="tts-audio-editor-loading">...</div>
  }

  return (
    <div className="tts-audio-editor">
      {/* Waveforms */}
      <div className="tts-audio-editor-waveforms">
        <div className="tts-waveform-block">
          <span className="tts-waveform-label">{t('editor_original')}</span>
          <canvas ref={originalCanvasRef} className="tts-waveform-canvas" />
        </div>
        <div className="tts-waveform-block">
          <span className="tts-waveform-label">
            {t('editor_processed')} {processing && '...'}
          </span>
          <canvas ref={processedCanvasRef} className="tts-waveform-canvas" />
        </div>
      </div>

      {/* Controls */}
      <div className="tts-audio-editor-controls">
        <div className="tts-control-row">
          <label>{t('editor_gain')}</label>
          <input
            type="range"
            min="0"
            max="2"
            step="0.05"
            value={settings.gain}
            onChange={(e) => updateSetting('gain', parseFloat(e.target.value))}
          />
          <span className="tts-control-value">{settings.gain.toFixed(2)}</span>
        </div>

        <div className="tts-control-row">
          <label>{t('editor_highpass')}</label>
          <input
            type="range"
            min="20"
            max="500"
            step="10"
            value={settings.highPassFreq}
            onChange={(e) => updateSetting('highPassFreq', parseInt(e.target.value))}
          />
          <span className="tts-control-value">{settings.highPassFreq} Hz</span>
        </div>

        <div className="tts-control-row">
          <label>{t('editor_lowpass')}</label>
          <input
            type="range"
            min="4000"
            max="20000"
            step="500"
            value={settings.lowPassFreq}
            onChange={(e) => updateSetting('lowPassFreq', parseInt(e.target.value))}
          />
          <span className="tts-control-value">{(settings.lowPassFreq / 1000).toFixed(1)}k Hz</span>
        </div>

        <div className="tts-control-row">
          <label>{t('editor_noisegate')}</label>
          <input
            type="range"
            min="-60"
            max="-10"
            step="1"
            value={settings.noiseGateDb}
            onChange={(e) => updateSetting('noiseGateDb', parseInt(e.target.value))}
          />
          <span className="tts-control-value">{settings.noiseGateDb} dB</span>
        </div>

        <div className="tts-control-row">
          <label>{t('editor_compression')}</label>
          <input
            type="range"
            min="1"
            max="12"
            step="0.5"
            value={settings.compressionRatio}
            onChange={(e) => updateSetting('compressionRatio', parseFloat(e.target.value))}
          />
          <span className="tts-control-value">{settings.compressionRatio}:1</span>
        </div>
      </div>

      {/* Hidden audio for preview */}
      <audio ref={audioRef} />

      {/* Actions */}
      <div className="tts-audio-editor-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          {t('record_retry')}
        </button>
        <button type="button" className="btn btn-secondary" onClick={handlePreview} disabled={!previewUrl}>
          {t('editor_preview')}
        </button>
        <button type="button" className="btn btn-primary" onClick={handleConfirm} disabled={processing}>
          {t('editor_confirm')}
        </button>
      </div>
    </div>
  )
}
