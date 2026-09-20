import asyncio
import re
import sqlite3

from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters
)


# =========================================================
# BOT TOKEN
# =========================================================

TOKEN = "8777357717:AAHBrLLZg6R88cZVHq9EDbir1oS4Q3wVOj8"


# =========================================================
# DATABASE
# =========================================================

DB_NAME = "cineflix_movies.db"

db = sqlite3.connect(
    DB_NAME,
    check_same_thread=False
)

cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    movie_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_id TEXT NOT NULL,
    caption TEXT
)
""")

db.commit()


# =========================================================
# BAD WORDS
# =========================================================

BAD_WORDS = [

    # English / Roman
    "mc",
    "bc",
    "madarchod",
    "madar chod",
    "bhenchod",
    "behenchod",
    "chutiya",
    "chutia",
    "gandu",
    "harami",
    "kamina",
    "kamine",
    "bhosdike",
    "bsdk",
    "randi",
    "lund",
    "laude",
    "lavde",
    "fuck",
    "fucking",
    "motherfucker",

    # বাংলা
    "মাদারচোদ",
    "মাদার চোদ",
    "ভোদাই",
    "ভোদার",
    "চোদা",
    "চোদাচুদি",
    "চুদ",
    "চুদবি",
    "চুদব",
    "চুতিয়া",
    "চুতিয়া",
    "গান্ডু",
    "হারামি",
    "হারামজাদা",
    "বাঞ্চোদ",
    "বানচোদ",
    "বাল",
    "বালছাল",
    "বালচাল",
    "শালা",
    "শালার",
    "খানকি",
    "রান্ডি"
]


# =========================================================
# ADULT DOMAINS
# =========================================================

ADULT_DOMAINS = [

    "pornhub.com",
    "xnxx.com",
    "xvideos.com",
    "xhamster.com",
    "redtube.com",
    "youporn.com",
    "tube8.com",
    "spankbang.com",
    "brazzers.com",
    "onlyfans.com"
]


# =========================================================
# NORMALIZER
# =========================================================

def normalize(text):

    text = str(text or "").lower()

    text = re.sub(
        r"[^\w\u0980-\u09FF]+",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =========================================================
# BAD WORD CHECK
# =========================================================

def contains_bad_word(text):

    text = normalize(text)

    for word in BAD_WORDS:

        word = normalize(word)

        if not word:
            continue

        pattern = (
            r"(?<!\w)"
            + re.escape(word)
            + r"(?!\w)"
        )

        if re.search(
            pattern,
            text,
            re.IGNORECASE
        ):
            return True

    return False


# =========================================================
# ADULT LINK CHECK
# =========================================================

def contains_adult_link(text):

    text = str(text or "").lower()

    for domain in ADULT_DOMAINS:

        if domain in text:
            return True

    adult_patterns = [

        r"\bporn\b",
        r"\bpornvideo\b",
        r"\bpornhub\b",
        r"\bxxx\b",
        r"\bxnxx\b",
        r"\bxvideos\b",
        r"\bxhamster\b",
        r"\bredtube\b",
        r"\byouporn\b",
        r"\bonlyfans\b",
        r"\bnsfw\b"

    ]

    for pattern in adult_patterns:

        if re.search(
            pattern,
            text,
            re.IGNORECASE
        ):
            return True

    return False


# =========================================================
# GET COMPLETE MESSAGE TEXT
# =========================================================

def get_message_text(message):

    parts = []

    if message.text:
        parts.append(message.text)

    if message.caption:
        parts.append(message.caption)

    if message.video:

        if message.video.file_name:
            parts.append(
                message.video.file_name
            )

    if message.document:

        if message.document.file_name:
            parts.append(
                message.document.file_name
            )

    if message.audio:

        if message.audio.file_name:
            parts.append(
                message.audio.file_name
            )

    return " ".join(parts)


# =========================================================
# EXTRACT MOVIE NAME
# =========================================================

def extract_movie_name(message):

    caption = (
        message.caption
        or ""
    ).strip()

    # Video
    if message.video:

        filename = (
            message.video.file_name
            or ""
        ).strip()

        if caption:
            return caption

        if filename:
            return filename

    # Document
    if message.document:

        filename = (
            message.document.file_name
            or ""
        ).strip()

        if caption:
            return caption

        if filename:
            return filename

    # Audio
    if message.audio:

        filename = (
            message.audio.file_name
            or ""
        ).strip()

        if caption:
            return caption

        if filename:
            return filename

    return ""


# =========================================================
# SAVE MOVIE
# =========================================================

def save_movie(
    chat_id,
    message_id,
    movie_name,
    file_type,
    file_id,
    caption
):

    movie_name = normalize(movie_name)

    if not movie_name:
        return

    # Check duplicate message
    cursor.execute("""
        SELECT id
        FROM movies
        WHERE chat_id = ?
        AND message_id = ?
        LIMIT 1
    """, (
        chat_id,
        message_id
    ))

    if cursor.fetchone():
        return

    cursor.execute("""
        INSERT INTO movies
        (
            chat_id,
            message_id,
            movie_name,
            file_type,
            file_id,
            caption
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        chat_id,
        message_id,
        movie_name,
        file_type,
        file_id,
        caption
    ))

    db.commit()


# =========================================================
# INDEX VIDEO / DOCUMENT / AUDIO
# =========================================================

async def index_movie(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message:
        return

    if message.chat.type not in [
        "group",
        "supergroup"
    ]:
        return

    movie_name = extract_movie_name(message)

    if not movie_name:
        return

    # Don't index prohibited content
    if contains_bad_word(movie_name):
        return

    if contains_adult_link(movie_name):
        return

    caption = message.caption or ""

    # =====================================================
    # VIDEO
    # =====================================================

    if message.video:

        save_movie(
            message.chat.id,
            message.message_id,
            movie_name,
            "video",
            message.video.file_id,
            caption
        )

        print(
            "INDEXED VIDEO:",
            movie_name
        )

        return

    # =====================================================
    # DOCUMENT
    # =====================================================

    if message.document:

        save_movie(
            message.chat.id,
            message.message_id,
            movie_name,
            "document",
            message.document.file_id,
            caption
        )

        print(
            "INDEXED DOCUMENT:",
            movie_name
        )

        return

    # =====================================================
    # AUDIO
    # =====================================================

    if message.audio:

        save_movie(
            message.chat.id,
            message.message_id,
            movie_name,
            "audio",
            message.audio.file_id,
            caption
        )

        print(
            "INDEXED AUDIO:",
            movie_name
        )


# =========================================================
# SEARCH MOVIE
# =========================================================

def search_movie(
    chat_id,
    query
):

    query = normalize(query)

    if not query:
        return None

    # =====================================================
    # EXACT / CONTAINING MATCH
    # =====================================================

    cursor.execute("""
        SELECT
            id,
            movie_name,
            file_type,
            file_id,
            caption
        FROM movies
        WHERE chat_id = ?
        AND movie_name LIKE ?
        ORDER BY id DESC
        LIMIT 1
    """, (
        chat_id,
        "%" + query + "%"
    ))

    return cursor.fetchone()


# =========================================================
# MOVIE SEARCH
# =========================================================

async def movie_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message:
        return

    if message.chat.type not in [
        "group",
        "supergroup"
    ]:
        return

    if not message.text:
        return

    original_text = message.text.strip()

    if not original_text:
        return

    # =====================================================
    # ONLY SEARCH WHEN "MOVIE" IS PRESENT
    # =====================================================

    match = re.search(
        r"\bmovie\b",
        original_text,
        re.IGNORECASE
    )

    if not match:
        return

    # Remove "movie"
    query = re.sub(
        r"\bmovie\b",
        "",
        original_text,
        flags=re.IGNORECASE
    ).strip()

    # Remove extra spaces
    query = re.sub(
        r"\s+",
        " ",
        query
    ).strip()

    # No movie name
    if not query:
        return

    # Don't search prohibited content
    if contains_bad_word(query):
        return

    if contains_adult_link(query):
        return

    print(
        "SEARCH:",
        query
    )

    # =====================================================
    # DATABASE SEARCH
    # =====================================================

    result = search_movie(
        message.chat.id,
        query
    )

    # =====================================================
    # MOVIE FOUND
    # =====================================================

    if result:

        (
            movie_id,
            movie_name,
            file_type,
            file_id,
            caption
        ) = result

        try:

            if file_type == "video":

                await message.reply_video(
                    video=file_id,
                    caption=caption or None
                )

            elif file_type == "document":

                await message.reply_document(
                    document=file_id,
                    caption=caption or None
                )

            elif file_type == "audio":

                await message.reply_audio(
                    audio=file_id,
                    caption=caption or None
                )

            print(
                "MOVIE RESENT:",
                movie_name
            )

        except Exception as error:

            print(
                "RESEND ERROR:",
                error
            )

        return

    # =====================================================
    # MOVIE NOT FOUND
    # =====================================================

    await asyncio.sleep(1.2)

    try:

        await message.reply_text(
            "Sorry, movie is not available."
        )

        print(
            "NOT AVAILABLE:",
            query
        )

    except Exception as error:

        print(
            "REPLY ERROR:",
            error
        )


# =========================================================
# MAIN MESSAGE HANDLER
# =========================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message:
        return

    # Only groups
    if message.chat.type not in [
        "group",
        "supergroup"
    ]:
        return

    # =====================================================
    # MODERATION
    # =====================================================

    full_text = get_message_text(message)

    if full_text:

        bad = contains_bad_word(
            full_text
        )

        adult = contains_adult_link(
            full_text
        )

        if bad or adult:

            await asyncio.sleep(1.2)

            try:

                await message.delete()

                print(
                    "DELETED:",
                    "BAD WORD"
                    if bad
                    else "ADULT LINK"
                )

            except Exception as error:

                print(
                    "DELETE ERROR:",
                    error
                )

            return

    # =====================================================
    # MOVIE FILE INDEX
    #
    # NO REPLY HERE
    # =====================================================

    if (
        message.video
        or
        message.document
        or
        message.audio
    ):

        await index_movie(
            update,
            context
        )

        return

    # =====================================================
    # TEXT SEARCH
    #
    # ONLY "movie" WORD PRESENT
    # =====================================================

    if message.text:

        await movie_search(
            update,
            context
        )


# =========================================================
# START BOT
# =========================================================

def main():

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    # =====================================================
    # ALL GROUP MESSAGES
    # =====================================================

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & ~filters.StatusUpdate.ALL,
            handle_message
        )
    )

    print("")
    print("==========================================")
    print(" CineFlix Bot")
    print(" Moderation + Movie Search")
    print("==========================================")
    print("🤖 Bot is running...")
    print("🎬 Search format: KGF movie")
    print("==========================================")
    print("")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
