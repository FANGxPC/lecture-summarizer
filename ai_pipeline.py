import os
os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"
import whisper
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
from database import update_task_status
import threading
import torch
whisper_model = None
summarizer_tokenizer = None
summarizer_model = None
classifier = None
pipeline_has_cuda = False

CANDIDATE_LABELS = [
    "Technology", "Science", "History", "Business", "Health",
    "Education", "Entertainment", "Politics", "Art", "Sports"
]

def load_models():
    """Lazily load model components once and reuse them across requests."""
    global whisper_model, summarizer_tokenizer, summarizer_model, classifier, pipeline_has_cuda
    has_cuda = torch.cuda.is_available()
    pipeline_has_cuda = has_cuda
    device = "cuda" if has_cuda else "cpu"
    pipe_device = 0 if has_cuda else -1
    torch_dtype = torch.float16 if has_cuda else torch.float32

    if whisper_model is None:
        print("Loading Whisper model...")
        whisper_model = whisper.load_model("base", device=device)
        print("Whisper loaded.")
    
    if summarizer_model is None:
        print("Loading Summarization model...")
        summarizer_tokenizer = AutoTokenizer.from_pretrained("facebook/bart-large-cnn")
        summarizer_model = AutoModelForSeq2SeqLM.from_pretrained(
            "facebook/bart-large-cnn", 
            torch_dtype=torch_dtype,
            attn_implementation="eager"
        ).to(device)
        print("Summarizer loaded.")
        
    if classifier is None:
        print("Loading Zero-shot Classification pipeline...")
        classifier = pipeline(
            "zero-shot-classification", 
            model="facebook/bart-large-mnli", 
            device=pipe_device,
            torch_dtype=torch_dtype,
            model_kwargs={"attn_implementation": "eager"}
        )
        print("Classifier loaded.")


pipeline_lock = threading.Lock()

def process_audio_task(task_id: str, file_path: str):
    """Execute the end-to-end transcription, summary, and classification flow."""
    try:
        # Model loading/transcription are serialized to avoid concurrent GPU spikes.
        with pipeline_lock:
            load_models()
            print(f"[{task_id}] Transcribing audio: {file_path}")
            update_task_status(task_id, status="transcribing")
            result = whisper_model.transcribe(file_path, fp16=pipeline_has_cuda)
            transcript = result["text"]
            
        words = transcript.split()
        if len(words) < 20:
            summary = "Audio is too short to summarize."
            topics = ["N/A"]
            update_task_status(task_id, status="completed", transcript=transcript, summary=summary, topics=topics)
            return

        print(f"[{task_id}] Summarizing transcript...")
        update_task_status(task_id, status="summarizing", transcript=transcript)
        
        max_chunk_words = 600
        # Chunking keeps the summarizer within token limits for long transcripts.
        chunks = [" ".join(words[i:i + max_chunk_words]) for i in range(0, len(words), max_chunk_words)]
        
        num_chunks = len(chunks)
        chunk_max_length = max(60, min(250, 1000 // num_chunks))
        chunk_min_length = max(30, min(100, 200 // num_chunks))

        all_summaries = []
        
        with pipeline_lock:
            with torch.inference_mode():
                for i, chunk in enumerate(chunks):
                    print(f"[{task_id}] Summarizing chunk {i+1}/{num_chunks}...")
                    inputs = summarizer_tokenizer([chunk], max_length=1024, truncation=True, return_tensors="pt")
                    input_ids = inputs["input_ids"].to(summarizer_model.device)
                    
                    summary_ids = summarizer_model.generate(
                        input_ids,
                        num_beams=4 if pipeline_has_cuda else 2,
                        max_length=chunk_max_length, 
                        min_length=chunk_min_length,
                        no_repeat_ngram_size=3
                    )
                    chunk_summary = summarizer_tokenizer.batch_decode(summary_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
                    all_summaries.append(chunk_summary)
            
        summary = " ".join(all_summaries)

        print(f"[{task_id}] Classifying topics...")
        update_task_status(task_id, status="classifying", transcript=transcript, summary=summary)
        
        with pipeline_lock:
            with torch.inference_mode():
                topic_result = classifier(summary, CANDIDATE_LABELS, multi_label=True)
        top_topics = topic_result['labels'][:3]
        
        print(f"[{task_id}] Done.")
        update_task_status(task_id, status="completed", transcript=transcript, summary=summary, topics=top_topics)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[{task_id}] Error: {str(e)}")
        update_task_status(task_id, status="failed", transcript=f"Error occurred: {str(e)}")

def start_processing(task_id: str, file_path: str):
    """Run audio processing asynchronously so upload requests return immediately."""
    thread = threading.Thread(target=process_audio_task, args=(task_id, file_path), daemon=True)
    thread.start()
