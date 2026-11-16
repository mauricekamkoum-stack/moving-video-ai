import os
import json
import time
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

#Page Configuration
st.set_page_config(page_title="Moving Quote AI", page_icon="📦", layout="centered")

st.title("📦 Moving Quote AI — Volume Estimator")
st.write("Upload up to 10 photos of your apartment to automatically detect furniture and estimate moving volume ($\text{m}^3$).")

#API Key Check
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    api_key = st.text_input("Enter your Gemini API Key (or set GEMINI_API_KEY in terminal):", type="password")

if not api_key:
    st.warning("Please provide a Gemini API key to enable estimation.")
    st.stop()

client = genai.Client(api_key=api_key)

#Prompt (Refined based on M2 findings)
PROMPT = """
Analyze this apartment photo for a moving company quote.
Identify all furniture, large appliances, and moving boxes that need to be transported.
IMPORTANT: Ignore small personal items such as laptops, books, clothes, decor, lamps, or plants. 
(Note: Include suitcases only if clearly visible as luggage).

For each item, estimate realistic dimensions in centimeters (length, width, height) and calculate its volume in cubic meters (m3).

Return ONLY a valid JSON object matching this exact structure:
{
  "items": [
    {
      "name": "Item name",
      "dimensions_cm": {"length": 100, "width": 50, "height": 80},
      "volume_m3": 0.40
    }
  ],
  "photo_total_volume_m3": 0.40
}
"""

#File Upload Box
uploaded_files = st.file_uploader(
    "Drag and drop apartment photos here (Max 10 photos)",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True
)

if uploaded_files:
    if len(uploaded_files) > 10:
        st.error(f"You uploaded {len(uploaded_files)} photos. Please remove {len(uploaded_files) - 10} photo(s) to stay within the 10-photo limit.")
        st.stop()
    
    st.info(f"{len(uploaded_files)} photo(s) ready for analysis.")

    #ESTIMATE Button
    if st.button("ESTIMATE", type="primary", use_container_width=True):
        candidate_models = ['gemini-3.5-flash-lite', 'gemini-3.8-flash']
        all_results = []
        grand_total_volume = 0.0

        st.divider()
        st.subheader("Quote Estimation Results")

        #Process photo after photo and render immediately
        for idx, uploaded_file in enumerate(uploaded_files, start=1):
            image = Image.open(uploaded_file)
            
            with st.container(border=True):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.image(image, caption=f"Photo {idx}: {uploaded_file.name}", use_container_width=True)
                
                with col2:
                    with st.spinner(f"Analyzing {uploaded_file.name}..."):
                        parsed_data = None
                        last_error = None

                        for model_name in candidate_models:
                            for attempt in range(3):
                                try:
                                    response = client.models.generate_content(
                                        model=model_name,
                                        contents=[image, PROMPT],
                                        config=types.GenerateContentConfig(
                                            response_mime_type="application/json"
                                        )
                                    )
                                    parsed_data = json.loads(response.text)
                                    break
                                except Exception as e:
                                    last_error = e
                                    if "503" in str(e) or "unavailable" in str(e).lower():
                                        time.sleep(3)
                                    else:
                                        break
                            if parsed_data:
                                break

                    #Display results for this photo right away
                    if parsed_data and "items" in parsed_data:
                        items = parsed_data["items"]
                        photo_vol = sum(item.get("volume_m3", 0.0) for item in items)
                        grand_total_volume += photo_vol

                        if not items:
                            st.write("No major furniture detected in this photo.")
                        else:
                            for item in items:
                                dims = item.get("dimensions_cm", {})
                                l, w, h = dims.get("length", 0), dims.get("width", 0), dims.get("height", 0)
                                vol = item.get("volume_m3", 0.0)
                                st.markdown(f"- **{item['name']}** ({l}×{w}×{h} cm) — `{vol:.2f} m³`")
                        
                        st.markdown(f"**Photo Subtotal:** `{photo_vol:.2f} m³`")
                        
                        all_results.append({
                            "filename": uploaded_file.name,
                            "status": "success",
                            "extracted_data": parsed_data
                        })
                    else:
                        st.error(f"Failed to analyze {uploaded_file.name}: {last_error}")
                        all_results.append({
                            "filename": uploaded_file.name,
                            "status": "error",
                            "error_message": str(last_error)
                        })

        #Save to experiment_results.json
        output_payload = {
            "total_photos_tested": len(uploaded_files),
            "grand_total_volume_m3": round(grand_total_volume, 2),
            "results": all_results
        }
        with open("experiment_results.json", "w", encoding="utf-8") as f:
            json.dump(output_payload, f, indent=4)

        #Final Summary Banner
        st.divider()
        st.success(f"### Total Estimated Moving Volume: {grand_total_volume:.2f} m³")
        st.caption("Preliminary estimate saved to `experiment_results.json`. Requires moving company validation.")