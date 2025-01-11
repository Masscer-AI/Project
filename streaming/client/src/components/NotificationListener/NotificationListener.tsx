import React, { useEffect } from "react";
import { useStore } from "../../modules/store";
import toast from "react-hot-toast";

export const NotificationListener = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const { socket } = useStore((state) => ({
    socket: state.socket,
  }));

  useEffect(() => {
    console.log("NotificationListener");
    socket.on("video_generated", (data) => {
      console.log(data, "VIDEO GENERATED");
      toast.success("Video generated");
    });
  }, []);
  return <>{children}</>;
};
