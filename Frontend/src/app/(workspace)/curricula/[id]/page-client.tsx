"use client";

import { useParams } from "next/navigation";
import CurriculumWorkspace from "../../curriculum-workspace";

export default function CurriculumDetailClient() {
  const params = useParams<{ id: string }>();
  return <CurriculumWorkspace curriculumId={params.id} />;
}
