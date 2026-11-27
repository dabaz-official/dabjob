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
