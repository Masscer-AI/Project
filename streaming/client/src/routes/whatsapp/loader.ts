import { getWhatsappNumbers } from "../../modules/apiCalls";

export const whatsappLoader = async () => {
  const numbers = await getWhatsappNumbers();

  return { numbers };
};
