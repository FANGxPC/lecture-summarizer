document.addEventListener("DOMContentLoaded", () => {
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");

    const uploadSection = document.getElementById("upload-section");
    const processingSection = document.getElementById("processing-section");
    const resultsSection = document.getElementById("results-section");

    const statusTitle = document.getElementById("status-title");
    const statusDesc = document.getElementById("status-desc");

    const resultSummary = document.getElementById("result-summary");
    const resultTopics = document.getElementById("result-topics");
    const resultTranscript = document.getElementById("result-transcript");
    const summaryWordCount = document.getElementById("summary-word-count");
    const transcriptWordCount = document.getElementById("transcript-word-count");
    const topicsCount = document.getElementById("topics-count");
    const transcriptCharCount = document.getElementById("transcript-char-count");

    const btnNew = document.getElementById("btn-new");
    const btnCopy = document.getElementById("btn-copy");

    let currentTaskId = null;
    let pollInterval = null;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('border-brand-500', 'bg-brand-50', 'dark:bg-gray-800/80');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('border-brand-500', 'bg-brand-50', 'dark:bg-gray-800/80');
        }, false);
    });

    dropZone.addEventListener('drop', handleDrop, false);
    fileInput.addEventListener('change', handleFileSelect, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            uploadFile(files[0]);
        }
    }

    function handleFileSelect(e) {
        const files = e.target.files;
        if (files.length > 0) {
            uploadFile(files[0]);
        }
    }

    async function uploadFile(file) {
        const validTypes = ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/x-m4a', 'audio/mp4', 'audio/m4a', 'video/mp4'];
        const ext = file.name.split('.').pop().toLowerCase();
        if (!['mp3', 'wav', 'm4a'].includes(ext)) {
            alert('Please upload an MP3, WAV, or M4A file.');
            return;
        }
        uploadSection.classList.remove('animate-fade-in-up', 'animate-fade-in-up-delay-1');
        uploadSection.classList.add('opacity-0', '-translate-y-4');
        setTimeout(() => {
            uploadSection.classList.add('hidden');
            processingSection.classList.remove('hidden');
            processingSection.classList.add('flex');
            void processingSection.offsetWidth;
            processingSection.classList.remove('opacity-0', 'scale-95');
            processingSection.classList.add('opacity-100', 'scale-100', 'transition-all', 'duration-500');
        }, 300);

        statusTitle.textContent = "Uploading File...";
        statusDesc.textContent = `Sending ${file.name} to server`;

        const formData = new FormData();
        formData.append("file", file);

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || "Upload failed");
            }

            const data = await response.json();
            currentTaskId = data.task_id;

            startPolling();

        } catch (error) {
            alert(`Error: ${error.message}`);
            resetUI();
        }
    }

    function startPolling() {
        if (pollInterval) clearInterval(pollInterval);

        const updateStep = (stepId) => {
            const steps = ['uploading', 'transcribing', 'summarizing', 'classifying'];
            let found = false;
            steps.forEach(s => {
                const el = document.getElementById(`step-${s}`);
                const iconContainer = el.querySelector('div');
                const span = el.querySelector('span');

                if (s === stepId) {
                    found = true;
                    el.classList.remove('opacity-50');
                    iconContainer.className = "w-6 h-6 rounded-full border-2 border-brand-500 flex items-center justify-center";
                    iconContainer.innerHTML = '<div class="w-3 h-3 bg-brand-500 rounded-full animate-ping"></div>';
                    span.classList.add('text-brand-600', 'dark:text-brand-400', 'animate-pulse');
                } else if (!found) {
                    el.classList.remove('opacity-50');
                    iconContainer.className = "w-6 h-6 rounded-full border-2 border-brand-500 flex items-center justify-center bg-brand-500 text-white shadow-[0_0_10px_rgba(99,102,241,0.5)]";
                    iconContainer.innerHTML = '<i class="ph ph-check text-xs"></i>';
                    span.classList.remove('text-brand-600', 'dark:text-brand-400', 'animate-pulse');
                    span.classList.add('text-gray-900', 'dark:text-gray-100');
                } else {
                    el.classList.add('opacity-50');
                    iconContainer.className = "w-6 h-6 rounded-full border-2 border-gray-300 dark:border-gray-600 flex items-center justify-center";
                    iconContainer.innerHTML = '';
                    span.classList.remove('text-brand-600', 'dark:text-brand-400', 'animate-pulse', 'text-gray-900', 'dark:text-gray-100');
                }
            });
        };

        const checkStatus = async () => {
            try {
                const response = await fetch(`/api/status/${currentTaskId}`);
                if (!response.ok) throw new Error("Status check failed");
                const data = await response.json();

                statusTitle.textContent = "Analyzing Audio...";
                statusDesc.textContent = `Current step: ${data.status}`;

                if (data.status === 'processing') {
                    updateStep('transcribing');
                } else if (data.status === 'transcribing') {
                    updateStep('transcribing');
                } else if (data.status === 'summarizing') {
                    updateStep('summarizing');
                } else if (data.status === 'classifying') {
                    updateStep('classifying');
                } else if (data.status === 'completed') {
                    clearInterval(pollInterval);
                    showResults(data);
                } else if (data.status === 'failed') {
                    clearInterval(pollInterval);
                    alert(`Processing failed: ${data.transcript || 'Unknown error'}`);
                    resetUI();
                }

            } catch (error) {
                console.error(error);
            }
        };

        checkStatus();
        pollInterval = setInterval(checkStatus, 2500);
    }

    function showResults(data) {
        processingSection.classList.remove('opacity-100', 'scale-100');
        processingSection.classList.add('opacity-0', 'scale-95');

        setTimeout(() => {
            processingSection.classList.remove('flex');
            processingSection.classList.add('hidden');

            resultSummary.textContent = data.summary || "No summary available.";
            resultTranscript.textContent = data.transcript || "No transcript available.";
            const summaryWords = (resultSummary.textContent.trim().match(/\S+/g) || []).length;
            const transcriptWords = (resultTranscript.textContent.trim().match(/\S+/g) || []).length;
            summaryWordCount.textContent = summaryWords.toLocaleString();
            transcriptWordCount.textContent = transcriptWords.toLocaleString();
            transcriptCharCount.textContent = resultTranscript.textContent.length.toLocaleString();
        }, 300);

        resultTopics.innerHTML = '';
        if (data.topics && data.topics.length > 0) {
            topicsCount.textContent = data.topics.length.toLocaleString();
            data.topics.forEach(topic => {
                const span = document.createElement('span');
                span.className = "px-3 py-1 bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 rounded-full text-sm font-medium border border-purple-200 dark:border-purple-800/50";
                span.textContent = topic;
                resultTopics.appendChild(span);
            });
        } else {
            topicsCount.textContent = "0";
            resultTopics.textContent = "No topics identified.";
            resultTopics.className = "text-gray-500 text-sm";
        }

        resultsSection.classList.remove('hidden');
        setTimeout(() => {
            resultsSection.classList.remove('opacity-0', 'translate-y-8');
        }, 50);
    }

    function resetUI() {
        clearInterval(pollInterval);
        currentTaskId = null;
        fileInput.value = '';
        summaryWordCount.textContent = "0";
        transcriptWordCount.textContent = "0";
        topicsCount.textContent = "0";
        transcriptCharCount.textContent = "0";

        resultsSection.classList.add('opacity-0', 'translate-y-8');
        processingSection.classList.remove('opacity-100', 'scale-100');
        processingSection.classList.add('opacity-0', 'scale-95');

        setTimeout(() => {
            resultsSection.classList.add('hidden');
            processingSection.classList.add('hidden');
            processingSection.classList.remove('flex');

            uploadSection.classList.remove('hidden');
            void uploadSection.offsetWidth;
            uploadSection.classList.remove('opacity-0', '-translate-y-4');
            uploadSection.classList.add('animate-fade-in-up');
        }, 500);
    }

    btnNew.addEventListener('click', resetUI);

    btnCopy.addEventListener('click', () => {
        const text = resultTranscript.textContent;
        navigator.clipboard.writeText(text).then(() => {
            const originalHTML = btnCopy.innerHTML;
            btnCopy.innerHTML = '<i class="ph ph-check text-xl text-green-500"></i>';
            setTimeout(() => {
                btnCopy.innerHTML = originalHTML;
            }, 2000);
        });
    });
});
