import os
import uuid
import subprocess
import threading
import time

from flask import Flask, request, jsonify, send_file, render_template

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# 2 GB MAX FILE
# ==========================================

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024

app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE


# ==========================================
# JOB STORAGE
# ==========================================

jobs = {}

jobs_lock = threading.Lock()


# ==========================================
# HELPERS
# ==========================================

def safe_float(value, default, minimum, maximum):
    try:
        value = float(value)
        return max(minimum, min(maximum, value))
    except (TypeError, ValueError):
        return default


def safe_int(value, default, allowed):
    try:
        value = int(value)

        if value in allowed:
            return value

        return default

    except (TypeError, ValueError):
        return default


def update_job(job_id, **data):

    with jobs_lock:

        if job_id in jobs:
            jobs[job_id].update(data)


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
        filters.append("hflip")

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

    if filters:
        return ",".join(filters)

    return "null"


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

    if filters:
        return ",".join(filters)

    return "anull"


# ==========================================
# FFMPEG WORKER
# ==========================================

def process_job(
    job_id,
    input_file,
    output_file,
    settings
):

    try:

        update_job(
            job_id,
            status="processing",
            progress=10,
            message="FFmpeg processing started..."
        )

        mode = settings["mode"]

        mirror = settings["mirror"]

        crop = settings["crop"]

        remove_metadata = settings["metadata"]

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


        # ==================================
        # ENCODING
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

            "-progress",
            "pipe:1",

            "-nostats",

            output_file
        ])


        # ==================================
        # RUN FFMPEG
        # ==================================

        process = subprocess.Popen(

            command,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            text=True,

            bufsize=1
        )


        duration = None


        # ==================================
        # READ PROGRESS
        # ==================================

        while True:

            line = process.stdout.readline()

            if not line:

                if process.poll() is not None:
                    break

                time.sleep(0.05)

                continue


            line = line.strip()


            # Duration
            if line.startswith(
                "out_time_ms="
            ):

                try:

                    out_time_ms = int(
                        line.split(
                            "=",
                            1
                        )[1]
                    )

                    if duration:

                        current_seconds = (
                            out_time_ms / 1000000
                        )

                        percent = (
                            current_seconds /
                            duration
                        ) * 100

                        percent = max(
                            10,
                            min(
                                99,
                                percent
                            )
                        )

                        update_job(

                            job_id,

                            progress=round(
                                percent,
                                1
                            ),

                            message=
                                "FFmpeg video process kar raha hai..."
                        )

                except Exception:
                    pass


            # End
            if line == "progress=end":
                break


        # ==================================
        # WAIT
        # ==================================

        return_code = process.wait()


        # ==================================
        # READ ERROR
        # ==================================

        stderr_output = ""

        try:

            stderr_output = (
                process.stderr.read()
            )

        except Exception:
            pass


        # ==================================
        # ERROR
        # ==================================

        if return_code != 0:

            update_job(

                job_id,

                status="error",

                progress=0,

                error=
                    "FFmpeg processing failed."
            )

            print(
                "FFmpeg ERROR:",
                stderr_output[-5000:]
            )

            return


        # ==================================
        # OUTPUT CHECK
        # ==================================

        if not os.path.exists(
            output_file
        ):

            update_job(

                job_id,

                status="error",

                progress=0,

                error=
                    "Processed video create nahi hui."
            )

            return


        # ==================================
        # COMPLETE
        # ==================================

        update_job(

            job_id,

            status="complete",

            progress=100,

            message=
                "Video successfully process ho gayi."
        )


    except Exception as e:

        print(
            "JOB ERROR:",
            str(e)
        )

        update_job(

            job_id,

            status="error",

            progress=0,

            error=str(e)
        )


# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


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
# PROCESS
# ==========================================

@app.route(
    "/process",
    methods=["POST"]
)
def process_video():

    if "video" not in request.files:

        return jsonify({

            "error":
                "Video file missing."
        }), 400


    video = request.files["video"]


    if not video.filename:

        return jsonify({

            "error":
                "Invalid video filename."
        }), 400


    # ======================================
    # JOB ID
    # ======================================

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

        # ==================================
        # SAVE FILE
        # ==================================

        video.save(
            input_file
        )


        if not os.path.exists(
            input_file
        ):

            return jsonify({

                "error":
                    "Upload failed."
            }), 400


        # ==================================
        # SIZE CHECK
        # ==================================

        if (
            os.path.getsize(
                input_file
            )
            > MAX_FILE_SIZE
        ):

            os.remove(
                input_file
            )

            return jsonify({

                "error":
                    "Video 2 GB se badi hai."
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


        # ==================================
        # CREATE JOB
        # ==================================

        with jobs_lock:

            jobs[job_id] = {

                "status":
                    "queued",

                "progress":
                    5,

                "message":
                    "Video upload complete.",

                "error":
                    None
            }


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


        # ==================================
        # RETURN JOB ID
        # ==================================

        return jsonify({

            "success":
                True,

            "job_id":
                job_id,

            "status":
                "queued"
        })


    except Exception as e:

        if os.path.exists(
            input_file
        ):

            try:

                os.remove(
                    input_file
                )

            except OSError:
                pass


        return jsonify({

            "error":
                str(e)
        }), 500


# ==========================================
# STATUS
# ==========================================

@app.route(
    "/status/<job_id>"
)
def job_status(job_id):

    with jobs_lock:

        job = jobs.get(
            job_id
        )


    if not job:

        return jsonify({

            "error":
                "Job not found."
        }), 404


    return jsonify({

        "status":
            job.get(
                "status",
                "unknown"
            ),

        "progress":
            job.get(
                "progress",
                0
            ),

        "message":
            job.get(
                "message",
                ""
            ),

        "error":
            job.get(
                "error"
            )
    })


# ==========================================
# DOWNLOAD
# ==========================================

@app.route(
    "/download/<job_id>"
)
def download_file(job_id):

    with jobs_lock:

        job = jobs.get(
            job_id
        )


    if not job:

        return jsonify({

            "error":
                "Job not found."
        }), 404


    if job.get(
        "status"
    ) != "complete":

        return jsonify({

            "error":
                "Video abhi ready nahi hai."
        }), 400


    output_file = os.path.join(

        OUTPUT_DIR,

        f"{job_id}_output.mp4"
    )


    if not os.path.exists(
        output_file
    ):

        return jsonify({

            "error":
                "Output file nahi mili."
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
# ERROR 413
# ==========================================

@app.errorhandler(413)
def too_large(error):

    return jsonify({

        "error":
            "Video 2 GB se badi hai."
    }), 413


# ==========================================
# CLEANUP OLD JOBS
# ==========================================

def cleanup_old_files():

    while True:

        time.sleep(
            3600
        )

        try:

            now = time.time()


            for folder in [
                UPLOAD_DIR,
                OUTPUT_DIR
            ]:

                for filename in os.listdir(
                    folder
                ):

                    path = os.path.join(
                        folder,
                        filename
                    )


                    if not os.path.isfile(
                        path
                    ):
                        continue


                    try:

                        age = (
                            now -
                            os.path.getmtime(
                                path
                            )
                        )


                        # 2 hours
                        if age > 7200:

                            os.remove(
                                path
                            )

                    except OSError:
                        pass


        except Exception as e:

            print(
                "Cleanup error:",
                e
            )


# ==========================================
# START CLEANUP THREAD
# ==========================================

cleanup_thread = threading.Thread(

    target=cleanup_old_files,

    daemon=True
)

cleanup_thread.start()


# ==========================================
# START SERVER
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
