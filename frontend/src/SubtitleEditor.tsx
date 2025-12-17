import React, { useRef, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { useSubtitleStore, Subtitle } from './store';

// Helper component for individual subtitle item
const SubtitleItem: React.FC<{
  sub: Subtitle;
  onSave: (id: number, updates: Partial<Subtitle>) => void;
  onSeek: (time: number) => void;
}> = ({ sub, onSave, onSeek }) => {
  const [text, setText] = useState(sub.text_translated);

  useEffect(() => {
    setText(sub.text_translated);
  }, [sub.text_translated]);

  const handleBlur = () => {
    if (text !== sub.text_translated) {
      onSave(sub.id, { text_translated: text });
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      onSave(sub.id, { text_translated: text });
      (e.target as HTMLTextAreaElement).blur();
    }
  };

  return (
    <div
      className="p-3 bg-white border rounded hover:bg-blue-50 hover:border-blue-300 transition-colors duration-200"
      onClick={() => onSeek(sub.start_time)}
    >
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>{formatTime(sub.start_time)} - {formatTime(sub.end_time)}</span>
        <span>Confidence: {(sub.confidence * 100).toFixed(0)}%</span>
      </div>
      <div className="text-sm text-gray-700 mb-1">
        {sub.text_original}
      </div>
      <textarea
        className="w-full text-sm font-medium text-gray-900 bg-transparent border-none focus:ring-1 focus:ring-blue-500 rounded p-1 resize-none"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        onClick={(e) => e.stopPropagation()} // Prevent seeking when clicking input
        rows={2}
      />
    </div>
  );
};

export const SubtitleEditor: React.FC = () => {
  const { videoId } = useParams<{ videoId: string }>();
  const videoRef = useRef<HTMLVideoElement>(null);
  const { subtitles, setCurrentTime, fetchSubtitles, saveSubtitle } = useSubtitleStore();
  const [videoSrc, setVideoSrc] = useState<string>("");
  const [status, setStatus] = useState<string>("loading");

  // Polling for video status
  useEffect(() => {
    if (!videoId) return;

    let intervalId: NodeJS.Timeout;

    const checkStatus = async () => {
      try {
        const response = await axios.get(`/api/videos/${videoId}/status`);
        const { status: videoStatus, video_url } = response.data;

        setStatus(videoStatus);

        if (videoStatus === 'ready') {
          // 设置视频 URL（从状态响应中获取）
          setVideoSrc(video_url);
          fetchSubtitles(videoId);
          return true; // Stop polling
        }
      } catch (error) {
        console.error("Error polling status:", error);
      }
      return false;
    };

    checkStatus().then((shouldStop) => {
      if (!shouldStop) {
        intervalId = setInterval(async () => {
          const stop = await checkStatus();
          if (stop) {
            clearInterval(intervalId);
          }
        }, 2000);
      }
    });

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [videoId, fetchSubtitles]);

  // Optional: Sync video time to store on time update
  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleSubtitleClick = (startTime: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = startTime;
      // Ensure video plays or stays paused based on your requirements, 
      // usually jumping to a timestamp implies seeking.
    }
  };

  return (
    <div className="flex h-screen p-4 gap-4">
      {/* Left Side: Video Player */}
      <div className="w-1/2 flex flex-col">
        <div className="bg-black rounded-lg overflow-hidden shadow-lg">
          {videoSrc ? (
            <video
              ref={videoRef}
              className="w-full h-auto"
              controls
              onTimeUpdate={handleTimeUpdate}
              src={videoSrc}
            >
              Your browser does not support the video tag.
            </video>
          ) : (
            <div className="w-full h-64 flex items-center justify-center text-white">
              {status === 'loading' ? 'Checking status...' : 'Waiting for video...'}
            </div>
          )}
        </div>
      </div>

      {/* Right Side: Subtitle List */}
      <div className="w-1/2 flex flex-col bg-gray-50 rounded-lg shadow-inner overflow-hidden">
        <div className="p-4 bg-white border-b font-bold text-lg">
          Subtitles
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {subtitles.map((sub) => (
            <SubtitleItem
              key={sub.id}
              sub={sub}
              onSave={saveSubtitle}
              onSeek={handleSubtitleClick}
            />
          ))}
          {subtitles.length === 0 && (
            <div className="text-center text-gray-400 mt-10">
              {status === 'ready' ? 'No subtitles loaded.' : `Status: ${status}. Processing video...`}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Helper to format seconds into MM:SS
const formatTime = (seconds: number) => {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};
