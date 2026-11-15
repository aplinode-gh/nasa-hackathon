import type { Metadata } from "next";
import ForgotPasswordFlow from "./forgot-password-flow";

export const metadata: Metadata = {
  title: "Reset your password — agro ai",
  description:
    "Forgot your agro ai password? Recover your account in three quick steps — email, verification code, and a new password.",
};

export default function ForgotPasswordPage() {
  return <ForgotPasswordFlow />;
}
