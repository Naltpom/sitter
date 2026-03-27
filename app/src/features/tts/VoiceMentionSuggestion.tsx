import { useState, useEffect, useCallback, useImperativeHandle, type Ref, type RefObject } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import type { SuggestionProps, SuggestionKeyDownProps } from '@tiptap/suggestion'
import i18next from 'i18next'
import type { Voice } from './types'

interface VoiceMentionListProps {
  items: Voice[]
  command: (item: { id: string; label: string }) => void
  ref?: Ref<VoiceMentionListRef>
}

interface VoiceMentionListRef {
  onKeyDown: (props: SuggestionKeyDownProps) => boolean
}

function VoiceMentionList({ items, command, ref }: VoiceMentionListProps) {
  const [selectedIndex, setSelectedIndex] = useState(0)

  useEffect(() => {
    setSelectedIndex(0)
  }, [items])

  const selectItem = useCallback(
    (index: number) => {
      const item = items[index]
      if (item) {
        command({ id: item.slug, label: item.name })
      }
    },
    [items, command],
  )

  useImperativeHandle(ref, () => ({
    onKeyDown: ({ event }: SuggestionKeyDownProps) => {
      if (event.key === 'ArrowUp') {
        setSelectedIndex((prev) => (prev + items.length - 1) % items.length)
        return true
      }
      if (event.key === 'ArrowDown') {
        setSelectedIndex((prev) => (prev + 1) % items.length)
        return true
      }
      if (event.key === 'Enter') {
        selectItem(selectedIndex)
        return true
      }
      return false
    },
  }))

  if (items.length === 0) {
    return <div className="voice-mention-suggestion-empty">{i18next.t('tts:no_voice_found')}</div>
  }

  return (
    <>
      {items.map((item, index) => (
        <button
          key={item.uuid}
          className={`voice-mention-suggestion-item ${index === selectedIndex ? 'is-selected' : ''}`}
          onClick={() => selectItem(index)}
          type="button"
        >
          <span
            className="voice-mention-dot"
            style={{ '--voice-dot-color': item.color } as React.CSSProperties}
          />
          <span>{item.name}</span>
          <span className="tts-voice-card-badge">
            {item.voice_type === 'custom' ? i18next.t('tts:custom') : i18next.t('tts:generic')}
          </span>
        </button>
      ))}
    </>
  )
}

export function createVoiceMentionSuggestion(voicesRef: RefObject<Voice[]>) {
  return {
    items: ({ query }: { query: string }) => {
      const voices = voicesRef.current || []
      if (!query) return voices.slice(0, 10)
      const q = query.toLowerCase()
      return voices
        .filter(
          (v) =>
            v.name.toLowerCase().includes(q) ||
            v.slug.toLowerCase().includes(q),
        )
        .slice(0, 10)
    },

    render: () => {
      let popup: HTMLDivElement | null = null
      let root: Root | null = null
      let componentRef: VoiceMentionListRef | null = null

      return {
        onStart: (props: SuggestionProps) => {
          popup = document.createElement('div')
          popup.className = 'voice-mention-suggestion'
          document.body.appendChild(popup)
          root = createRoot(popup)

          const rect = props.clientRect?.()
          if (rect && popup) {
            popup.style.top = `${rect.bottom + 4}px`
            popup.style.left = `${rect.left}px`
          }

          root.render(
            <VoiceMentionList
              ref={(ref) => { componentRef = ref }}
              items={props.items as Voice[]}
              command={props.command}
            />,
          )
        },

        onUpdate: (props: SuggestionProps) => {
          if (!root || !popup) return

          const rect = props.clientRect?.()
          if (rect) {
            popup.style.top = `${rect.bottom + 4}px`
            popup.style.left = `${rect.left}px`
          }

          root.render(
            <VoiceMentionList
              ref={(ref) => { componentRef = ref }}
              items={props.items as Voice[]}
              command={props.command}
            />,
          )
        },

        onKeyDown: (props: SuggestionKeyDownProps) => {
          if (props.event.key === 'Escape') {
            popup?.remove()
            popup = null
            root?.unmount()
            root = null
            return true
          }
          return componentRef?.onKeyDown(props) ?? false
        },

        onExit: () => {
          popup?.remove()
          popup = null
          root?.unmount()
          root = null
          componentRef = null
        },
      }
    },
  }
}
