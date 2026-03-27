/**
 * Audio processing utilities using Web Audio API.
 * Applies gain, high-pass filter, low-pass filter, and compression
 * to clean up voice recordings for optimal TTS cloning.
 */

export interface AudioSettings {
  gain: number            // 0.0 - 2.0 (1.0 = no change)
  highPassFreq: number    // 20 - 500 Hz (remove rumble)
  lowPassFreq: number     // 4000 - 20000 Hz (remove hiss)
  noiseGateDb: number     // -60 to -10 dB (silence below threshold)
  compressionRatio: number // 1 - 12 (dynamic range compression)
}

export const DEFAULT_SETTINGS: AudioSettings = {
  gain: 1.0,
  highPassFreq: 80,
  lowPassFreq: 14000,
  noiseGateDb: -40,
  compressionRatio: 3,
}

/** Decode a Blob into an AudioBuffer. */
export async function decodeBlob(blob: Blob): Promise<AudioBuffer> {
  const ctx = new OfflineAudioContext(1, 1, 44100)
  const arrayBuffer = await blob.arrayBuffer()
  return await ctx.decodeAudioData(arrayBuffer)
}

/** Apply processing pipeline and return a new AudioBuffer. */
export async function processAudio(
  buffer: AudioBuffer,
  settings: AudioSettings,
): Promise<AudioBuffer> {
  const ctx = new OfflineAudioContext(
    buffer.numberOfChannels,
    buffer.length,
    buffer.sampleRate,
  )

  const source = ctx.createBufferSource()
  source.buffer = buffer

  // Gain
  const gain = ctx.createGain()
  gain.gain.value = settings.gain

  // High-pass: remove low rumble / background noise
  const highPass = ctx.createBiquadFilter()
  highPass.type = 'highpass'
  highPass.frequency.value = settings.highPassFreq
  highPass.Q.value = 0.7

  // Low-pass: remove high-frequency hiss
  const lowPass = ctx.createBiquadFilter()
  lowPass.type = 'lowpass'
  lowPass.frequency.value = settings.lowPassFreq
  lowPass.Q.value = 0.7

  // Compressor: even out volume
  const compressor = ctx.createDynamicsCompressor()
  compressor.threshold.value = -24
  compressor.knee.value = 20
  compressor.ratio.value = settings.compressionRatio
  compressor.attack.value = 0.003
  compressor.release.value = 0.25

  // Chain: source → gain → highPass → lowPass → compressor → dest
  source.connect(gain)
  gain.connect(highPass)
  highPass.connect(lowPass)
  lowPass.connect(compressor)
  compressor.connect(ctx.destination)

  source.start(0)
  const rendered = await ctx.startRendering()

  // Apply noise gate (manual per-sample, not available as Web Audio node)
  return applyNoiseGate(rendered, settings.noiseGateDb)
}

/** Simple noise gate: silence samples below a dB threshold. */
function applyNoiseGate(buffer: AudioBuffer, thresholdDb: number): AudioBuffer {
  const thresholdLinear = Math.pow(10, thresholdDb / 20)
  const ctx = new OfflineAudioContext(buffer.numberOfChannels, buffer.length, buffer.sampleRate)
  const newBuffer = ctx.createBuffer(buffer.numberOfChannels, buffer.length, buffer.sampleRate)

  for (let ch = 0; ch < buffer.numberOfChannels; ch++) {
    const input = buffer.getChannelData(ch)
    const output = newBuffer.getChannelData(ch)
    let envelope = 0
    const attack = 0.002
    const release = 0.05

    for (let i = 0; i < input.length; i++) {
      const abs = Math.abs(input[i])
      if (abs > thresholdLinear) {
        envelope = Math.min(1, envelope + attack)
      } else {
        envelope = Math.max(0, envelope - release)
      }
      output[i] = input[i] * envelope
    }
  }

  return newBuffer
}

/** Convert AudioBuffer to WAV Blob. */
export function audioBufferToWavBlob(buffer: AudioBuffer): Blob {
  const numChannels = buffer.numberOfChannels
  const sampleRate = buffer.sampleRate
  const format = 1 // PCM
  const bitDepth = 16

  const bytesPerSample = bitDepth / 8
  const blockAlign = numChannels * bytesPerSample
  const dataLength = buffer.length * blockAlign
  const headerLength = 44
  const totalLength = headerLength + dataLength

  const wav = new ArrayBuffer(totalLength)
  const view = new DataView(wav)

  // WAV header
  const writeStr = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
  }
  writeStr(0, 'RIFF')
  view.setUint32(4, totalLength - 8, true)
  writeStr(8, 'WAVE')
  writeStr(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, format, true)
  view.setUint16(22, numChannels, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * blockAlign, true)
  view.setUint16(32, blockAlign, true)
  view.setUint16(34, bitDepth, true)
  writeStr(36, 'data')
  view.setUint32(40, dataLength, true)

  // Interleave channels and write samples
  let offset = 44
  for (let i = 0; i < buffer.length; i++) {
    for (let ch = 0; ch < numChannels; ch++) {
      const sample = Math.max(-1, Math.min(1, buffer.getChannelData(ch)[i]))
      view.setInt16(offset, sample * 0x7FFF, true)
      offset += 2
    }
  }

  return new Blob([wav], { type: 'audio/wav' })
}

/** Draw waveform on a canvas from an AudioBuffer. */
export function drawWaveform(
  canvas: HTMLCanvasElement,
  buffer: AudioBuffer,
  color: string = 'var(--primary)',
  bgColor: string = 'transparent',
) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const dpr = window.devicePixelRatio || 1
  const rect = canvas.getBoundingClientRect()
  canvas.width = rect.width * dpr
  canvas.height = rect.height * dpr
  ctx.scale(dpr, dpr)

  const width = rect.width
  const height = rect.height
  const data = buffer.getChannelData(0)
  const step = Math.ceil(data.length / width)
  const amp = height / 2

  // Resolve CSS variable
  const resolved = getComputedStyle(canvas).getPropertyValue('--primary').trim() || '#6366f1'
  const drawColor = color === 'var(--primary)' ? resolved : color

  ctx.clearRect(0, 0, width, height)

  if (bgColor !== 'transparent') {
    ctx.fillStyle = bgColor
    ctx.fillRect(0, 0, width, height)
  }

  // Center line
  ctx.strokeStyle = 'rgba(128,128,128,0.15)'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(0, amp)
  ctx.lineTo(width, amp)
  ctx.stroke()

  // Waveform bars
  ctx.fillStyle = drawColor
  for (let i = 0; i < width; i++) {
    const start = i * step
    const end = Math.min(start + step, data.length)
    let min = 1
    let max = -1
    for (let j = start; j < end; j++) {
      if (data[j] < min) min = data[j]
      if (data[j] > max) max = data[j]
    }
    const barTop = amp - max * amp
    const barHeight = Math.max(1, (max - min) * amp)
    ctx.fillRect(i, barTop, 1, barHeight)
  }
}
