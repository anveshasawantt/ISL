import os
from typing import Generator
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

CHUNK_SIZE = 1024 * 512  # 512 KB

def range_requests_response(
    file_path: str,
    range_header: str | None,
    content_type: str = "video/mp4"
) -> StreamingResponse:
    """
    Handles HTTP Range requests for video streaming to support browser seeking.
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found")

    file_size = os.path.getsize(file_path)

    if range_header is None:
        def full_iter() -> Generator[bytes, None, None]:
            with open(file_path, mode="rb") as f:
                while chunk := f.read(CHUNK_SIZE):
                    yield chunk

        headers = {
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Content-Type": content_type,
        }
        return StreamingResponse(full_iter(), headers=headers, status_code=200)

    # Parse range header e.g. "bytes=0-1000" or "bytes=500-"
    try:
        range_str = range_header.strip().split("=")[1]
        start_str, end_str = range_str.split("-")
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
    except Exception:
        raise HTTPException(status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE, detail="Invalid Range header")

    if start >= file_size or end >= file_size or start > end:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            headers={"Content-Range": f"bytes */{file_size}"},
            detail="Range not satisfiable"
        )

    content_length = (end - start) + 1

    def ranged_iter() -> Generator[bytes, None, None]:
        with open(file_path, mode="rb") as f:
            f.seek(start)
            bytes_left = content_length
            while bytes_left > 0:
                chunk_to_read = min(CHUNK_SIZE, bytes_left)
                data = f.read(chunk_to_read)
                if not data:
                    break
                bytes_left -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": content_type,
    }

    return StreamingResponse(ranged_iter(), headers=headers, status_code=206)
