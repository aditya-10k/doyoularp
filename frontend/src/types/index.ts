export type VerdictType = "SUPPORTED" | "PARTIALLY_SUPPORTED" | "UNVERIFIED" | "CONTRADICTED";

export interface Evaluation {
  id: string;
  verdict: VerdictType;
  confidence: number;
  reasoning: string;
  evidence_ids: string[];
}

export interface Claim {
  id: string;
  claim_text: string;
  category: string;
  section?: string | null;
  source_text: string;
  page_number: number;
  evaluation?: Evaluation | null;
}

export interface EvidenceItem {
  id: string;
  evidence_type: string;
  title: string;
  content: string;
  url?: string | null;
  created_at: string;
}

export interface SourceSummary {
  type: string;
  url: string;
  status: string;
}

export interface AnalysisStatus {
  analysis_id: string;
  candidate_alias: string;
  status: "created" | "running" | "completed" | "failed";
  stage: string;
  progress: number;
  created_at: string;
  completed_at?: string | null;
  error?: string | null;
}

export interface ResultResponse {
  analysis_id: string;
  anonymous_alias: string;
  larp_score: number;
  roast: string;
  verdict_summary: string;
  strongest_claim?: string | null;
  weakest_claim?: string | null;
  funny_mismatch?: string | null;
  claims_count: number;
  claims_breakdown: Claim[];
  sources: SourceSummary[];
  leaderboard_token: string;
  completed_at?: string | null;
}

export interface LeaderboardEntryItem {
  rank: number;
  anonymous_alias: string;
  larp_score: number;
  roast: string;
  created_at: string;
}

export interface LeaderboardResponse {
  total: number;
  user_entry?: LeaderboardEntryItem | null;
  leaderboard: LeaderboardEntryItem[];
}
