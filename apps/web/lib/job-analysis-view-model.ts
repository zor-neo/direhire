import type { components } from "../../../contracts/generated/api-types";

export type JobDemandProfileContent = components["schemas"]["JobDemandProfileContent"];

export interface JobFacts {
  title: string;
  company: string;
  location: string;
  salary: string;
  canonicalUrl?: string;
  postedAt?: string;
}

export interface RoleRealityView {
  headline: string;
  primaryArchetype: string;
  primaryOccupation: string;
  secondaryOccupations: string[];
  titleAlignment: "ACCURATE" | "UNDERSTATES_SCOPE" | "OVERSTATES_SCOPE" | "MISLEADING";
  primaryMission: string;
  breadth: "SPECIALIZED" | "MODERATE" | "BROAD";
}

export interface SeniorityView {
  assessment: string;
  explicitMinYears?: number | null;
  explicitMaxYears?: number | null;
  reason: string;
  confidence: "HIGH" | "MEDIUM" | "LOW";
}

export interface EmployerPriorityCluster {
  name: string;
  priority: "CORE" | "IMPORTANT" | "SUPPORTING" | "PREFERRED";
  reason: string;
  evidence: string;
  evidenceStrength: "EXPLICIT" | "STRONGLY_IMPLIED" | "INFERRED";
}

export interface RequirementView {
  category: "ELIGIBILITY" | "CAPABILITY" | "PROFESSIONAL" | "PREFERRED";
  title: string;
  evidence: string;
  evidenceStrength: "EXPLICIT" | "STRONGLY_IMPLIED" | "INFERRED";
}

export interface ConstraintView {
  constraintType: string;
  description: string;
  evidenceStrength: "EXPLICIT" | "STRONGLY_IMPLIED" | "INFERRED";
}

export interface JobAnalysisViewModel {
  facts: JobFacts;
  roleReality: RoleRealityView;
  seniority: SeniorityView;
  priorities: {
    core: EmployerPriorityCluster[];
    important: EmployerPriorityCluster[];
    supporting: EmployerPriorityCluster[];
    preferred: EmployerPriorityCluster[];
  };
  requirements: RequirementView[];
  constraints: ConstraintView[];
  scenarios: string[];
  workLocationSummary?: string;
  workArrangementSummary?: string;
  remoteEligibility: string;
  overallConfidence: "HIGH" | "MEDIUM" | "LOW";
}

/** Transform concrete generated OpenAPI analysis payload into a presentation JobAnalysisViewModel. */
export function toJobAnalysisViewModel(
  analysis: JobDemandProfileContent | Record<string, unknown> | null | undefined,
  fallbackUrl?: string,
): JobAnalysisViewModel | null {
  if (!analysis) return null;

  // Type assertion for wrapped payload or direct content schema
  const content = (
    "role_reality" in analysis ? analysis : (analysis as { content?: JobDemandProfileContent }).content ?? analysis
  ) as JobDemandProfileContent;

  const realityRaw = content.role_reality || {};
  const seniorityRaw = content.seniority || {};
  const clustersRaw = Array.isArray(content.demand_clusters) ? content.demand_clusters : [];
  const reqsRaw = Array.isArray(content.requirements) ? content.requirements : [];
  const constraintsRaw = Array.isArray(content.job_constraints) ? content.job_constraints : [];

  const roleReality: RoleRealityView = {
    headline: realityRaw.headline ?? "Job Demand Analysis",
    primaryArchetype: realityRaw.primary_archetype ?? "GENERALIST",
    primaryOccupation: realityRaw.primary_occupation ?? "Role",
    secondaryOccupations: realityRaw.secondary_occupations ?? [],
    titleAlignment: realityRaw.title_alignment ?? "ACCURATE",
    primaryMission: realityRaw.primary_mission ?? "",
    breadth: realityRaw.breadth ?? "MODERATE",
  };

  const seniority: SeniorityView = {
    assessment: seniorityRaw.assessment ?? "UNCLEAR",
    explicitMinYears: seniorityRaw.explicit_min_years ?? null,
    explicitMaxYears: seniorityRaw.explicit_max_years ?? null,
    reason: seniorityRaw.reason ?? "",
    confidence: seniorityRaw.interpretation_confidence ?? "MEDIUM",
  };

  const priorities = {
    core: [] as EmployerPriorityCluster[],
    important: [] as EmployerPriorityCluster[],
    supporting: [] as EmployerPriorityCluster[],
    preferred: [] as EmployerPriorityCluster[],
  };

  for (const item of clustersRaw) {
    const cluster: EmployerPriorityCluster = {
      name: item.name,
      priority: item.priority,
      reason: item.reason,
      evidence: item.evidence,
      evidenceStrength: item.evidence_strength,
    };
    if (cluster.priority === "CORE") priorities.core.push(cluster);
    else if (cluster.priority === "IMPORTANT") priorities.important.push(cluster);
    else if (cluster.priority === "SUPPORTING") priorities.supporting.push(cluster);
    else priorities.preferred.push(cluster);
  }

  const requirements: RequirementView[] = reqsRaw.map((item) => ({
    category: item.category,
    title: item.title,
    evidence: item.evidence,
    evidenceStrength: item.evidence_strength,
  }));

  const constraints: ConstraintView[] = constraintsRaw.map((item) => ({
    constraintType: item.constraint_type,
    description: item.description,
    evidenceStrength: item.evidence_strength,
  }));

  const scenarios = content.real_work_scenarios ?? [];
  const locSummary = content.work_location_summary;
  const arrSummary = content.work_arrangement_summary;

  return {
    facts: {
      title: roleReality.primaryOccupation,
      company: "Source Listing",
      location: locSummary?.value ?? "Thailand",
      salary: "Disclosed in listing",
      canonicalUrl: fallbackUrl,
    },
    roleReality,
    seniority,
    priorities,
    requirements,
    constraints,
    scenarios,
    workLocationSummary: locSummary?.value,
    workArrangementSummary: arrSummary?.value,
    remoteEligibility: content.remote_eligibility ?? "UNCLEAR",
    overallConfidence: content.overall_confidence ?? "HIGH",
  };
}
