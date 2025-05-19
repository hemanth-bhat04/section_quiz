import psycopg2
from collections import Counter

# === CONFIGURATION ===
VIDEO_ID = '982406834'  # Your video ID
DB_CONFIG = {
    "dbname": "piruby_automation",
    "user": "postgres",
    "password": "piruby@157",
    "host": "164.52.194.25",
    "port": "5432"
}

def fetch_all_keywords(video_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT critical_keywords
                    FROM public.new_vimeo_master_m
                    WHERE video_id = %s
                    ORDER BY _offset
                """, (video_id,))
                result = cur.fetchall()
                keywords = []
                for row in result:
                    if isinstance(row[0], list):
                        keywords.extend(row[0])
                return keywords
    except Exception as e:
        print(f"[Keyword Fetch Error] {e}")
        return []

def main():
    keywords = fetch_all_keywords(VIDEO_ID)

    if not keywords:
        print("No keywords found for this video.")
        return

    print(f"✅ Total keywords fetched: {len(keywords)}\n")

    for i, word in enumerate(keywords, 1):
        print(f"{i:3}. {word}")

    print("\n--- Unique Keywords (with frequency) ---")
    counts = Counter(keywords)
    for word, count in counts.most_common():
        print(f"{word}: {count}")

if __name__ == "__main__":
    main()
