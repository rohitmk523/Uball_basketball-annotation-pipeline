#!/usr/bin/env python3
"""Check which games have plays data in Supabase."""

import os
from supabase import create_client

# Supabase credentials from environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mhbrsftxvxxtfgbajrlc.supabase.co")
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

# Game IDs from GCS
game_ids = [
    "23135de8-36ca-4882-bdf1-8796cd8caa8a",
    "776981a3-b898-4df1-83ab-5e5b1bb4d2c5",
    "a3c9c041-6762-450a-8444-413767bb6428",
    "c07e85e8-9ae4-4adc-a757-3ca00d9d292a",
    "c56b96a1-6e85-469e-8ebe-6a86b929bad9",
    "d6ba2cbb-da84-4614-82fc-ff58ba12d5ab"
]

def main():
    print("=" * 60)
    print("📊 Checking Supabase for Games with Plays Data")
    print("=" * 60)
    print()

    # Initialize Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    valid_games = []

    for game_id in game_ids:
        try:
            # Query plays for this game
            response = supabase.table("plays").select("id, angle, start_timestamp, end_timestamp").eq("game_id", game_id).execute()

            plays_count = len(response.data)

            # Count by angle
            left_plays = sum(1 for p in response.data if p.get('angle') == 'LEFT')
            right_plays = sum(1 for p in response.data if p.get('angle') == 'RIGHT')

            # Check for valid timestamps
            valid_timestamps = sum(1 for p in response.data if p.get('start_timestamp') is not None and p.get('end_timestamp') is not None)

            print(f"Game: {game_id}")
            print(f"  Total plays: {plays_count}")
            print(f"  LEFT plays: {left_plays}")
            print(f"  RIGHT plays: {right_plays}")
            print(f"  Valid timestamps: {valid_timestamps}/{plays_count}")

            if plays_count > 0 and valid_timestamps > 0:
                print(f"  ✅ VALID - Ready for training")
                valid_games.append(game_id)
            else:
                print(f"  ❌ INVALID - Missing data")

            print()

        except Exception as e:
            print(f"Game: {game_id}")
            print(f"  ❌ ERROR: {e}")
            print()

    print("=" * 60)
    print(f"📊 Summary: {len(valid_games)}/{len(game_ids)} games ready for training")
    print("=" * 60)
    print()

    if valid_games:
        print("✅ Ready for training:")
        for game_id in valid_games:
            print(f"  - {game_id}")
        print()
        print("📋 JSON format for workflow:")
        import json
        print(json.dumps({"game_ids": valid_games}, indent=2))

if __name__ == "__main__":
    main()
