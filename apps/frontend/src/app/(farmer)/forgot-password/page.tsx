import type { Metadata } from "next";
import ForgotPasswordFlow from "./forgot-password-flow";

export const metadata: Metadata = {
  title: "Reset your password — AgroAI",
  description:
    "Forgot your AgroAI password? Recover your account in three quick steps — email, verification code, and a new password.",
};

export default function ForgotPasswordPage() {
  return <ForgotPasswordFlow />;
}
