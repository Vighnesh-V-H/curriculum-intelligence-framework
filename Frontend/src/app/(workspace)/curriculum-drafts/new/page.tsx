import { redirect } from "next/navigation";

export default function LegacyDraftStudioPage(): never {
  redirect("/generate-curriculum");
}
