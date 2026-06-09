from collections import deque

from app.director.media.database import MediaDatabase, LightScene, SoundAsset, VideoAsset


class MediaSelector:
    def __init__(self, media_db: MediaDatabase, history_size: int = 5) -> None:
        self.media_db = media_db
        self._recent_ids: deque[str] = deque(maxlen=history_size)

    def select_video(self, tags: list[str], mood: str, intensity: float) -> VideoAsset | None:
        asset = self.media_db.get_video_by_tags(tags, mood, intensity, list(self._recent_ids))
        if asset:
            self._recent_ids.append(asset.id)
        return asset

    def select_sound(self, tags: list[str], mood: str, intensity: float) -> SoundAsset | None:
        asset = self.media_db.get_sound_by_tags(tags, mood, intensity, list(self._recent_ids))
        if asset:
            self._recent_ids.append(asset.id)
        return asset

    def select_light(self, mood: str, intensity: float) -> LightScene | None:
        return self.media_db.get_light_scene(mood, intensity)
