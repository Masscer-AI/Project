import io from "socket.io-client";

// Clase para manejar WebSocket
export class SocketManager {
  socket: any;

  constructor(serverUrl) {
    this.socket = io(serverUrl, {
      transports: ["websocket", "polling"]
    });

    this.socket.on("connect", () => {
      console.log(`Connected to socket server at ${serverUrl}`);
    });

    this.socket.on("disconnect", () => {
      console.log("Disconnected from socket server");
    });
  }

  on(event, callback) {
    this.socket.on(event, callback);
  }

  off(event) {
    this.socket.off(event);
  }

  emit(event, data) {
    this.socket.emit(event, data);
  }

  disconnect() {
    this.socket.disconnect();
  }
}
