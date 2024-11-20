import toast from "react-hot-toast";

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

    URL.revokeObjectURL(audioUrl);
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
      const link = document.createElement("a");
      link.href = audioUrl;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(audioUrl);
    },
    destroy: () => {
      audio.pause();
      URL.revokeObjectURL(audioUrl);
    },
  };
};

export type AudioPlayerWithAppendOptions = {
  append: (position: number, audioData: ArrayBuffer) => void;
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
  const currentBytes: ArrayBuffer[] = [];
  let totalLength = 0;
  let isPlaying = false;
  let currentPosition = 0;

  const append = (position: number, audioData: ArrayBuffer) => {
    currentBytes.push(audioData);
    totalLength += audioData.byteLength;

    const audioBlob = new Blob(currentBytes, { type: "audio/mp3" });
    const audioUrl = URL.createObjectURL(audioBlob);

    audioElement.src = audioUrl;
    audioElement.currentTime = currentPosition;
    toast.success(`Audio appended. Total length: ${totalLength} bytes.`);

    // Check if we have at least 1 MB of audio and play if not already playing
    if (totalLength >= 1048576 && !isPlaying) {
      play(); // Start playback if we have enough data
    }
  };

  const replace = (audioData: ArrayBuffer) => {
    currentBytes.length = 0;
    currentBytes.push(audioData);
    totalLength = audioData.byteLength;

    const audioBlob = new Blob(currentBytes, { type: "audio/mp3" });
    const audioUrl = URL.createObjectURL(audioBlob);

    audioElement.src = audioUrl;
    audioElement.currentTime = 0;
    // toast.success(`Audio replaced. Total length: ${totalLength} bytes.`);
  };

  const play = () => {
    if (isPlaying) {
      console.warn("Audio is already playing.");
      return;
    }

    toast.success("Trying to play audio in the new audio player");

    audioElement
      .play()
      .then(() => {
        isPlaying = true;
        audioElement.onended = () => {
          isPlaying = false; // Reset the flag when playback ends
          currentPosition = 0; // Reset position for next playback
          if (typeof onFinish === "function") {
            onFinish(); // Call onFinish if provided
          }

          // Check if we have new audio data to play
          const audioBlob = new Blob(currentBytes, { type: "audio/mp3" });
          const audioUrl = URL.createObjectURL(audioBlob);
          audioElement.src = audioUrl; // Update to the latest audio
          audioElement.play(); // Start playing the updated audio
          isPlaying = true; // Set isPlaying to true again
        };
      })
      .catch((err) => {
        console.error("Error playing audio:", err);
      });
  };

  const pause = () => {
    if (!isPlaying) {
      toast.error("Nothing is currently playing to pause.");
      return;
    }

    toast.success("Paused audio.");
    currentPosition = audioElement.currentTime;
    audioElement.pause();
    isPlaying = false;
  };

  const stop = () => {
    audioElement.pause();
    audioElement.currentTime = 0;
    isPlaying = false;
  };

  const download = (filename = "audio.mp3") => {
    const audioBlob = new Blob(currentBytes, { type: "audio/mp3" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(audioBlob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const destroy = () => {
    audioElement.pause();
    audioElement.src = "";
    currentBytes.length = 0;
  };

  return {
    append,
    play,
    pause,
    stop,
    download,
    destroy,
    replace
  };
};
