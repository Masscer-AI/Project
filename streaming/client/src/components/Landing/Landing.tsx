import React, { useEffect, useState } from "react";
import styles from "./Landing.module.css";

export const Landing = () => {
  return (
    <>
      <div className={styles.landingComponent}>
        <section className={styles.heroContent}>
          <h1 className={styles.heroTitle}>
            Welcome to <span className={styles.highlight}>Masscer AI</span>
          </h1>
          <WrittingText text="AI is changing our lives, we know it, and our focus is let you create professional grade AI agents customize it to your unique special needs" />
        </section>
      </div>
      <div className={styles.carouselContainer}>
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
    }, 7000);

    return () => clearInterval(interval);
  }, [sections.length]);

  const goToSection = (index: number) => {
    setCurrentSection(index);
  };

  return (
    <div className={styles.carouselWrapper}>
      <div className={styles.carousel}>
        <div
          className={styles.carouselContent}
          style={{
            transform: `translateX(-${currentSection * 100}%)`,
          }}
        >
          {sections.map((section, index) => (
            <div key={index} className={styles.carouselSlide}>
              {section}
            </div>
          ))}
        </div>
      </div>
      <div className={styles.carouselIndicators}>
        {sections.map((_, index) => (
          <button
            key={index}
            className={`${styles.indicator} ${
              index === currentSection ? styles.indicatorActive : ""
            }`}
            onClick={() => goToSection(index)}
            aria-label={`Go to slide ${index + 1}`}
          />
        ))}
      </div>
    </div>
  );
};

const WrittingText = ({ text }: { text: string }) => {
  return <p className={styles.heroSubtitle}>{text}</p>;
};

const CreateAIAgents = () => {
  return (
    <div className={styles.featureCard}>
      <div className={styles.featureIcon}>🤖</div>
      <h3 className={styles.featureTitle}>Create AI Agents effortlessly!</h3>
      <p className={styles.featureDescription}>
        Focus on what matters to you, we take care of the rest. Create AI Agents
        effortlessly with your user data. Use these Agents to answer WhatsApp
        messages, create videos, documents, and much more!
      </p>
    </div>
  );
};

const AutomateWhatsApp = () => {
  return (
    <div className={styles.featureCard}>
      <div className={styles.featureIcon}>💬</div>
      <h3 className={styles.featureTitle}>Automate WhatsApp messages</h3>
      <p className={styles.featureDescription}>
        Automate WhatsApp messages with your AI Agent. Let your AI handle
        customer inquiries, support tickets, and conversations 24/7.
      </p>
    </div>
  );
};

const GenerateMedia = () => {
  return (
    <div className={styles.featureCard}>
      <div className={styles.featureIcon}>🎨</div>
      <h3 className={styles.featureTitle}>Generate any kind of media!</h3>
      <p className={styles.featureDescription}>
        As a team of creators, one focus in our application is to make the
        creative process easier and productive.
      </p>
      <div className={styles.featureList}>
        <span className={styles.featureTag}>Videos</span>
        <span className={styles.featureTag}>Images</span>
        <span className={styles.featureTag}>Documents</span>
        <span className={styles.featureTag}>Transcriptions</span>
      </div>
    </div>
  );
};
