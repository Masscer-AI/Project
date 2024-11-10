import React from "react";
import { QRCodeSVG } from "qrcode.react";

const QRCodeDisplay = ({ url }) => {
  // Verifica si la URL es válida
  if (!url) {
    return <p>No se ha proporcionado ninguna URL.</p>;
  }

  return (
    <div>
      {/* <QRCode
        value={url}
        size={256} // Tamaño del QR
        style={{ maxWidth: '100%', height: 'auto' }} // Mantiene las proporciones
      /> */}
      <QRCodeSVG value="https://reactjs.org/" />
    </div>
  );
};

export default QRCodeDisplay;
