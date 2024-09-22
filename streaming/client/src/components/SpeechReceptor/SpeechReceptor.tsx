import React, { useEffect, useRef } from "react";
import { Socket } from "socket.io-client";

interface SpeechReceptorProps {
  socket: Socket;
}

export const SpeechReceptor: React.FC<SpeechReceptorProps> = ({
  socket,
}) => {
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const mediaSourceRef = useRef<MediaSource>(new MediaSource());

  useEffect(() => {
    const audioElement = audioElementRef.current;
    const mediaSource = mediaSourceRef.current;

    if (audioElement) {
      audioElement.src = URL.createObjectURL(mediaSource);

      mediaSource.addEventListener("sourceopen", () => {
        const sourceBuffer = mediaSource.addSourceBuffer("audio/mpeg");

        socket.on("audio-chunk", (data: ArrayBuffer) => {
          console.log("Reciving audio chunk!");

          const byteArray = new Uint8Array(data);
          sourceBuffer.appendBuffer(byteArray);

          if (audioElement.paused) {
            audioElement.play().catch((error) => {
              console.error("Error al reproducir el audio:", error);
            });
          }
        });

        sourceBuffer.addEventListener("updateend", () => {
          console.log("The source buffer has ended!");

          if (mediaSource.readyState === "open" && !sourceBuffer.updating) {
            mediaSource.endOfStream();
          }
        });

        // Add event listener to detect when audio playback has ended
        audioElement.addEventListener("ended", () => {
          console.log("Audio playback ended, cleaning up source buffer (in theory)");
          // if (sourceBuffer) {
          //   // Extract buffered data and create a Blob
          //   const bufferedData = sourceBuffer.buffered;
          //   const chunks: Uint8Array[] = [];
          //   for (let i = 0; i < bufferedData.length; i++) {
          //     const start = bufferedData.start(i);
          //     const end = bufferedData.end(i);
          //     const chunk = new Uint8Array(end - start);
          //     const tempBuffer = new Uint8Array(
          //       sourceBuffer.buffered.end(i) - sourceBuffer.buffered.start(i)
          //     );
          //     tempBuffer.set(chunk, 0);
          //     chunks.push(tempBuffer);
          //   }
          //   const blob = new Blob(chunks, { type: "audio/mpeg" });
          // }
        });
      });
    }

    return () => {
      socket.disconnect();
    };
  }, [socket]);

  return <audio ref={audioElementRef} controls />;
};
