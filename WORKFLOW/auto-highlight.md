---
description: Auto-Highlight Pipeline (Agent Vision)
---
This workflow uses Antigravity's built-in vision and context understanding (Gemini 3.1 Pro) to identify and extract highlights from a YouTube video, without using external API calls.

## Steps

1. **Run Mechanical Extraction (Phase 1)**
   Run the Go backend to download the video and extract raw clips based on chat algorithms. If the user did not provide a URL, ask them for one first.
   ```powershell
   cd src/backend/p1-v1
   go run main.go -url "<Youtube_URL>"
   ```

2. **Understand Context (Phase 2 - Agent Vision)**
   Read `src/backend/p1-v1/state.json` to get the list of generated `clips_path`.
   For each clip:
   - Use the `view_file` tool to watch the `.mp4` video.
   - Use your superior context understanding to determine the exact "peak" moment (15-30 seconds).
   - Generate engaging Japanese telops (captions) that fit the context of the peak moment.

3. **Generate Configuration (Phase 3)**
   Based on your analysis, construct the JSON configuration and write it directly to `src/frontend/p1-v1/src/edit-config.json` using the `write_to_file` tool.
   Ensure the JSON strictly follows this format:
   ```json
   [
     {
       "id": "scene_001",
       "title": "Your Generated Catchy Title",
       "start_time_sec": 0,
       "end_time_sec": 15,
       "clip_start_offset_sec": <start time relative to original clip>,
       "video_path": "<basename_of_the_clip.mp4>",
       "telops": [
         {
           "relative_start_sec": <start time relative to peak (0 is peak start)>,
           "duration_sec": <duration>,
           "text": "Your Telop Text"
         }
       ]
     }
   ]
   ```

// turbo
4. **Prepare Video Assets**
   Run the Python script to copy the video clips into the frontend assets directory.
   ```powershell
   cd src/backend
   python prepare_assets.py
   ```

// turbo
5. **Render Final Video (Phase 4)**
   Call Python to execute the video editing and rendering process (this will invoke Remotion to output the mp4).
   ```powershell
   cd src/backend
   python render_video.py
   ```
