import io, { Socket } from "socket.io-client";

// Clase para manejar WebSocket
export class SocketManager {
  socket: Socket;

  constructor(serverUrl: string) {
    console.log(`SocketManager: Connecting to ${serverUrl}`);
    this.socket = io(serverUrl, {
      transports: ["websocket", "polling"],
      path: "/socket.io/",
    });

    this.socket.on("connect", () => {
      console.log(`SocketManager: Connected to socket server at ${serverUrl}`);
    });

    this.socket.on("disconnect", (reason) => {
      console.log(`SocketManager: Disconnected from socket server. Reason: ${reason}`);
    });

    this.socket.on("connect_error", (error) => {
      console.error(`SocketManager: Connection error to ${serverUrl}:`, error);
    });
  }

  on(event, callback) {
    this.socket.on(event, callback);
  }

  off(event, callback?: (...args: any[]) => void) {
    if (callback) {
      this.socket.off(event, callback);
    } else {
      this.socket.off(event);
    }
  }

  emit(event, data) {
    this.socket.emit(event, data);
  }

  registerWidgetSession(routeKey: string) {
    this.socket.emit("register_widget_session", routeKey);
  }

  disconnect() {
    this.socket.disconnect();
  }
}
