import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { UploadZone } from './components/UploadZone';
import { SubtitleEditor } from './SubtitleEditor';

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<UploadZone />} />
        <Route path="/editor/:videoId" element={<SubtitleEditor />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
