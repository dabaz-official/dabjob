export type JobSummary = {
  id: number;
  title: string;
  company_name: string;
  city: string | null;
  platform: string;
  url: string | null;
  salary_text: string | null;
  captured_at: string;
  snippet: string | null;
};

export type JobList = {
  items: JobSummary[];
  total: number;
};

export type PasteResult = {
  run_id: number;
  outcome: "accepted" | "duplicate";
  job: JobSummary | null;
  flags: string[];
};

export async function fetchJobs(query = ""): Promise<JobList> {
  const params = new URLSearchParams();
  const trimmed = query.trim();
  if (trimmed) {
    params.set("q", trimmed);
  }

  const response = await fetch(`/api/jobs?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`request failed with ${response.status}`);
  }
  return (await response.json()) as JobList;
}

export async function pasteJob(text: string): Promise<PasteResult> {  const response = await fetch("/api/ingest/paste", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) {
    throw new Error(`request failed with ${response.status}`);
  }
  return (await response.json()) as PasteResult;
}

export type JobChanges = {
  title?: string;
  company_name?: string;
  city?: string | null;
  url?: string | null;
  salary_text?: string | null;
  seniority?: string | null;
};

export async function updateJob(id: number, changes: JobChanges): Promise<JobSummary> {
  const response = await fetch(`/api/jobs/${id}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(changes),
  });
  if (!response.ok) {
    throw new Error(`request failed with ${response.status}`);
  }
  return (await response.json()) as JobSummary;
}

export type ProfileDocument = {
  id: number;
  kind: string;
  filename: string;
  content_type: string | null;
  char_count: number;
  created_at: string;
};

export type ProfileDocumentDetail = ProfileDocument & {
  extracted_text: string;
};

export async function uploadDocument(file: File, kind = "resume"): Promise<ProfileDocument> {
  const body = new FormData();
  body.append("file", file);
  body.append("kind", kind);

  const response = await fetch("/api/profile/documents", { method: "POST", body });
  if (!response.ok) {
    const detail = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(detail?.detail ?? `request failed with ${response.status}`);
  }
  return (await response.json()) as ProfileDocument;
}

export async function fetchDocument(id: number): Promise<ProfileDocumentDetail> {
  const response = await fetch(`/api/profile/documents/${id}`);
  if (!response.ok) {
    throw new Error(`request failed with ${response.status}`);
  }
  return (await response.json()) as ProfileDocumentDetail;
}

export type Profile = {
  id: number;
  years_experience: number | null;
  target_roles: string[];
  target_cities: string[];
  salary_floor: number | null;
  strengths: string | null;
  gaps: string | null;
  positioning: string | null;
  target_fit: string | null;
  updated_at: string;
};

export type ProfileChanges = Partial<
  Pick<
    Profile,
    | "years_experience"
    | "target_roles"
    | "target_cities"
    | "salary_floor"
    | "strengths"
    | "gaps"
    | "positioning"
    | "target_fit"
  >
>;

export type AssessmentDraft = {
  task_id: number;
  transport: string;
  strengths: string[];
  gaps: string[];
  target_fit: string;
  positioning: string;
};

export async function fetchProfile(): Promise<Profile> {
  const response = await fetch("/api/profile");
  if (!response.ok) {
    throw new Error(`request failed with ${response.status}`);
  }
  return (await response.json()) as Profile;
}

export async function saveProfile(changes: ProfileChanges): Promise<Profile> {
  const response = await fetch("/api/profile", {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(changes),
  });
  if (!response.ok) {
    throw new Error(`request failed with ${response.status}`);
  }
  return (await response.json()) as Profile;
}

export async function generateAssessment(): Promise<AssessmentDraft> {
  const response = await fetch("/api/profile/assessment", { method: "POST" });
  if (!response.ok) {
    const detail = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(detail?.detail ?? `request failed with ${response.status}`);
  }
  return (await response.json()) as AssessmentDraft;
}
