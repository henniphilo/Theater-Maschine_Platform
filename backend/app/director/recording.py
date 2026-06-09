"""Phase 4 stub: recording lifecycle management."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.director.media.database import MediaDatabase
from app.director.outputs.touchdesigner import TouchDesignerBridge


@dataclass
class RecordingSession:
    recording_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    active: bool = True


class RecordingManager:
    """Manages live recording sessions (Phase 4)."""

    def __init__(
        self,
        touchdesigner: TouchDesignerBridge | None = None,
        media_db: MediaDatabase | None = None,
    ) -> None:
        self.touchdesigner = touchdesigner or TouchDesignerBridge()
        self.media_db = media_db or MediaDatabase()
        self._session: RecordingSession | None = None

    @property
    def active_session(self) -> RecordingSession | None:
        return self._session

    def start(self, recording_id: str) -> RecordingSession:
        self.touchdesigner.start_recording(recording_id)
        self._session = RecordingSession(recording_id=recording_id)
        return self._session

    def stop(self) -> RecordingSession | None:
        if self._session is None:
            return None
        self.touchdesigner.stop_recording()
        session = self._session
        session.active = False
        path = f"media/recordings/{session.recording_id}.mp4"
        self.media_db.register_recording(session.recording_id, path, tags=["live", "recent"])
        self._session = None
        return session

    def play(self, recording_id: str) -> None:
        self.touchdesigner.play_recording(recording_id)
