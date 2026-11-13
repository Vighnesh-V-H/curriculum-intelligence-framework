import { Suspense } from "react";
import CurriculumDetailClient from "./page-client";

export default function CurriculumDetailPage() {
  return <Suspense fallback={<main className="academic-page" role="status">Loading curriculum…</main>}>
    <CurriculumDetailClient />
  </Suspense>;
}
