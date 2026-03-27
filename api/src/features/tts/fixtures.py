"""TTS feature fixtures — seed generic Piper voices."""

from ...core.fixture_registry import FixtureDefinition


async def _generate_voices(db, ctx):
    """Seed generic Piper French voices."""
    from .models import Voice

    voices_data = [
        {
            "name": "Siwis",
            "slug": "siwis",
            "voice_type": "generic",
            "engine": "piper",
            "piper_model_name": "fr_FR-siwis-medium",
            "color": "#8b5cf6",
            "language": "fr",
        },
        {
            "name": "UPMC",
            "slug": "upmc",
            "voice_type": "generic",
            "engine": "piper",
            "piper_model_name": "fr_FR-upmc-medium",
            "color": "#3b82f6",
            "language": "fr",
        },
    ]

    created = []
    for data in voices_data:
        voice = Voice(**data)
        db.add(voice)
        created.append(voice)

    await db.flush()
    return {"voices_created": len(created)}


fixtures = [
    FixtureDefinition(
        name="tts_voices",
        label="TTS Generic Voices",
        description="Voix generiques Piper pour la synthese vocale",
        depends=["_identity"],
        handler=_generate_voices,
        check_table="tts_voices",
        check_min_rows=2,
    ),
]
