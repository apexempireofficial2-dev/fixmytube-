import os
import uuid
import subprocess
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 2 GB target
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024

app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE


def safe_float(value, default, minimum, maximum):
    try:
        value = float(value)
        return max(minimum, min(maximum, value))
    except (TypeError, ValueError):
        return default


def safe_int(value, default, allowed):
    try:
        value = int(value)
        return value if value in allowed else default
    except (TypeError, ValueError):
        return default


def build_video_filter(mirror, crop, resolution):
    filters = []

    # Mirror
    if mirror:
        filters.append("hflip")

    # Deep pixel crop
    if crop:
        filters.append(
            "scale=iw*1.03:ih*1.03,"
            "crop=iw/1.03:ih/1.03"
        )

    # Resolution
    resolution_map = {
        "1080": "scale=-2:1080",
        "720": "scale=-2:720",
        "480": "scale=-2:480",
        "360": "scale=-2:360",
    }

    if resolution in resolution_map:
        filters.append(resolution_map[resolution])

    return ",".join(filters) if filters else "null"


def build_audio_filter(pitch, tempo):
    filters = []

    # Pitch changes sample rate and then restores output sample rate.
    # atempo controls playback tempo.
    if abs(pitch - 1.0) > 0.001:
        filters.append(
            f"asetrate=44100*{pitch:.4f},"
            "aresample=44100"
        )

    if abs(tempo - 1.0) > 0.001:
        filters.append(
            f"atempo={tempo:.4f}"
        )

    return ",".join(filters) if filters else "anull"


@app.route("/")
def home():
    return "FixMyTube Backend is running!"


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "FixMyTube"
    })


@app.errorhandler(413)
def too_large(error):
    return jsonify({
        "error": "Video 2 GB se badi hai."
    }), 413


@app.route("/process", methods=["POST"])
def process_video():

    if "video" not in request.files:
        return jsonify({
            "error": "Video file missing."
        }), 400

    video = request.files["video"]

    if not video.filename:
        return jsonify({
            "error": "Invalid video filename."
        }), 400

    job_id = uuid.uuid4().hex

    input_file = os.path.join(
        UPLOAD_DIR,
        f"{job_id}_input"
    )

    output_file = os.path.join(
        OUTPUT_DIR,
        f"{job_id}_output.mp4"
    )

    try:

        # -------------------------
        # Save uploaded video
        # -------------------------

        video.save(input_file)

        if not os.path.exists(input_file):
            return jsonify({
                "error": "Upload failed."
            }), 400

        if os.path.getsize(input_file) > MAX_FILE_SIZE:
            os.remove(input_file)

            return jsonify({
                "error": "Video 2 GB se badi hai."
            }), 413

        # -------------------------
        # Read settings
        # -------------------------

        mode = request.form.get(
            "mode",
            "basic"
        )

        if mode not in ("basic", "heavy"):
            mode = "basic"

        mirror = request.form.get(
            "mirror",
            "1"
        ) == "1"

        crop = request.form.get(
            "crop",
            "1"
        ) == "1"

        remove_metadata = request.form.get(
            "metadata",
            "1"
        ) == "1"

        fps_value = request.form.get(
            "fps",
            "source"
        )

        resolution = request.form.get(
            "resolution",
            "source"
        )

        pitch = safe_float(
            request.form.get("pitch"),
            1.0,
            0.90,
            1.10
        )

        tempo = safe_float(
            request.form.get("tempo"),
            1.0,
            0.90,
            1.10
        )

        fps = safe_int(
            fps_value,
            30,
            [24, 30, 60]
        )

        # -------------------------
        # Heavy preset
        # -------------------------

        if mode == "heavy":

            # Original heavy preset:
            # mirror + crop + 30 FPS
            mirror = True
            crop = True

            if abs(pitch - 1.0) < 0.001:
                pitch = 1.04

            if abs(tempo - 1.0) < 0.001:
                tempo = 0.96

            fps = 30

        # -------------------------
        # Build filters
        # -------------------------

        video_filter = build_video_filter(
            mirror,
            crop,
            resolution
        )

        audio_filter = build_audio_filter(
            pitch,
            tempo
        )

        # -------------------------
        # FFmpeg command
        # -------------------------

        command = [
            "ffmpeg",
            "-y",
            "-i",
            input_file
        ]

        # Video filter
        if video_filter:
            command.extend([
                "-vf",
                video_filter
            ])

        # FPS
        if fps_value != "source" or mode == "heavy":
            command.extend([
                "-r",
                str(fps)
            ])

        # Audio filter
        if audio_filter:
            command.extend([
                "-af",
                audio_filter
            ])

        # Metadata
        if remove_metadata:
            command.extend([
                "-map_metadata",
                "-1"
            ])

        # Video encoding
        if mode == "heavy":
            crf = "25"
        else:
            crf = "23"

        command.extend([
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            crf,

            "-c:a",
            "aac",
            "-b:a",
            "192k",

            "-movflags",
            "+faststart",

            output_file
        ])

        # -------------------------
        # Run FFmpeg
        # -------------------------

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # -------------------------
        # FFmpeg error
        # -------------------------

        if result.returncode != 0:

            error_log = result.stderr[-3000:]

            return jsonify({
                "error": "FFmpeg processing failed.",
                "details": error_log
            }), 500

        # -------------------------
        # Check output
        # -------------------------

        if not os.path.exists(output_file):

            return jsonify({
                "error": "Processed video create nahi hui."
            }), 500

        # -------------------------
        # Send output
        # -------------------------

        return send_file(
            output_file,
            as_attachment=True,
            download_name="FixMyTube_Transformed.mp4",
            mimetype="video/mp4"
        )

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500

    finally:

        # Input cleanup
        if os.path.exists(input_file):
            try:
                os.remove(input_file)
            except OSError:
                pass

        # Output cleanup
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
            except OSError:
                pass


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "5000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
