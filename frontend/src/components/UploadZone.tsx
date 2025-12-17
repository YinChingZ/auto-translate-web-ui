import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Upload, FileVideo, Loader2, CheckCircle, AlertCircle } from 'lucide-react';

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

export const UploadZone: React.FC = () => {
  const navigate = useNavigate();
  const [status, setStatus] = useState<UploadStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];
    const formData = new FormData();
    formData.append('file', file);

    setStatus('uploading');
    setProgress(0);
    setErrorMessage('');

    try {
      const response = await axios.post('/api/videos/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            setProgress(percent);
          }
        },
      });

      const { id } = response.data;
      setStatus('success');
      
      // 短暂延迟后跳转，让用户看到成功状态
      setTimeout(() => {
        navigate(`/editor/${id}`);
      }, 500);
    } catch (error) {
      setStatus('error');
      if (axios.isAxiosError(error) && error.response) {
        setErrorMessage(error.response.data?.detail || 'Upload failed');
      } else {
        setErrorMessage('Network error. Please try again.');
      }
    }
  }, [navigate]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'video/*': ['.mp4', '.mkv', '.avi', '.mov', '.webm'],
    },
    maxFiles: 1,
    disabled: status === 'uploading',
  });

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">Auto Translate</h1>
          <p className="text-gray-600">Upload your video to start automatic translation</p>
        </div>

        <div
          {...getRootProps()}
          className={`
            relative border-2 border-dashed rounded-2xl p-12 transition-all duration-300 cursor-pointer
            ${isDragActive 
              ? 'border-blue-500 bg-blue-50 scale-105' 
              : 'border-gray-300 bg-white hover:border-blue-400 hover:bg-gray-50'
            }
            ${status === 'uploading' ? 'pointer-events-none' : ''}
            ${status === 'error' ? 'border-red-300 bg-red-50' : ''}
            ${status === 'success' ? 'border-green-300 bg-green-50' : ''}
          `}
        >
          <input {...getInputProps()} />

          <div className="flex flex-col items-center justify-center space-y-4">
            {status === 'idle' && (
              <>
                {isDragActive ? (
                  <FileVideo className="w-16 h-16 text-blue-500 animate-bounce" />
                ) : (
                  <Upload className="w-16 h-16 text-gray-400" />
                )}
                <div className="text-center">
                  <p className="text-lg font-medium text-gray-700">
                    {isDragActive ? 'Drop your video here' : 'Drag & drop your video'}
                  </p>
                  <p className="text-sm text-gray-500 mt-1">
                    or click to browse (MP4, MKV, AVI, MOV, WebM)
                  </p>
                </div>
              </>
            )}

            {status === 'uploading' && (
              <>
                <Loader2 className="w-16 h-16 text-blue-500 animate-spin" />
                <div className="text-center">
                  <p className="text-lg font-medium text-gray-700">Uploading...</p>
                  <p className="text-sm text-gray-500 mt-1">{progress}% complete</p>
                </div>
                <div className="w-full max-w-xs bg-gray-200 rounded-full h-2 mt-2">
                  <div 
                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </>
            )}

            {status === 'success' && (
              <>
                <CheckCircle className="w-16 h-16 text-green-500" />
                <div className="text-center">
                  <p className="text-lg font-medium text-green-700">Upload successful!</p>
                  <p className="text-sm text-gray-500 mt-1">Redirecting to editor...</p>
                </div>
              </>
            )}

            {status === 'error' && (
              <>
                <AlertCircle className="w-16 h-16 text-red-500" />
                <div className="text-center">
                  <p className="text-lg font-medium text-red-700">Upload failed</p>
                  <p className="text-sm text-red-500 mt-1">{errorMessage}</p>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setStatus('idle');
                      setErrorMessage('');
                    }}
                    className="mt-4 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
                  >
                    Try again
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

        <p className="text-center text-sm text-gray-500 mt-6">
          Supported formats: MP4, MKV, AVI, MOV, WebM • Max file size: 500MB
        </p>
      </div>
    </div>
  );
};
