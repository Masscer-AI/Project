import React, { useEffect, useState } from "react";
import {
  getMedia,
  getVideos,
  requestVideoGeneration,
} from "../../modules/apiCalls";
import toast from "react-hot-toast";
import "./VideoTools.css";
import { Modal } from "../Modal/Modal";
import { SvgButton } from "../SvgButton/SvgButton";
import { Icon } from "../Icon/Icon";

export const VideoTools = () => {
  const [state, setState] = useState({
    action: "shorts",
    duration: "LESS_THAN_MINUTE",
    about: "",
    orientation: "LANDSCAPE",
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setState((prevState) => ({ ...prevState, [name]: value }));
  };

  const handleGenerate = async () => {
    if (state.about) {
      try {
        const response = await requestVideoGeneration(
          state.about,
          state.duration,
          state.orientation
        );
        toast.success("Video generation job created succesfully");
        console.log("Video generation response:", response);
      } catch (error) {
        toast.error(
          "Something happened requesting the video generation, check the console for more info"
        );
        console.error("Error generating video:", error);
      }
    } else {
      alert("Please fill in all fields.");
    }
  };

  return (
    <main className="video-tools flex-y">
      <h4>Which video you want to generate today?</h4>
      {/* <select name="action" value={state.action} onChange={handleChange}>
        <option value="shorts">Generate Shorts</option>
        
      </select> */}

      <form className="flex-y form generate-video-card">
        <label>
          Duration:
          <select
            name="duration"
            value={state.duration}
            onChange={handleChange}
          >
            <option value="LESS_THAN_MINUTE">Less than a minute</option>{" "}
            {/* Updated to match model */}
            <option value="MORE_THAN_MINUTE">More than a minute</option>{" "}
            {/* Added option */}
          </select>
        </label>

        <label>
          About:
          <input
            type="text"
            name="about"
            value={state.about}
            onChange={handleChange}
          />
        </label>

        <label>
          Orientation:
          <select
            name="orientation"
            value={state.orientation}
            onChange={handleChange}
          >
            <option value="LANDSCAPE">Landscape</option>{" "}
            <option value="SQUARE">Square</option>{" "}
            <option value="PORTRAIT">Portrait</option>{" "}
          </select>
        </label>

        <button type="button" onClick={handleGenerate}>
          Generate
        </button>
      </form>
      <VideosContainer />
    </main>
  );
};

type TVideo = {
  id: number;
};

const VideosContainer = () => {
  const [videos, setVideos] = useState([] as TVideo[]);

  useEffect(() => {
    _fetch();
  }, []);

  const _fetch = async () => {
    const fetchedVideos = await getVideos();
    setVideos(fetchedVideos);
    console.log(fetchedVideos);
  };

  return (
    <div className="videos-container">
      <h2>Videos</h2>
      {videos.map((video) => (
        <VideoCard key={video.id} video={video} />
      ))}
    </div>
  );
};

type TVideoSource = {
  duration: string;
};

type TMediaResponse = {
  videos: TVideoSource[];
};
const VideoCard = ({ video }) => {
  const [videos, setvideos] = useState([] as TVideoSource[]);
  const [showSources, setShowSources] = useState(false);
  const [isOpened, setIsOpened] = useState(false);

  const fetchMedia = async (query: string) => {
    const media: TMediaResponse = await getMedia(query);
    console.log(media);
    const videosCopy = [...videos, ...media.videos];

    setvideos(videosCopy);
  };

  const toggleShowMedia = () => {
    setShowSources(!showSources);
  };

  const hideModal = () => {
    setShowSources(false);
  };

  useEffect(() => {
    const queries = video.chunks.map((c) => c.resource_query);

    queries.forEach((q) => {
      fetchMedia(q);
    });
  }, []);

  return (
    <div className="video-card">
      <h3>{video.title}</h3>
      <div>
        {video.chunks.map((c, index) => (
          <ScriptSection text={c.speech_text} key={index} />
        ))}
      </div>
      <SvgButton
        size="big"
        text="Show media"
        svg={<Icon name="Eye" size={20} />}
        onClick={toggleShowMedia}
      />
      {showSources && <VideoSources hide={hideModal} videos={videos} />}
    </div>
  );
};

const ScriptSection = ({ text }) => {
  return <div className="script-hovered">{text}</div>;
};

const VideoSources = ({ videos, hide }) => {
  return (
    <div>
      <Modal hide={hide}>
        {videos.map((video) => (
          <SourceVideo key={video.id} video={video} />
        ))}
      </Modal>
    </div>
  );
};

const SourceVideo = ({ video }) => {
  return (
    <div className="source-video-component">
      <img src={video.image} alt={`Thumbnail for video ${video.id}`} />
      <div className="source-video-info" style={{ marginBottom: "20px" }}>
        <h3>Video by {video.user.name}</h3>
        <p>Duration: {video.duration} seconds</p>
        <p>
          URL:{" "}
          <a href={video.url} target="_blank" rel="noopener noreferrer">
            {video.url}
          </a>
        </p>
        <div>
          <h4>Video Files:</h4>
          {video.video_files.map((file) => (
            <div key={file.id}>
              <span>{file.quality}</span>
              <span>
                Resolution: {file.width}x{file.height}
              </span>
              <span>
                Link:{" "}
                <a href={file.link} target="_blank" rel="noopener noreferrer">
                  Download
                </a>
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
