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
let currentJobId = null;


// =====================================
// FORMAT FILE SIZE
// =====================================

function formatBytes(bytes) {

    if (bytes === 0) {
        return "0 Bytes";
    }

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


// =====================================
// VIDEO SELECT
// =====================================

videoInput.addEventListener(
    "change",
    function () {

        const file = this.files[0];

        if (!file) {

            selectedFile = null;

            fileInfo.classList.add(
                "hidden"
            );

            return;
        }


        if (
            !file.type ||
            !file.type.startsWith("video/")
        ) {

            alert(
                "Please select a valid video file."
            );

            this.value = "";

            selectedFile = null;

            fileInfo.classList.add(
                "hidden"
            );

            return;
        }


        // 2 GB
        const maxSize =
            2 * 1024 * 1024 * 1024;


        if (file.size > maxSize) {

            alert(
                "Video 2 GB se badi hai."
            );

            this.value = "";

            selectedFile = null;

            fileInfo.classList.add(
                "hidden"
            );

            return;
        }


        selectedFile = file;


        fileInfo.innerHTML = `
            <strong>✓ Video Selected</strong><br>
            ${file.name}<br>
            ${formatBytes(file.size)}
        `;


        fileInfo.classList.remove(
            "hidden"
        );


        downloadBtn.classList.add(
            "hidden"
        );
    }
);


// =====================================
// MODE
// =====================================

const modeCards =
    document.querySelectorAll(
        ".mode-card"
    );


modeCards.forEach(
    card => {

        card.addEventListener(
            "click",
            function () {

                modeCards.forEach(
                    item => {

                        item.classList.remove(
                            "active"
                        );
                    }
                );


                this.classList.add(
                    "active"
                );


                selectedMode =
                    this.dataset.mode;
            }
        );
    }
);


// =====================================
// PITCH
// =====================================

pitch.addEventListener(
    "input",
    function () {

        pitchValue.textContent =
            Number(this.value)
                .toFixed(2)
            + "x";
    }
);


// =====================================
// TEMPO
// =====================================

tempo.addEventListener(
    "input",
    function () {

        tempoValue.textContent =
            Number(this.value)
                .toFixed(2)
            + "x";
    }
);


// =====================================
// PROCESS VIDEO
// =====================================

processBtn.addEventListener(
    "click",
    async function () {

        if (!selectedFile) {

            alert(
                "Pehle video select karo."
            );

            return;
        }


        processBtn.disabled = true;

        processBtn.innerHTML =
            "⏳ UPLOADING...";


        progressCard.classList.remove(
            "hidden"
        );


        downloadBtn.classList.add(
            "hidden"
        );


        setProgress(
            0,
            "Preparing...",
            "Video processing ke liye prepare ho rahi hai..."
        );


        const formData =
            new FormData();


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
            document.getElementById(
                "mirror"
            ).checked
                ? "1"
                : "0"
        );


        formData.append(
            "crop",
            document.getElementById(
                "crop"
            ).checked
                ? "1"
                : "0"
        );


        formData.append(
            "metadata",
            document.getElementById(
                "metadata"
            ).checked
                ? "1"
                : "0"
        );


        formData.append(
            "fps",
            document.getElementById(
                "fps"
            ).value
        );


        formData.append(
            "resolution",
            document.getElementById(
                "resolution"
            ).value
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

            // =================================
            // UPLOAD WITH REAL PROGRESS
            // =================================

            const result =
                await uploadVideo(
                    formData
                );


            if (
                !result ||
                !result.job_id
            ) {

                throw new Error(
                    "Server ne job ID nahi diya."
                );
            }


            currentJobId =
                result.job_id;


            // =================================
            // PROCESSING
            // =================================

            processBtn.innerHTML =
                "⚙️ PROCESSING...";


            setProgress(
                10,
                "Processing...",
                "FFmpeg video process kar raha hai..."
            );


            await monitorJob(
                currentJobId
            );


        } catch (error) {

            console.error(
                error
            );


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

            processBtn.disabled =
                false;


            processBtn.innerHTML =
                "<span>✨</span> PROCESS VIDEO";
        }
    }
);


// =====================================
// UPLOAD FUNCTION
// =====================================

function uploadVideo(formData) {

    return new Promise(
        (resolve, reject) => {

            const xhr =
                new XMLHttpRequest();


            xhr.open(
                "POST",
                "/process",
                true
            );


            xhr.upload.onprogress =
                function (event) {

                    if (!event.lengthComputable) {
                        return;
                    }


                    const percent =
                        Math.round(
                            (
                                event.loaded /
                                event.total
                            ) * 10
                        );


                    setProgress(
                        percent,
                        "Uploading...",
                        "Video server par upload ho rahi hai..."
                    );
                };


            xhr.onload =
                function () {

                    if (
                        xhr.status >= 200 &&
                        xhr.status < 300
                    ) {

                        try {

                            const data =
                                JSON.parse(
                                    xhr.responseText
                                );


                            resolve(
                                data
                            );

                        } catch (error) {

                            reject(
                                new Error(
                                    "Server response invalid hai."
                                )
                            );
                        }

                    } else {

                        let message =
                            "Video upload nahi ho saki.";


                        try {

                            const data =
                                JSON.parse(
                                    xhr.responseText
                                );


                            if (data.error) {
                                message =
                                    data.error;
                            }

                        } catch (error) {
                            // Ignore
                        }


                        reject(
                            new Error(
                                message
                            )
                        );
                    }
                };


            xhr.onerror =
                function () {

                    reject(
                        new Error(
                            "Network error: upload failed."
                        )
                    );
                };


            xhr.ontimeout =
                function () {

                    reject(
                        new Error(
                            "Upload timeout ho gaya."
                        )
                    );
                };


            xhr.timeout =
                0;


            xhr.send(
                formData
            );
        }
    );
}


// =====================================
// MONITOR JOB
// =====================================

async function monitorJob(
    jobId
) {

    while (true) {

        const response =
            await fetch(
                "/status/" + jobId,
                {
                    cache: "no-store"
                }
            );


        if (!response.ok) {

            throw new Error(
                "Processing status nahi mil raha."
            );
        }


        const data =
            await response.json();


        const progress =
            Number(
                data.progress || 0
            );


        if (
            data.status ===
            "queued"
        ) {

            setProgress(
                Math.max(
                    10,
                    progress
                ),
                "Queued...",
                "Video processing queue mein hai..."
            );
        }


        else if (
            data.status ===
            "processing"
        ) {

            setProgress(
                Math.min(
                    99,
                    Math.max(
                        10,
                        progress
                    )
                ),
                "Processing...",
                "FFmpeg video process kar raha hai..."
            );
        }


        else if (
            data.status ===
            "complete"
        ) {

            setProgress(
                100,
                "Complete!",
                "Video successfully process ho gayi."
            );


            downloadBtn.href =
                "/download/" + jobId;


            downloadBtn.download =
                "FixMyTube_Transformed.mp4";


            downloadBtn.classList.remove(
                "hidden"
            );


            return;
        }


        else if (
            data.status ===
            "error"
        ) {

            throw new Error(
                data.error ||
                "FFmpeg processing failed."
            );
        }


        await sleep(
            1500
        );
    }
}


// =====================================
// SLEEP
// =====================================

function sleep(
    milliseconds
) {

    return new Promise(
        resolve =>
            setTimeout(
                resolve,
                milliseconds
            )
    );
}


// =====================================
// PROGRESS
// =====================================

function setProgress(
    percent,
    title,
    message
) {

    percent =
        Math.max(
            0,
            Math.min(
                100,
                percent
            )
        );


    progressFill.style.width =
        percent + "%";


    progressPercent.textContent =
        Math.round(
            percent
        ) + "%";


    progressText.textContent =
        title;


    statusText.textContent =
        message;
}
