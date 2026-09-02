import { LoaderFunction, redirect } from "react-router-dom";
import { loginUrlWithNext, resolveAuthenticatedHome } from "../../utils/loginRedirect";

export const homeLoader: LoaderFunction = async () => {
  if (!localStorage.getItem("token")) {
    return redirect(loginUrlWithNext("/home"));
  }
  return redirect(await resolveAuthenticatedHome(null));
};
