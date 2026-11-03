import { LoaderFunction, redirect } from "react-router-dom";
import { resolveAuthenticatedHome } from "../../utils/loginRedirect";

export const rootLoader: LoaderFunction = async () => {
  if (!localStorage.getItem("token")) {
    return null;
  }
  return redirect(await resolveAuthenticatedHome(null));
};
