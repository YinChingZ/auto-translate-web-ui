import React, { useRef, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, RefreshCw, Clock, Play, Pause, Plus } from 'lucide-react';
import { useSubtitleStore, Subtitle } from './store';

// Helper to format seconds into MM:SS.ms
const formatTime = (seconds: number) => {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 100);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
};

// Helper to parse time string back to seconds (simple implementation)
const parseTime = (timeStr: string) => {
  const parts = timeStr.split(':');
  if (parts.length === 2) {
    const mins = parseInt(parts[0]);
    const secs = parseFloat(parts[1]);
    return mins * 60 + secs;
  }
  return parseFloat(timeStr);
};

const SubtitleItem: React.FC<{
  sub: Subtitle;
  isActive: boolean;
  currentTime: number;
  onSave: (id: number, updates: Partial<Subtitle>, triggerTranslation?: boolean) => Promise<void>;
  onSeek: (time: number) => void;
  onDelete: (id: number) => void;
}> = ({ sub, isActive, currentTime, onSave, onSeek, onDelete }) => {
  const [text, setText] = useState(sub.text_translated);
  const [originalText, setOriginalText] = useState(sub.text_original);
  const [startTime, setStartTime] = useState(formatTime(sub.start_time));
  const [endTime, setEndTime] = useState(formatTime(sub.end_time));
  const [isTranslating, setIsTranslating] = useState(false);

  useEffect(() => {
    setText(sub.text_translated);
    setOriginalText(sub.text_original);
    setStartTime(formatTime(sub.start_time));
    setEndTime(formatTime(sub.end_time));
  }, [sub]);

  const handleSetStart = () => {
      onSave(sub.id, { start_time: currentTime });
      setStartTime(formatTime(currentTime));
  };

  const handleSetEnd = () => {
      onSave(sub.id, { end_time: currentTime });
      setEndTime(formatTime(currentTime));
  };

  const handleBlurText = () => {
    if (text !== sub.text_translated) {
      onSave(sub.id, { text_translated: text });
    }
  };

  const handleBlurOriginalText = async () => {
    if (originalText !== sub.text_original) {
      setIsTranslating(true);
      try {
          await onSave(sub.id, { text_original: originalText }, true);
      } finally {
          setIsTranslating(false);
      }
    }
  };

  const handleBlurTime = () => {
    const newStart = parseTime(startTime);
    const newEnd = parseTime(endTime);
    
    if (newStart !== sub.start_time || newEnd !== sub.end_time) {
        // Basic validation
        if (!isNaN(newStart) && !isNaN(newEnd) && newStart < newEnd) {
            onSave(sub.id, { start_time: newStart, end_time: newEnd });
        } else {
            // Revert if invalid
            setStartTime(formatTime(sub.start_time));
            setEndTime(formatTime(sub.end_time));
        }
    }
  };

  const handleReTranslate = async () => {
    setIsTranslating(true);
    try {
        await onSave(sub.id, {}, true);
    } finally {
        setIsTranslating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      handleBlurText();
      handleBlurOriginalText();
      handleBlurTime();
      (e.target as HTMLElement).blur();
    }
    // Alt + [ : Set Start Time
    if (e.altKey && e.key === '[') {
        e.preventDefault();
        handleSetStart();
    }
    // Alt + ] : Set End Time
    if (e.altKey && e.key === ']') {
        e.preventDefault();
        handleSetEnd();
    }
    // Alt + R : Re-translate
    if (e.altKey && (e.key === 'r' || e.key === 'R')) {
        e.preventDefault();
        handleReTranslate();
    }
  };

  return (
    <div
      id={`subtitle-${sub.id}`}
      className={`p-3 border rounded transition-colors duration-200 ${
        isActive 
          ? 'bg-blue-100 border-blue-500 shadow-md' 
          : 'bg-white border-gray-200 hover:bg-gray-50'
      }`}
      onClick={() => onSeek(sub.start_time)}
    >
      <div className="flex justify-between items-center mb-2 gap-2">
        <div className="flex items-center gap-1 text-xs">
            <button 
                className="p-1 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded"
                onClick={(e) => { e.stopPropagation(); handleSetStart(); }}
                title="Set Start to Current Time (Alt+[)"
            >
                <Clock className="h-3 w-3" />
            </button>
            <input 
                className="w-20 p-1 border rounded text-center"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                onBlur={handleBlurTime}
                onClick={(e) => e.stopPropagation()}
            />
            <span>-</span>
            <input 
                className="w-20 p-1 border rounded text-center"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                onBlur={handleBlurTime}
                onClick={(e) => e.stopPropagation()}
            />
            <button 
                className="p-1 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded"
                onClick={(e) => { e.stopPropagation(); handleSetEnd(); }}
                title="Set End to Current Time (Alt+])"
            >
                <Clock className="h-3 w-3" />
            </button>
        </div>
        <div className="flex items-center gap-2">
            {isTranslating && <span className="text-xs text-blue-500 animate-pulse">Translating...</span>}
            <span className="text-xs text-gray-400">{(sub.confidence * 100).toFixed(0)}%</span>
            <button 
                className="text-blue-500 hover:text-blue-700 p-1 rounded hover:bg-blue-50"
                onClick={(e) => {
                    e.stopPropagation();
                    handleReTranslate();
                }}
                title="Re-translate"
                disabled={isTranslating}
            >
                <RefreshCw className={`h-4 w-4 ${isTranslating ? 'animate-spin' : ''}`} />
            </button>
            <button 
                className="text-red-500 hover:text-red-700 p-1 rounded hover:bg-red-50"
                onClick={(e) => {
                    e.stopPropagation();
                    if(confirm('Delete this subtitle?')) onDelete(sub.id);
                }}
            >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
            </button>
        </div>
      </div>
      
      <textarea
        className="w-full text-sm text-gray-600 bg-transparent border border-transparent hover:border-gray-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded p-1 resize-none transition-all mb-1"
        value={originalText}
        onChange={(e) => setOriginalText(e.target.value)}
        onBlur={handleBlurOriginalText}
        onKeyDown={handleKeyDown}
        onClick={(e) => e.stopPropagation()}
        rows={2}
        placeholder="Original text..."
        disabled={isTranslating}
      />
      
      <textarea
        className={`w-full text-sm font-medium text-gray-900 bg-transparent border border-transparent hover:border-gray-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded p-1 resize-none transition-all ${isTranslating ? 'opacity-50 cursor-not-allowed' : ''}`}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={handleBlurText}
        onKeyDown={handleKeyDown}
        onClick={(e) => e.stopPropagation()}
        rows={2}
        disabled={isTranslating}
      />
    </div>
  );
};

export const SubtitleEditor: React.FC = () => {
  const { videoId } = useParams<{ videoId: string }>();
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  
  const { 
      subtitles, 
      currentTime, 
      setCurrentTime, 
      fetchSubtitles, 
      saveSubtitle, 
      addSubtitle, 
      deleteSubtitle,
      reset
  } = useSubtitleStore();
  
  const [videoSrc, setVideoSrc] = useState<string>("");
  const [status, setStatus] = useState<string>("loading");

  // Reset store when videoId changes
  useEffect(() => {
    reset();
  }, [videoId, reset]);

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
          setVideoSrc(video_url);
          fetchSubtitles(videoId);
          return true;
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

  const handleAddSubtitle = async () => {
      if (!videoId) return;
      const start = currentTime;
      const end = start + 2.0; // Default 2 seconds duration
      await addSubtitle(videoId, {
          start_time: start,
          end_time: end,
          text_original: "New Subtitle",
          text_translated: ""
      });
  };

  // Global shortcuts
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
        // Add Subtitle: Alt+N
        if (e.altKey && (e.key === 'n' || e.key === 'N')) {
            e.preventDefault();
            handleAddSubtitle();
        }
        // Play/Pause: Ctrl+Space
        if ((e.ctrlKey || e.metaKey) && e.code === 'Space') {
            e.preventDefault();
            if (videoRef.current) {
                if (videoRef.current.paused) videoRef.current.play();
                else videoRef.current.pause();
            }
        }
    };

    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, [handleAddSubtitle]);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleSubtitleClick = (startTime: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = startTime;
      videoRef.current.play();
    }
  };

  // Auto-scroll to active subtitle
  useEffect(() => {
    const activeSub = subtitles.find(s => currentTime >= s.start_time && currentTime < s.end_time);
    if (activeSub && listRef.current) {
        const element = document.getElementById(`subtitle-${activeSub.id}`);
        if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
  }, [currentTime, subtitles]);

  const handleExport = (translated: boolean) => {
      if (!videoId) return;
      window.open(`/api/videos/${videoId}/export?translated=${translated}`, '_blank');
  };

  return (
    <div className="flex h-screen p-4 gap-4 bg-gray-100">
      {/* Left Side: Video Player */}
      <div className="w-1/2 flex flex-col gap-4">
        <div className="bg-black rounded-lg overflow-hidden shadow-lg aspect-video relative">
          {videoSrc ? (
            <video
              ref={videoRef}
              className="w-full h-full"
              controls
              onTimeUpdate={handleTimeUpdate}
              src={videoSrc}
            >
              Your browser does not support the video tag.
            </video>
          ) : (
            <div className="w-full h-full flex items-center justify-center text-white">
              {status === 'loading' ? 'Checking status...' : 'Waiting for video...'}
            </div>
          )}
        </div>
        
        {/* Controls */}
        <div className="bg-white p-4 rounded-lg shadow flex gap-2 justify-between items-center">
            <div className="flex gap-2">
                <button 
                    onClick={() => navigate('/')}
                    className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors flex items-center gap-2"
                    title="Back to Home"
                >
                    <ArrowLeft className="h-5 w-5" />
                    Back
                </button>
                <button 
                    onClick={handleAddSubtitle}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors flex items-center gap-2"
                    title="Add Subtitle (Alt+N)"
                >
                    <Plus className="h-5 w-5" />
                    Add Subtitle
                </button>
            </div>
            <div className="flex gap-2">
                <button 
                    onClick={() => handleExport(false)}
                    className="px-3 py-2 border border-gray-300 rounded hover:bg-gray-50 text-sm text-gray-700"
                >
                    Export Original
                </button>
                <button 
                    onClick={() => handleExport(true)}
                    className="px-3 py-2 border border-gray-300 rounded hover:bg-gray-50 text-sm text-gray-700"
                >
                    Export Translated
                </button>
            </div>
        </div>
      </div>

      {/* Right Side: Subtitle List */}
      <div className="w-1/2 flex flex-col bg-white rounded-lg shadow overflow-hidden">
        <div className="p-4 border-b bg-gray-50 flex justify-between items-center">
          <h2 className="font-bold text-lg text-gray-800">Subtitles</h2>
          <span className="text-sm text-gray-500">{subtitles.length} items</span>
        </div>
        <div ref={listRef} className="flex-1 overflow-y-auto p-4 space-y-3">
          {subtitles.map((sub) => (
            <SubtitleItem
              key={sub.id}
              sub={sub}
              isActive={currentTime >= sub.start_time && currentTime < sub.end_time}
              currentTime={currentTime}
              onSave={saveSubtitle}
              onSeek={handleSubtitleClick}
              onDelete={deleteSubtitle}
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
