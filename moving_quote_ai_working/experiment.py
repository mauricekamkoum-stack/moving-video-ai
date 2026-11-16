import os
import json
from google import genai
from google.genai import types
from PIL import Image

# 1. Initialize the Gemini client
# It automatically looks for the GEMINI_API_KEY environment variable
client = genai.Client()

# Path configuration
PHOTOS_DIR = "test_photos"
OUTPUT_FILE = "experiment_results.json"

# The prompt designed for the moving estimate use-case
PROMPT = """
You are an expert AI logistics and moving estimator. Analyze this room/furniture photo.
Please provide:
1. A list of visible furniture items, appliances, and boxes.
2. Estimated dimensions (Length x Width x Height in centimeters) for each item.
3. Estimated volume for each item in cubic meters (m³).
4. Total estimated volume for the items in this photo (m³).

Format your response clearly as JSON with keys: "items" (list of objects with name, dimensions, volume_m3) and "total_volume_m3" (number).
"""

def run_experiment():
    if not os.path.exists(PHOTOS_DIR):
        print(f"Error: Directory '{PHOTOS_DIR}' not found. Please create it and add your 10 photos.")
        return

    photo_files = [f for f in os.listdir(PHOTOS_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if len(photo_files) < 1:
        print("Error: No photos found in the 'test_photos' folder.")
        return

    print(f"Found {len(photo_files)} photos. Starting Gemini evaluation...\n")

    results = []
    successful_extractions = 0

    import time

    # List of stable model IDs to try sequentially if a 503 high demand error occurs
    candidate_models = [
        'gemini-3.8-flash',
        'gemini-3.5-flash-lite',
        'gemini-4-argon'
    ]

    for filename in sorted(photo_files):
        photo_path = os.path.join(PHOTOS_DIR, filename)
        print(f"Processing: {filename}...")

        response_text = None
        last_error = None

        # Try each candidate model
        for model_name in candidate_models:
            # Try up to 3 times per model if it's busy
            for attempt in range(3):
                try:
                    image = Image.open(photo_path)

                    response = client.models.generate_content(
                        model=model_name,
                        contents=[image, PROMPT]
                    )

                    response_text = response.text
                    break # Success! Break out of the retry loop
                except Exception as e:
                    last_error = e
                    if "503" in str(e) or "unavailable" in str(e).lower():
                        print(f"  -> [{model_name}] busy (503). Retrying in 4 seconds... (Attempt {attempt+1}/3)")
                        time.sleep(4)
                    else:
                        break # If it's a different error, stop retrying this specific model
            
            if response_text:
                break # Break out of the model loop once a response is successfully received

        if response_text:
            is_successful = "total_volume_m3" in response_text.lower() or "m³" in response_text.lower()
            if is_successful:
                successful_extractions += 1

            results.append({
                "filename": filename,
                "status": "success" if is_successful else "partial_failure",
                "gemini_output": response_text
            })
        else:
            print(f"  -> Error processing {filename} across all models: {last_error}")
            results.append({
                "filename": filename,
                "status": "error",
                "error_message": str(last_error)
            })

    # Calculate overall metric
    total_tested = len(photo_files)
    success_rate = (successful_extractions / total_tested) * 100 if total_tested > 0 else 0

    summary = {
        "total_photos_tested": total_tested,
        "successful_extractions": successful_extractions,
        "success_rate_percentage": success_rate,
        "results": results
    }

    # Save results to a JSON report file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4, ensure_ascii=False)

    print("\n==============================")
    print(" EXPERIMENT COMPLETE ")
    print("==============================")
    print(f"Total Tested: {total_tested}")
    print(f"Successful Extractions: {successful_extractions}")
    print(f"Success Rate Metric: {success_rate:.1f}%")
    print(f"Detailed results saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_experiment()


#this part is for displaying a part of json result file in terminal so we can comment it (its not necessary) 
    import json
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        print("\n" + "="*40)
        print(" FINAL EXPERIMENT REPORT SUMMARY")
        print("="*40)
        print(f"Total Photos Tested: {data['total_photos_tested']}")
        print(f"Success Rate: {data['success_rate_percentage']}%")
        print("-" * 40)
        
        for res in data["results"]:
            print(f"\n📂 File: {res['filename']}")
            print(f"Status: {res['status'].upper()}")
            if "gemini_output" in res:
                print("Gemini Output:")
                print(res["gemini_output"])
            elif "error_message" in res:
                print(f"Error: {res['error_message']}")
            print("-" * 40)

