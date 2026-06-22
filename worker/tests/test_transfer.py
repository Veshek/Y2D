"""Tests for the worker transfer logic.

Google API calls are mocked — we test the state machine (status transitions,
progress updates, Redis writes) without real credentials or network calls.
"""
import json
import pytest
from unittest.mock import MagicMock, patch, call

from app.transfer import run_transfer
from app import store


def _make_mock_drive(filename="test-video.mp4"):
    """Build a mock Drive client that returns a fake file and fake download chunks."""
    drive = MagicMock()
    drive.files.return_value.get.return_value.execute.return_value = {"name": filename}

    # Simulate two download chunks (50%, 100%)
    chunk1 = MagicMock()
    chunk1.progress.return_value = 0.5
    chunk2 = MagicMock()
    chunk2.progress.return_value = 1.0

    mock_downloader = MagicMock()
    mock_downloader.next_chunk.side_effect = [
        (chunk1, False),
        (chunk2, True),
    ]

    drive.files.return_value.get_media.return_value = MagicMock()
    return drive, mock_downloader


def _make_mock_youtube(video_id="yt-video-abc"):
    """Build a mock YouTube client that simulates a resumable upload."""
    youtube = MagicMock()
    upload_status = MagicMock()
    upload_status.progress.return_value = 1.0
    youtube.videos.return_value.insert.return_value.next_chunk.side_effect = [
        (upload_status, None),
        (None, {"id": video_id}),
    ]
    return youtube


def test_successful_transfer(fake_redis, seeded_session):
    """Happy path: status goes queued → downloading → uploading → done."""
    transfer_id = "transfer-001"
    fake_redis.set(f"transfer:{transfer_id}", json.dumps({
        "id": transfer_id, "status": "queued", "progress": 0,
        "file_id": "drive-file-1", "title": "", "privacy": "private",
    }))

    drive, mock_downloader = _make_mock_drive("my-video.mp4")
    youtube = _make_mock_youtube("yt-abc-123")

    with patch("app.transfer.build") as mock_build, \
         patch("app.transfer.MediaIoBaseDownload", return_value=mock_downloader), \
         patch("app.transfer.MediaFileUpload"), \
         patch("app.transfer.tempfile.mkstemp", return_value=(0, "/tmp/fake.video")), \
         patch("app.transfer.io.FileIO"), \
         patch("app.transfer.os.close"), \
         patch("app.transfer.os.remove"), \
         patch("app.transfer.os.path.exists", return_value=True):

        mock_build.side_effect = lambda service, *a, **kw: drive if service == "drive" else youtube
        run_transfer(transfer_id, seeded_session, "drive-file-1", None, "private")

    final = json.loads(fake_redis.get(f"transfer:{transfer_id}"))
    assert final["status"] == "done"
    assert final["progress"] == 100
    assert final["youtube_video_id"] == "yt-abc-123"
    assert final["title"] == "my-video.mp4"  # defaulted from Drive filename


def test_transfer_uses_provided_title(fake_redis, seeded_session):
    transfer_id = "transfer-002"
    fake_redis.set(f"transfer:{transfer_id}", json.dumps({
        "id": transfer_id, "status": "queued", "progress": 0,
        "file_id": "f1", "title": "Custom Title", "privacy": "public",
    }))

    drive, mock_downloader = _make_mock_drive()
    youtube = _make_mock_youtube()

    with patch("app.transfer.build") as mock_build, \
         patch("app.transfer.MediaIoBaseDownload", return_value=mock_downloader), \
         patch("app.transfer.MediaFileUpload"), \
         patch("app.transfer.tempfile.mkstemp", return_value=(0, "/tmp/fake.video")), \
         patch("app.transfer.io.FileIO"), \
         patch("app.transfer.os.close"), \
         patch("app.transfer.os.remove"), \
         patch("app.transfer.os.path.exists", return_value=True):

        mock_build.side_effect = lambda service, *a, **kw: drive if service == "drive" else youtube
        run_transfer(transfer_id, seeded_session, "f1", "Custom Title", "public")

    final = json.loads(fake_redis.get(f"transfer:{transfer_id}"))
    assert final["title"] == "Custom Title"


def test_transfer_error_on_missing_session(fake_redis):
    """If session is gone from Redis, transfer should record error status."""
    transfer_id = "transfer-003"
    fake_redis.set(f"transfer:{transfer_id}", json.dumps({
        "id": transfer_id, "status": "queued", "progress": 0,
        "file_id": "f1", "title": "", "privacy": "private",
    }))

    run_transfer(transfer_id, "nonexistent-session", "f1", None, "private")

    final = json.loads(fake_redis.get(f"transfer:{transfer_id}"))
    assert final["status"] == "error"
    assert "session" in final["error"].lower()


def test_transfer_publishes_progress_to_redis(fake_redis, seeded_session):
    """Worker should publish progress events so the SSE relay picks them up."""
    transfer_id = "transfer-004"
    fake_redis.set(f"transfer:{transfer_id}", json.dumps({
        "id": transfer_id, "status": "queued", "progress": 0,
        "file_id": "f1", "title": "", "privacy": "private",
    }))

    # Subscribe before running so we can count publishes
    pubsub = fake_redis.pubsub()
    pubsub.subscribe(f"progress:{transfer_id}")

    drive, mock_downloader = _make_mock_drive()
    youtube = _make_mock_youtube()

    with patch("app.transfer.build") as mock_build, \
         patch("app.transfer.MediaIoBaseDownload", return_value=mock_downloader), \
         patch("app.transfer.MediaFileUpload"), \
         patch("app.transfer.tempfile.mkstemp", return_value=(0, "/tmp/fake.video")), \
         patch("app.transfer.io.FileIO"), \
         patch("app.transfer.os.close"), \
         patch("app.transfer.os.remove"), \
         patch("app.transfer.os.path.exists", return_value=True):

        mock_build.side_effect = lambda service, *a, **kw: drive if service == "drive" else youtube
        run_transfer(transfer_id, seeded_session, "f1", None, "private")

    # Should have received multiple progress messages
    messages = []
    while True:
        msg = pubsub.get_message()
        if msg and msg["type"] == "message":
            messages.append(json.loads(msg["data"]))
        elif msg is None:
            break

    assert len(messages) >= 2
    statuses = [m["status"] for m in messages]
    assert "downloading" in statuses
    assert "done" in statuses
