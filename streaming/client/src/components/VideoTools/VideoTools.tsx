import React, { useState } from "react";
import { requestVideoGeneration } from "../../modules/apiCalls";
import toast from "react-hot-toast";
import "./VideoTools.css"
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
        toast.error("Something happened requesting the video generation, check the console for more info");
        console.error("Error generating video:", error);
      }
    } else {
      alert("Please fill in all fields.");
    }
  };

  return (
    <main className="video-tools flex-y">
      <h4>What do you want to do with video?</h4>
      <select name="action" value={state.action} onChange={handleChange}>
        <option value="shorts">Generate Shorts</option>
        <option value="scripts">Write Video Scripts</option>
      </select>

      {state.action === "shorts" && (
        <form className="flex-y">
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
              {/* Updated to match model */}
              <option value="SQUARE">Square</option>{" "}
              {/* Updated to match model */}
              <option value="PORTRAIT">Portrait</option>{" "}
              {/* Updated to match model */}
            </select>
          </label>

          <button type="button" onClick={handleGenerate}>
            Generate
          </button>
        </form>
      )}
    </main>
  );
};
