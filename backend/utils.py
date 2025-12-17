from typing import List, Any


def format_srt_time(seconds: float) -> str:
    """将秒数转换为 SRT 时间格式 (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt(subtitles: List[Any], use_translated: bool = True) -> str:
    """
    将字幕数据库对象列表转换为标准 SRT 格式字符串。
    
    Args:
        subtitles: 字幕对象列表，每个对象需包含 start_time, end_time, 
                   text_original, text_translated 属性
        use_translated: 是否优先使用翻译文本，默认为 True
    
    Returns:
        标准 SRT 格式的字符串
    """
    srt_lines = []
    
    for index, subtitle in enumerate(subtitles, start=1):
        # 序号
        srt_lines.append(str(index))
        
        # 时间轴: 00:00:00,000 --> 00:00:00,000
        start = format_srt_time(subtitle.start_time)
        end = format_srt_time(subtitle.end_time)
        srt_lines.append(f"{start} --> {end}")
        
        # 字幕文本：优先使用翻译文本，否则使用原始文本
        if use_translated and subtitle.text_translated:
            text = subtitle.text_translated
        else:
            text = subtitle.text_original or ""
        
        srt_lines.append(text)
        
        # 空行分隔每条字幕
        srt_lines.append("")
    
    return "\n".join(srt_lines)
