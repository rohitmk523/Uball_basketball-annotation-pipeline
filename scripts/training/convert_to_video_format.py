#!/usr/bin/env python3
"""
Convert existing training data to proper Vertex AI video fine-tuning format.

This script converts the current simple text format to the new video fine-tuning
format required by Vertex AI Gemini 2.5 models.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def convert_to_video_format(old_example: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert old format to new video fine-tuning format.
    
    Args:
        old_example: Old format example
        
    Returns:
        New format example for video fine-tuning
    """
    return {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "fileData": {
                            "fileUri": old_example["clip_uri"],
                            "mimeType": "video/mp4"
                        },
                        "videoMetadata": {
                            "startOffset": "0s",
                            "endOffset": "30s"  # Default 30 second clips
                        }
                    },
                    {
                        "text": f"Analyze this basketball play clip from {old_example['angle']} camera angle. Identify the key actions, player movements, and strategic elements in this play."
                    }
                ]
            },
            {
                "role": "model",
                "parts": [
                    {
                        "text": f"This is a basketball play video from the {old_example['angle']} perspective showing game action. Play ID: {old_example['play_id']}. The clip demonstrates basketball fundamentals including player positioning, ball movement, and tactical execution typical of organized basketball gameplay."
                    }
                ]
            }
        ],
        "generationConfig": {
            "mediaResolution": "MEDIA_RESOLUTION_LOW"  # Faster processing, 4x speed improvement
        }
    }


def convert_dataset(input_file: str, output_file: str) -> None:
    """
    Convert entire dataset from old to new format.
    
    Args:
        input_file: Path to input JSONL file
        output_file: Path to output JSONL file
    """
    logger.info(f"Converting {input_file} to {output_file}")
    
    converted_count = 0
    error_count = 0
    
    with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
        for line_num, line in enumerate(infile, 1):
            try:
                old_example = json.loads(line.strip())
                new_example = convert_to_video_format(old_example)
                outfile.write(json.dumps(new_example) + '\n')
                converted_count += 1
                
            except Exception as e:
                logger.error(f"Error converting line {line_num}: {e}")
                error_count += 1
                continue
    
    logger.info(f"✅ Conversion complete:")
    logger.info(f"  - Converted: {converted_count} examples")
    logger.info(f"  - Errors: {error_count} examples")
    logger.info(f"  - Output: {output_file}")


def main():
    """Main conversion function."""
    if len(sys.argv) != 3:
        print("Usage: python convert_to_video_format.py <input_jsonl> <output_jsonl>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    # Validate input file exists
    if not Path(input_file).exists():
        logger.error(f"Input file not found: {input_file}")
        sys.exit(1)
    
    # Create output directory if needed
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Convert the dataset
    convert_dataset(input_file, output_file)
    
    logger.info("🎉 Video format conversion completed successfully!")


if __name__ == "__main__":
    main()