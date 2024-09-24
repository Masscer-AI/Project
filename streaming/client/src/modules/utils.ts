export const playAudioFromBytes = (audioFile) => {
    const audioBlob = new Blob([audioFile], { type: "audio/mp3" });
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    audio.play();
  };