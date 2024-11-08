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
};

export const createAudioPlayer = (audioFile: BlobPart, onFinish?: () => void): AudioPlayerOptions => {
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
  };
};
