from typing import Any

from studio.ports.providers import ExecutionContext


class FakeSongProvider:
    def describe(self) -> dict[str, Any]:
        return {
            "provider_id": "fake-song", "adapter_version": "1", "model_id": None,
            "is_mock": True, "supported_operations": ["mock_song"],
            "stems": False, "region_regeneration": False,
            "symbolic_conditioning": False, "reference_conditioning": "none",
            "supported_controls": [], "cancellation_granularity": "checkpoint",
        }

    def generate(self, snapshot: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        context.checkpoint("running")
        # A fixed 8-second fixture; user prompt and target duration are recorded, not fulfilled.
        return {
            "brief": snapshot["brief"],
            "reference_snapshot": snapshot["references"],
            "timing": {"ticks_per_quarter": 960, "duration_ticks": 15360,
                       "tempo_map": [{"tick": 0, "bpm": 120}],
                       "meter_map": [{"tick": 0, "numerator": 4, "denominator": 4}]},
            "tonality": {"key": None, "status": "unsupported"},
            "sections": [{"id": "fixture-section", "type": "demo", "label": "구조 예시",
                          "start_tick": 0, "end_tick": 15360}],
            "lyrics": [],
            "composition": {"status": "unsupported", "vocal_notes": [], "chords": [],
                            "arrangement": [], "symbolic_asset_ids": []},
            "performances": [], "tracks": [], "mix": {"rendered_asset_ids": []},
            "provenance": {**self.describe(), "job_id": context.job_id, "seed": context.seed,
                           "warnings": ["고정 구조 예시입니다. 참조 분석·작곡·오디오 생성은 수행하지 않았습니다."],
                           "applied_controls": [], "unsupported_controls": ["prompt", "duration", "references"]},
        }
