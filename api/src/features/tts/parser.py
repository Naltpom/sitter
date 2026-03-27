"""Parse TipTap HTML content into voice-tagged text segments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

from ...core.config import settings


@dataclass
class TextSegment:
    """A segment of text assigned to a specific voice."""
    voice_slug: str
    text: str


class _TipTapVoiceParser(HTMLParser):
    """Custom HTML parser that extracts voice-tagged segments from TipTap mention markup.

    TipTap renders mentions as:
    <span data-type="mention" data-id="slug" data-label="Name" class="mention">@Name</span>
    """

    def __init__(self, default_voice: str):
        super().__init__()
        self._current_voice = default_voice
        self._segments: list[TextSegment] = []
        self._current_text = ""
        self._in_mention = False
        self._skip_mention_text = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr_dict = dict(attrs)

        # Detect mention span
        if tag == "span" and attr_dict.get("data-type") == "mention":
            self._in_mention = True
            self._skip_mention_text = True
            voice_slug = attr_dict.get("data-id", "")
            if voice_slug:
                # Flush current text as a segment before switching voice
                self._flush_segment()
                self._current_voice = voice_slug

        # Add line breaks for block elements
        elif tag in ("p", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6"):
            if tag != "br":
                self._current_text += "\n"
            else:
                self._current_text += "\n"

    def handle_endtag(self, tag: str):
        if tag == "span" and self._in_mention:
            self._in_mention = False
            self._skip_mention_text = False

        if tag in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._current_text += "\n"

    def handle_data(self, data: str):
        if self._skip_mention_text:
            return
        self._current_text += data

    def _flush_segment(self):
        """Flush accumulated text as a segment."""
        text = self._current_text.strip()
        # Collapse multiple whitespace/newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        if text:
            self._segments.append(TextSegment(voice_slug=self._current_voice, text=text))
        self._current_text = ""

    def get_segments(self) -> list[TextSegment]:
        self._flush_segment()
        return self._segments


def parse_content(html: str) -> list[TextSegment]:
    """Parse TipTap HTML content into voice-tagged text segments.

    Text before the first @mention uses the default voice from settings.
    Each @mention switches the voice for all subsequent text until the next @mention.

    Args:
        html: TipTap HTML content with voice mention spans.

    Returns:
        List of TextSegment with voice_slug and text.
    """
    default_voice = settings.TTS_DEFAULT_VOICE_SLUG
    parser = _TipTapVoiceParser(default_voice)
    parser.feed(html)
    return parser.get_segments()
