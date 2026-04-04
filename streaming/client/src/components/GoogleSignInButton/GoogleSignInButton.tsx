import { useGoogleLogin } from "@react-oauth/google";
import { toast } from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Button } from "@mantine/core";
import { IconBrandGoogle } from "@tabler/icons-react";

type Props = {
  onAccessToken: (accessToken: string) => Promise<void>;
  disabled?: boolean;
};

/**
 * Must render only when inside GoogleOAuthProvider (see main.tsx + hasGoogleOAuthClientId).
 */
export function GoogleSignInButton({ onAccessToken, disabled }: Props) {
  const { t } = useTranslation();

  const loginWithGoogle = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      await onAccessToken(tokenResponse.access_token);
    },
    onError: () => toast.error(t("an-error-occurred")),
  });

  return (
    <Button
      type="button"
      onClick={() => loginWithGoogle()}
      fullWidth
      size="md"
      variant="default"
      leftSection={<IconBrandGoogle size={18} />}
      disabled={disabled}
    >
      Continue with Google
    </Button>
  );
}
