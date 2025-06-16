import psycopg2

# DB config
DB_CONFIG = {
    "dbname": "piruby_automation",
    "user": "postgres",
    "password": "piruby@157",
    "host": "164.52.194.25",
    "port": "5432"
}

# Function to fetch and save transcript
def save_transcript(video_id, output_file="transcript.txt"):
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT text FROM public.new_vimeo_master_m
                    WHERE video_id = %s
                    ORDER BY _offset
                """, (video_id,))
                rows = cur.fetchall()
                transcript = " ".join(row[0] for row in rows if row[0])
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(transcript)
                print(f"Transcript saved to {output_file}")
    except Exception as e:
        print(f"Error: {e}")

# Usage
save_transcript("982394038")
