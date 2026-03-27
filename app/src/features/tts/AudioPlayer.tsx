import { useRef, useState, useCallback, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import api from '../../api'

interface Props {
  src: string | null
}

export default function AudioPlayer({ src }: Props) {
  const { t } = useTranslation('tts')
  const audioRef = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [blobUrl, setBlobUrl] = useState<string | null>(null)

  // Fetch audio via authenticated API
  useEffect(() => {
    if (!src) {
      setBlobUrl(null)
      return
    }
    let cancelled = false
    api.get(src, { responseType: 'blob' }).then((res) => {
      if (!cancelled) {
        const url = URL.createObjectURL(res.data)
        setBlobUrl(url)
      }
    }).catch(() => {})

    return () => {
      cancelled = true
      if (blobUrl) URL.revokeObjectURL(blobUrl)
    }
  }, [src])

  const togglePlay = useCallback(() => {
    if (!audioRef.current) return
    if (playing) {
      audioRef.current.pause()
    } else {
      audioRef.current.play()
    }
    setPlaying(!playing)
  }, [playing])

  const handleTimeUpdate = () => {
    if (audioRef.current) setCurrentTime(audioRef.current.currentTime)
  }

  const handleLoadedMetadata = () => {
    if (audioRef.current) setDuration(audioRef.current.duration)
  }

  const handleEnded = () => setPlaying(false)

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!audioRef.current || !duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const pct = (e.clientX - rect.left) / rect.width
    audioRef.current.currentTime = pct * duration
  }

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60)
    const s = Math.floor(secs % 60)
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  const handleDownload = () => {
    if (!blobUrl) return
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = 'tts_audio.mp3'
    a.click()
  }

  if (!blobUrl) return null

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0

  return (
    <div className="tts-audio-player">
      <audio
        ref={audioRef}
        src={blobUrl}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
      />

      <button type="button" className="tts-audio-player-btn" onClick={togglePlay}>
        {playing ? '⏸' : '▶'}
      </button>

      <div className="tts-audio-progress" onClick={handleSeek}>
        <div className="tts-audio-progress-fill" style={{ width: `${progress}%` }} />
      </div>

      <span className="tts-audio-time">
        {formatTime(currentTime)} / {formatTime(duration)}
      </span>

      <button type="button" className="btn btn-sm btn-secondary" onClick={handleDownload}>
        {t('download')}
      </button>
    </div>
  )
}
