"use client";

import {
  ChangeEvent,
  FormEvent,
  useRef,
  useState,
} from "react";
import { SparklesIcon } from "lucide-react";
import { toast } from "sonner";

import { ApiError, CurriculumDraft, api } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md", ".csv"];
const MAX_FILE_MB = 20;
const MAX_FILES = 5;

function fileExtension(filename: string): string {
  const dot = filename.lastIndexOf(".");
  if (dot <= 0) {
    return "";
  }
  return filename.slice(dot).toLowerCase();
}

function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function validateFiles(files: File[]): string | null {
  if (files.length < 1) {
    return "Select at least one file.";
  }
  if (files.length > MAX_FILES) {
    return `Select at most ${MAX_FILES} files per draft.`;
  }
  for (const file of files) {
    if (!ALLOWED_EXTENSIONS.includes(fileExtension(file.name))) {
      return `"${file.name}" is not supported. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`;
    }
    if (file.size === 0) {
      return `"${file.name}" is empty.`;
    }
    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      return `"${file.name}" exceeds the ${MAX_FILE_MB} MB limit.`;
    }
  }
  return null;
}

export function GenerateCurriculumDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<CurriculumDraft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const formRef = useRef<HTMLFormElement>(null);

  function handleOpenChange(next: boolean) {
    if (!next) {
      setFiles([]);
      setDraft(null);
      setError(null);
      setBusy(false);
      formRef.current?.reset();
    }
    onOpenChange(next);
  }

  function close() {
    onOpenChange(false);
  }

  function startOver() {
    setDraft(null);
    setFiles([]);
    setError(null);
    formRef.current?.reset();
  }

  function handleFilesChanged(event: ChangeEvent<HTMLInputElement>) {
    setFiles(Array.from(event.target.files ?? []));
    setError(null);
  }

  async function handleGenerate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateFiles(files);
    setError(validationError);
    if (validationError) {
      return;
    }
    setBusy(true);
    try {
      const response = await api.generateCurriculumDraft(files);
      setDraft(response);
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : "Could not reach the curriculum service.";
      toast.error("Draft generation failed", { description: message });
    } finally {
      setBusy(false);
    }
  }

  const mappingLevels = new Map<string, 1 | 2 | 3>(
    draft?.mappings.map((mapping) => [
      `${mapping.course_code}|${mapping.course_outcome_code}|${mapping.program_outcome_code}`.toUpperCase(),
      mapping.level,
    ]) ?? [],
  );
  const poCodes = draft?.pos.map((po) => po.code.toUpperCase()) ?? [];

  if (draft) {
    return (
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="curriculum-dialog sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Generated curriculum draft</DialogTitle>
            <DialogDescription>
              AI suggestion from your files. Review it before turning it into
              real curricula, outcomes, and mappings.
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh] px-1">
            <div className="flex flex-col gap-4 pr-3">
              <Card>
                <CardHeader>
                  <CardTitle>
                    {draft.program.name ?? "Generated program"}
                  </CardTitle>
                  <CardDescription>{draft.program.summary}</CardDescription>
                  <div className="flex flex-wrap gap-2">
                    {draft.program.degree ? (
                      <Badge variant="secondary">{draft.program.degree}</Badge>
                    ) : null}
                    {draft.program.duration_years ? (
                      <Badge variant="secondary">
                        {draft.program.duration_years} years
                      </Badge>
                    ) : null}
                  </div>
                </CardHeader>
              </Card>

              <div className="flex flex-col gap-3">
                <h3 className="text-sm font-semibold text-foreground">
                  Curriculum roadmap
                </h3>
                {draft.semesters.map((semester) => (
                  <Card key={semester.semester_number}>
                    <CardHeader>
                      <CardTitle className="text-base">
                        {`Semester ${semester.semester_number}`} ·{" "}
                        {semester.semester_name}
                      </CardTitle>
                      <CardDescription>{semester.focus}</CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-3 sm:grid-cols-2">
                      {semester.courses.map((course) => (
                        <div
                          key={course.code}
                          className="rounded-lg border bg-muted/30 p-3"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="outline">{course.code}</Badge>
                            <p className="text-sm font-semibold text-foreground">
                              {course.title}
                            </p>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            <Badge variant="secondary">{course.category}</Badge>
                            {course.credits ? (
                              <Badge variant="secondary">
                                {course.credits} credits
                              </Badge>
                            ) : null}
                          </div>
                          <p className="mt-2 text-xs text-muted-foreground">
                            {course.summary}
                          </p>
                          <Separator className="my-2" />
                          <ul className="flex flex-col gap-1.5">
                            {course.outcomes.map((outcome) => (
                              <li
                                key={outcome.code}
                                className="flex gap-2 text-xs text-muted-foreground"
                              >
                                <Badge variant="outline" className="shrink-0">
                                  {outcome.code}
                                </Badge>
                                <span>{outcome.statement}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                ))}
              </div>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    Program educational objectives (PEO)
                  </CardTitle>
                  <CardDescription>
                    Long-term outcomes for graduates of this program.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="flex flex-col gap-2">
                    {draft.peos.map((peo) => (
                      <li
                        key={peo.code}
                        className="flex gap-2 text-sm text-muted-foreground"
                      >
                        <Badge variant="secondary" className="shrink-0">
                          {peo.code}
                        </Badge>
                        <span>{peo.statement}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">CO–PO mapping</CardTitle>
                  <CardDescription>
                    How strongly each course outcome supports a program
                    outcome (1 low, 2 moderate, 3 high).
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {poCodes.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No program outcomes were generated for this draft.
                    </p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-28">Course</TableHead>
                          <TableHead className="w-16">CO</TableHead>
                          {poCodes.map((code) => (
                            <TableHead key={code}>{code}</TableHead>
                          ))}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {draft.semesters.flatMap((semester) =>
                          semester.courses.flatMap((course) =>
                            course.outcomes.map((outcome) => (
                              <TableRow key={`${course.code}|${outcome.code}`}>
                                <TableCell className="font-mono text-xs font-medium">
                                  {course.code}
                                </TableCell>
                                <TableCell className="font-mono text-xs">
                                  {outcome.code}
                                </TableCell>
                                {poCodes.map((code) => {
                                  const level = mappingLevels.get(
                                    `${course.code}|${outcome.code}|${code}`.toUpperCase(),
                                  );
                                  return (
                                    <TableCell
                                      key={code}
                                      className="text-center text-xs font-semibold text-foreground"
                                    >
                                      {level ?? "—"}
                                    </TableCell>
                                  );
                                })}
                              </TableRow>
                            )),
                          ),
                        )}
                      </TableBody>
                    </Table>
                  )}
                  {draft.mappings.length === 0 ? (
                    <p className="mt-2 text-xs text-muted-foreground">
                      No mappings were generated for this draft.
                    </p>
                  ) : null}
                </CardContent>
              </Card>
            </div>
          </ScrollArea>
          <DialogFooter>
            <Button variant="outline" onClick={startOver}>
              Start over
            </Button>
            <Button onClick={close}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="curriculum-dialog sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Generate a curriculum draft</DialogTitle>
          <DialogDescription>
            Select the files describing your program — syllabi, regulations,
            or curriculum outlines. Text is extracted and analyzed by the LLM
            to produce a roadmap-style draft with basic PEOs and CO–PO
            mappings.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleGenerate} className="flex flex-col gap-4">
          <FieldGroup>
            <Field data-invalid={error ? true : undefined}>
              <FieldLabel htmlFor="generate-curriculum-files">
                Curriculum files
              </FieldLabel>
              <Input
                id="generate-curriculum-files"
                type="file"
                multiple
                accept={ALLOWED_EXTENSIONS.join(",")}
                onChange={handleFilesChanged}
                disabled={busy}
              />
              <FieldDescription>
                {ALLOWED_EXTENSIONS.join(" · ")} — up to {MAX_FILES} files,{" "}
                {MAX_FILE_MB} MB each.
              </FieldDescription>
              {files.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {files.map((file, index) => (
                    <Badge key={index} variant="secondary">
                      {file.name} · {formatBytes(file.size)}
                    </Badge>
                  ))}
                </div>
              ) : null}
              {error ? (
                <Alert variant="destructive">
                  <AlertTitle>Selection is not valid</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              ) : null}
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={close} disabled={busy}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy || files.length < 1}>
              {busy ? (
                <>
                  <Spinner data-icon="inline-start" />
                  Drafting…
                </>
              ) : (
                <>
                  <SparklesIcon data-icon="inline-start" />
                  Generate draft
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
