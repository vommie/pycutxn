"""
Codec specifications dictionary and helper class defining supported video render codecs,
their CRF bounds, default quality values, preset lists, and audio mappings.
"""

CODEC_SPECS = {
    'libsvtav1': {
        'name': 'AV1 (SVT-AV1)',
        'min_crf': 0,
        'max_crf': 63,
        'default_crf': 26,
        'presets': [
            ('0', '0 - Slowest (Archival)'),
            ('2', '2 - Very Slow'),
            ('4', '4 - High Quality'),
            ('5', '5 - Slow Quality'),
            ('6', '6 - Recommended Balance'),
            ('7', '7 - Fast'),
            ('8', '8 - Faster'),
            ('10', '10 - Very Fast'),
            ('12', '12 - Fastest')
        ],
        'default_preset': '6',
        'recommended_audio': 'libopus'
    },
    'libx265': {
        'name': 'H.265 (HEVC)',
        'min_crf': 0,
        'max_crf': 51,
        'default_crf': 22,
        'presets': [
            ('ultrafast', 'ultrafast'),
            ('superfast', 'superfast'),
            ('veryfast', 'veryfast'),
            ('faster', 'faster'),
            ('fast', 'fast'),
            ('medium', 'medium'),
            ('slow', 'slow'),
            ('slower', 'slower'),
            ('veryslow', 'veryslow')
        ],
        'default_preset': 'medium',
        'recommended_audio': 'aac'
    },
    'libx264': {
        'name': 'H.264 (AVC)',
        'min_crf': 0,
        'max_crf': 51,
        'default_crf': 20,
        'presets': [
            ('ultrafast', 'ultrafast'),
            ('superfast', 'superfast'),
            ('veryfast', 'veryfast'),
            ('faster', 'faster'),
            ('fast', 'fast'),
            ('medium', 'medium'),
            ('slow', 'slow'),
            ('slower', 'slower'),
            ('veryslow', 'veryslow')
        ],
        'default_preset': 'medium',
        'recommended_audio': 'aac'
    }
}

class CodecSpecs:
    DEFAULT_CODEC = 'libsvtav1'

    @staticmethod
    def get_spec(codec_name: str) -> dict:
        """Returns the spec dictionary for a given codec or default if missing."""
        return CODEC_SPECS.get(codec_name, CODEC_SPECS.get(CodecSpecs.DEFAULT_CODEC))

    @staticmethod
    def get_supported_codecs() -> list:
        """Returns list of supported video codec keys."""
        return list(CODEC_SPECS.keys())
