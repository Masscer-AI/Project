import React, { useState } from "react";
import { AudioTools } from "../../components/AudioTools/AudioTools";
import { ImageTools } from "../../components/ImageTools/ImageTools";
import { VideoTools } from "../../components/VideoTools/VideoTools";
import "./page.css"

export default function Tools() {
  const [selectedTool, setSelectedTool] = useState(null);

  return (
    <main>
      <ToolsOptions
        selectedTool={selectedTool}
        setSelectedTool={setSelectedTool}
      />

      {selectedTool === "audio" && <AudioTools />}
      {selectedTool === "images" && <ImageTools />}
      {selectedTool === "videos" && <VideoTools />}
    </main>
  );
}

const ToolsOptions = ({ setSelectedTool, selectedTool }) => {
  return (
    <nav className="floating-navbar flex-x tool-options">
      <section className={`${selectedTool === "audio" && "selected"}`} onClick={() => setSelectedTool("audio")}>Audio</section>
      <section className={`${selectedTool === "images" && "selected"}`} onClick={() => setSelectedTool("images")}>Images</section>
      <section className={`${selectedTool === "videos" && "selected"}`} onClick={() => setSelectedTool("videos")}>Videos</section>
    </nav>
  );
};
