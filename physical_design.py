import psycopg2

DB_CONFIG = {
    "dbname": "piruby_automation",
    "user": "postgres",
    "password": "piruby@157",
    "host": "164.52.194.25",
    "port": "5432"
}

VIDEO_ID = '982406834'  # Change if needed
OUTPUT_FILE = f"transcript_{VIDEO_ID}.txt"

def fetch_video_text(video_id):
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT text
                    FROM public.new_vimeo_master_m
                    WHERE video_id = %s
                    ORDER BY _offset
                """, (video_id,))
                results = cur.fetchall()
                return [row[0] for row in results if row[0]]
    except Exception as e:
        print(f"[Error] {e}")
        return []

if __name__ == "__main__":
    texts = fetch_video_text(VIDEO_ID)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for line in texts:
            f.write(line.strip() + "\n")
    print(f"[Saved] Transcript saved to {OUTPUT_FILE}")
