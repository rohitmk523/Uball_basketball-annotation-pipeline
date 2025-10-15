"""
Test database and storage connections.

Run this after setting up credentials to verify everything works.
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

def test_supabase():
    """Test Supabase connection."""
    print("🔄 Testing Supabase connection...")
    try:
        from app.core.database import get_supabase
        client = get_supabase()
        
        # Try a simple query
        response = client.table("games").select("id").limit(1).execute()
        
        print("✅ Supabase connection successful!")
        print(f"   URL: {client.supabase_url}")
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        print("\n💡 Make sure:")
        print("   1. SUPABASE_URL is correct in .env")
        print("   2. SUPABASE_SERVICE_KEY is set (not anon key!)")
        return False


def test_gcs():
    """Test GCS connection."""
    print("\n🔄 Testing GCS connection...")
    try:
        from app.core.storage import get_storage
        client = get_storage()
        
        # Try to list buckets
        buckets = list(client.list_buckets())
        
        print("✅ GCS connection successful!")
        print(f"   Project: {client.project}")
        print(f"   Buckets found: {len(buckets)}")
        
        # Check for our buckets
        bucket_names = [b.name for b in buckets]
        
        required_buckets = [
            "uball-videos-production",
            "uball-training-data",
            "uball-models"
        ]
        
        for bucket_name in required_buckets:
            if bucket_name in bucket_names:
                print(f"   ✓ {bucket_name}")
            else:
                print(f"   ⚠️  {bucket_name} (not found - will be created if needed)")
        
        return True
    except Exception as e:
        print(f"❌ GCS connection failed: {e}")
        print("\n💡 Make sure:")
        print("   1. service-account-key.json exists in project root")
        print("   2. GOOGLE_APPLICATION_CREDENTIALS is set in .env")
        print("   3. Service account has Storage Admin role")
        return False


def test_video_access():
    """Test access to video bucket."""
    print("\n🔄 Testing video bucket access...")
    try:
        from app.core.storage import get_storage
        from app.core.config import settings
        
        client = get_storage()
        bucket = client.bucket(settings.GCS_VIDEO_BUCKET)
        
        # Try to list some files
        blobs = list(bucket.list_blobs(max_results=5))
        
        print(f"✅ Video bucket accessible: gs://{settings.GCS_VIDEO_BUCKET}/")
        print(f"   Sample files: {len(blobs)}")
        
        for blob in blobs[:3]:
            print(f"   - {blob.name}")
        
        return True
    except Exception as e:
        print(f"⚠️  Video bucket access issue: {e}")
        print("   (This is OK if bucket is empty or doesn't exist yet)")
        return True  # Don't fail on this


def main():
    """Run all connection tests."""
    print("="*60)
    print("CONNECTION TEST")
    print("="*60)
    
    supabase_ok = test_supabase()
    gcs_ok = test_gcs()
    test_video_access()
    
    print("\n" + "="*60)
    if supabase_ok and gcs_ok:
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\nYou're ready to:")
        print("1. Run the API: uvicorn app.main:app --reload")
        print("2. Export training data: python scripts/training/export_plays.py")
        print("3. Visit API docs: http://localhost:8000/docs")
    else:
        print("❌ SOME TESTS FAILED")
        print("="*60)
        print("\nPlease fix the issues above before proceeding.")
        print("See QUICK_START.md for help.")


if __name__ == "__main__":
    main()

