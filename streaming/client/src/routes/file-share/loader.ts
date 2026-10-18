import { LoaderFunctionArgs } from "react-router-dom";

import { getFileShare, TFileShare } from "../../modules/apiCalls";

export const fileShareLoader = async ({
  params,
}: LoaderFunctionArgs): Promise<TFileShare | null> => {
  try {
    const data = await getFileShare(params.shareId as string);
    return data ?? null;
  } catch (e) {
    console.log(e);
  }
  return null;
};
