# Project Specification: AutoTranslateWebUI (AI Video Translation System)

## 1. Project Overview
A web application to automate video translation.
Workflow: User Uploads Video -> Server Extracts Audio -> VAD Segmentation -> Whisper Transcription -> LLM Translation -> User Edits Subtitles -> Export.

## 2. Tech Stack (Strict Constraints)
- **Monorepo Structure**: `/backend` (Python) and `/frontend` (TypeScript).
- **Backend**: 
    - Framework: FastAPI (Async).
    - Database: SQLite (Dev) / PostgreSQL (Prod) with SQLAlchemy (Async).
    - Task Queue: Redis + Celery (for long-running video tasks).
    - Core Libs: `ffmpeg-python`, `silero-vad` (Voice Activity Detection), `openai-whisper`.
- **Frontend**:
    - Framework: React + Vite.
    - Styling: Tailwind CSS + Shadcn/UI.
    - State Management: Zustand (Critical for syncing video player with subtitle list).
    - HTTP: Axios + TanStack Query.

## 3. Data Models (Schema Strategy)
### Table: `videos`
- `id` (UUID): Primary Key.
- `filename`: Original name.
- `file_path`: Local storage path.
- `status`: Enum (uploading, processing, ready, error).
- `duration`: Float (seconds).

### Table: `subtitles`
- `id`: PK.
- `video_id`: FK.
- `start_time`: Float (seconds).
- `end_time`: Float (seconds).
- `text_original`: String (Whisper output).
- `text_translated`: String (LLM output).
- `confidence`: Float (0.0-1.0, low confidence triggers UI warning).

## 4. API Endpoints (Core)
- `POST /videos/upload`: Handles file upload, saves to disk, triggers Celery task.
- `GET /videos/{id}/status`: Polling for processing progress.
- `GET /videos/{id}/subtitles`: Returns list of subtitles for the editor.
- `PUT /subtitles/{id}`: Update translation text or timestamps.

## 5. Processing Pipeline (Logic)
1. **FFmpeg**: Extract audio (`.wav`) from video.
2. **VAD**: Use Silero VAD to detect timestamps of speech `[{start: 0.5, end: 3.2}, ...]`.
3. **Whisper**: Transcribe ONLY the segments detected by VAD to avoid hallucinations in silence.
4. **LLM**: Translate text contextually (batch processing recommended).