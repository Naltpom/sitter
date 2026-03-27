from ...core.feature_registry import FeatureManifest

manifest = FeatureManifest(
    name="tts",
    label="Synthese vocale",
    description="Synthese vocale locale avec clonage de voix et editeur multi-voix",
    permissions=[
        "tts.read",
        "tts.create",
        "tts.manage_voices",
        "tts.manage",
    ],
    events=[
        {
            "event_type": "tts.generation_completed",
            "label": "Generation audio terminee",
            "category": "TTS",
            "description": "Une generation audio a ete completee",
        },
        {
            "event_type": "tts.voice_created",
            "label": "Voix personnalisee creee",
            "category": "TTS",
            "description": "Une voix personnalisee a ete creee par clonage",
        },
    ],
    router_module="src.features.tts.routes",
    router_prefix="/api/tts",
    router_tags=["TTS"],
)
