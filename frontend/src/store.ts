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
  saveSubtitle: (id: number, updates: Partial<Subtitle>, triggerTranslation?: boolean) => Promise<void>;
  addSubtitle: (videoId: string, subtitle: { start_time: number; end_time: number; text_original?: string; text_translated?: string }) => Promise<void>;
  deleteSubtitle: (id: number) => Promise<void>;
  reset: () => void;
}

export const useSubtitleStore = create<SubtitleState>((set) => ({
  subtitles: [],
  currentTime: 0,

  reset: () => set({ subtitles: [], currentTime: 0 }),

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

  saveSubtitle: async (id: number, updates: Partial<Subtitle>, triggerTranslation = false) => {
    try {
      // Optimistic update (only if not triggering translation, or update other fields)
      // If triggering translation, we might want to wait for the server response to get the new translation
      // But for UI responsiveness, we update what we have (e.g. original text)
      set((state) => ({
        subtitles: state.subtitles.map((sub) =>
          sub.id === id ? { ...sub, ...updates } : sub
        ),
      }));
      
      const response = await axios.put(`/api/subtitles/${id}`, updates, {
          params: { trigger_translation: triggerTranslation }
      });
      
      // If translation was triggered, update the store with the response (which contains the new translation)
      if (triggerTranslation) {
          set((state) => ({
            subtitles: state.subtitles.map((sub) =>
              sub.id === id ? response.data : sub
            ),
          }));
      }
    } catch (error) {
      console.error('Failed to save subtitle:', error);
    }
  },

  addSubtitle: async (videoId, subtitle) => {
    try {
      const response = await axios.post(`/api/videos/${videoId}/subtitles`, subtitle);
      const newSubtitle = response.data;
      set((state) => ({
        subtitles: [...state.subtitles, newSubtitle].sort((a, b) => a.start_time - b.start_time)
      }));
    } catch (error) {
      console.error('Failed to add subtitle:', error);
    }
  },

  deleteSubtitle: async (id) => {
    try {
      await axios.delete(`/api/subtitles/${id}`);
      set((state) => ({
        subtitles: state.subtitles.filter((sub) => sub.id !== id)
      }));
    } catch (error) {
      console.error('Failed to delete subtitle:', error);
    }
  }
}));
