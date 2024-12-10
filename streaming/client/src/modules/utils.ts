import axios from "axios";

export const playAudioFromBytes = (audioFile) => {
  const audioBlob = new Blob([audioFile], { type: "audio/mp3" });
  const audioUrl = URL.createObjectURL(audioBlob);
  const audio = new Audio(audioUrl);
  audio.play();
};

export const debounce = (func: Function, delay: number) => {
  let timeoutId;
  return (...args: any[]) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      func(...args);
    }, delay);
  };
};

export type AudioPlayerOptions = {
  play: () => void;
  pause: () => void;
  stop: () => void;
  download: (filename?: string) => void;
  destroy: () => void;
};

export const createAudioPlayer = (
  audioFile: BlobPart,
  onFinish?: () => void
): AudioPlayerOptions => {
  const audioBlob = new Blob([audioFile], { type: "audio/mp3" });
  const audioUrl = URL.createObjectURL(audioBlob);
  const audio = new Audio(audioUrl);

  audio.addEventListener("ended", () => {
    if (typeof onFinish === "function") {
      onFinish();
    }
  });

  return {
    play: () => {
      audio.play().catch((err) => console.error("Playback failed:", err));
    },
    pause: () => {
      audio.pause();
    },
    stop: () => {
      audio.pause();
      audio.currentTime = 0;
    },
    download: (filename = "audio.mp3") => {
      console.log("downloading audio");
      console.log(audioUrl);

      const link = document.createElement("a");
      link.href = audioUrl;
      link.download = filename;
      link.click();
    },
    destroy: () => {
      audio.pause();
      URL.revokeObjectURL(audioUrl);
    },
  };
};

export type AudioPlayerWithAppendOptions = {
  append: (audioData: ArrayBuffer) => void;
  play: () => void;
  pause: () => void;
  stop: () => void;
  download: (filename?: string) => void;
  destroy: () => void;
  replace: (audioData: ArrayBuffer) => void;
} & AudioPlayerOptions;

export const createAudioPlayerWithAppend = (
  onFinish?: () => void
): AudioPlayerWithAppendOptions => {
  const audioElement = new Audio();
  const mediaSource = new MediaSource();
  let sourceBuffer: SourceBuffer | null = null;
  let isPlaying = false;

  audioElement.src = URL.createObjectURL(mediaSource);

  mediaSource.addEventListener("sourceopen", () => {
    sourceBuffer = mediaSource.addSourceBuffer("audio/mp3");
    sourceBuffer.addEventListener("updateend", () => {
      if (isPlaying) {
        audioElement.play().catch((err) => {
          console.error("Playback error:", err);
        });
      }
    });
  });

  const append = (audioData: ArrayBuffer) => {
    if (!sourceBuffer || sourceBuffer.updating) {
      console.warn("SourceBuffer is updating or not initialized.");
      return;
    }

    sourceBuffer.appendBuffer(new Uint8Array(audioData));
    console.log(`Appended audio data: ${audioData.byteLength} bytes.`);
  };

  const play = () => {
    if (isPlaying) {
      console.warn("Audio is already playing.");
      return;
    }

    audioElement
      .play()
      .then(() => {
        isPlaying = true;
        audioElement.onended = () => {
          isPlaying = false; // Reset the flag when playback ends
          if (typeof onFinish === "function") {
            onFinish(); // Call onFinish if provided
          }
        };
      })
      .catch((err) => {
        console.error("Error playing audio:", err);
      });
  };

  const pause = () => {
    if (!isPlaying) {
      console.error("Nothing is currently playing to pause.");
      return;
    }

    audioElement.pause();
    isPlaying = false;
    console.log("Paused audio.");
  };

  const stop = () => {
    audioElement.pause();
    audioElement.currentTime = 0;
    isPlaying = false;
    console.log("Stopped audio.");
  };

  const download = (filename = "audio.mp3") => {
    console.log("Downloading audio...");
    // @ts-ignore
    const audioBlob = new Blob([sourceBuffer!.buffer], { type: "audio/mp3" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(audioBlob);
    link.download = filename;
    link.click();
  };

  const destroy = () => {
    audioElement.pause();
    audioElement.src = "";
    mediaSource.endOfStream();
    console.log("Audio player destroyed.");
  };

  return {
    append,
    play,
    pause,
    stop,
    download,
    destroy,
    replace: (audioData: ArrayBuffer) => {
      if (!sourceBuffer || sourceBuffer.updating) {
        console.warn("SourceBuffer is updating or not initialized.");
        return;
      }
      sourceBuffer!.abort();
      sourceBuffer!.appendBuffer(new Uint8Array(audioData));
      console.log("Audio replaced.");
    },
  };
};

const languageMap = {
  "en-US": "en",
  "en-GB": "en",
  "es-US": "es",
  "es-MX": "es",
  "fr-FR": "fr",
  "fr-CA": "fr",
  "de-DE": "de",
  "zh-CN": "zh",
  "zh-TW": "zh",
  "pt-BR": "pt",
  "pt-PT": "pt",
  "ja-JP": "ja",
  "ru-RU": "ru",
  "it-IT": "it",
  "ar-SA": "ar",
};

export const getPreferredLanguage = () => {
  const lang = navigator.language;

  const generalLanguage = languageMap[lang] || lang;

  return generalLanguage.substring(0, 2);
};

export const getStoredPreferences = () => {
  const storedPreferences = localStorage.getItem("userPreferences");
  if (storedPreferences) {
    return JSON.parse(storedPreferences);
  }
  return null;
};

// type TResponseFormat = "text" | "json";
// export const fetchUrlContent = async (
//   url: string,
//   responseFormat: TResponseFormat
// ) => {
//   try {
//     const response = await axios.get(url, { timeout: 5000 });
//     if (responseFormat === "text") {
//       return response.data;
//     } else if (responseFormat === "json") {
//       return response.data;
//     }
//   } catch (error) {
//     if (axios.isAxiosError(error)) {
//       console.error("Error fetching the URL content:", {
//         message: error.message,
//         code: error.code,
//         config: error.config,
//       });
//     } else {
//       console.error("Unexpected error:", error);
//     }
//     throw error; // Consider whether to throw or return a fallback value
//   }
// };
