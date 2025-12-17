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
        client = OpenAI(api_key=settings.openai_api_key)
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
    
    (get_speech_timestamps, _, read_audio, _, _) = utils
    
    wav = read_audio(audio_path)
    # 采样率必须与 extract_audio 中设置的一致 (16000)
    speech_timestamps = get_speech_timestamps(wav, model, sampling_rate=16000)
    return speech_timestamps

def transcribe_with_whisper(audio_path: str, vad_segments: List[Dict[str, int]]) -> List[Dict[str, Any]]:
    """
    Step 3: 调用 Whisper 识别
    仅对 VAD 检测到的片段进行识别，避免静音部分的幻觉
    """
    # 加载 Whisper 模型（从配置文件加载模型名称）
    model = whisper.load_model(settings.whisper_model)
    
    # 加载完整音频到内存 (numpy array)
    audio = whisper.load_audio(audio_path)
    
    transcriptions = []
    
    for segment in vad_segments:
        start_sample = segment['start']
        end_sample = segment['end']
        
        # 提取对应片段的音频数据
        segment_audio = audio[start_sample:end_sample]
        
        # Whisper 识别
        # fp16=False 确保在 CPU 上也能运行，如果有 GPU 可以设为 True
        result = model.transcribe(segment_audio, fp16=False)
        
        transcriptions.append({
            "start": start_sample / 16000.0, # 转换为秒
            "end": end_sample / 16000.0,     # 转换为秒
            "text_original": result["text"].strip(),
            "confidence": 1.0 # Whisper segment 级置信度获取较复杂，暂设为 1.0 或后续优化
        })
        
    return transcriptions


def _build_translation_prompt(texts: List[str], target_language: str) -> str:
    """
    构建翻译 prompt
    """
    numbered_texts = "\n".join([f"{i+1}. {text}" for i, text in enumerate(texts)])
    
    prompt = f"""You are a professional subtitle translator. Translate the following sentences to {target_language}.

Rules:
1. Maintain the original meaning and tone
2. Keep translations concise and suitable for subtitles
3. Return ONLY a valid JSON array, no other text
4. Each object must have "index" (1-based), "translated_text", and "confidence" (0.0-1.0) fields

Sentences to translate:
{numbered_texts}

Respond with a JSON array like:
[{{{"index": 1, "translated_text": "翻译内容", "confidence": 0.95}}}, ...]"""
    
    return prompt


def _call_llm_for_translation(texts: List[str], target_language: str) -> List[Dict[str, Any]]:
    """
    调用 OpenAI API 进行翻译
    """
    prompt = _build_translation_prompt(texts, target_language)
    openai_client = get_openai_client()
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # 性价比较高的模型
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional translator. Always respond with valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,  # 降低随机性，提高翻译一致性
            response_format={"type": "json_object"}  # 强制 JSON 输出
        )
        
        # 解析响应
        content = response.choices[0].message.content
        result = json.loads(content)
        
        # 处理可能的嵌套结构（有些模型会返回 {"translations": [...]}）
        if isinstance(result, dict):
            # 尝试找到数组
            for key in ["translations", "results", "data"]:
                if key in result and isinstance(result[key], list):
                    return result[key]
            # 如果是单个翻译结果的字典
            if "translated_text" in result:
                return [result]
        
        return result if isinstance(result, list) else []
        
    except json.JSONDecodeError as e:
        print(f"Failed to parse LLM response as JSON: {e}")
        # 返回空翻译，保留原文
        return [{"index": i+1, "translated_text": "", "confidence": 0.0} for i in range(len(texts))]
    except Exception as e:
        print(f"LLM API call failed: {e}")
        raise RuntimeError(f"Translation failed: {e}")


def translate_segments(segments: List[Dict[str, Any]], target_language: str = TARGET_LANGUAGE) -> List[Dict[str, Any]]:
    """
    Step 4: 使用 LLM 翻译字幕片段
    
    Args:
        segments: 包含 text_original 的字幕片段列表
        target_language: 目标语言，默认为中文
    
    Returns:
        更新后的 segments，每个片段增加 text_translated 和更新的 confidence 字段
    """
    if not segments:
        return segments
    
    # 提取所有原始文本
    texts = [seg.get("text_original", "") for seg in segments]
    
    # 分批处理
    all_translations = []
    for i in range(0, len(texts), TRANSLATION_BATCH_SIZE):
        batch_texts = texts[i:i + TRANSLATION_BATCH_SIZE]
        batch_start_idx = i
        
        print(f"Translating batch {i // TRANSLATION_BATCH_SIZE + 1}/{(len(texts) - 1) // TRANSLATION_BATCH_SIZE + 1}...")
        
        # 调用 LLM 翻译
        batch_results = _call_llm_for_translation(batch_texts, target_language)
        
        # 将结果映射回原始索引
        for result in batch_results:
            # result 的 index 是 1-based 的批次内索引
            batch_idx = result.get("index", 1) - 1
            global_idx = batch_start_idx + batch_idx
            
            if 0 <= global_idx < len(segments):
                all_translations.append({
                    "global_idx": global_idx,
                    "translated_text": result.get("translated_text", ""),
                    "confidence": result.get("confidence", 0.0)
                })
    
    # 更新 segments
    for trans in all_translations:
        idx = trans["global_idx"]
        if 0 <= idx < len(segments):
            segments[idx]["text_translated"] = trans["translated_text"]
            # 综合 Whisper 置信度和翻译置信度
            original_confidence = segments[idx].get("confidence", 1.0)
            translation_confidence = trans["confidence"]
            # 取两者的平均作为最终置信度
            segments[idx]["confidence"] = (original_confidence + translation_confidence) / 2
    
    # 确保所有 segment 都有 text_translated 字段
    for seg in segments:
        if "text_translated" not in seg:
            seg["text_translated"] = ""
    
    return segments


def process_video(video_path: str) -> List[Dict[str, Any]]:
    """
    核心处理流程函数
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
        
    # 生成临时音频文件路径
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    # 建议将临时文件放在专门的 temp 目录，这里为了演示放在同级或系统 temp
    temp_audio_path = f"/tmp/{base_name}_temp.wav"
    
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
        print("Step 3: Transcribing with Whisper...")
        subtitles = transcribe_with_whisper(temp_audio_path, vad_segments)
        
        # 4. LLM 翻译
        print("Step 4: Translating with LLM...")
        subtitles = translate_segments(subtitles)
        
        print("Processing complete.")
        return subtitles
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
