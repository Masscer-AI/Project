import React, { useEffect, useState } from "react";
import styles from "./Landing.module.css";
export const Landing = () => {
  return (
    <>
      <div className={styles.landingComponent}>
        <section>
          <h1 className="text-center">Welcome to Masscer AI</h1>
          <WrittingText text="AI is changing our lives, we know it, and our focus is let you create professional grade AI agents customize it to your unique special needs" />
        </section>
      </div>
      <div className="d-flex flex-y gap-big padding-medium">
        <Carousel
          sections={[
            <CreateAIAgents />,
            <AutomateWhatsApp />,
            <GenerateMedia />,
          ]}
      />
      </div>
    </>
  );
};

const Carousel = ({ sections }: { sections: React.ReactNode[] }) => {
  const [currentSection, setCurrentSection] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentSection((prev) => (prev + 1) % sections.length);
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  return <div className="carousel">{sections[currentSection]}</div>;
};

const WrittingText = ({ text }: { text: string }) => {
  return <h3 className="text-center">{text}</h3>;
};

const CreateAIAgents = () => {
  return (
    <div className="call-to-action">
      <h3>Create AI Agents effortlessly!</h3>
      <p>
        Focus on what matters to you, we take care of the rest. Create AI Agents
        effortlessly with your user data. Use these Agents to answer WhatsApp
        messages, create videos, documents, and much more!
      </p>
    </div>
  );
};

const AutomateWhatsApp = () => {
  return (
    <div className="call-to-action">
      <h3>Automate WhatsApp messages</h3>
      <p>Automate WhatsApp messages with your AI Agent.</p>
    </div>
  );
};

const GenerateMedia = () => {
  return (
    <div className="call-to-action">
      <h3>Generate any kind of media!</h3>
      <p>
        As a team of creators, one focus in out application is to make the
        creative process easier and productive.
      </p>
      <h4>Generate:</h4>
      <ul>
        <li>Videos</li>
        <li>Images</li>
        <li>Documents</li>
        <li>Transcriptions</li>
      </ul>
    </div>
  );
};
