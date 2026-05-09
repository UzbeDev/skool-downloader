# Skool Downloader Pro

A premium, futuristic web application for downloading Skool-hosted videos using `yt-dlp` with browser cookie authentication.

## Features

- **Premium UI** — Glassmorphism, animated orbs, glowing gradients, smooth transitions
- **yt-dlp Engine** — Downloads best video + audio merged into MP4
- **Cookie Auth** — Upload `cookies.txt` for authenticated video access
- **Smart Loading** — Forced 6-second countdown with dynamic status messages + real progress tracking
- **Error Handling** — Invalid URL, auth errors, download failures with clear notifications
- **Responsive** — Mobile-first, works on all screen sizes

## Project Structure

```
skool-downloader/
├── backend/
│   ├── app.py              # Flask API server
│   ├── requirements.txt    # Python dependencies
│   ├── downloads/          # Downloaded videos (auto-created)
│   └── cookies/            # Uploaded cookie files (auto-created)
├── frontend/
│   ├── index.html          # Main page
│   ├── css/style.css       # Premium styling
│   └── js/script.js        # Frontend logic
├── .gitignore
└── README.md
```

## Prerequisites

- **Python 3.8+**
- **ffmpeg** (required by yt-dlp for merging video+audio)
  - Windows: `winget install ffmpeg` or download from [ffmpeg.org](https://ffmpeg.org/)
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`
- **yt-dlp** (installed automatically via pip)

## Setup & Running

### 1. Install Python dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Start the server

```bash
cd backend
python app.py
```

The server starts at **http://localhost:5000**.

### 3. Open in browser

Navigate to **http://localhost:5000** in your browser.

### 4. Get your cookies.txt (for authenticated videos)

1. Install a browser extension like [Get cookies.txt](https://chrome.google.com/webstore/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid) (Chrome) or similar
2. Log in to Skool.com in your browser
3. Export cookies as `cookies.txt` (Netscape format)
4. Upload the file via the "Add cookies.txt" section in the app

### 5. Download a video

1. Paste a Skool.com video URL
2. Optionally upload `cookies.txt`
3. Click **Download Video**
4. Wait for the 6-second processing animation
5. File downloads automatically as MP4

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/download` | Start a download task |
| GET | `/api/download/<id>/status` | Check download progress |
| GET | `/api/download/<id>/file` | Download the completed file |
| POST | `/api/upload-cookies` | Upload a cookies.txt file |
| POST | `/api/validate-url` | Validate a Skool URL |
| GET | `/api/health` | Health check |

## Configuration

- **Port**: Set `PORT` environment variable (default: `5000`)
- **Environment**: Set `FLASK_ENV=development` for debug mode
- **File cleanup**: Old downloads are auto-deleted after 1 hour

## Tech Stack

- **Frontend**: Vanilla HTML/CSS/JS with custom animations
- **Backend**: Python Flask
- **Download Engine**: yt-dlp (Python API)
- **Fonts**: Space Grotesk, Inter (Google Fonts)
