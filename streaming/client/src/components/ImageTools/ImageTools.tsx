import React from "react";
export const ImageTools = () => (
  <main className="centered-container flex-y">
    <h4>What do you want to do with images?</h4>
    <select>
      <option value="generate">Generate Images</option>
      <option value="edit">Edit Images</option>
    </select>
  </main>
);
