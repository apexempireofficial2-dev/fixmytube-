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


@app.route("/")
def home():
    return "FixMyTube Backend is running!"


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "FixMyTube"
    })


@app.route("/process", methods=["POST"])
def process_video():

    if "video" not in request.files:
        return jsonify({"error": "Video file missing"}), 400

    video = request.files["video"]

    if not video.filename:
        return jsonify({"error": "Invalid filename"}), 400

    job_id = str(uuid.uuid4())

    input_file = os.path.join(
        UPLOAD_DIR,
        f"{job_id}_input.mp4"
    )

    output_file = os.path.join(
        OUTPUT_DIR,
        f"{job_id}_output.mp4"
    )

    video.save(input_file)

    mode = request.form.get("mode", "basic")

    if mode == "basic":

        vf = (
            "hflip,"
            "scale=iw*1.01:ih*1.01,"
            "crop=iw/1.01:ih/1.01"
        )

        audio_filter = "atempo=1.02"

        command = [
            "ffmpeg",
            "-y",
            "-i", input_file,
            "-vf", vf,
            "-filter:a", audio_filter,
            "-map_metadata", "-1",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-c:a", "aac",
            output_file
        ]

    elif mode == "heavy":

        vf = (
            "hflip,"
            "scale=iw*1.03:ih*1.03,"
            "crop=iw/1.03:ih/1.03"
        )

        audio_filter = (
            "asetrate=44100*1.04,"
            "aresample=44100,"
            "atempo=0.96"
        )

        command = [
            "ffmpeg",
            "-y",
            "-i", input_file,
            "-vf", vf,
            "-r", "30",
            "-filter:a", audio_filter,
            "-map_metadata", "-1",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "25",
            "-c:a", "aac",
            output_file
        ]

    else:
        os.remove(input_file)
        return jsonify({"error": "Invalid transform mode"}), 400

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            os.remove(input_file)

            return jsonify({
                "error": "FFmpeg processing failed",
                "details": result.stderr[-2000:]
            }), 500

        if not os.path.exists(output_file):
            os.remove(input_file)

            return jsonify({
                "error": "Output file was not created"
            }), 500

        os.remove(input_file)

        return send_file(
            output_file,
            as_attachment=True,
            download_name="FixMyTube_Transformed.mp4",
            mimetype="video/mp4"
        )

    except Exception as e:

        if os.path.exists(input_file):
            os.remove(input_file)

        if os.path.exists(output_file):
            os.remove(output_file)

        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
)
