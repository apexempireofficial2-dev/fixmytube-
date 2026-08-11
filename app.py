import os
import uuid
import threading
import subprocess

from flask import (
    Flask,
    request,
    jsonify,
    send_file,
    render_template
)

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Target: 2 GB
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024

app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE


# ==========================================
# JOB STORAGE
# ==========================================

jobs = {}


# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():
    return render_template("index.html")


# ==========================================
# HEALTH
# ==========================================

@app.route("/health")
def health():

    return jsonify({
        "status": "ok",
        "service": "FixMyTube"
    })


# ==========================================
# 2 GB ERROR
# ==========================================

@app.errorhandler(413)
def too_large(error):

    return jsonify({
        "error": "Video 2 GB se badi hai."
    }), 413


# ==========================================
# SAFE FLOAT
# ==========================================

def safe_float(
    value,
    default,
    minimum,
    maximum
):

    try:

        value = float(value)

        return max(
            minimum,
            min(maximum, value)
        )

    except:

        return default


# ==========================================
# SAFE INT
# ==========================================

def safe_int(
    value,
    default,
    allowed
):

    try:

        value = int(value)

        if value in allowed:
            return value

        return default

    except:

        return default


# ==========================================
# VIDEO FILTER
# ==========================================

def build_video_filter(
    mirror,
    crop,
    resolution
):

    filters = []

    # Mirror
    if mirror:

        filters.append(
            "hflip"
        )

    # Deep pixel crop
    if crop:

        filters.append(
            "scale=iw*1.03:ih*1.03,"
            "crop=iw/1.03:ih/1.03"
        )

    # Resolution
    resolution_map = {

        "1080":
            "scale=-2:1080",

        "720":
            "scale=-2:720",

        "480":
            "scale=-2:480",

        "360":
            "scale=-2:360"
    }

    if resolution in resolution_map:

        filters.append(
            resolution_map[resolution]
        )

    if not filters:

        return None

    return ",".join(filters)


# ==========================================
# AUDIO FILTER
# ==========================================

def build_audio_filter(
    pitch,
    tempo
):

    filters = []

    # Pitch
    if abs(pitch - 1.0) > 0.001:

        filters.append(
            f"asetrate=44100*{pitch:.4f},"
            "aresample=44100"
        )

    # Tempo
    if abs(tempo - 1.0) > 0.001:

        filters.append(
            f"atempo={tempo:.4f}"
        )

    if not filters:

        return None

    return ",".join(filters)


# ==========================================
# BACKGROUND PROCESS
# ==========================================

def process_job(
    job_id,
    input_file,
    output_file,
    settings
):

    try:

        jobs[job_id]["status"] = "processing"
        jobs[job_id]["progress"] = 5

        mode = settings["mode"]

        mirror = settings["mirror"]
        crop = settings["crop"]
        metadata = settings["metadata"]

        fps_value = settings["fps"]
        resolution = settings["resolution"]

        pitch = settings["pitch"]
        tempo = settings["tempo"]


        # ==================================
        # HEAVY MODE
        # ==================================

        if mode == "heavy":

            mirror = True
            crop = True

            if abs(pitch - 1.0) < 0.001:
                pitch = 1.04

            if abs(tempo - 1.0) < 0.001:
                tempo = 0.96

            fps_value = "30"


        # ==================================
        # FILTERS
        # ==================================

        video_filter = build_video_filter(
            mirror,
            crop,
            resolution
        )

        audio_filter = build_audio_filter(
            pitch,
            tempo
        )


        # ==================================
        # FFMPEG COMMAND
        # ==================================

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
        if fps_value != "source":

            fps = safe_int(
                fps_value,
                30,
                [24, 30, 60]
            )

            command.extend([
                "-r",
                str(fps)
            ])


        # Audio
        if audio_filter:

            command.extend([
                "-af",
                audio_filter
            ])


        # Metadata removal
        if metadata:

            command.extend([
                "-map_metadata",
                "-1"
            ])


        # ==================================
        # ENCODER
        # ==================================

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


        jobs[job_id]["progress"] = 10


        # ==================================
        # START FFMPEG
        # ==================================

        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )


        # ==================================
        # READ FFMPEG LOG
        # ==================================

        for line in process.stderr:

            line = line.strip()

            if "frame=" in line:

                # Processing is active.
                # Exact duration requires ffprobe,
                # so keep UI progress moving.

                current = jobs[job_id].get(
                    "progress",
                    10
                )

                if current < 95:

                    jobs[job_id]["progress"] = (
                        current + 1
                    )


        return_code = process.wait()


        # ==================================
        # FAILED
        # ==================================

        if return_code != 0:

            jobs[job_id]["status"] = "error"

            jobs[job_id]["error"] = (
                "FFmpeg video processing failed."
            )

            return


        # ==================================
        # SUCCESS
        # ==================================

        if not os.path.exists(
            output_file
        ):

            jobs[job_id]["status"] = "error"

            jobs[job_id]["error"] = (
                "Output video create nahi hui."
            )

            return


        jobs[job_id]["progress"] = 100

        jobs[job_id]["status"] = "complete"


    except Exception as e:

        jobs[job_id]["status"] = "error"

        jobs[job_id]["error"] = str(e)


# ==========================================
# CREATE JOB
# ==========================================

@app.route(
    "/process",
    methods=["POST"]
)
def process_video():

    if "video" not in request.files:

        return jsonify({
            "error": "Video file missing."
        }), 400


    video = request.files["video"]


    if not video.filename:

        return jsonify({
            "error": "Invalid video."
        }), 400


    job_id = uuid.uuid4().hex


    input_file = os.path.join(
        UPLOAD_DIR,
        job_id + "_input"
    )


    output_file = os.path.join(
        OUTPUT_DIR,
        job_id + "_output.mp4"
    )


    try:

        # ==================================
        # SAVE
        # ==================================

        video.save(
            input_file
        )


        if not os.path.exists(
            input_file
        ):

            return jsonify({
                "error": "Upload failed."
            }), 400


        file_size = os.path.getsize(
            input_file
        )


        if file_size > MAX_FILE_SIZE:

            os.remove(
                input_file
            )

            return jsonify({
                "error": "Video 2 GB se badi hai."
            }), 413


        # ==================================
        # SETTINGS
        # ==================================

        mode = request.form.get(
            "mode",
            "basic"
        )

        if mode not in (
            "basic",
            "heavy"
        ):

            mode = "basic"


        mirror = (
            request.form.get(
                "mirror",
                "1"
            ) == "1"
        )


        crop = (
            request.form.get(
                "crop",
                "1"
            ) == "1"
        )


        metadata = (
            request.form.get(
                "metadata",
                "1"
            ) == "1"
        )


        fps = request.form.get(
            "fps",
            "source"
        )


        resolution = request.form.get(
            "resolution",
            "source"
        )


        pitch = safe_float(
            request.form.get(
                "pitch"
            ),
            1.0,
            0.90,
            1.10
        )


        tempo = safe_float(
            request.form.get(
                "tempo"
            ),
            1.0,
            0.90,
            1.10
        )


        settings = {

            "mode":
                mode,

            "mirror":
                mirror,

            "crop":
                crop,

            "metadata":
                metadata,

            "fps":
                fps,

            "resolution":
                resolution,

            "pitch":
                pitch,

            "tempo":
                tempo
        }


        # ==================================
        # CREATE JOB
        # ==================================

        jobs[job_id] = {

            "status":
                "queued",

            "progress":
                0,

            "error":
                None
        }


        # ==================================
        # BACKGROUND THREAD
        # ==================================

        thread = threading.Thread(

            target=process_job,

            args=(
                job_id,
                input_file,
                output_file,
                settings
            ),

            daemon=True
        )

        thread.start()


        return jsonify({

            "success":
                True,

            "job_id":
                job_id
        })


    except Exception as e:

        if os.path.exists(
            input_file
        ):

            os.remove(
                input_file
            )


        return jsonify({
            "error": str(e)
        }), 500


# ==========================================
# JOB STATUS
# ==========================================

@app.route(
    "/status/<job_id>"
)
def job_status(job_id):

    job = jobs.get(
        job_id
    )


    if not job:

        return jsonify({
            "error": "Job not found."
        }), 404


    return jsonify({

        "status":
            job["status"],

        "progress":
            job["progress"],

        "error":
            job.get("error")
    })


# ==========================================
# DOWNLOAD
# ==========================================

@app.route(
    "/download/<job_id>"
)
def download(job_id):

    job = jobs.get(
        job_id
    )


    if not job:

        return jsonify({
            "error": "Job not found."
        }), 404


    if job["status"] != "complete":

        return jsonify({
            "error": "Video abhi ready nahi hai."
        }), 400


    output_file = os.path.join(
        OUTPUT_DIR,
        job_id + "_output.mp4"
    )


    if not os.path.exists(
        output_file
    ):

        return jsonify({
            "error": "Output file nahi mili."
        }), 404


    return send_file(

        output_file,

        as_attachment=True,

        download_name=
            "FixMyTube_Transformed.mp4",

        mimetype=
            "video/mp4"
    )


# ==========================================
# RUN
# ==========================================

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
