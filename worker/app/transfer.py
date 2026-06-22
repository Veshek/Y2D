"""The actual Drive -> YouTube transfer.

The file is downloaded to a temp file on the worker, then resumable-uploaded to
YouTube. This is the "server-side double-dip" we accept on purpose: the worker
spends the bandwidth so the *user* doesn't have to download then re-upload large
videos. For very large files you can stream Drive -> YouTube without buffering the
whole file to disk; the temp-file approach here keeps the scaffold readable.
"""
import io
import os
import tempfile

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from . import store


def _credentials(session: dict) -> Credentials:
    c = session["credentials"]
    return Credentials(**{k: c[k] for k in
                          ("token", "refresh_token", "token_uri",
                           "client_id", "client_secret", "scopes")})


def run_transfer(transfer_id: str, session_id: str, file_id: str,
                 title: str | None, privacy: str) -> None:
    session = store.get_session(session_id)
    if not session:
        store.update_transfer(transfer_id, status="error",
                              error="Session not found or expired")
        return

    creds = _credentials(session)
    tmp_path = None
    try:
        drive = build("drive", "v3", credentials=creds)

        # Resolve a default title from the Drive filename if none was given.
        meta = drive.files().get(fileId=file_id, fields="name").execute()
        final_title = title or meta.get("name") or "Untitled"

        # --- Download from Drive ---
        store.update_transfer(transfer_id, status="downloading", progress=0,
                              title=final_title)
        fd, tmp_path = tempfile.mkstemp(suffix=".video")
        os.close(fd)
        request = drive.files().get_media(fileId=file_id)
        with io.FileIO(tmp_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request, chunksize=8 * 1024 * 1024)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    pct = int(status.progress() * 100)
                    # Downloading occupies the first half of the progress bar.
                    store.update_transfer(transfer_id, status="downloading",
                                          progress=pct // 2)

        # --- Upload to YouTube ---
        store.update_transfer(transfer_id, status="uploading", progress=50)
        youtube = build("youtube", "v3", credentials=creds)
        media = MediaFileUpload(tmp_path, chunksize=8 * 1024 * 1024, resumable=True)
        insert = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {"title": final_title, "description": ""},
                "status": {"privacyStatus": privacy},  # private | unlisted | public
            },
            media_body=media,
        )
        response = None
        while response is None:
            status, response = insert.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                # Uploading occupies the second half.
                store.update_transfer(transfer_id, status="uploading",
                                      progress=50 + pct // 2)

        store.update_transfer(transfer_id, status="done", progress=100,
                              youtube_video_id=response.get("id"))
    except Exception as exc:  # surface the failure to the UI
        store.update_transfer(transfer_id, status="error", error=str(exc))
        raise
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
