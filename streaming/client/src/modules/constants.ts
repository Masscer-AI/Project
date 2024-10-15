export const API_URL = "http://127.0.0.1:8000";
export const STREAMING_BACKEND_URL = "http://127.0.0.1:8001";
export const PUBLIC_TOKEN = "5ce40b5c8ea34599957efb54f7c5f8a9";

export function getRandomWordsAndSlug() {
  const randomWords = [
    "apple",
    "banana",
    "cherry",
    "date",
    "elderberry",
    "fig",
    "grape",
    "honeydew",
    "kiwi",
    "lemon",
    "mango",
    "nectarine",
    "orange",
    "papaya",
    "quince",
    "raspberry",
    "strawberry",
    "tangerine",
    "ugli",
    "vanilla",
    "watermelon",
    "xigua",
    "yam",
    "zucchini",
    "avocado",
    "blueberry",
    "cantaloupe",
    "dragonfruit",
    "eggplant",
    "fennel",
    "guava",
    "huckleberry",
    "jackfruit",
    "kumquat",
    "lime",
    "mulberry",
    "olive",
    "peach",
    "plum",
    "starfruit",
  ];

  // Shuffle the array and select the first three words
  const selectedWords = randomWords.sort(() => 0.5 - Math.random()).slice(0, 3);

  // Create a slugified version by joining the words with hyphens
  const slug = selectedWords.join("-").toLowerCase();

  return {
    name: selectedWords.join(" "),
    slug: slug,
  };
}

