# AI News Agent

AI News Agent adalah worker Python untuk mengumpulkan berita real-time, menyimpan metadata ke SQLite, menyimpan indeks semantik ke ChromaDB, lalu mengirim hasil pencarian, breaking news, alert, dan daily digest melalui Telegram.

Proyek ini tidak memakai Streamlit atau FastAPI. Output utama aplikasi adalah Telegram.

## Alur Sistem

```text
Google News RSS  ---\
GDELT             ----\
HackerNews        ----- > Ingestion -> Processor -> SQLite + ChromaDB
NewsAPI optional ----/                              |
Reddit optional  ---/                               v
                                                  Retrieval
                                                     |
                                             Agent + Formatter
                                                     |
                                                  Telegram
```

## Fitur

- Mengambil berita otomatis sesuai `POLL_INTERVAL_MINUTES`.
- Sumber gratis/no-key tetap aktif: Google News RSS, GDELT, HackerNews.
- Sumber opsional aktif jika API key tersedia: NewsAPI, Reddit, MediaStack, Currents, GNews.
- Deduplication artikel berbasis hash URL.
- Penyimpanan metadata di SQLite dan pencarian semantik di ChromaDB.
- Sentiment enrichment, trending detection, breaking-news marker, dan daily digest.
- Chat Telegram untuk pencarian berita langsung.

## Struktur Penting

```text
main.py                     Entry point utama Telegram worker
bot/                        Telegram application, command, handler, formatter
ingestion/                  Scheduler, fetcher, processor berita
ingestion/fetchers/         Adapter sumber berita
analysis/                   Summarizer, sentiment, trending, entity utilities
retrieval/                  Hybrid search dan vector store
notifications/              Digest, breaking news, dispatcher Telegram
core/                       Database, model, schema
config/                     Settings dan prompt
data/news.db                SQLite database lokal
data/chroma/                ChromaDB persistence
```

## Instalasi

Gunakan Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Jika pertama kali setup:

```bash
cp .env.example .env
```

Lalu isi `.env`.

## Konfigurasi `.env`

Minimal untuk menjalankan bot:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groq_api_key
GOOGLE_API_KEY=your_google_api_key
DATABASE_URL=sqlite+aiosqlite:///./data/news.db
CHROMA_PATH=./data/chroma
```

Target broadcast Telegram:

```env
TELEGRAM_CHAT_ID=
TELEGRAM_CHANNEL_ID=
TELEGRAM_ADMIN_ID=0
```

Jika `TELEGRAM_CHAT_ID` dan `TELEGRAM_CHANNEL_ID` kosong, user tetap bisa menerima digest setelah mengirim `/start` ke bot karena chat akan disimpan ke database.

Sumber berita opsional:

```env
NEWSAPI_KEY=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
MEDIASTACK_API_KEY=
CURRENTS_API_KEY=
GNEWS_API_KEY=
```

Pengaturan ingestion dan output AI:

```env
POLL_INTERVAL_MINUTES=15
MAX_ARTICLES_PER_SOURCE=50
MAX_ARTICLES_PER_CYCLE=500
ARTICLE_RETENTION_DAYS=30
ENABLED_COUNTRIES=["us","gb","id","in","au","ca","de","fr","jp","br","za","ng","mx","eg"]
ENABLED_LANGUAGES=["en","id","de","fr","ja","pt","ar","es"]
DAILY_DIGEST_HOUR=7
DAILY_DIGEST_MINUTE=0
MAX_TOKENS_SUMMARY=300
MAX_TOKENS_ANSWER=500
TEMPERATURE=0.3
```

## Menjalankan

Jalankan langsung:

```bash
source .venv/bin/activate
python main.py
```

Atau gunakan helper tmux:

```bash
bash run.sh start
```

Perintah helper:

```bash
bash run.sh start
bash run.sh stop
bash run.sh restart
bash run.sh status
bash run.sh logs
```

## FastMCP Backend

Selain bot Telegram, proyek ini punya backend FastMCP di [mcp_server.py](</home/aditama/Documents/AI News Agent/mcp_server.py>). Anggap ini sebagai backend alat kerja: bot/asisten bisa memanggil tool, sementara server melakukan pekerjaan berat.

Entrypoint cloud tersedia di [server.py](</home/aditama/Documents/AI News Agent/server.py>) dan konfigurasi deploy ada di [fastmcp.json](</home/aditama/Documents/AI News Agent/fastmcp.json>).

Tool yang tersedia:

```text
news_search(query, top_k)
daily_digest_preview(hours, limit)
web_search(query, limit)
system_info()
```

Jalankan MCP server lokal:

```bash
source .venv/bin/activate
pip install -r requirements.txt
fastmcp run fastmcp.json --skip-env --skip-source
```

Default:

```text
MCP_HOST=0.0.0.0
MCP_PORT=3000
MCP_TRANSPORT=http
```

Alternatif untuk menjalankan file langsung:

```bash
MCP_TRANSPORT=http MCP_PORT=8001 python mcp_server.py
```

### Deploy ke Prefect Horizon Cloud

Untuk Horizon, deploy backend MCP, bukan proses Telegram bot. Telegram bot tetap dijalankan terpisah dengan `python main.py` atau `bash run.sh start`.

```text
Entrypoint: server.py:mcp
Config: fastmcp.json
Install dependencies: requirements.txt
```

Checklist deploy:

```text
1. Push project ini ke GitHub.
2. Buka https://horizon.prefect.io dan login dengan GitHub.
3. Create/Deploy MCP Server.
4. Pilih repository project ini.
5. Isi entrypoint: server.py:mcp
6. Pastikan dependency file yang terdeteksi adalah requirements.txt.
7. Tambahkan environment variables dari .env yang dibutuhkan.
8. Deploy, lalu test tool dari Inspector atau ChatMCP.
```

Sebelum push, validasi lokal:

```bash
source .venv/bin/activate
fastmcp inspect server.py:mcp
python -m compileall -q . -x './.venv/.*'
pytest -q
```

Environment variables minimal untuk Horizon:

```env
GROQ_API_KEY=...
GOOGLE_API_KEY=...
DATABASE_URL=sqlite+aiosqlite:///./data/news.db
CHROMA_PATH=./data/chroma
MCP_TRANSPORT=http
```

Environment variables opsional jika ingin tool memakai sumber berbayar/opsional:

```env
NEWSAPI_KEY=...
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
MEDIASTACK_API_KEY=...
CURRENTS_API_KEY=...
GNEWS_API_KEY=...
```

API/token Horizon tidak dibutuhkan untuk menjalankan bot lokal. Token Horizon hanya diperlukan jika kamu memakai API/CLI Horizon, atau jika dashboard meminta token sebagai secret. Jangan commit token ke repo dan jangan taruh token di `README.md`.

Jika perlu memakai token dari terminal lokal, set sebagai environment variable sementara:

```bash
export FASTMCP_API_KEY="<horizon_api_key>"
```

Catatan penting:

- Horizon cocok untuk tool MCP seperti `web_search`, `system_info`, `news_search`, dan `daily_digest_preview`.
- `news_search` dan `daily_digest_preview` membaca database lokal server. Jika database di Horizon kosong, hasilnya juga kosong sampai ada ingestion yang mengisi data.
- Jika Horizon melakukan scale-to-zero atau filesystem runtime tidak persisten, `data/news.db` dan `data/chroma` di server bisa kosong/hilang antar deploy.
- Untuk produksi serius, pindahkan state ke layanan eksternal: Postgres/Turso untuk database dan vector store managed untuk embedding/index.
- Sambil masih lokal, bot Telegram bisa tetap jalan di mesin sendiri, sementara Horizon menjadi backend MCP yang bisa dipanggil client lain.

### Error `Bearer token required`

Jika membuka URL seperti `https://<server>.fastmcp.app/mcp` langsung dari browser dan muncul:

```json
{
  "error": "invalid_request",
  "error_description": "Bearer token required"
}
```

Itu normal. Endpoint MCP di Horizon bukan halaman web publik, melainkan endpoint tool yang diproteksi authentication. Browser biasa tidak mengirim header `Authorization: Bearer ...`, jadi request ditolak sebelum tool dijalankan.

Gunakan salah satu cara berikut untuk test:

```text
1. Horizon Inspector / ChatMCP dari dashboard Horizon.
2. MCP client yang mendukung OAuth Horizon.
3. FastMCP client dengan bearer token yang valid.
```

Contoh client Python:

```python
import asyncio
from fastmcp import Client


async def main():
    async with Client(
        "https://<server>.fastmcp.app/mcp",
        auth="<access_token>",
    ) as client:
        print(await client.ping())
        print(await client.call_tool("system_info", {}))


asyncio.run(main())
```

Jangan menaruh token Horizon, Google, Groq, atau Telegram di repo. Simpan di Environment Variables Horizon atau `.env` lokal yang tidak ikut commit.

## Bicara Dengan Bot

Kamu tidak harus memakai command. Bot dirancang agar bisa diajak bicara seperti asisten pribadi.

Contoh:

```text
kasih briefing hari ini
ada perkembangan penting apa pagi ini?
apa kabar ekonomi global?
rangkum berita AI Indonesia
coba cek konflik global terbaru
carikan berita tentang chip AI
```

Command tetap tersedia sebagai shortcut:

```text
/start
/ping
/digest
/cari AI Indonesia
/search ekonomi global
```

## Verifikasi

Compile source:

```bash
python -m compileall -q . -x './.venv/.*'
```

Jalankan test:

```bash
pytest -q
```

## Catatan Operasional

- `.env` berisi secret dan sudah masuk `.gitignore`.
- `data/` dan `logs/` juga diabaikan oleh git karena berisi state lokal.
- Sumber gratis/no-key akan tetap berjalan meskipun API opsional kosong.
- `TELEGRAM_BOT_TOKEN` wajib ada untuk menjalankan bot.
- ChromaDB dapat butuh waktu saat inisialisasi model embedding pertama kali.

## Troubleshooting

- Bot tidak merespons: cek `TELEGRAM_BOT_TOKEN`, koneksi internet, dan pastikan proses `python main.py` masih berjalan.
- Digest tidak terkirim: kirim `/start` ke bot atau isi `TELEGRAM_CHAT_ID`/`TELEGRAM_CHANNEL_ID`.
- Pencarian kosong: tunggu satu siklus ingestion atau jalankan ulang setelah data masuk ke `data/news.db`.
- Error dependency: aktifkan `.venv`, lalu jalankan `pip install -r requirements.txt`.
- Error database SQLite async: pastikan `DATABASE_URL` memakai format `sqlite+aiosqlite:///./data/news.db`.
