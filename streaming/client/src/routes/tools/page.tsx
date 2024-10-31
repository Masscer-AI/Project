import React, { useState } from "react";
import { AudioTools } from "../../components/AudioTools/AudioTools";
import { ImageTools } from "../../components/ImageTools/ImageTools";
import { VideoTools } from "../../components/VideoTools/VideoTools";
import "./page.css";
import { Toaster } from "react-hot-toast";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import { SvgButton } from "../../components/SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";

export default function Tools() {
  const { chatState } = useStore((state) => ({
    chatState: state.chatState,
  }));
  const [selectedTool, setSelectedTool] = useState(null);

  return (
    <main>
      {chatState.isSidebarOpened && <Sidebar />}
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
  const { toggleSidebar } = useStore((state) => ({
    toggleSidebar: state.toggleSidebar,
  }));

  return (
    <nav className="floating-navbar flex-x tool-options">
      <SvgButton onClick={toggleSidebar} svg={SVGS.burger} />
      <section
        className={`${selectedTool === "audio" && "selected"}`}
        onClick={() => setSelectedTool("audio")}
      >
        Audio
      </section>
      <section
        className={`${selectedTool === "images" && "selected"}`}
        onClick={() => setSelectedTool("images")}
      >
        Images
      </section>
      <section
        className={`${selectedTool === "videos" && "selected"}`}
        onClick={() => setSelectedTool("videos")}
      >
        Videos
      </section>
    </nav>
  );
};
