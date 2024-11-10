import React from "react";
import { QRCodeSVG } from "qrcode.react";
import toast from "react-hot-toast";

const isValidURL = (string) => {
  const res = string.match(/(http|https):\/\/[^\s/$.?#].[^\s]*/);
  return res !== null;
};

const QRCodeDisplay = ({ url }) => {
  // Verify if the URL is valid
  if (!url || !isValidURL(url)) {
    return <p>Por favor, proporciona una URL válida.</p>;
  }

  // Encode the URL before passing it to QRCodeSVG
  // const encodedUrl = encodeURIComponent(url);

  // toast.success(encodedUrl);
  console.log("");

  // return <QRCodeSVG value={encodedUrl} />;
  return <QRCodeSVG value={url} />;
};

export default QRCodeDisplay;
