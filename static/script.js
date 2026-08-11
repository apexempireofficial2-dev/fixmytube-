const videoInput = document.getElementById("videoInput");
const fileInfo = document.getElementById("fileInfo");

const processBtn = document.getElementById("processBtn");
const progressCard = document.getElementById("progressCard");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");
const progressPercent = document.getElementById("progressPercent");
const statusText = document.getElementById("statusText");
const downloadBtn = document.getElementById("downloadBtn");

const pitch = document.getElementById("pitch");
const tempo = document.getElementById("tempo");

const pitchValue = document.getElementById("pitchValue");
const tempoValue = document.getElementById("tempoValue");

let selectedMode = "basic";
let selectedFile = null;


// ============================
// FILE SIZE
// ============================

function formatBytes(bytes) {
    if (bytes === 0) return "0 Bytes";

    const units = [
        "Bytes",
        "KB",
        "MB",
        "GB"
    ];

    const index = Math.floor(
        Math.log(bytes) / Math.log(1024)
    );

    return (
        (bytes / Math.pow(1024, index)).toFixed(2)
        + " "
        + units[index]
    );
}


// ============================
// VIDEO SELECT
// ============================

videoInput.addEventListener("change", function () {

    const file = this.files[0];

    if (!file) {
        selectedFile = null;
        fileInfo.classList.add("hidden");
        return;
    }

    if (!file.type.startsWith("video/")) {

        alert("Please select a valid video file.");

        this.value = "";
        selectedFile = null;

        fileInfo.classList.add("hidden");

        return;
    }


    // 2 GB client-side check
    const maxSize = 2 * 1024 * 1024 * 1024;

    if (file.size > maxSize) {

        alert("Video 2 GB se badi hai.");

        this.value = "";
        selectedFile = null;

        fileInfo.classList.add("hidden");

        return;
    }


    selectedFile = file;

    fileInfo.innerHTML = `
        <strong>✓ Video Selected</strong><br>
        ${file.name}<br>
        ${formatBytes(file.size)}
    `;

    fileInfo.classList.remove("hidden");

    downloadBtn.classList.add("hidden");
});


// ============================
// TRANSFORMATION MODE
// ============================

const modeCards = document.querySelectorAll(".mode-card");

modeCards.forEach(card => {

    card.addEventListener("click", function () {

        modeCards.forEach(item => {
            item.classList.remove("active");
        });

        this.classList.add("active");

        selectedMode = this.dataset.mode;
    });
});


// ============================
// AUDIO PITCH
// ============================

pitch.addEventListener("input", function () {

    pitchValue.textContent =
        Number(this.value).toFixed(2) + "x";
});


// ============================
// AUDIO TEMPO
// ============================

tempo.addEventListener("input", function () {

    tempoValue.textContent =
        Number(this.value).toFixed(2) + "x";
});


// ============================
// PROCESS VIDEO
// ============================

processBtn.addEventListener("click", async function () {

    if (!selectedFile) {

        alert("Pehle video select karo.");

        return;
    }


    processBtn.disabled = true;

    processBtn.innerHTML =
        "⏳ PROCESSING...";


    progressCard.classList.remove("hidden");

    downloadBtn.classList.add("hidden");

    setProgress(
        5,
        "Preparing...",
        "Video processing ke liye prepare ho rahi hai..."
    );


    const formData = new FormData();

    formData.append(
        "video",
        selectedFile
    );

    formData.append(
        "mode",
        selectedMode
    );

    formData.append(
        "mirror",
        document.getElementById("mirror").checked
            ? "1"
            : "0"
    );

    formData.append(
        "crop",
        document.getElementById("crop").checked
            ? "1"
            : "0"
    );

    formData.append(
        "metadata",
        document.getElementById("metadata").checked
            ? "1"
            : "0"
    );

    formData.append(
        "fps",
        document.getElementById("fps").value
    );

    formData.append(
        "resolution",
        document.getElementById("resolution").value
    );

    formData.append(
        "pitch",
        pitch.value
    );

    formData.append(
        "tempo",
        tempo.value
    );


    try {

        setProgress(
            10,
            "Uploading...",
            "Video server par upload ho rahi hai..."
        );


        const response = await fetch(
            "/process",
            {
                method: "POST",
                body: formData
            }
        );


        setProgress(
            70,
            "Processing...",
            "FFmpeg video process kar raha hai..."
        );


        if (!response.ok) {

            let errorMessage =
                "Video process nahi ho saki.";

            try {

                const errorData =
                    await response.json();

                if (errorData.error) {
                    errorMessage =
                        errorData.error;
                }

            } catch (e) {
                // Ignore JSON parsing error
            }

            throw new Error(errorMessage);
        }


        setProgress(
            95,
            "Finalizing...",
            "Processed video prepare ho rahi hai..."
        );


        const blob =
            await response.blob();


        const downloadUrl =
            URL.createObjectURL(blob);


        downloadBtn.href =
            downloadUrl;

        downloadBtn.download =
            "FixMyTube_Transformed.mp4";


        downloadBtn.classList.remove(
            "hidden"
        );


        setProgress(
            100,
            "Complete!",
            "Video successfully process ho gayi."
        );


    } catch (error) {

        console.error(error);

        setProgress(
            0,
            "Error",
            error.message ||
            "Processing mein error aa gayi."
        );

        alert(
            error.message ||
            "Video process nahi ho saki."
        );

    } finally {

        processBtn.disabled = false;

        processBtn.innerHTML =
            "<span>✨</span> PROCESS VIDEO";
    }
});


// ============================
// PROGRESS HELPER
// ============================

function setProgress(
    percent,
    title,
    message
) {

    progressFill.style.width =
        percent + "%";

    progressPercent.textContent =
        percent + "%";

    progressText.textContent =
        title;

    statusText.textContent =
        message;
                          }
