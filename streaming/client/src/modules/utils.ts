import TurndownService from "turndown";
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

const turndownService = new TurndownService();

export const convertHtmlToMarkdown = (html: string): string => {
  return turndownService.turndown(html);
};
