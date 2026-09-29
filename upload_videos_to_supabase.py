import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

def upload_local_videos():
    load_dotenv()
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
        return
        
    supabase: Client = create_client(url, key)
    bucket = "urban_watch_evidence"
    
    uploads_dir = Path(__file__).parent / "backend" / "uploads"
    if not uploads_dir.exists():
        print(f"Directory not found: {uploads_dir}")
        return
        
    for video_file in uploads_dir.glob("*.mp4"):
        print(f"Uploading {video_file.name} to Supabase...")
        storage_path = f"uploads/{video_file.name}"
        
        with open(video_file, "rb") as f:
            try:
                # Use upsert to avoid duplicate errors if already uploaded
                supabase.storage.from_(bucket).upload(
                    path=storage_path,
                    file=f,
                    file_options={"content-type": "video/mp4", "upsert": "true"}
                )
                print(f"✅ Successfully uploaded: {video_file.name}")
            except Exception as e:
                print(f"❌ Failed to upload {video_file.name}: {e}")

if __name__ == "__main__":
    print("Starting video uploads to Supabase...")
    upload_local_videos()
    print("Done!")
