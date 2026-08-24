import { LoaderFunctionArgs } from "react-router-dom";

import {
  getPublicSignatureRequest,
  TPublicSignatureRequest,
} from "../../modules/apiCalls";

export const signatureRequestLoader = async ({
  params,
}: LoaderFunctionArgs): Promise<TPublicSignatureRequest | null> => {
  const id = params.signatureRequestId as string;
  try {
    const data = await getPublicSignatureRequest(id);
    return data;
  } catch (e) {
    console.log(e);
  }
  return null;
};
