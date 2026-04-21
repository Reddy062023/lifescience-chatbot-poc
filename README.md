# Add signature to local README first
@"

---
Built by Japendra
Portfolio: https://Reddy062023.github.io
GitHub: https://github.com/Reddy062023
Contact: japendras06@gmail.com
"@ | Add-Content -Path "README.md" -Encoding utf8

# Now force checkout and keep your local files
git checkout -f main

# Check status
git status

# YouTube Knowledge Base Chatbot

A full-stack AI chatbot that learns from YouTube videos and answers questions using Snowflake, dbt, and FastAPI.

---

## What It Does

- Downloads transcripts from any YouTube video
- Stores and transforms data in Snowflake using dbt
- Generates AI-powered answers using Snowflake Cortex
- Exposes a REST API via FastAPI

---

## Tech Stack

| Tool | Purpose |
|---|---|
| Python 3.11 | Core programming language |
| yt-dlp | Download YouTube transcripts |
| sentence-transformers | Generate embeddings locally (free) |
| Snowflake | Store videos, chunks, and embeddings |
| dbt (dbt-snowflake) | Transform raw data into clean models |
| Snowflake Cortex | Generate AI answers (free inside Snowflake) |
| FastAPI | REST API endpoint |
| uvicorn | Run the FastAPI server |

---

## Project Structure

```
my-chatbot/
│
├── ingest.py           # Step 1: Download YouTube transcript + load into Snowflake
├── chat.py             # Step 2: Search chunks + generate answers via Cortex
├── main.py             # Step 3: FastAPI /chat endpoint
│
└── youtube_kb/         # dbt project folder
    ├── dbt_project.yml
    ├── models/
    │   ├── sources.yml
    │   ├── stg_transcripts.sql       # staging model
    │   ├── int_chunks.sql            # intermediate model
    │   └── mart_knowledge_base.sql   # final mart model
    └── profiles.yml    # (stored at C:\Users\<you>\.dbt\profiles.yml)
```

---

## Setup Instructions

### 1. Prerequisites

- Python 3.11 (not 3.14 — dbt not yet compatible)
- Snowflake account
- Microsoft C++ Build Tools (for snowflake-connector-python)

### 2. Install Libraries

```bash
pip install yt-dlp snowflake-connector-python sentence-transformers dbt-snowflake fastapi uvicorn
```

### 3. Create Snowflake Database and Tables

Run this SQL in your Snowflake Worksheet:

```sql
CREATE DATABASE IF NOT EXISTS YOUTUBE_KB;
CREATE SCHEMA IF NOT EXISTS YOUTUBE_KB.RAW;
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH
    WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE;

USE DATABASE YOUTUBE_KB;
USE SCHEMA RAW;

CREATE TABLE IF NOT EXISTS RAW_VIDEOS (
    video_id   VARCHAR,
    title      VARCHAR,
    url        VARCHAR,
    loaded_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS RAW_TRANSCRIPTS (
    chunk_id    VARCHAR,
    video_id    VARCHAR,
    chunk_index INT,
    chunk_text  VARCHAR
);

CREATE TABLE IF NOT EXISTS RAW_EMBEDDINGS (
    chunk_id   VARCHAR,
    embedding  VARCHAR
);
```

---

## How to Run — Complete Execution Steps

Every time you want to use the chatbot, follow these steps IN ORDER.
Open your terminal (Command Prompt) and run each command one by one.

---

### STEP 1 — Open your terminal

Press `Windows key + R`, type `cmd`, press Enter.

---

### STEP 2 — Go to your project folder

```bash
cd C:\Users\Geetu\my-chatbot
```

What you should see:
```
C:\Users\Geetu\my-chatbot>
```

---

### STEP 3 — Ingest a YouTube video into Snowflake

> Only do this when you want to add a NEW video to the knowledge base.
> You do NOT need to run this every time — only when adding new content.

Open `ingest.py` in Notepad and make sure these are filled in correctly:

```python
SNOWFLAKE = {
    "account"  : "ewzqeyy-iic66448",
    "user"     : "YOUR_SNOWFLAKE_USERNAME",
    "password" : "YOUR_SNOWFLAKE_PASSWORD",
    "warehouse": "COMPUTE_WH",
    "database" : "YOUTUBE_KB",
    "schema"   : "RAW",
}
YOUTUBE_URL = "https://www.youtube.com/watch?v=9PBvVeCQi0w"
```

Then run:

```bash
py -3.11 ingest.py
```

Wait for it to finish. Expected output:
```
Fetching transcript...
Video: What is Snowflake?
Created 3 chunks
Video saved: What is Snowflake?
Generating embeddings for 3 chunks...
  Chunk 1/3 saved
  Chunk 2/3 saved
  Chunk 3/3 saved
Done! 3 chunks loaded into Snowflake.
```

---

### STEP 4 — Run dbt to transform the data

> Only do this after ingesting a new video (Step 3).
> dbt cleans and prepares your data for the chatbot to search.

First go into the dbt project folder:

```bash
cd C:\Users\Geetu\my-chatbot\youtube_kb
```

Then run dbt:

```bash
py -3.11 -m dbt.cli.main run
```

Wait for it to finish. Expected output:
```
1 of 3 OK created sql view model DBT_TRANSFORM.stg_transcripts
2 of 3 OK created sql view model DBT_TRANSFORM.int_chunks
3 of 3 OK created sql view model DBT_TRANSFORM.mart_knowledge_base

PASS=3  WARN=0  ERROR=0
Completed successfully
```

---

### STEP 5 — Start the chatbot API

> Do this EVERY TIME you want to use the chatbot.
> This starts the server that listens for questions.

Go back to your main project folder:

```bash
cd C:\Users\Geetu\my-chatbot
```

Start the API:

```bash
py -3.11 -m uvicorn main:app --reload
```

Wait until you see this — it means the server is ready:
```
Uvicorn running on http://127.0.0.1:8000
Application startup complete.
```

> IMPORTANT: Keep this terminal window open. If you close it, the chatbot stops.

---

### STEP 6 — Ask a question

Open your browser and go to:
```
http://127.0.0.1:8000/docs
```

Then:
1. Click **POST /chat**
2. Click **Try it out**
3. Paste your question in the box:
```json
{
  "question": "What is Snowflake?"
}
```
4. Click **Execute**
5. Scroll down to see the answer!

---

### STEP 7 — Stop the chatbot

When you are done, go back to the terminal and press:
```
Ctrl + C
```

This stops the server.

---

### Quick Reference — Which steps to run when?

| Situation | Steps to run |
|---|---|
| First time setup | Steps 1 → 2 → 3 → 4 → 5 → 6 |
| Adding a new YouTube video | Steps 3 → 4 only |
| Just want to chat (data already loaded) | Steps 2 → 5 → 6 |
| Something broke | Check Troubleshooting section below |

---

## API Usage

### Test in Browser

Open: `http://127.0.0.1:8000/docs`

Click **POST /chat** → **Try it out** → paste a question → **Execute**

### Test with curl

```bash
curl -X POST "http://127.0.0.1:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{"question": "What is Snowflake?"}'
```

### Example Response

```json
{
  "question": "What is Snowflake?",
  "answer": "Snowflake is a cloud-based data platform that provides an intuitive interface for data integration, warehousing, and analytics...",
  "sources": [
    {
      "video_title": "What is Snowflake?",
      "video_url": "https://www.youtube.com/watch?v=9PBvVeCQi0w",
      "score": 0.643
    }
  ]
}
```

---

## How Do We Know What to Clean?

This is the most important question about dbt. The honest answer is: **YOU decide what to clean. dbt does not automatically know what is messy.**

The process is always the same:

```
Step 1 → Look at your raw data
Step 2 → Spot the problems
Step 3 → Write SQL to fix them
Step 4 → That SQL becomes your dbt model
```

---

### Step 1 — Look at your raw data first

Before writing any dbt model, always run this in your Snowflake Worksheet:

```sql
SELECT * FROM YOUTUBE_KB.RAW.RAW_TRANSCRIPTS LIMIT 10;
```

You might see messy results like this:

```
"   what is snowflake ?   "    ← extra spaces at start and end
""                              ← completely empty row
"[Music]"                       ← not real text, just a music tag
"snowflake is a  cloud"         ← double spaces inside the text
```

---

### Step 2 — Ask yourself: what would break my chatbot?

Look at each problem and think about the impact:

| Problem spotted | Why it matters | SQL fix |
|---|---|---|
| Extra spaces around text | Chatbot may not match correctly | `TRIM(chunk_text)` |
| Empty rows | Chatbot wastes time searching nothing | `WHERE chunk_text != ''` |
| `[Music]` or `[Applause]` rows | Not useful for answering questions | `WHERE LENGTH(chunk_text) > 20` |
| Chunks have no video title | Chatbot cannot show sources | Join with `RAW_VIDEOS` table |
| Chunks have no embedding | Cannot do similarity search | `WHERE embedding IS NOT NULL` |

---

### Step 3 — Write the SQL fix

Each problem becomes one line of SQL in your dbt model:

```sql
SELECT
    TRIM(chunk_text)     AS chunk_text,    -- fixes extra spaces
    LENGTH(chunk_text)   AS chunk_length,
    v.title              AS video_title    -- joins video name in
FROM RAW_TRANSCRIPTS
WHERE TRIM(chunk_text) != ''              -- removes empty rows
AND   LENGTH(chunk_text) > 20             -- removes [Music] etc
```

After cleaning, the same data looks like this:

```
Before cleaning                         After cleaning
─────────────────────────────────────────────────────
"   what is snowflake ?   "    →    "what is snowflake ?"
""                             →    (removed)
"[Music]"                      →    (removed)
"snowflake is a  cloud"        →    "snowflake is a  cloud"
```

---

### The key insight

**dbt is just a tool — like a microwave. You are the cook.**
dbt does not decide what to clean. You look at the raw data, spot the problems, write the SQL fix, and save it as a `.sql` file in the `models/` folder. dbt then runs all your fixes in the correct order every time you run `dbt run`.

The real skill is not knowing how to use dbt — it is knowing how to **look at raw data and spot what needs fixing**. That comes from experience of working with real data.

---

## dbt Models Explained

Think of dbt models like a factory assembly line. Raw data goes in one end, a clean finished product comes out the other. Each model is one station on that line.

---

### Model 1 — stg_transcripts.sql (The Cleaner)

**What it does in plain English:**
Reads the raw transcript chunks from Snowflake and cleans them up. It removes extra spaces, filters out empty rows, and adds a column showing how long each chunk is. Nothing fancy — just tidying up the messy raw data.

```
In:  RAW_TRANSCRIPTS (messy raw data)
Out: clean transcript chunks with length column
```

```sql
SELECT
    chunk_id,
    video_id,
    chunk_index,
    TRIM(chunk_text)   AS chunk_text,    -- removes extra spaces
    LENGTH(chunk_text) AS chunk_length   -- adds length column
FROM RAW_TRANSCRIPTS
WHERE chunk_text IS NOT NULL
AND TRIM(chunk_text) != ''              -- filters empty rows
```

---

### Model 2 — int_chunks.sql (The Joiner)

**What it does in plain English:**
Takes the clean chunks from Model 1 and glues extra information onto each one — the video title, the YouTube URL, and the embedding (the numbers that represent the meaning of the text). Now each row has everything in one place.

```
In:  clean chunks + RAW_VIDEOS + RAW_EMBEDDINGS (3 separate tables)
Out: one wide combined row per chunk
```

```sql
SELECT
    t.chunk_id,
    t.chunk_text,
    v.title      AS video_title,    -- video name joined in
    v.url        AS video_url,      -- YouTube link joined in
    e.embedding                     -- AI numbers joined in
FROM stg_transcripts t
LEFT JOIN RAW_VIDEOS     v ON t.video_id = v.video_id
LEFT JOIN RAW_EMBEDDINGS e ON t.chunk_id = e.chunk_id
```

---

### Model 3 — mart_knowledge_base.sql (The Final Product)

**What it does in plain English:**
Takes everything from Model 2 and filters out any rows that don't have an embedding. This is the final table that your chatbot actually reads when someone asks a question. It is clean, complete, and ready to search.

```
In:  combined rows from int_chunks
Out: MART_KNOWLEDGE_BASE — the table the chatbot queries
```

```sql
SELECT
    chunk_id,
    chunk_text,
    video_title,
    video_url,
    embedding
FROM int_chunks
WHERE embedding IS NOT NULL    -- only keep rows ready for search
```

---

### Why "View" and not "Table"?

Each model creates a **View** in Snowflake, not a physical table. A View is like a saved SQL query — Snowflake runs it fresh every time you read it. No data is copied or duplicated. It just reads from the raw tables on demand. This means if your raw data changes, the view always shows the latest version automatically.

### Why is dbt useful here?

If something changes — say you want to add a new column or fix a bug — you just edit one `.sql` file and run `dbt run` again. dbt figures out the correct order to run all 3 models automatically. No manual work needed.

---

## How It Works (RAG Pipeline)

```
User question
     │
     ▼
Embed question (sentence-transformers, local)
     │
     ▼
Fetch all chunks + embeddings from Snowflake
     │
     ▼
Compute cosine similarity → pick top 3 chunks
     │
     ▼
Build prompt with context chunks
     │
     ▼
Send to Snowflake Cortex COMPLETE() → get answer
     │
     ▼
Return answer + sources via FastAPI
```

---

## Add More Videos

To expand your knowledge base, edit `ingest.py` and change the `YOUTUBE_URL`, then run:

```bash
py -3.11 ingest.py
```

Repeat for as many videos as you want!

---

## Troubleshooting

| Error | Fix |
|---|---|
| `dbt` not working on Python 3.14 | Use Python 3.11 — dbt not yet compatible with 3.14 |
| `ModuleNotFoundError` | Run `pip install` again with `py -3.11 -m pip install ...` |
| Snowflake connection error | Check username/password in `profiles.yml` and `ingest.py` |
| `ffmpeg not found` warning | Safe to ignore — transcript still downloads fine |
| `UNEXPECTED embeddings.position_ids` | Safe to ignore — model loads correctly |

---

## Snowflake Account Details

- Account: `ewzqeyy-iic66448`
- Database: `YOUTUBE_KB`
- Raw Schema: `RAW`
- dbt Schema: `DBT_TRANSFORM`
- Warehouse: `COMPUTE_WH`
