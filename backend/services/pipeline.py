import os
import json
import ffmpeg
import torch
import whisper
import numpy as np
from typing import List, Dict, Any, Optional
from openai import OpenAI
from ..config import settings

# 初始化 OpenAI 客户端（延迟初始化，避免 API key 为空时崩溃）
client: Optional[OpenAI] = None

def get_openai_client() -> OpenAI:
    """获取 OpenAI 客户端实例（延迟初始化）"""
    global client
    if client is None:
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key is not configured. Please set OPENAI_API_KEY in .env file.")
        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
    return client

# 翻译配置（从配置文件加载）
TRANSLATION_BATCH_SIZE = settings.translation_batch_size
TARGET_LANGUAGE = settings.target_language

def extract_audio(video_path: str, audio_output_path: str) -> None:
    """
    Step 1: 使用 ffmpeg 从视频中提取音频
    转换为 16kHz 单声道 wav 格式 (Whisper 和 VAD 的标准输入要求)
    """
    try:
        (
            ffmpeg
            .input(video_path)
            .output(audio_output_path, ac=1, ar=16000)
            .run(quiet=True, overwrite_output=True)
        )
    except ffmpeg.Error as e:
        print(f"FFmpeg error: {e.stderr.decode()}")
        raise RuntimeError("Failed to extract audio")

def get_vad_segments(audio_path: str) -> List[Dict[str, int]]:
    """
    Step 2: 使用 Silero VAD 获取语音片段的时间戳
    返回的是采样点 (samples) 列表，例如 [{'start': 500, 'end': 1000}, ...]
    """
    # 加载 Silero VAD 模型
    # trust_repo=True 是必须的，因为是从 GitHub 加载
    model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                  model='silero_vad',
                                  force_reload=False,
                                  trust_repo=True)
    
    (get_speech_timestamps, _, _, _, _) = utils
    
    # Custom read_audio using soundfile to avoid torchaudio/torchcodec issues
    import soundfile as sf
    import numpy as np
    
    data, samplerate = sf.read(audio_path)
    # Ensure float32
    if data.dtype != np.float32:
        data = data.astype(np.float32)
    # Ensure mono
    if len(data.shape) > 1:
        data = data.mean(axis=1)
    # Convert to tensor
    wav = torch.from_numpy(data)
    # Ensure 1D tensor
    if wav.dim() > 1:
        wav = wav.squeeze()
    
    # 采样率必须与 extract_audio 中设置的一致 (16000)
    speech_timestamps = get_speech_timestamps(wav, model, sampling_rate=16000)
    return speech_timestamps

def transcribe_with_whisper(
    audio_path: str, 
    vad_segments: List[Dict[str, int]],
    model_name: str = settings.whisper_model
) -> List[Dict[str, Any]]:
    """
    Step 3: 调用 Whisper 识别
    仅对 VAD 检测到的片段进行识别，避免静音部分的幻觉
    """
    # 检查是否有可用的 GPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device} for Whisper transcription")

    # 加载 Whisper 模型
    model = whisper.load_model(model_name, device=device)
    
    # 加载完整音频到内存 (numpy array)
    audio = whisper.load_audio(audio_path)
    
    transcriptions = []
    
    for segment in vad_segments:
        start_sample = segment['start']
        end_sample = segment['end']
        
        # 提取对应片段的音频数据
        segment_audio = audio[start_sample:end_sample]
        
        # Whisper 识别
        # 如果是 CUDA，使用 fp16=True，否则使用 fp16=False
        # 强制指定语言为英语，提高准确率
        result = model.transcribe(segment_audio, fp16=(device == "cuda"), language="en")
        
        transcriptions.append({
            "start": start_sample / 16000.0, # 转换为秒
            "end": end_sample / 16000.0,     # 转换为秒
            "text_original": result["text"].strip(),
            "confidence": 1.0 # Whisper segment 级置信度获取较复杂，暂设为 1.0 或后续优化
        })
        
    return transcriptions


def _build_single_translation_prompt(
    text: str, 
    target_language: str, 
    context_before: str = "", 
    context_after: str = "",
    previous_translated: str = ""
) -> str:
    """
    构建单句翻译 prompt
    """
    context_section = ""
    if context_before:
        context_section += f"Previous original text: \"{context_before}\"\n"
    if context_after:
        context_section += f"Next original text: \"{context_after}\"\n"
    if previous_translated:
        context_section += f"Previously translated text: \"{previous_translated}\"\n"

    prompt = f"""You are a professional subtitle translator. Translate the following sentence to {target_language}.

Context information:
{context_section}

Rules:
1. Focus on reasonable segmentation and semantic coherence.
2. Maintain consistency with the previously translated text.
3. Return ONLY the translated text, no explanations or JSON.

Sentence to translate:
"{text}"
"""
    return prompt


def translate_single_text(
    text: str, 
    target_language: str = TARGET_LANGUAGE, 
    context_before: str = "", 
    context_after: str = "",
    previous_translated: str = ""
) -> str:
    """
    翻译单句文本
    """
    if not text.strip():
        return ""
        
    prompt = _build_single_translation_prompt(
        text, 
        target_language, 
        context_before, 
        context_after,
        previous_translated
    )
    
    client = get_openai_client()
    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": "You are a professional translator."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Translation failed: {e}")
        return text


def translate_segments(
    segments: List[Dict[str, Any]], 
    target_language: str = TARGET_LANGUAGE,
    batch_size: int = 1, # Deprecated, kept for compatibility
    context_window: int = 3
) -> List[Dict[str, Any]]:
    """
    Step 4: 使用 LLM 逐句翻译字幕片段
    """
    if not segments:
        return segments
    
    texts = [seg.get("text_original", "") for seg in segments]
    translated_texts = []
    
    print(f"Starting sentence-by-sentence translation for {len(texts)} segments...")
    
    for i, text in enumerate(texts):
        # 获取上下文
        start_idx = max(0, i - context_window)
        end_idx = min(len(texts), i + 1 + context_window)
        
        context_before = "\n".join(texts[start_idx:i])
        context_after = "\n".join(texts[i+1:end_idx])
        
        # 获取已翻译的上下文（取最近 context_window 句）
        prev_trans_start = max(0, len(translated_texts) - context_window)
        previous_translated = "\n".join(translated_texts[prev_trans_start:])
        
        print(f"Translating segment {i+1}/{len(texts)}...")
        
        translated = translate_single_text(
            text, 
            target_language, 
            context_before=context_before, 
            context_after=context_after,
            previous_translated=previous_translated
        )
        translated_texts.append(translated)
        
        # 更新 segment
        segments[i]["text_translated"] = translated
        # 简单设置置信度
        segments[i]["confidence"] = 0.9 
    
    return segments

def process_video(
    video_path: str, 
    batch_size: int = TRANSLATION_BATCH_SIZE,
    context_window: int = 3,
    whisper_model: str = settings.whisper_model
) -> List[Dict[str, Any]]:
    """
    核心处理流程函数
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
        
    # 生成临时音频文件路径
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    # 使用 uploads 目录下的 temp 子目录，避免跨平台路径问题
    temp_dir = os.path.join(os.path.dirname(video_path), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    temp_audio_path = os.path.join(temp_dir, f"{base_name}_temp.wav")
    
    try:
        # 1. 提取音频
        print(f"Processing {video_path}...")
        print("Step 1: Extracting audio...")
        extract_audio(video_path, temp_audio_path)
        
        # 2. VAD 分割
        print("Step 2: Detecting voice activity (VAD)...")
        vad_segments = get_vad_segments(temp_audio_path)
        print(f"Detected {len(vad_segments)} speech segments.")
        
        # 3. Whisper 识别
        print(f"Step 3: Transcribing with Whisper (Model: {whisper_model})...")
        subtitles = transcribe_with_whisper(temp_audio_path, vad_segments, model_name=whisper_model)
        
        # 4. LLM 翻译
        print("Step 4: Translating with LLM...")
        subtitles = translate_segments(
            subtitles, 
            batch_size=batch_size,
            context_window=context_window
        )
        
        print("Processing complete.")
        return subtitles
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
