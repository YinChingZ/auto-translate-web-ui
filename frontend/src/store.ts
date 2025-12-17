import { create } from 'zustand';
import axios from 'axios';

export interface Subtitle {
  id: number;
  video_id: string;
  start_time: number;
  end_time: number;
  text_original: string;
  text_translated: string;
  confidence: number;
}

interface SubtitleState {
  subtitles: Subtitle[];
  currentTime: number;
  
  // Actions
  loadSubtitles: (subtitles: Subtitle[]) => void;
  updateSubtitle: (id: number, updates: Partial<Subtitle>) => void;
  setCurrentTime: (time: number) => void;
  fetchSubtitles: (videoId: string) => Promise<void>;
  saveSubtitle: (id: number, updates: Partial<Subtitle>) => Promise<void>;
}

export const useSubtitleStore = create<SubtitleState>((set) => ({
  subtitles: [],
  currentTime: 0,

  loadSubtitles: (subtitles) => set({ subtitles }),

  updateSubtitle: (id, updates) =>
    set((state) => ({
      subtitles: state.subtitles.map((sub) =>
        sub.id === id ? { ...sub, ...updates } : sub
      ),
    })),

  setCurrentTime: (time) => set({ currentTime: time }),

  fetchSubtitles: async (videoId: string) => {
    try {
      const response = await axios.get(`/api/videos/${videoId}/subtitles`);
      set({ subtitles: response.data });
    } catch (error) {
      console.error('Failed to fetch subtitles:', error);
    }
  },

  saveSubtitle: async (id: number, updates: Partial<Subtitle>) => {
    try {
      await axios.put(`/api/subtitles/${id}`, updates);
      set((state) => ({
        subtitles: state.subtitles.map((sub) =>
          sub.id === id ? { ...sub, ...updates } : sub
        ),
      }));
    } catch (error) {
      console.error('Failed to save subtitle:', error);
    }
  },
}));
