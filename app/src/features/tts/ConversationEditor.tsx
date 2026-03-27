import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Mention from '@tiptap/extension-mention'
import { useEffect, useRef, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { createVoiceMentionSuggestion } from './VoiceMentionSuggestion'
import type { Voice } from './types'
import './tts.scss'

interface Props {
  content: string
  onChange: (html: string) => void
  voices: Voice[]
  placeholder?: string
}

export default function ConversationEditor({ content, onChange, voices, placeholder }: Props) {
  const { t } = useTranslation('tts')
  const resolvedPlaceholder = placeholder ?? t('editor_placeholder')
  const voicesRef = useRef<Voice[]>(voices)

  useEffect(() => {
    voicesRef.current = voices
  }, [voices])

  // Build a slug->color map for rendering mention chips with the voice color
  const voiceColorMap = useMemo(() => {
    const map: Record<string, string> = {}
    for (const v of voices) {
      map[v.slug] = v.color
    }
    return map
  }, [voices])

  const voiceColorMapRef = useRef(voiceColorMap)
  useEffect(() => {
    voiceColorMapRef.current = voiceColorMap
  }, [voiceColorMap])

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: false,
        codeBlock: false,
        code: false,
        bulletList: false,
        orderedList: false,
        blockquote: false,
        horizontalRule: false,
      }),
      Placeholder.configure({ placeholder: resolvedPlaceholder }),
      Mention.configure({
        HTMLAttributes: { class: 'voice-mention' },
        suggestion: createVoiceMentionSuggestion(voicesRef),
        renderHTML({ node }) {
          const slug = node.attrs.id as string
          const label = node.attrs.label as string
          const color = voiceColorMapRef.current[slug] || ''
          return [
            'span',
            {
              class: 'voice-mention',
              'data-type': 'mention',
              'data-id': slug,
              'data-label': label,
              style: color ? `--voice-mention-color: ${color}` : undefined,
            },
            `@${label}`,
          ]
        },
      }),
    ],
    content,
    onUpdate: ({ editor: ed }) => {
      onChange(ed.getHTML())
    },
  })

  useEffect(() => {
    if (editor && content !== editor.getHTML()) {
      editor.commands.setContent(content, false)
    }
  }, [content])

  if (!editor) return null

  return (
    <div className="tts-editor-wrapper">
      <div className="tts-editor-content">
        <EditorContent editor={editor} />
      </div>
    </div>
  )
}
