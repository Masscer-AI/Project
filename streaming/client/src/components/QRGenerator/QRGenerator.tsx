import React, { useRef } from "react";
import { QRCodeSVG } from "qrcode.react";
import "./QRGenerator.css";

const isValidURL = (string) => {
  const res = string.match(/(http|https):\/\/[^\s/$.?#].[^\s]*/);
  return res !== null;
};

// import React, { useRef } from "react";
// import { QRCodeSVG } from "qrcode.react";
// import "./QRGenerator.css";

type TQRCodeDisplayProps = {
  url: string;
  size?: number;
  fgColor?: string;
  bgColor?: string;
  svgRef?: React.RefObject<SVGElement>;
};

export const QRCodeDisplay = ({
  url,
  size = 128,
  fgColor = "black",
  bgColor = "white",
}: TQRCodeDisplayProps) => {
  if (!url || !isValidURL(url)) {
    return <p>Por favor, proporciona una URL válida.</p>;
  }

  return (
    <div>
      <QRCodeSVG fgColor={fgColor} size={size} value={url} bgColor={bgColor} />
    </div>
  );
};

export const QRGenerator = ({ url }: { url }) => {
  const [input, setInput] = React.useState(url);
  const [size, setSize] = React.useState(128);
  const [fgColor, setFgColor] = React.useState("black");
  const [bgColor, setBgColor] = React.useState("white");
  const svgContainer = useRef<HTMLDivElement>(null);


    const downloadQRCode = () => {
      const container = svgContainer.current;
      if (!container) return;

      const svg = container.querySelector("svg");
      if (!svg) return;

      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const padding = 30; // Adjust this if your padding changes
      const totalSize = size + padding * 2; // Total size including padding

      canvas.width = totalSize;
      canvas.height = totalSize;

      // Fill canvas with background color
      ctx.fillStyle = bgColor;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      const svgData = new XMLSerializer().serializeToString(svg);
      const img = new Image();

      img.onload = () => {
        // Draw the QR code in the center
        ctx.drawImage(img, padding, padding, size, size);
        const png = canvas.toDataURL("image/png");

        const link = document.createElement("a");
        link.href = png;
        link.download = "qrcode.png";
        link.click();
      };

      img.src = `data:image/svg+xml;base64,${btoa(svgData)}`;
    };


  return (
    <div className="qr-generator" style={{ background: bgColor }}>
      <div className="flex-y gap-small ">
        <input
          type="text"
          value={input}
          className="input"
          onChange={(e) => setInput(e.target.value)}
          placeholder="Introduce la URL"
          style={{ color: fgColor }}
        />
        <input
          type="number"
          className="input"
          value={size}
          onChange={(e) => setSize(Number(e.target.value))}
          style={{ color: fgColor }}
          placeholder="Tamaño"
        />
        <input
          className="input"
          type="text"
          value={fgColor}
          onChange={(e) => setFgColor(e.target.value)}
          style={{ color: fgColor }}
          placeholder="Color"
        />
        <input
          style={{ color: fgColor }}
          className="input"
          type="text"
          value={bgColor}
          onChange={(e) => setBgColor(e.target.value)}
          placeholder="Color de fondo"
        />
        <button onClick={downloadQRCode}>Download QR Code</button>
      </div>
      <div
        ref={svgContainer}
        className="qr-container"
        // style={{ padding: "20px" }}
      >
        <QRCodeDisplay
          url={input}
          size={size}
          fgColor={fgColor}
          bgColor={bgColor}
        />
      </div>
    </div>
  );
};
