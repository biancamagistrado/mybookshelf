# My Bookshelf

A personal reading tracker. Import a library export, browse it as a shelf, and get
back the genres and cover art the export leaves out.

Reads CSV exports from Goodreads, StoryGraph, LibraryThing and Calibre, or a pasted
list of titles and ISBNs. Genres and covers come from Google Books and Open Library.

**Stack:** React 19 · TypeScript · Tailwind CSS v4 · FastAPI · PostgreSQL 16 · Docker Compose

## Screenshots

| Three themes | Scrolling the shelf |
|:---:|:---:|
| <img src="docs/themes.gif" width="320" alt="Three themes"> | <img src="docs/shelf-scroll.gif" width="320" alt="Scrolling the shelf"> |

## Quick start

```bash
git clone https://github.com/biancamagistrado/mybookshelf.git
cd mybookshelf
cp .env.example .env
docker compose up --build
```

Set your own `POSTGRES_PASSWORD` in `.env`. Set `PER_VISITOR_LIBRARIES=true` to start
with the sample library.

App: <http://localhost:3000>
API docs: <http://localhost:8000/docs>

## Features

| | |
|---|---|
| **Import** | CSV from four services, or a pasted list of titles and ISBNs. Re-importing does not create duplicates. |
| **Shelves** | Read, currently reading, want to read, did not finish. |
| **Search** | Title, author and genre. |
| **Covers and genres** | Looked up on Google Books, then Open Library. |
| **Stats** | Books per year, pages read, top genres and authors. |
| **Your own library** | Each visitor gets their own copy of the sample library and can clear it. No sign-up. |
| **Themes** | Warm, light, dark. |

## Architecture

```
  Browser ──► frontend (React, served by nginx)
                 │
                 ▼  /api
              backend (FastAPI) ──► Google Books, Open Library
                 │
                 ▼
              PostgreSQL 16
```

## Development

```bash
docker compose up -d db backend
cd frontend && npm run dev
```

App: <http://localhost:5173>

```bash
docker compose up -d db
cd backend
.venv/bin/pytest -q
.venv/bin/ruff check app tests
```

## Security

- Visitors can only read and change their own library.
- Cover image links are checked before they are shown.
- The Docker setup adds security headers and keeps Postgres off the network.
- There is no rate limiting, and the visitor id is not a login.

## License

MIT. See [LICENSE](LICENSE).
